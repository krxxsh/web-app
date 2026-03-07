from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from backend.extensions import db
from backend.models.models import Appointment, Business, Service, Waitlist
from ai_engine.engine import generate_slots, get_ai_recommendations
from backend.services.notifications import notify_booking_confirmation
from backend.services.payments import create_razorpay_order, verify_payment_signature
from backend.services.waitlist import add_to_waitlist
from backend.ai_engine.pricing import calculate_dynamic_price
from backend.ai_engine.predictive import calculate_noshow_probability
from backend.services.kiosk_manager import start_kiosk, stop_kiosk, is_kiosk_running
from flask import redirect, url_for, session, request
from datetime import datetime

api_bp = Blueprint('api', __name__)

@api_bp.route("/slots", methods=['GET'])
def get_slots():
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
def create_order():
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
def book_appointment():
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
    
    # Conflict check
    existing = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status != 'cancelled'
    ).first()
    
    if existing:
        return jsonify({"error": "Slot already taken"}), 409
        
    appointment = Appointment(
        customer_id=current_user.id,
        business_id=business_id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        status='booked',
        payment_status='paid' if payment_data else 'pending'
    )
    # Create virtual link if service is virtual
    create_virtual_meeting(appointment)
    
    db.session.add(appointment)
    db.session.commit()
    
    # Notify
    notify_booking_confirmation(appointment)
    
    # Sync to Google Calendar if enabled
    sync_appointment_to_google(appointment)
    
    return jsonify({"message": "Appointment booked successfully!", "id": appointment.id})

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
def join_waitlist():
    data = request.get_json()
    business_id = data.get('business_id')
    service_id = data.get('service_id')
    
    if add_to_waitlist(current_user.id, business_id, service_id):
        return jsonify({"message": "Added to waitlist!"})
    return jsonify({"error": "Already on waitlist"}), 400

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
        
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
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
