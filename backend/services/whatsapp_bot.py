from twilio.twiml.messaging_response import MessagingResponse
from backend.models.models import Business, Service
from backend.ai_engine.engine import generate_slots
from backend.services.payments import create_razorpay_order
from datetime import datetime

# In a real app, use Redis for session management. 
# Using a simple dictionary given the SQLite/local dev context for rapid prototyping.
user_sessions = {}

def handle_whatsapp_message(incoming_msg, sender_number):
    """
    Main state machine for WhatsApp booking flow.
    Flow: 
    1. Greet & List Businesses
    2. Prompt for date
    3. Suggest Slots
    4. Generate Payment link
    """
    resp = MessagingResponse()
    msg = resp.message()

    # Initialize or fetch session
    if sender_number not in user_sessions:
        user_sessions[sender_number] = {"state": "GREETING"}

    session = user_sessions[sender_number]
    state = session["state"]
    text = incoming_msg.strip().lower()

    if text in ['hi', 'hello', 'start', 'reset']:
        session.clear()
        session["state"] = "SELECT_BUSINESS"
        businesses = Business.query.all()
        if not businesses:
            msg.body("Sorry, there are no businesses available for booking right now.")
            return str(resp)

        reply = "👋 Welcome to AI Sched! Please reply with the ID of the business you want to book:\n\n"
        for b in businesses:
            reply += f"[{b.id}] {b.name}\n"
        msg.body(reply)
        return str(resp)

    if state == "SELECT_BUSINESS":
        try:
            b_id = int(text)
            business = Business.query.get(b_id)
            if not business:
                raise ValueError
            session["business_id"] = b_id
            session["state"] = "SELECT_SERVICE"

            services = Service.query.filter_by(business_id=b_id).all()
            reply = f"Great! You chose {business.name}.\nWhat service do you need?\n\n"
            for s in services:
                reply += f"[{s.id}] {s.name} - ₹{s.price}\n"
            msg.body(reply)
        except ValueError:
            msg.body("Please reply with a valid business ID number.")

    elif state == "SELECT_SERVICE":
        try:
            s_id = int(text)
            service = Service.query.get(s_id)
            if not service:
                raise ValueError
            session["service_id"] = s_id
            session["state"] = "SELECT_DATE"
            msg.body(f"You selected {service.name}.\nPlease reply with your preferred date (YYYY-MM-DD):")
        except ValueError:
            msg.body("Please reply with a valid service ID number.")

    elif state == "SELECT_DATE":
        try:
            # Validate simple date format
            datetime.strptime(text, '%Y-%m-%d')
            session["date"] = text
            session["state"] = "SELECT_TIME"

            # Fetch slots
            service = Service.query.get(session["service_id"])
            slots = generate_slots(session["business_id"], service.id, text)
            if not slots:
                msg.body("Sorry, no slots available on that date. Try another date (YYYY-MM-DD):")
                session["state"] = "SELECT_DATE"
                return str(resp)

            session["avail_slots"] = slots
            reply = f"Slots for {text}:\n\n"
            for i, slot in enumerate(slots):
                reply += f"[{i}] {slot}\n"
            reply += "\nReply with the index [0], [1] etc. to choose a time."
            msg.body(reply)
        except ValueError:
            msg.body("Please use the format YYYY-MM-DD (e.g., 2026-10-25).")

    elif state == "SELECT_TIME":
        try:
            idx = int(text)
            slots = session.get("avail_slots", [])
            if idx < 0 or idx >= len(slots):
                raise ValueError

            selected_time = slots[idx]
            service = Service.query.get(session["service_id"])

            # Create Razorpay Order
            order = create_razorpay_order(service.price)
            # In a real scenario, this links to a distinct payment intent UI or deep link
            from flask import current_app
            base_url = current_app.config.get('BASE_URL', 'http://127.0.0.1:5000')
            payment_link = f"{base_url}/pay?order_id={order['id']}"

            msg.body(f"Awesome! Slot locked for {selected_time} on {session['date']}.\n\nTotal: ₹{service.price}\n\nPlease pay here to confirm your appointment:\n{payment_link}\n\n(Reply 'reset' to start over)")
            session["state"] = "AWAITING_PAYMENT"

        except ValueError:
            msg.body("Please reply with a valid slot index number from the list.")

    return str(resp)
