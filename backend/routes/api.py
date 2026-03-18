import logging
from flask import Blueprint, jsonify, request, redirect, url_for, session
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from typing import Any
from backend.extensions import db, limiter

logger = logging.getLogger(__name__)
from backend.models.models import Business, Service, Appointment, Feedback, Promotion, User
from backend.ai_engine.engine import generate_slots, get_ai_recommendations
from backend.services.notifications import notify_booking_confirmation
from backend.services.payments import create_razorpay_order, verify_payment_signature
from backend.ai_engine.pricing import calculate_dynamic_price
from backend.ai_engine.predictive import calculate_noshow_probability
from backend.services.kiosk_manager import start_kiosk, stop_kiosk, is_kiosk_running
from backend.services.scheduling_service import check_conflict, generate_secure_pin
from backend.services.waitlist import svc_join_waitlist
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

    # Notify - Email & WhatsApp
    notify_booking_confirmation(appointment)

    # NEW: Trigger real-time scheduling update for the business dashboard
    # This keeps the merchant view in sync without page refreshes
    from backend.services.notifications import send_realtime_update
    send_realtime_update("business", business_id, {
        "type": "NEW_BOOKING", 
        "appointment_id": appointment.id,
        "customer": current_user.username,
        "service": service.name
    })

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

    # Trigger gap filler (AI Auto-fill)
    from backend.services.waitlist import handle_cancellation
    success, message = handle_cancellation(appt.business_id, appt.service_id, appt.start_time, appt.end_time)
    if not success:
        logger.warning(f"Waitlist auto-fill failed: {message}")

    db.session.commit()
    return jsonify({"success": True, "message": "Appointment cancelled and filler notified."})

@api_bp.route("/appointments/status/<int:appt_id>", methods=['GET'])
@login_required
def get_appointment_status(appt_id):
    appt = Appointment.query.get_or_404(appt_id)

    from backend.ai_engine.engine import predict_delay
    delay_mins = predict_delay(appt.id)

    return jsonify({
        "id": appt.id,
        "status": appt.status,
        "start_time": appt.start_time.isoformat(),
        "predicted_delay": delay_mins,
        "is_delayed": delay_mins > 5,
        "message": f"Possible {delay_mins} min delay detected" if delay_mins > 5 else "On time"
    })

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

    # 1. Filter businesses by category and distance
    businesses = Business.query.filter_by(category_id=cat_id).all()
    candidates = []

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    limit_time = now + timedelta(minutes=60)

    from backend.services.geocoding import haversine_distance
    from ai_engine.engine import generate_slots

    for b in businesses:
        if not b.latitude or not b.longitude:
            continue

        dist = haversine_distance(user_lat, user_lng, b.latitude, b.longitude)
        if dist > 25: # 25km radius for 'nearby'
            continue

        # 2. Get today's slots for all services of this business
        for svc in b.services:
            slots = generate_slots(b.id, svc.id, today_str)

            # Find any slot within next 60 mins
            for s in slots:
                slot_time = datetime.strptime(f"{today_str} {s['time']}", '%Y-%m-%d %H:%M')
                if now < slot_time <= limit_time:
                    candidates.append({
                        "business_id": b.id,
                        "business_name": b.name,
                        "service_id": svc.id,
                        "service_name": svc.name,
                        "price": svc.price,
                        "time": s['time'],
                        "distance": round(dist, 2),
                        "score": s['score']
                    })
                    break # Take only the earliest for this service

    # Sort by arrival time and score
    return jsonify({
        "results": sorted(candidates, key=lambda x: (x['time'], -x['score']))[:5]
    })
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

@api_bp.route("/kiosk/check_in", methods=['POST'])
def kiosk_check_in():
    """Endpoint for the Kiosk to check in appointments via PIN."""
    data = request.get_json()
    pin = data.get('pin')
    if not pin:
        return jsonify({'error': 'PIN required'}), 400
    
    from backend.services.scheduling_service import check_in_with_pin
    success, message = check_in_with_pin(pin)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 400

@api_bp.route("/feedback/submit", methods=['POST'])
@login_required
def submit_feedback():
    data = request.get_json()
    appt_id = data.get('appointment_id')
    rating = data.get('rating')
    comment = data.get('comment', '')

    appt = Appointment.query.get_or_404(appt_id)

    # AI Fraud Detection
    from backend.services.fraud_detection import detect_review_fraud
    is_fraud, reason = detect_review_fraud(current_user.id, appt.id, rating, comment)
    if is_fraud:
        return jsonify({"error": f"Review submission failed: {reason}"}), 400

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
    reason = data.get('reason')

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

    start_param = request.args.get('start')
    end_param = request.args.get('end')

    query = Appointment.query.filter_by(business_id=current_user.businesses[0].id)
    if start_param:
        query = query.filter(Appointment.start_time >= start_param)
    if end_param:
        query = query.filter(Appointment.end_time <= end_param)
    appts = query.all()
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

@api_bp.route("/firebase-login", methods=['POST'])
@limiter.limit("5 per minute")
def firebase_login():
    data = request.get_json()
    id_token = data.get('idToken')

    # Optional metadata for registration
    reg_username = data.get('username')
    reg_role = data.get('role') # If None, it's a login from the login page, so we set 'pending' later
    reg_phone = data.get('phone')

    from backend.services.firebase_config import verify_firebase_token
    decoded_token = verify_firebase_token(id_token)

    if not decoded_token:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    uid = decoded_token.get('uid')
    email = decoded_token.get('email')

    # Sync with local DB
    user = User.query.filter_by(firebase_uid=uid).first()
    if not user:
        # Check if user exists by email (link accounts)
        user = User.query.filter_by(email=email).first()
        if user:
            user.firebase_uid = uid
        else:
            # Create a shadow user profile for the marketplace
            # Shadow user profile for marketplace
            # reg_role from registration will be 'customer' or 'admin' (which maps to business_owner)
            # If reg_role is None, it means it's a direct Google Login -> 'pending'
            role = reg_role
            if role == 'admin':
                role = 'business_owner'
            if not role:
                role = 'pending'

            import re
            # Generate unique username — strip spaces and non-alphanumeric chars
            raw = reg_username or decoded_token.get('name', email.split('@')[0])
            base_username = re.sub(r'[^a-zA-Z0-9_]', '', raw.replace(' ', '_'))[:15] or 'user'

            username = base_username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = User(
                username=username,
                email=email,
                firebase_uid=uid,
                role=role,
                phone_number=reg_phone,
                is_verified=True, # Firebase users are pre-verified
                is_platform_owner=False
            )
            db.session.add(user)
        db.session.commit()

    # Log in the user
    from flask_login import login_user
    login_user(user)

    # Determine redirect URL based on user role and verification status
    if user.role == 'pending':
        redirect_url = '/select-role'
    elif user.role == 'business_owner':
        if not user.is_verified:
            redirect_url = '/admin/pending_verification'
        else:
            # Check if user has a business setup
            business = Business.query.filter_by(owner_id=user.id).first()
            if business:
                redirect_url = url_for('admin.dashboard')
            else:
                redirect_url = '/admin/setup_business'
    else:  # customer or other roles
        redirect_url = '/'

    return jsonify({
        "success": True, 
        "needs_role": user.role == 'pending',
        "redirect": redirect_url,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_verified": user.is_verified
        }
    })

@api_bp.route('/user/select-role', methods=['POST'])
@login_required
def select_role():
    data = request.json or {}
    role = data.get('role')
    phone = data.get('phone')

    if role not in ['customer', 'business_owner']:
        return jsonify({"success": False, "message": "Invalid role selected"}), 400

    current_user.role = role
    if phone:
        current_user.phone_number = phone

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Role updated successfully",
        "redirect": "/admin/dashboard" if role == "business_owner" else "/",
    })




@api_bp.route("/subscription/plans", methods=['GET'])
def get_plans():
    from backend.models.models import SubscriptionPlan
    plans = SubscriptionPlan.query.all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price, "features": p.features} for p in plans])

@api_bp.route("/subscription/checkout", methods=['POST'])
@login_required
def subscription_checkout():
    data = request.get_json()
    plan_id = data.get('plan_id')

    from backend.models.models import SubscriptionPlan, Subscription
    plan = SubscriptionPlan.query.get_or_404(plan_id)

    end_date = datetime.utcnow() + timedelta(days=plan.duration_days)
    new_sub = Subscription(
        user_id=current_user.id,
        plan_id=plan.id,
        end_date=end_date,
        status='active'
    )
    db.session.add(new_sub)

    current_user.membership_level = plan.name.lower()
    db.session.commit()

    return jsonify({
        "success": True, 
        "message": f"Successfully subscribed to {plan.name}!",
        "expires_at": end_date.isoformat()
    })

@api_bp.route("/subscription/status", methods=['GET'])
@login_required
def get_subscription_status():
    from backend.models.models import Subscription
    sub = Subscription.query.filter_by(user_id=current_user.id, status='active').order_by(Subscription.end_date.desc()).first()

    if not sub:
        return jsonify({"has_active_sub": False, "level": "free"})

    return jsonify({
        "has_active_sub": True,
        "plan_name": sub.plan.name,
        "expires_at": sub.end_date.isoformat(),
        "features": sub.plan.features
    })

@api_bp.route("/dashboard/stats/<int:business_id>")
@login_required
def get_dashboard_stats(business_id):
    """Aggregated KPIs for the business dashboard."""
    from backend.models.models import Staff, Feedback
    from sqlalchemy import func

    business = Business.query.get_or_404(business_id)
    if business.owner_id != current_user.id and current_user.role not in ('admin', 'platform_owner'):
        return jsonify({"error": "Unauthorized"}), 403

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Core counts
    total_bookings = Appointment.query.filter_by(business_id=business_id).count()
    today_bookings = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time >= today_start,
        Appointment.start_time < today_end
    ).count()
    completed = Appointment.query.filter_by(business_id=business_id, status='completed').count()
    pending = Appointment.query.filter_by(business_id=business_id, status='booked').count()
    cancelled = Appointment.query.filter_by(business_id=business_id, status='cancelled').count()

    # Revenue from completed appointments
    revenue_result = (
        db.session.query(func.coalesce(func.sum(Service.price), 0))
        .join(Appointment, Appointment.service_id == Service.id)
        .filter(Appointment.business_id == business_id, Appointment.status == 'completed')
        .scalar()
    )
    total_revenue = float(revenue_result or 0)

    # Staff count
    active_staff = Staff.query.filter_by(business_id=business_id, is_active=True).count()

    # Average rating
    avg_rating_result = (
        db.session.query(func.avg(Feedback.rating))
        .join(Appointment, Appointment.id == Feedback.appointment_id)
        .filter(Appointment.business_id == business_id)
        .scalar()
    )
    avg_rating = round(float(avg_rating_result), 1) if avg_rating_result else 0.0

    # 7-day booking trend
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        count = Appointment.query.filter(
            Appointment.business_id == business_id,
            Appointment.start_time >= day_start,
            Appointment.start_time < day_end
        ).count()
        trend_labels.append(day.strftime('%a'))
        trend_data.append(count)

    return jsonify({
        "total_bookings": total_bookings,
        "today_bookings": today_bookings,
        "completed_bookings": completed,
        "pending_bookings": pending,
        "cancelled_bookings": cancelled,
        "total_revenue": total_revenue,
        "active_staff": active_staff,
        "avg_rating": avg_rating,
        "booking_trend": {
            "labels": trend_labels,
            "data": trend_data
        }
    })


# Authentication API Endpoints
@api_bp.route("/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ["email", "password", "username", "role", "phone"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400
    
    email = data["email"]
    password = data["password"]
    username = data["username"]
    role = data["role"]
    phone = data["phone"]
    
    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already registered"}), 409
    
    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "message": "Username already taken"}), 409
    
    # Create new user
    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(
        username=username,
        email=email,
        password=hashed_pw,
        role="business_owner" if role in ["admin", "business_owner"] else "customer",
        phone_number=phone,
        is_verified=True
    )
    
    db.session.add(user)
    db.session.commit()
    
    # Generate JWT token
    jwt_payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    }
    access_token = jwt.encode(jwt_payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")
    
    return jsonify({
        "success": True,
        "message": "Account created successfully",
        "data": {
            "token": access_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
        }
    })

@api_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json()
    
    # Validate required fields
    if not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "message": "Email and password are required"}), 400
    
    email = data["email"]
    password = data["password"]
    
    # Find user
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    
    # Verify password
    if not bcrypt.check_password_hash(user.password, password):
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    
    # Generate JWT token
    jwt_payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])
    }
    access_token = jwt.encode(jwt_payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")
    
    return jsonify({
        "success": True,
        "message": "Login successful",
        "data": {
            "token": access_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
        }
    })

@api_bp.route("/forgot-password", methods=["POST"])
def api_forgot_password():
    data = request.get_json()
    
    if not data.get("email"):
        return jsonify({"success": False, "message": "Email is required"}), 400
    
    email = data["email"]
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # Don't reveal whether email exists for security
        return jsonify({"success": True, "message": "If the email exists, an OTP has been sent"}), 200
    
    # Rate limiting: only send OTP every 60 seconds
    if user.otp_created_at:
        now = datetime.now(timezone.utc)
        last_otp = user.otp_created_at.replace(tzinfo=timezone.utc)
        if now - last_otp < timedelta(seconds=60):
            return jsonify({"success": False, "message": "Please wait before requesting another OTP"}), 429
    
    if send_password_reset_otp(user):
        return jsonify({"success": True, "message": "If the email exists, an OTP has been sent"})
    
    # Internal logging for failure tracking
    logger.error(f"Failed to dispatch password reset OTP for user: {user.email}")
    return jsonify({
        "success": False,
        "message": "We're experiencing temporary issues with our notification service. Please try again in a few minutes or contact support if the issue persists."
    }), 503

@api_bp.route("/verify-otp", methods=["POST"])
def api_verify_otp():
    data = request.get_json()
    
    # Validate required fields
    if not data.get("email") or not data.get("otp") or not data.get("password"):
        return jsonify({"success": False, "message": "Email, OTP, and new password are required"}), 400
    
    email = data["email"]
    otp = data["otp"]
    new_password = data["password"]
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "Invalid email or OTP"}), 400
    
    # Verify OTP
    if user.email_otp != otp:
        return jsonify({"success": False, "message": "Invalid email or OTP"}), 400
    
    # Check OTP expiration (10 minutes)
    if user.otp_created_at:
        if datetime.now(timezone.utc) - user.otp_created_at.replace(tzinfo=timezone.utc) > timedelta(minutes=10):
            return jsonify({"success": False, "message": "OTP expired"}), 400
    
    # Update password
    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.email_otp = None  # Clear OTP after use
    db.session.commit()
    
    return jsonify({
        "success": True,
        "message": "Password reset successful"
    })
