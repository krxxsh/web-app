import os
import random
import json
import secrets
import logging
from flask import current_app
from twilio.rest import Client
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from firebase_admin import messaging

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
import sentry_sdk

def send_push_notification(user, title, body, data=None):
    """Sends a push notification via Firebase Cloud Messaging."""
    if not user or not user.fcm_token:
        logger.warning(f"Push skipped: No FCM token for user {user.id if user else 'Unknown'}")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=user.fcm_token,
        )
        response = messaging.send(message)
        logger.info(f"Successfully sent push message: {response}")
        return True
    except Exception as e:
        log_and_notify_critical_failure("FCM Push Dispatch", e, {"user_id": user.id})
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
        log_and_notify_critical_failure("WhatsApp Dispatch", e, {"to": to_number})
        return False

# Localization Mapping
MESSAGES = {
    'en': {
        'confirmed_subject': 'Booking Confirmed!',
        'confirmed_body': 'Your appointment with {business} for {service} is confirmed for {time}.',
        'reminder_subject': 'Appointment Reminder',
        'reminder_body': 'Hi {user}, reminder for your appointment at {business} tomorrow at {time}.',
        'whatsapp_confirmed': '✅ Booking Confirmed! Your appointment for {service} on {time} is set. See you soon!'
    },
    'hi': {
        'confirmed_subject': 'बुकिंग की पुष्टि!',
        'confirmed_body': '{business} के साथ {service} के लिए आपका अपॉइंटमेंट {time} पर कंफर्म हो गया है।',
        'reminder_subject': 'अपॉइंटमेंट रिमाइंडर',
        'reminder_body': 'नमस्ते {user}, कल {time} पर {business} में आपके अपॉइंटमेंट के लिए एक रिमाइंडर है।',
        'whatsapp_confirmed': '✅ बुकिंग की पुष्टि! {service} के लिए आपका अपॉइंटमेंट {time} पर तय है। जल्द ही मिलते हैं!'
    },
    'traffic_alert': {
        'en': '🚨 Time to Leave! Traffic is {traffic_state}. Travel to {business} is ~{duration} mins. Appt at {time}.',
        'hi': '🚨 निकलने का समय! ट्रैफिक {traffic_state} है। {business} तक ~{duration} मिनट लगेंगे। अपॉइंटमेंट {time} पर है।'
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

def log_and_notify_critical_failure(operation, error, details=None):
    """Logs a critical failure to Sentry and local logs."""
    msg = f"CRITICAL FAILURE: {operation} | Error: {str(error)}"
    logger.critical(msg)
    
    with sentry_sdk.push_scope() as scope:
        if details:
            for k, v in details.items():
                scope.set_extra(k, v)
        sentry_sdk.capture_message(msg, level="fatal")
    
    print(f"🚨 ALERT: {msg}")

def send_verification_otp(user):
    """Sends a verification OTP via email/SMS."""
    if not user:
        return False
    
    # Generate 6-digit OTPs
    email_otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    phone_otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    
    user.email_otp = email_otp
    user.phone_otp = phone_otp
    user.otp_created_at = datetime.now(timezone.utc)
    
    from backend.extensions import db
    db.session.commit()
    
    # In a real production app, we would call an email/SMS provider here.
    # For now, we log it (and it will show in simulated logs for the user to see).
    logger.info(f"Verification OTPs generated for {user.email}: Email={email_otp}, Phone={phone_otp}")
    
    print("\n" + "!"*50)
    print(f"🔐 [SECURITY] OTPs for {user.email}")
    print(f"Email OTP: {email_otp}")
    print(f"Phone OTP: {phone_otp}")
    print("!"*50 + "\n")
    
    return True

def notify_booking_confirmation(appointment, lang='en'):
    # Push Notification
    title = get_message('confirmed_subject', lang, service=appointment.service.name)
    body = get_message('confirmed_body', lang, user=appointment.customer.username, 
                       business=appointment.business.name, time=appointment.start_time.strftime('%b %d at %H:%M'))
    
    send_push_notification(appointment.customer, title, body, {
        "type": "BOOKING_CONFIRMED",
        "appointment_id": str(appointment.id)
    })

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
    if appointment.customer and appointment.customer.phone_number:
        send_whatsapp(appointment.customer.phone_number, whatsapp_msg)

def notify_appointment_reminder(appointment, lang='en'):
    title = get_message('reminder_subject', lang)
    body = get_message('reminder_body', lang, user=appointment.customer.username,
                       business=appointment.business.name, time=appointment.start_time.strftime('%H:%M'))
    
    send_push_notification(appointment.customer, title, body, {
        "type": "REMINDER",
        "appointment_id": str(appointment.id)
    })

def notify_waitlist_open(waitlist_entry):
    title = "Slot Available! 📢"
    body = f"A slot for {waitlist_entry.service.name} at {waitlist_entry.business.name} has just become available. Book now!"
    
    send_push_notification(waitlist_entry.user, title, body, {
        "type": "WAITLIST_OPEN",
        "service_id": str(waitlist_entry.service_id)
    })

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

    # Push
    send_push_notification(appointment.customer, "🚨 Time to Leave", text, {
        "type": "TIME_TO_LEAVE",
        "appointment_id": str(appointment.id)
    })

    # WhatsApp
    if appointment.customer and appointment.customer.phone_number:
        send_whatsapp(appointment.customer.phone_number, text)
