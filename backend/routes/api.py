import logging
from flask import Blueprint, jsonify, request, redirect, url_for, session
from flask_login import current_user, login_required
from datetime import datetime, timedelta, timezone
from typing import Any
from backend.extensions import db, limiter

logger = logging.getLogger(__name__)
from backend.models.models import Business, Service, Appointment, Feedback, Promotion
from backend.utils.auth_helper import firebase_token_required
from backend.ai_engine.engine import generate_slots, get_ai_recommendations, predict_delay
from backend.services.notifications import notify_booking_confirmation, send_realtime_update
from backend.services.payments import create_razorpay_order, verify_payment_signature
from backend.ai_engine.pricing import calculate_dynamic_price
from backend.ai_engine.predictive import calculate_noshow_probability
from backend.services.kiosk_manager import start_kiosk, stop_kiosk, is_kiosk_running
from backend.services.scheduling_service import check_conflict, generate_secure_pin, check_in_with_pin
from backend.services.waitlist import svc_join_waitlist, handle_cancellation
from backend.services.calendar_sync import get_google_flow, save_google_token, sync_appointment_to_google
from backend.services.virtual_rooms import create_virtual_meeting
from backend.services.chatbot import extract_booking_intent, generate_chatbot_response
from backend.services.whatsapp_bot import handle_whatsapp_message
from backend.services.ai_analytics import analyze_sentiment, predict_wait_time, get_smart_recommendations
from backend.services.geocoding import haversine_distance
from backend.services.fraud_detection import detect_review_fraud

api_bp = Blueprint('api', __name__)

@api_bp.route("/slots", methods=['GET'])
def get_slots() -> Any:
    business_id = request.args.get('business_id', type=int)
    service_id = request.args.get('service_id', type=int)
    date_str = request.args.get('date')

    if not all([business_id, service_id, date_str]):
        return jsonify({"error": "Missing parameters"}), 400

    service = Service.query.get_or_404(service_id)
    slots = generate_slots(business_id, service_id, date_str)
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
@firebase_token_required
def create_order() -> Any:
    data = request.get_json()
    service_id = data.get('service_id')
    dynamic_price = data.get('dynamic_price')
    service = Service.query.get_or_404(service_id)

    final_price = dynamic_price if dynamic_price else service.price
    order = create_razorpay_order(final_price)
    return jsonify({
        "order_id": order['id'],
        "amount": order['amount'],
        "currency": order['currency']
    })

@api_bp.route("/book", methods=['POST'])
@firebase_token_required
def book_appointment() -> Any:
    data = request.get_json()
    business_id = data.get('business_id')
    service_id = data.get('service_id')
    date_str = data.get('date')
    time_str = data.get('time')
    payment_data = data.get('payment')

    if payment_data:
        verified = verify_payment_signature(
            payment_data['razorpay_payment_id'],
            payment_data['razorpay_order_id'],
            payment_data['razorpay_signature']
        )
        if not verified:
            return jsonify({"error": "Payment verification failed"}), 400

    if not all([business_id, service_id, date_str, time_str]):
        return jsonify({"error": "Missing required fields: business_id, service_id, date, time"}), 400

    start_time = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    service = Service.query.get(service_id)

    if not service:
        return jsonify({"error": "Service not found"}), 404

    if service.member_only and current_user.membership_level == 'free':
        return jsonify({"error": "This service requires a premium membership."}), 403

    end_time = start_time + timedelta(minutes=service.duration)
    staff_id = data.get('staff_id')

    existing = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status != 'cancelled'
    ).first()

    if existing:
        return jsonify({"error": "Slot already taken"}), 409

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
        checkin_pin=generate_secure_pin()
    )
    create_virtual_meeting(appointment)

    db.session.add(appointment)
    db.session.commit()

    notify_booking_confirmation(appointment)
    send_realtime_update("business", business_id, {
        "type": "NEW_BOOKING", 
        "appointment_id": appointment.id,
        "customer": current_user.username,
        "service": service.name
    })

    sync_appointment_to_google(appointment)

    return jsonify({
        "message": "Appointment booked successfully!", 
        "id": appointment.id,
        "pin": appointment.checkin_pin
    })

@api_bp.route("/book_sequence", methods=['POST'])
@firebase_token_required
def book_sequence():
    data = request.get_json()
    business_id = data.get('business_id')
    service_ids = data.get('service_ids')
    start_time_str = data.get('start_time')

    if not all([business_id, service_ids, start_time_str]):
        return jsonify({"error": "Missing required fields: business_id, service_ids, start_time"}), 400

    if not isinstance(service_ids, list) or len(service_ids) == 0:
        return jsonify({"error": "service_ids must be a non-empty list"}), 400

    current_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
    booked_ids = []

    try:
        for sid in service_ids:
            service = Service.query.get(sid)
            if not service:
                db.session.rollback()
                return jsonify({"error": f"Service {sid} not found"}), 404
            end_time = current_time + timedelta(minutes=service.duration)

            if check_conflict(current_user.id, current_time, end_time):
                db.session.rollback()
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
            current_time = end_time
            booked_ids.append(appt)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in book_sequence: {e}")
        return jsonify({"error": "Booking failed due to a server error"}), 500

    return jsonify({"success": True, "booked_count": len(booked_ids)})

@api_bp.route("/google/login")
@firebase_token_required
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
@firebase_token_required
def api_join_waitlist():
    data = request.get_json()
    business_id = data.get('business_id')
    service_id = data.get('service_id')

    success, message = svc_join_waitlist(current_user.id, business_id, service_id)
    if success:
        return jsonify({"message": message})
    return jsonify({"error": message}), 400

@api_bp.route("/appointments/cancel/<int:appt_id>", methods=['POST'])
@firebase_token_required
def cancel_appointment(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id and current_user.role != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    appt.status = 'cancelled'
    appt.cancellation_reason = (request.get_json() or {}).get('reason', 'User cancelled')

    success, message = handle_cancellation(appt.business_id, appt.service_id, appt.start_time, appt.end_time)
    if not success:
        logger.warning(f"Waitlist auto-fill failed: {message}")

    db.session.commit()
    return jsonify({"success": True, "message": "Appointment cancelled and filler notified."})

@api_bp.route("/appointments/status/<int:appt_id>", methods=['GET'])
@firebase_token_required
def get_appointment_status(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    
    # SECURITY: Ensure only associated customer or business/admin can view status
    is_owner = current_user.role in ['admin', 'platform_owner']
    is_business = current_user.role == 'business_owner' and any(b.id == appt.business_id for b in current_user.businesses)
    is_customer = appt.customer_id == current_user.id
    
    if not (is_owner or is_business or is_customer):
        return jsonify({"error": "Unauthorized"}), 403

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
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    cat_id = request.args.get('category_id', type=int)

    if not all([user_lat, user_lng, cat_id]):
        return jsonify({"error": "Missing coordinates or category"}), 400

    businesses = Business.query.filter_by(category_id=cat_id).all()
    candidates = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    limit_time = now + timedelta(minutes=60)

    for b in businesses:
        if not (b.latitude and b.longitude):
            continue
        dist = haversine_distance(user_lat, user_lng, b.latitude, b.longitude)
        if dist > 25:
            continue
        for svc in b.services:
            slots = generate_slots(b.id, svc.id, today_str)
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
                    break
    return jsonify({"results": sorted(candidates, key=lambda x: (x['time'], -x['score']))[:5]})

@api_bp.route("/check_in/<int:appt_id>", methods=['POST'])
@firebase_token_required
def check_in(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    now = datetime.now()
    if now < appt.start_time - timedelta(minutes=30):
        return jsonify({"error": "Too early to check-in"}), 400
    appt.status = 'arrived'
    appt.check_in_time = now
    db.session.commit()
    return jsonify({"success": True, "message": "Checked in successfully!"})

@api_bp.route("/kiosk/check_in", methods=['POST'])
def kiosk_check_in():
    data = request.get_json()
    pin = data.get('pin')
    if not pin:
        return jsonify({'error': 'PIN required'}), 400
    success, message = check_in_with_pin(pin)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 400

@api_bp.route("/feedback/submit", methods=['POST'])
@firebase_token_required
def submit_feedback():
    data = request.get_json()
    appt_id = data.get('appointment_id')
    rating = data.get('rating')
    comment = data.get('comment', '')
    appt = Appointment.query.get_or_404(appt_id)
 
    is_fraud, reason = detect_review_fraud(current_user.id, appt.id, rating, comment)
    if is_fraud:
        return jsonify({"error": f"Review submission failed: {reason}"}), 400

    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    ai_result = analyze_sentiment(comment)
    feedback = Feedback(
        appointment_id=appt_id,
        user_id=current_user.id,
        rating=rating,
        comment=comment,
        sentiment_score=ai_result.get('score', 0.5),
        ai_category=", ".join(ai_result.get('key_issues', []))
    )
    if appt.status == 'arrived':
        appt.status = 'completed'
    db.session.add(feedback)
    db.session.commit()
    return jsonify({"success": True, "message": "Feedback submitted!", "reflection": ai_result.get('user_reflection', 'Thank you!')})

@api_bp.route("/business/stats/<int:business_id>")
def get_business_stats(business_id):
    wait_time = predict_wait_time(business_id)
    feedback = Feedback.query.join(Appointment).filter(Appointment.business_id == business_id).limit(10).all()
    categories = []
    for f in feedback:
        if f.ai_category:
            categories.extend([c.strip() for c in f.ai_category.split(',')])
    return jsonify({"live_wait_time": wait_time, "recent_ai_insights": list(set(categories))[:3]})

@api_bp.route("/recommendations")
@firebase_token_required
def get_recommendations():
    business_id = request.args.get('business_id', type=int)
    ids = get_smart_recommendations(current_user.id, business_id)
    services = Service.query.filter(Service.id.in_(ids)).all()
    return jsonify([{"id": s.id, "name": s.name, "price": s.price, "duration": s.duration} for s in services])

@api_bp.route("/forecast/<int:business_id>")
def get_business_forecast(business_id):
    business = Business.query.get_or_404(business_id)
    working_hours = business.working_hours or {}
    
    days_short = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    days_full = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    forecast = []
    for i, d_full in enumerate(days_full):
        day_hours = working_hours.get(d_full[:3]) or working_hours.get(d_full)
        if not day_hours or len(day_hours) < 2:
            continue
            
        start_h = int(day_hours[0].split(':')[0])
        end_h = int(day_hours[1].split(':')[0])
        
        for h in range(start_h, end_h + 1, 3): # 3-hour blocks
            hour_str = f"{h:02d}:00"
            forecast.append({
                "day": days_short[i],
                "hour": hour_str,
                "occupancy": 0.2 if 10 <= h <= 14 else 0.1 # Slight midday bump mock
            })
            
    if not forecast:
        # Fallback to defaults if no hours found
        forecast = [{"day": d, "hour": h, "occupancy": 0.0} for d in days_short for h in ['09:00', '12:00', '15:00', '18:00']]
        
    return jsonify(forecast)

@api_bp.route("/promotions/active/<int:business_id>")
def get_active_promotions(business_id):
    now = datetime.now(timezone.utc)
    promos = Promotion.query.filter(Promotion.business_id == business_id, Promotion.is_active, Promotion.start_date <= now, Promotion.end_date >= now).all()
    return jsonify([{"id": p.id, "title": p.title, "description": p.description, "discount": p.discount_pct} for p in promos])

@api_bp.route("/appointments/priority", methods=['POST'])
@firebase_token_required
def request_priority():
    data = request.get_json()
    appt_id = data.get('appointment_id')
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    appt.is_priority = True
    appt.status = 'pending'
    db.session.commit()
    return jsonify({"success": True, "message": "Priority request sent to admin."})

@api_bp.route("/admin/triage/process", methods=['POST'])
@firebase_token_required
def admin_process_triage():
    if current_user.role != 'admin':
        return jsonify({"error": "Admin only"}), 403
    data = request.get_json()
    appt = Appointment.query.get_or_404(data.get('appointment_id'))
    if data.get('action') == 'approve':
        appt.status = 'booked'
    else:
        appt.status = 'cancelled'
        appt.cancellation_reason = "Priority request denied by admin."
    db.session.commit()
    return jsonify({"success": True})

@api_bp.route("/chat", methods=['POST'])
def chat():
    data = request.json
    intent = extract_booking_intent(data.get('message'))
    reply = generate_chatbot_response(intent, context={"business_id": data.get('business_id')})
    return jsonify({"reply": reply, "intent": intent})

@api_bp.route("/whatsapp/webhook", methods=['POST'])
def whatsapp_webhook():
    return handle_whatsapp_message(request.values.get('Body', ''), request.values.get('From', '')), 200, {'Content-Type': 'text/xml'}

@api_bp.route("/kiosk/start", methods=['POST'])
@firebase_token_required
def api_start_kiosk():
    return jsonify({"success": start_kiosk(), "status": "running"})

@api_bp.route("/kiosk/stop", methods=['POST'])
@firebase_token_required
def api_stop_kiosk():
    return jsonify({"success": stop_kiosk(), "status": "stopped"})

@api_bp.route("/kiosk/status", methods=['GET'])
@login_required
def api_kiosk_status():
    return jsonify({"running": is_kiosk_running()})

@api_bp.route("/calendar/events", methods=['GET'])
@firebase_token_required
def get_calendar_events():
    if current_user.role not in ['business_owner', 'admin']:
        return jsonify([])
    query = Appointment.query.filter_by(business_id=current_user.businesses[0].id)
    start_param, end_param = request.args.get('start'), request.args.get('end')
    if start_param:
        query = query.filter(Appointment.start_time >= start_param)
    if end_param:
        query = query.filter(Appointment.end_time <= end_param)
    return jsonify([{"id": str(a.id), "title": f"{a.customer.username} - {a.service.name}", "start": a.start_time.isoformat(), "end": a.end_time.isoformat(), "backgroundColor": '#198754' if a.status == 'arrived' else '#0d6efd'} for a in query.all()])

@api_bp.route("/subscription/plans", methods=['GET'])
def get_plans():
    from backend.models.models import SubscriptionPlan
    return jsonify([{"id": p.id, "name": p.name, "price": p.price, "features": p.features} for p in SubscriptionPlan.query.all()])

@api_bp.route("/subscription/checkout", methods=['POST'])
@firebase_token_required
def subscription_checkout():
    from backend.models.models import SubscriptionPlan, Subscription
    plan = SubscriptionPlan.query.get_or_404(request.get_json().get('plan_id'))
    end_date = datetime.now(timezone.utc) + timedelta(days=plan.duration_days)
    new_sub = Subscription(user_id=current_user.id, plan_id=plan.id, end_date=end_date, status='active')
    db.session.add(new_sub)
    current_user.membership_level = plan.name.lower()
    db.session.commit()
    return jsonify({"success": True, "message": f"Subscribed to {plan.name}!", "expires_at": end_date.isoformat()})

@api_bp.route("/subscription/status", methods=['GET'])
@firebase_token_required
def get_subscription_status():
    from backend.models.models import Subscription
    sub = Subscription.query.filter_by(user_id=current_user.id, status='active').order_by(Subscription.end_date.desc()).first()
    if not sub:
        return jsonify({"has_active_sub": False, "level": "free"})
    return jsonify({"has_active_sub": True, "plan_name": sub.plan.name, "expires_at": sub.end_date.isoformat(), "features": sub.plan.features})

@api_bp.route("/dashboard/stats/<int:business_id>")
@firebase_token_required
def get_dashboard_stats(business_id):
    from backend.models.models import Staff, Feedback
    from sqlalchemy import func
    business = Business.query.get_or_404(business_id)
    if business.owner_id != current_user.id and current_user.role not in ('admin', 'platform_owner'):
        return jsonify({"error": "Unauthorized"}), 403
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    total_bookings = Appointment.query.filter_by(business_id=business_id).count()
    today_bookings = Appointment.query.filter(Appointment.business_id == business_id, Appointment.start_time >= today_start, Appointment.start_time < today_end).count()
    completed = Appointment.query.filter_by(business_id=business_id, status='completed').count()
    pending = Appointment.query.filter_by(business_id=business_id, status='booked').count()
    cancelled = Appointment.query.filter_by(business_id=business_id, status='cancelled').count()
    revenue_result = db.session.query(func.coalesce(func.sum(Service.price), 0)).join(Appointment).filter(Appointment.business_id == business_id, Appointment.status == 'completed').scalar()
    active_staff = Staff.query.filter_by(business_id=business_id, is_active=True).count()
    avg_rating_result = db.session.query(func.avg(Feedback.rating)).join(Appointment).filter(Appointment.business_id == business_id).scalar()
    trend_labels, trend_data = [], []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        count = Appointment.query.filter(Appointment.business_id == business_id, Appointment.start_time >= day_start, Appointment.start_time < day_start + timedelta(days=1)).count()
        trend_labels.append(day.strftime('%a'))
        trend_data.append(count)
    return jsonify({"total_bookings": total_bookings, "today_bookings": today_bookings, "completed_bookings": completed, "pending_bookings": pending, "cancelled_bookings": cancelled, "total_revenue": float(revenue_result or 0), "active_staff": active_staff, "avg_rating": round(float(avg_rating_result), 1) if avg_rating_result else 0.0, "booking_trend": {"labels": trend_labels, "data": trend_data}})

@api_bp.route('/user/select-role', methods=['POST'])
@firebase_token_required
def select_role():
    data = request.json or {}
    role = data.get('role')
    phone = data.get('phone')
    business_name = data.get('business_name') or data.get('businessName')

    if role not in ['customer', 'business_owner']:
        return jsonify({"success": False, "message": "Invalid role"}), 400
    
    try:
        current_user.role = role
        if phone:
            current_user.phone_number = phone
        
        if role == 'business_owner' and business_name:
            from backend.models.models import BusinessCategory, Business
            default_category = BusinessCategory.query.first()
            business = Business(
                name=business_name,
                owner_id=current_user.id,
                status='pending',
                category_id=default_category.id if default_category else None
            )
            db.session.add(business)
        
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": "Role updated", 
            "redirect": "/admin/dashboard" if role == "business_owner" else "/"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in select_role: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@api_bp.route('/auth/sync', methods=['POST'])
@firebase_token_required
def auth_sync():
    """
    Sync endpoint to establish backend session after Firebase login.
    firebase_token_required handles login_user(user).
    """
    from flask_login import current_user
    return jsonify({
        "success": True,
        "message": "Session synchronized",
        "role": current_user.role,
        "redirect": "/admin/dashboard" if current_user.role == "business_owner" else "/"
    })

@api_bp.route('/update-fcm-token', methods=['POST'])
@firebase_token_required
def update_fcm_token():
    data = request.get_json()
    token = data.get('fcmToken')
    if not token:
        return jsonify({"success": False, "message": "Token required"}), 400
    
    current_user.fcm_token = token
    db.session.commit()
    return jsonify({"success": True})
