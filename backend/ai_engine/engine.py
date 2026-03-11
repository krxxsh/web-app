from datetime import datetime, timedelta
from backend.models.models import Appointment, Business, Service, Resource, Staff

def generate_slots(business_id, service_id, date_str):
    """
    Enhanced Slot Generation with AI Weighting.
    Weights slots based on:
    - Staff availability
    - Resource constraints
    - Clustering optimization (minimizing gaps)
    """
    business = Business.query.get(business_id)
    service = Service.query.get(service_id)
    if not (service and business):
        return []
    
    # Default work hours
    start_time_str, end_time_str = "09:00", "17:00"
    if business.working_hours:
        day_name = datetime.strptime(date_str, '%Y-%m-%d').strftime('%a').lower()
        if day_name in business.working_hours:
            start_time_str, end_time_str = business.working_hours[day_name]
        else:
            return []

    start_time = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %H:%M')
    end_time = datetime.strptime(f"{date_str} {end_time_str}", '%Y-%m-%d %H:%M')
    
    existing_appointments = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time >= start_time,
        Appointment.end_time <= end_time,
        Appointment.status != 'cancelled'
    ).all()
    
    all_staff = Staff.query.filter_by(business_id=business_id, is_active=True).all()
    
    slots = []
    current_slot_start = start_time
    
    while current_slot_start + timedelta(minutes=service.duration) <= end_time:
        current_slot_end = current_slot_start + timedelta(minutes=service.duration)
        
        # Check Staff availability
        available_staff = []
        for s in all_staff:
            is_busy = any(
                appt.staff_id == s.id and 
                ( (current_slot_start < appt.end_time) and (current_slot_end > appt.start_time) )
                for appt in existing_appointments
            )
            if not is_busy:
                available_staff.append(s.id)
        
        # Check Resource availability
        resource_available = True
        if service.requires_resource_id:
            resource = Resource.query.get(service.requires_resource_id)
            if resource:
                resource_usage = Appointment.query.join(Service).filter(
                    Service.requires_resource_id == resource.id,
                    Appointment.start_time < current_slot_end,
                    Appointment.end_time > current_slot_start,
                    Appointment.status != 'cancelled'
                ).count()
                if resource_usage >= resource.quantity:
                    resource_available = False
        
        if available_staff and resource_available and current_slot_start > datetime.now():
            # Scoring logic for recommendations
            score = 1.0
            if current_slot_start.hour < 12:
                score += 0.1  # Early bird
            
            # Gap minimization (Clustering)
            has_edge = any(
                abs((appt.start_time - current_slot_end).total_seconds()) < 60 or
                abs((appt.end_time - current_slot_start).total_seconds()) < 60
                for appt in existing_appointments
            )
            if has_edge:
                score += 0.3
            
            slots.append({
                "time": current_slot_start.strftime('%H:%M'),
                "score": round(score, 2),
                "staff_available": len(available_staff)
            })
            
        current_slot_start += timedelta(minutes=30) 
        
    return sorted(slots, key=lambda x: x['score'], reverse=True)

def get_ai_recommendations(slots, limit=3):
    """Returns top N recommended slots based on computed scores."""
    return [s['time'] for s in slots[:limit]]

def predict_delay(appointment_id):
    """
    AI Delay Prediction based on previous appointment drift.
    """
    from backend.models.models import Appointment
    appt = Appointment.query.get(appointment_id)
    if not appt:
        return 0
    
    # Check if a live appointment for the same staff is currently running late
    now = datetime.utcnow()
    live_appt = Appointment.query.filter(
        Appointment.staff_id == appt.staff_id,
        Appointment.status == 'booked',
        Appointment.start_time < now,
        Appointment.end_time > (now - timedelta(hours=1)) # Just in case
    ).order_by(Appointment.start_time.desc()).first()
    
    if live_appt and now > live_appt.end_time:
        return int((now - live_appt.end_time).total_seconds() / 60)
        
    return 0

def route_optimal_staff(business_id, service_id, start_time_str, end_time_str):
    """
    Enterprise Routing Engine.
    Routes a booking to the optimal staff member based on:
    1. Skill match (simulated implicitly by business association)
    2. Availability (no conflicting appointments)
    3. Utilization (round-robin to the least busy staff that day)
    """
    from backend.models.models import Staff, Appointment
    
    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
    end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')
    
    # 1. Get all staff for the business
    business_staff = Staff.query.filter_by(business_id=business_id).all()
    if not business_staff:
        return None
        
    viable_staff = []
    
    # 2. Filter by availability
    for staff in business_staff:
        conflict = Appointment.query.filter(
            Appointment.staff_id == staff.id,
            Appointment.status != 'cancelled',
            Appointment.start_time < end_time,
            Appointment.end_time > start_time
        ).first()
        
        if not conflict:
            viable_staff.append(staff)
            
    if not viable_staff:
        return None
        
    # 3. Optimization: least busy that day (Round-robin balancing)
    staff_utilization = []
    target_date = start_time.date()
    
    for staff in viable_staff:
        # Count appointments for this staff on this specific date
        day_appts = Appointment.query.filter(
            Appointment.staff_id == staff.id,
            Appointment.status != 'cancelled'
        ).all()
        
        count_that_day = len([a for a in day_appts if a.start_time.date() == target_date])
        staff_utilization.append((count_that_day, staff))
        
    # Sort by utilization count ascending
    staff_utilization.sort(key=lambda x: x[0])
    
    optimal_staff = staff_utilization[0][1]
    return optimal_staff.id
