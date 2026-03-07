from datetime import datetime, timedelta
from backend.models.models import Appointment, Business, Service, Resource

def generate_slots(business_id, service_id, date_str):
    """
    Generate available time slots for a business and service on a specific date,
    considering business hours, existing appointments, and resource availability.
    """
    business = Business.query.get(business_id)
    service = Service.query.get(service_id)
    
    # Default working hours: 09:00 - 17:00
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
    
    slots = []
    current_slot_start = start_time
    
    while current_slot_start + timedelta(minutes=service.duration) <= end_time:
        current_slot_end = current_slot_start + timedelta(minutes=service.duration)
        
        # Check Staff availability (simplified: business-wide conflict)
        conflict = any((current_slot_start < appt.end_time) and (current_slot_end > appt.start_time) for appt in existing_appointments)
        
        # Check Resource availability if required
        resource_available = True
        if service.requires_resource_id:
            resource = Resource.query.get(service.requires_resource_id)
            if resource:
                # Count appointments using this resource at this time
                resource_usage = Appointment.query.join(Service).filter(
                    Service.requires_resource_id == resource.id,
                    Appointment.start_time < current_slot_end,
                    Appointment.end_time > current_slot_start,
                    Appointment.status != 'cancelled'
                ).count()
                if resource_usage >= resource.quantity:
                    resource_available = False
        
        if not conflict and resource_available and current_slot_start > datetime.now():
            slots.append(current_slot_start.strftime('%H:%M'))
            
        current_slot_start += timedelta(minutes=30) 
        
    return slots

def get_ai_recommendations(slots, limit=3):
    """
    Recommend best slots based on business density or specific logic.
    For now, simplicity: recommend early slots and weekend slots.
    """
    if not slots:
        return []
    
    # Logic: Prefer morning slots (before 12:00)
    recommended = [s for s in slots if int(s.split(':')[0]) < 12][:limit]
    
    # If not enough morning slots, just take the first few
    if len(recommended) < limit:
        remaining = [s for s in slots if s not in recommended]
        recommended.extend(remaining[:limit - len(recommended)])
        
    return recommended

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
