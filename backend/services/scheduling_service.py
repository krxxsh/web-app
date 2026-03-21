from datetime import datetime, timezone
import secrets
import string
import logging
from backend.extensions import db
from backend.models.models import Appointment, Waitlist, Service

logger = logging.getLogger(__name__)

def check_conflict(user_id, start_time, end_time, staff_id=None):
    """
    Checks if a user OR staff member has an overlapping appointment.
    """
    # Check user conflict
    user_conflicting = Appointment.query.filter(
        Appointment.customer_id == user_id,
        Appointment.status != 'cancelled',
        Appointment.start_time < end_time,
        Appointment.end_time > start_time
    ).first()

    if user_conflicting:
        return True

    # Check staff conflict
    if staff_id:
        staff_conflicting = Appointment.query.filter(
            Appointment.staff_id == staff_id,
            Appointment.status != 'cancelled',
            Appointment.start_time < end_time,
            Appointment.end_time > start_time
        ).first()
        return staff_conflicting is not None

    return False

def generate_secure_pin():
    """Generates a cryptographically secure 6-digit numeric PIN."""
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def handle_cancellation(appointment):
    """
    Called when an appointment is cancelled.
    Finds interested users on the waitlist and 'notifies' them.
    In a real app, this would trigger an SMS/Push.
    """
    # Find active waitlist entries for this business and service
    waitlist_entries = Waitlist.query.filter_by(
        business_id=appointment.business_id,
        service_id=appointment.service_id,
        status='active'
    ).order_by(Waitlist.request_date.asc()).all()

    if not waitlist_entries:
        return

    # Notify the users (mocked here by setting 'notified' flag)
    for entry in waitlist_entries:
        entry.notified = True
        # In a real scenario, we'd send a link to a 'claim' page
        logger.info(f"User {entry.user_id} notified of opening at {appointment.start_time}")

    db.session.commit()

def get_rebook_suggestion(user_id):
    """
    Finds the most frequent service the user has booked in the past.
    Returns the service_id or None.
    """
    from sqlalchemy import func

    result = db.session.query(
        Appointment.service_id, 
        func.count(Appointment.id).label('count')
    ).filter_by(customer_id=user_id).group_by(Appointment.service_id).order_by(db.desc('count')).first()

    if result:
        return Service.query.get(result[0])
    return None

def join_waitlist(user_id, business_id, service_id):
    """
    Adds a user to the waitlist if not already on it for that service.
    """
    existing = Waitlist.query.filter_by(
        user_id=user_id, 
        business_id=business_id, 
        service_id=service_id,
        status='active'
    ).first()

    if existing:
        return False, "Already on waitlist for this service."

    new_entry = Waitlist(
        user_id=user_id,
        business_id=business_id,
        service_id=service_id,
        request_date=datetime.now(timezone.utc)
    )
    db.session.add(new_entry)
    db.session.commit()
    return True, "Joined waitlist successfully."

def check_in_with_pin(pin):
    """
    Locates an appointment for the current time window matching the 6-digit PIN.
    Marks it as checked-in.
    """
    # Find appointments starting within 15 mins before/after now
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    # Check-in is only valid FOR TODAY
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Window: 15 mins before to 60 mins after START time
    window_start = now - timedelta(minutes=60) # Allowed to check in 60 mins late
    window_end = now + timedelta(minutes=15)   # Allowed to check in 15 mins early

    appt = Appointment.query.filter(
        Appointment.checkin_pin == pin,
        Appointment.status == 'booked', # Must be in 'booked' status
        Appointment.start_time >= today_start,
        Appointment.start_time <= today_end,
        Appointment.start_time >= window_start,
        Appointment.start_time <= window_end
    ).first()

    if appt:
        appt.status = 'arrived'
        appt.check_in_time = now
        db.session.commit()
        return True, f"Successfully checked in for {appt.service.name}"
    
    return False, "Invalid PIN or appointment not found today"
