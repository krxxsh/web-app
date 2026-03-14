import random
import json
import smtplib
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from flask import current_app
from twilio.rest import Client
from azure.messaging.webpubsubservice import WebPubSubServiceClient

logger = logging.getLogger(__name__)

from datetime import datetime, timezone

def generate_secure_otp():
    """Generates a cryptographically secure 6-digit OTP."""
    return "".join([str(secrets.randbelow(10)) for _ in range(6)])

def send_verification_otp(user):
    """Generate and send one unified OTP via Email and SMS."""
    # Generate 6-digit OTP
    otp = generate_secure_otp()
    
    user.email_otp = otp
    user.phone_otp = otp  # Unified
    user.otp_created_at = datetime.now(timezone.utc)

    # Contextual Message
    subject = "Verify your AI Sched Account"
    body = f"Hello {user.username},\n\nYour verification code is: {otp}\n\nThis code expires in 10 minutes."

    # Send Email
    send_email(user.email, subject, body)

    # Send SMS/WhatsApp if phone exists
    if user.phone_number:
        logger.debug(f"Sending OTP {otp} to {user.phone_number}")
        send_whatsapp(user.phone_number, f"Your AI Sched verification code is: {otp}")

    from backend.extensions import db
    db.session.commit()

def send_password_reset_otp(user):
    """Generate and send OTP for password recovery."""
    otp = generate_secure_otp()
    
    user.email_otp = otp
    user.otp_created_at = datetime.now(timezone.utc)

    # SECURE LOGGING: Never log the actual OTP in production
    logger.info(f"Password reset OTP generated for user ID: {user.id}")

    subject = "Password Reset Request - AI Sched"
    body = f"Hello {user.username},\n\nWe received a request to reset your password. Use the following code: {otp}\n\nIf you didn't request this, please ignore this email."

    send_email(user.email, subject, body)

    from backend.extensions import db
    db.session.commit()

def send_email(to_email, subject, body):
    """Sends an email using SMTP. Simulates if credentials missing."""
    if not current_app.config.get('MAIL_PASSWORD'):
        print("\n" + "="*50)
        print(f"📧 [SIMULATED EMAIL] To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        print("="*50 + "\n")
        logger.debug(f"[SIMULATED EMAIL] To: {to_email} | Subject: {subject}")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(current_app.config.get('MAIL_SERVER'), current_app.config.get('MAIL_PORT'))
        server.starttls()
        server.login(current_app.config.get('MAIL_USERNAME'), current_app.config.get('MAIL_PASSWORD'))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

def send_whatsapp(to_number, message):
    """Sends a WhatsApp message via Twilio."""
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    from_number = current_app.config.get('TWILIO_WHATSAPP_NUMBER')

    if not all([account_sid, auth_token, from_number]):
        print("\n" + "="*50)
        print(f"📱 [SIMULATED WHATSAPP] To: {to_number}")
        print(f"Message: {message}")
        print("="*50 + "\n")
        logger.debug(f"[WHATSAPP]: {to_number} -> {message}")
        return True

    try:
        client = Client(account_sid, auth_token)
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        client.messages.create(from_=from_number, body=message, to=to_number)
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp: {e}")
        return False

# Localization Mapping
MESSAGES = {
    'en': {
        'confirmed_subject': 'Booking Confirmed: {service}',
        'confirmed_body': 'Hello {user},\n\nYour appointment with {business} for {service} is confirmed for {time}.\n\nThank you for choosing AI Sched!',
        'reminder_subject': 'Appointment Reminder - AI Sched',
        'reminder_body': 'Hi {user},\n\nThis is a reminder for your appointment at {business} tomorrow at {time}. See you soon!',
        'whatsapp_confirmed': '✅ Booking Confirmed! Your appointment for {service} on {time} is set. See you soon!'
    },
    'hi': {
        'confirmed_subject': 'बुकिंग की पुष्टि: {service}',
        'confirmed_body': 'नमस्ते {user},\n\n{business} के साथ {service} के लिए आपका अपॉइंटमेंट {time} पर कंफर्म हो गया है।\n\nAI Sched चुनने के लिए धन्यवाद!',
        'reminder_subject': 'अपॉइंटमेंट रिमाइंडर - AI Sched',
        'reminder_body': 'नमस्ते {user},\n\nयह कल {time} पर {business} में आपके अपॉइंटमेंट के लिए एक रिमाइंडर है। जल्द ही मिलते हैं!',
        'whatsapp_confirmed': '✅ बुकिंग की पुष्टि! {service} के लिए आपका अपॉइंटमेंट {time} पर तय है। जल्द ही मिलते हैं!'
    },
    'traffic_alert': {
        'en': '🚨 Time to Leave! Traffic is currently {traffic_state}. Travel time to {business} is approx {duration} mins. Your appt is at {time}.',
        'hi': '🚨 निकलने का समय! ट्रैफिक अभी {traffic_state} है। {business} तक पहुँचने में करीब {duration} मिनट लगेंगे। आपका अपॉइंटमेंट {time} पर है।'
    }
}

def get_message(key, lang='en', **kwargs):
    template = MESSAGES.get(lang, MESSAGES['en']).get(key, '')
    return template.format(**kwargs)

def send_realtime_update(target_type, target_id, data):
    """Sends a real-time event via Azure Web PubSub."""
    conn_str = current_app.config.get('AZURE_WEBPUBSUB_CONNECTION_STRING')
    hub_name = current_app.config.get('AZURE_WEBPUBSUB_HUB', 'marketplace')

    if not conn_str:
        logger.debug(f"[REALTIME]: {target_type} {target_id} -> {data}")
        return True

    try:
        client = WebPubSubServiceClient.from_connection_string(conn_str, hub=hub_name)
        group = f"{target_type}_{target_id}" # e.g. user_1 or business_5
        client.send_to_group(group, message=json.dumps(data), content_type="application/json")
        return True
    except Exception as e:
        logger.error(f"Web PubSub error: {e}")
        return False

def notify_booking_confirmation(appointment, lang='en'):
    # Email
    subject = get_message('confirmed_subject', lang, service=appointment.service.name)
    body = get_message('confirmed_body', lang, user=appointment.customer.username, 
                       business=appointment.business.name, time=appointment.start_time.strftime('%b %d at %H:%M'))
    send_email(appointment.customer.email, subject, body)

    # Real-time update for Merchant & Customer
    event_data = {
        "type": "BOOKING_CONFIRMED",
        "appointment_id": appointment.id,
        "message": f"New booking for {appointment.service.name}"
    }
    send_realtime_update("business", appointment.business_id, event_data)
    send_realtime_update("user", appointment.customer_id, event_data)

    # WhatsApp
    whatsapp_msg = get_message('whatsapp_confirmed', lang, service=appointment.service.name, 
                                time=appointment.start_time.strftime('%d %b, %H:%M'))
    send_whatsapp("+919876543210", whatsapp_msg)

def notify_appointment_reminder(appointment, lang='en'):
    subject = get_message('reminder_subject', lang)
    body = get_message('reminder_body', lang, user=appointment.customer.username,
                       business=appointment.business.name, time=appointment.start_time.strftime('%H:%M'))
    send_email(appointment.customer.email, subject, body)

def notify_waitlist_open(waitlist_entry):
    subject = "Slot Available! - AI Sched"
    body = f"Hello {waitlist_entry.user.username},\n\nA slot for {waitlist_entry.service.name} at {waitlist_entry.business.name} has just become available. Book now before it's gone!\n\nBest, AI Sched Team"
    send_email(waitlist_entry.user.email, subject, body)

def notify_time_to_leave(appointment, duration_mins, lang='en'):
    """Sends a push/WhatsApp alert based on OSRM travel estimation."""
    traffic_state = "high" if duration_mins > 30 else "moderate"
    msg_tmpl = MESSAGES['traffic_alert'].get(lang, MESSAGES['traffic_alert']['en'])

    text = msg_tmpl.format(
        traffic_state=traffic_state,
        business=appointment.business.name,
        duration=duration_mins,
        time=appointment.start_time.strftime('%H:%M')
    )

    send_whatsapp("+919876543210", text)
    # Also email
    send_email(appointment.customer.email, "🚨 Time to Leave - AI Sched", text)
