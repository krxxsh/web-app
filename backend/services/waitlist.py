from datetime import datetime
from backend.extensions import db
from backend.models.models import Waitlist
from backend.services.notifications import notify_waitlist_open

def svc_join_waitlist(user_id, business_id, service_id):
    """Adds a user to the waitlist for a specific service."""
    existing = Waitlist.query.filter_by(
        user_id=user_id, 
        business_id=business_id, 
        service_id=service_id, 
        notified=False
    ).first()

    if not existing:
        entry = Waitlist(
            user_id=user_id, 
            business_id=business_id, 
            service_id=service_id, 
            request_date=datetime.now()
        )
        db.session.add(entry)
        db.session.commit()
        return True, "Joined waitlist successfully."
    return False, "Already on waitlist for this service."

def handle_cancellation(business_id, service_id, start_time, end_time):
    """
    AI Auto-fill: Finds first eligible user on waitlist and automatically
    reserves the slot for them.
    """
    from backend.models.models import Appointment

    # 1. Get first active waitlist entry (FIFO)
    entry = Waitlist.query.filter_by(
        business_id=business_id, 
        service_id=service_id, 
        status='active'
    ).order_by(Waitlist.request_date.asc()).first()

    if entry:
        # AI Auto-fill logic
        new_appt = Appointment(
            customer_id=entry.user_id,
            business_id=business_id,
            service_id=service_id,
            start_time=start_time,
            end_time=end_time,
            status='booked',
            is_priority=True # AI filled slots are marked priority
        )
        db.session.add(new_appt)

        # Mark waitlist entry completed
        entry.status = 'converted'
        entry.notified = True

        db.session.commit()

        # Notify the lucky user
        notify_waitlist_open(entry)
        return True, "Waitlist entry converted to appointment."
    return False, "No active waitlist entries found."
