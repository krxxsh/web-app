from flask import Blueprint, jsonify, request, redirect, url_for, session
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from typing import Any
from backend.extensions import db
from backend.models.models import Business, Service, Appointment, Feedback, Promotion
from ai_engine.engine import generate_slots, get_ai_recommendations
from backend.services.notifications import notify_booking_confirmation
from backend.services.payments import create_razorpay_order, verify_payment_signature
from backend.ai_engine.pricing import calculate_dynamic_price
from backend.ai_engine.predictive import calculate_noshow_probability
from backend.services.kiosk_manager import start_kiosk, stop_kiosk, is_kiosk_running
from backend.services.scheduling_service import check_conflict, generate_secure_pin
from backend.services.waitlist import svc_join_waitlist, handle_cancellation
from backend.services.geocoding import get_travel_time, haversine_distance
from backend.services.calendar_sync import get_google_flow, save_google_token, sync_appointment_to_google
from backend.services.virtual_rooms import create_virtual_meeting
from backend.services.chatbot import extract_booking_intent, generate_chatbot_response
from backend.services.whatsapp_bot import handle_whatsapp_message
from backend.services.ai_analytics import analyze_sentiment, predict_wait_time, get_smart_recommendations

api_bp = Blueprint('api', __name__)

@api_bp.route("/slots", methods=['GET'])
def get_slots() -> Any:
    business_id = request.args.get('business_id', type=int)
    service_id = request.args.get('service_id', type=int)
    date_str = request.args.get('date')
    
    if not all([business_id, service_id, date_str]):
        return jsonify({"error": "Missing parameters"}), 400
        
    service = Service.query.get_or_404(service_id)
    slots = generate_slots(business_id, service.duration, date_str)
    recommendations = get_ai_recommendations(slots)
    
    # Calculate surge pricing
    dynamic_price, multiplier = calculate_dynamic_price(business_id, service.price, date_str, "00:00")
    
    # Calculate ML No-show risk
    ml_risk = calculate_noshow_probability(
        current_user.id if current_user.is_authenticated else None,
        business_id, 
        date_str, 
        "00:00", 
        service_id
    )
    
    return jsonify({
        "available_slots": slots,
        "recommendations": recommendations,
        "is_full": len(slots) == 0,
        "dynamic_price": dynamic_price,
        "surge_multiplier": multiplier,
        "requires_deposit": ml_risk["recommend_deposit"]
    })

@api_bp.route("/create_order", methods=['POST'])
@login_required
def create_order() -> Any:
    data = request.get_json()
    service_id = data.get('service_id')
    dynamic_price = data.get('dynamic_price') # Passed from frontend 
    service = Service.query.get_or_404(service_id)
    
    final_price = dynamic_price if dynamic_price else service.price
    
    order = create_razorpay_order(final_price)
    return jsonify({
        "order_id": order['id'],
        "amount": order['amount'], # amount comes back from razorpay in paise
        "currency": order['currency']
    })

@api_bp.route("/book", methods=['POST'])
@login_required
def book_appointment() -> Any:
    data = request.get_json()
    business_id = data.get('business_id')
    service_id = data.get('service_id')
    date_str = data.get('date')
    time_str = data.get('time')
    payment_data = data.get('payment')

    if payment_data:
        # Verify payment
        verified = verify_payment_signature(
            payment_data['razorpay_payment_id'],
            payment_data['razorpay_order_id'],
            payment_data['razorpay_signature']
        )
        if not verified:
            return jsonify({"error": "Payment verification failed"}), 400

    start_time = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    service = Service.query.get(service_id)
    
    # Membership check
    if service.member_only and current_user.membership_level == 'free':
        return jsonify({"error": "This service requires a premium membership."}), 403

    end_time = start_time + timedelta(minutes=service.duration)
    
    staff_id = data.get('staff_id')
    
    # Conflict check (Business/Slot)
    existing = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status != 'cancelled'
    ).first()
    
    if existing:
        return jsonify({"error": "Slot already taken"}), 409
        
    # NEW: Staff and User conflict check
    if check_conflict(current_user.id, start_time, end_time, staff_id=staff_id):
        return jsonify({"error": "Conflict detected. Please choose a different time or staff member."}), 409
        
    appointment = Appointment(
        customer_id=current_user.id,
        business_id=business_id,
        service_id=service_id,
        staff_id=staff_id,
        start_time=start_time,
        end_time=end_time,
        status='booked',
        payment_status='paid' if payment_data else 'pending',
        party_size=data.get('party_size', 1),
        checkin_pin=generate_secure_pin() # Secure PIN for Kiosk
    )
    # Create virtual link if service is virtual
    create_virtual_meeting(appointment)
    
    db.session.add(appointment)
    db.session.commit()
    
    # Notify
    notify_booking_confirmation(appointment)
    
    # Sync to Google Calendar if enabled
    sync_appointment_to_google(appointment)
    
    return jsonify({
        "message": "Appointment booked successfully!", 
        "id": appointment.id,
        "pin": appointment.checkin_pin
    })

@api_bp.route("/book_sequence", methods=['POST'])
@login_required
def book_sequence():
    """Book multiple services one after another"""
    data = request.get_json()
    business_id = data.get('business_id')
    service_ids = data.get('service_ids') # list
    start_time_str = data.get('start_time')
    
    current_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
    booked_ids = []
    
    for sid in service_ids:
        service = Service.query.get(sid)
        end_time = current_time + timedelta(minutes=service.duration)
        
        # Conflict check for each slot
        if check_conflict(current_user.id, current_time, end_time):
            return jsonify({"error": f"Conflict at {current_time}. Partial booking failed."}), 409
            
        appt = Appointment(
            customer_id=current_user.id,
            business_id=business_id,
            service_id=sid,
            start_time=current_time,
            end_time=end_time,
            status='booked'
        )
        db.session.add(appt)
        current_time = end_time # Set next start to current's end
        booked_ids.append(appt)
        
    db.session.commit()
    return jsonify({"success": True, "booked_count": len(booked_ids)})

@api_bp.route("/google/login")
@login_required
def google_login():
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['google_auth_state'] = state
    return redirect(authorization_url)

@api_bp.route("/google/callback")
def google_callback():
    flow = get_google_flow()
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    save_google_token(current_user.id, credentials)
    
    return redirect(url_for('admin.dashboard'))

@api_bp.route("/waitlist", methods=['POST'])
@login_required
def api_join_waitlist():
    data = request.get_json()
    business_id = data.get('business_id')
    service_id = data.get('service_id')
    
    success, message = svc_join_waitlist(current_user.id, business_id, service_id)
    if success:
        return jsonify({"message": message})
    return jsonify({"error": message}), 400

@api_bp.route("/appointments/cancel/<int:appt_id>", methods=['POST'])
@login_required
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id and current_user.role != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    appt.status = 'cancelled'
    appt.cancellation_reason = request.json.get('reason', 'User cancelled')
    
    # Trigger gap filler
    handle_cancellation(appt.business_id, appt.service_id)
    
    db.session.commit()
    return jsonify({"success": True, "message": "Appointment cancelled and filler notified."})

@api_bp.route("/fastest_near_me", methods=['GET'])
def get_fastest_near_me():
    """
    Search for the absolute earliest appointment available near user.
    Params: lat, lng, category_id
    """
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    cat_id = request.args.get('category_id', type=int)
    
    if not all([user_lat, user_lng, cat_id]):
        return jsonify({"error": "Missing coordinates or category"}), 400
        
    # 1. Filter businesses by category
    businesses = Business.query.filter_by(category_id=cat_id).all()
    candidates = []
    
    for b in businesses:
        if not b.latitude or not b.longitude:
            continue
        
        # 2. Haversine Pre-filter (within 50km for sanity)
        dist = haversine_distance(user_lat, user_lng, b.latitude, b.longitude)
        if dist > 50:
            continue
        
        # 3. Get Real Travel Time (OSRM)
        travel_sec = get_travel_time(user_lat, user_lng, b.latitude, b.longitude)
        arrival_time = datetime.now() + timedelta(seconds=travel_sec)
        
        # 4. Check earliest slot that is AFTER arrival_time
        # We find earliest slot for the first service of the business
        if not b.services:
            continue
        svc = b.services[0]
        date_str = arrival_time.strftime('%Y-%m-%d')
        slots = generate_slots(b.id, svc.duration, date_str)
        
        earliest_possible = None
        for s in slots:
            slot_dt = datetime.strptime(f"{date_str} {s}", '%Y-%m-%d %H:%M')
            if slot_dt >= arrival_time:
                earliest_possible = slot_dt
                break
        
        if earliest_possible:
            candidates.append({
                "business_id": b.id,
                "business_name": b.name,
                "distance_km": round(dist, 2),
                "travel_time_mins": round(travel_sec / 60),
                "earliest_slot": earliest_possible.strftime('%H:%M'),
                "earliest_arrival": arrival_time.strftime('%H:%M'),
                "service_id": svc.id,
                "lat": b.latitude,
                "lng": b.longitude
            })

    # 5. Sort by earliest slot time
    candidates.sort(key=lambda x: x['earliest_slot'])
    
    return jsonify(candidates[:5])

@api_bp.route("/check_in/<int:appt_id>", methods=['POST'])
@login_required
def check_in(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    # Check if appointment is within 30 mins of start
    now = datetime.now()
    if now < appt.start_time - timedelta(minutes=30):
        return jsonify({"error": "Too early to check-in"}), 400
        
    appt.status = 'arrived'
    appt.check_in_time = now
    db.session.commit()
    
    return jsonify({"success": True, "message": "Checked in successfully!"})

@api_bp.route("/feedback/submit", methods=['POST'])
@login_required
def submit_feedback():
    data = request.get_json()
    appt_id = data.get('appointment_id')
    rating = data.get('rating')
    comment = data.get('comment')
    
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    # AI Analysis
    ai_result = analyze_sentiment(comment)
    
    feedback = Feedback(
        appointment_id=appt_id,
        user_id=current_user.id,
        rating=rating,
        comment=comment,
        sentiment_score=ai_result.get('score', 0.5),
        ai_category=", ".join(ai_result.get('key_issues', []))
    )
    
    # Mark appointment as completed if it was in arrived state
    if appt.status == 'arrived':
        appt.status = 'completed'
        
    db.session.add(feedback)
    db.session.commit()
    
    return jsonify({
        "success": True, 
        "message": "Feedback submitted!", 
        "reflection": ai_result.get('user_reflection', 'Thank you!')
    })

@api_bp.route("/business/stats/<int:business_id>")
def get_business_stats(business_id):
    """Returns AI-calculated wait times and high-level sentiment summary for public view."""
    wait_time = predict_wait_time(business_id)
    
    # Pull recent feedback categories
    feedback = Feedback.query.join(Appointment).filter(Appointment.business_id == business_id).limit(10).all()
    categories = []
    for f in feedback:
        if f.ai_category:
            categories.extend([c.strip() for c in f.ai_category.split(',')])
    
    return jsonify({
        "live_wait_time": wait_time,
        "recent_ai_insights": list(set(categories))[:3]
    })

@api_bp.route("/recommendations")
@login_required
def get_recommendations():
    business_id = request.args.get('business_id', type=int)
    ids = get_smart_recommendations(current_user.id, business_id)
    
    # Fetch full service objects
    services = Service.query.filter(Service.id.in_(ids)).all()
    return jsonify([
        {"id": s.id, "name": s.name, "price": s.price, "duration": s.duration} 
        for s in services
    ])

@api_bp.route("/forecast/<int:business_id>")
def get_business_forecast(business_id):
    """Generates a simple 'Heatmap' data structure for weekly busy hours."""
    # Historical logic or mockup for heatmap
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    hours = ['09:00', '12:00', '15:00', '18:00']
    
    import random
    forecast = []
    for day in days:
        for hour in hours:
            # Random occupancy between 0 and 1
            forecast.append({
                "day": day,
                "hour": hour,
                "occupancy": random.uniform(0.1, 0.9)
            })
            
    return jsonify(forecast)

@api_bp.route("/promotions/active/<int:business_id>")
def get_active_promotions(business_id):
    """Returns currently active deals for a business."""
    now = datetime.utcnow()
    promos = Promotion.query.filter(
        Promotion.business_id == business_id,
        Promotion.is_active,
        Promotion.start_date <= now,
        Promotion.end_date >= now
    ).all()
    
    return jsonify([{
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "discount": p.discount_pct
    } for p in promos])

@api_bp.route("/appointments/priority", methods=['POST'])
@login_required
def request_priority():
    """Allows user to flag an appointment for 'Urgent' triage by admin."""
    data = request.get_json()
    appt_id = data.get('appointment_id')
    data.get('reason')
    
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    appt.is_priority = True
    appt.status = 'pending' # Triage state
    db.session.commit()
    
    return jsonify({"success": True, "message": "Priority request sent to admin."})

@api_bp.route("/admin/triage/process", methods=['POST'])
@login_required
def admin_process_triage():
    """Admin approves or denies priority requests."""
    if current_user.role != 'admin':
        return jsonify({"error": "Admin only"}), 403
        
    data = request.get_json()
    appt_id = data.get('appointment_id')
    action = data.get('action') # approve, reject
    
    appt = Appointment.query.get_or_404(appt_id)
    if action == 'approve':
        appt.status = 'booked' # confirmed
    else:
        appt.status = 'cancelled'
        appt.cancellation_reason = "Priority request denied by admin."
        
    db.session.commit()
    return jsonify({"success": True})

@api_bp.route("/chat", methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('message')
    business_id = data.get('business_id')
    
    intent = extract_booking_intent(user_text)
    reply = generate_chatbot_response(intent, context={"business_id": business_id})
    
    return jsonify({
        "reply": reply,
        "intent": intent
    })

@api_bp.route("/whatsapp/webhook", methods=['POST'])
def whatsapp_webhook():
    """Endpoint for Twilio WhatsApp Webhook"""
    incoming_msg = request.values.get('Body', '')
    sender = request.values.get('From', '')
    
    # Delegate to the whatsapp_bot state machine
    response_xml = handle_whatsapp_message(incoming_msg, sender)
    return response_xml, 200, {'Content-Type': 'text/xml'}

@api_bp.route("/kiosk/start", methods=['POST'])
@login_required
def api_start_kiosk():
    success = start_kiosk()
    return jsonify({"success": success, "status": "running" if success else "failed"})

@api_bp.route("/kiosk/stop", methods=['POST'])
@login_required
def api_stop_kiosk():
    success = stop_kiosk()
    return jsonify({"success": success, "status": "stopped"})

@api_bp.route("/kiosk/status", methods=['GET'])
@login_required
def api_kiosk_status():
    return jsonify({"running": is_kiosk_running()})

@api_bp.route("/calendar/events", methods=['GET'])
@login_required
def get_calendar_events():
    """Fetch appointments formatted for FullCalendar.js"""
    if current_user.role not in ['business', 'admin']:
        return jsonify([])
        
    request.args.get('start')
    request.args.get('end')
    
    appts = Appointment.query.filter_by(business_id=current_user.businesses[0].id).all()
    events = []
    
    for a in appts:
        color = '#198754' if a.status == 'arrived' else '#0d6efd'
        events.append({
            "id": str(a.id),
            "title": f"{a.customer.username} - {a.service.name}",
            "start": a.start_time.isoformat(),
            "end": a.end_time.isoformat(),
            "backgroundColor": color,
            "borderColor": color
        })
        
    return jsonify(events)

@api_bp.route("/calendar/reschedule", methods=['POST'])
@login_required
def reschedule_calendar_event():
    """Handle drag and drop rescheduling"""
    if current_user.role not in ['business', 'admin']:
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    data = request.json
    appt = Appointment.query.get(data.get('appointment_id'))
    
    if not appt or appt.business_id != current_user.businesses[0].id:
        return jsonify({"success": False, "message": "Appointment not found."}), 404
        
    try:
        # FullCalendar sends ISO strings with timezone info sometimes, slice off the timezone for raw datetime
        new_start = datetime.fromisoformat(data['new_start'].split('+')[0].replace('Z', ''))
        new_end = datetime.fromisoformat(data['new_end'].split('+')[0].replace('Z', ''))
        
        appt.start_time = new_start
        appt.end_time = new_end
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
