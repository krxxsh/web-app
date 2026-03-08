from datetime import datetime, timedelta
from backend.models.models import Appointment, Business, Staff, Service
from sqlalchemy import and_

def get_smart_slots(business_id, service_id, target_date):
    """
    Calculates available time slots for a specific service and date.
    Weights slots based on:
    - Business capacity (staff/resources)
    - Existing appointments
    - Optimization goal (minimize gaps)
    """
    service = Service.query.get(service_id)
    business = Business.query.get(business_id)
    if not (service and business):
        return []

    duration = service.duration
    # For now, assume business hours are 9 AM to 6 PM if not defined
    # Real implementation would use working_hours from Business model
    work_start_hour = 9
    work_end_hour = 18

    day_start = datetime.combine(target_date, datetime.min.time().replace(hour=work_start_hour))
    day_end = datetime.combine(target_date, datetime.min.time().replace(hour=work_end_hour))

    # Get all staff for this business
    all_staff = Staff.query.filter_by(business_id=business_id, is_active=True).all()
    if not all_staff:
        return []

    # Get all existing appointments for this day
    existing_appointments = Appointment.query.filter(
        and_(
            Appointment.business_id == business_id,
            Appointment.start_time >= day_start,
            Appointment.end_time <= day_end,
            Appointment.status != 'cancelled'
        )
    ).all()

    # Generate potential slots (15-min intervals)
    available_slots = []
    current_time = day_start

    while current_time + timedelta(minutes=duration) <= day_end:
        slot_start = current_time
        slot_end = current_time + timedelta(minutes=duration)

        # Check capacity: Is at least one staff member free?
        free_staff = []
        for staff in all_staff:
            is_busy = any(
                appt.staff_id == staff.id and 
                ( (slot_start < appt.end_time) and (slot_end > appt.start_time) )
                for appt in existing_appointments
            )
            if not is_busy:
                free_staff.append(staff.id)

        if free_staff:
            # AI Weighting: Calculate a score for this slot
            # 1.0 = Default, Higher = Better
            score = 1.0

            # Merit: Encourage filling morning slots (early bird optimization)
            if slot_start.hour < 12:
                score += 0.1

            # Merit: Encourage minimizing gaps (clustering)
            has_nearby = any(
                abs((appt.start_time - slot_end).total_seconds()) < 900 or
                abs((appt.end_time - slot_start).total_seconds()) < 900
                for appt in existing_appointments
            )
            if has_nearby:
                score += 0.2

            available_slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat(),
                "staff_count": len(free_staff),
                "score": round(score, 2)
            })

        current_time += timedelta(minutes=15)

    # Sort by score descending (Smart Recommendations)
    return sorted(available_slots, key=lambda x: x['score'], reverse=True)

def predict_delay_v1(appointment_id):
    """
    Predicts if an appointment will be delayed based on 'drift'.
    Check if previous appointment for the same staff is completed or still running.
    """
    appt = Appointment.query.get(appointment_id)
    if not appt:
        return 0

    # Simple drift logic: if current time is > predicted start time and appt is not started
    # Or if previous appt for same staff is still 'booked'/'pending' past its end_time
    now = datetime.utcnow()

    previous_appt = Appointment.query.filter(
        and_(
            Appointment.staff_id == appt.staff_id,
            Appointment.end_time <= appt.start_time,
            Appointment.status == 'booked' # Still not marked completed
        )
    ).order_by(Appointment.end_time.desc()).first()

    drift = 0
    if previous_appt and now > previous_appt.end_time:
        drift = (now - previous_appt.end_time).total_seconds() / 60

    return drift
