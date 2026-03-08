from datetime import datetime
from backend.models.models import Appointment

def calculate_dynamic_price(business_id, base_price, date_str, time_str):
    """
    Dynamic Surge Pricing Algorithm.
    Increases price when a specific day is heavily booked.

    Logic:
    - If > 70% of standard arbitrary slots (assume 8 per day) are booked, apply 1.2x surge.
    - If > 90% are booked, apply 1.5x surge.
    """
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Get all appointments for that business on that day
    appointments = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.status != 'cancelled'
    ).all()

    appointments_on_date = [a for a in appointments if a.start_time.date() == target_date]

    # Assume a standard 8-hour workday with 1-hour slots for the capacity heuristic
    baseline_capacity = 8 
    booked_count = len(appointments_on_date)

    utilization_rate = booked_count / baseline_capacity

    surge_multiplier = 1.0

    if utilization_rate >= 0.9:
        surge_multiplier = 1.5
    elif utilization_rate >= 0.7:
        surge_multiplier = 1.2

    dynamic_price = round(base_price * surge_multiplier, 2)

    return dynamic_price, surge_multiplier

