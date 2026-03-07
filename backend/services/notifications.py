import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from twilio.rest import Client

def send_email(to_email, subject, body):
    """Sends an email using SMTP. Simulates if credentials missing."""
    if not current_app.config.get('MAIL_PASSWORD'):
        print(f"DEBUG: [SIMULATED EMAIL] To: {to_email} | Subject: {subject}")
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
        print(f"Error sending email: {e}")
        return False

def send_whatsapp(to_number, message):
    """Sends a WhatsApp message via Twilio."""
    account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    from_number = current_app.config.get('TWILIO_WHATSAPP_NUMBER')
    
    if not all([account_sid, auth_token, from_number]):
        print(f"DEBUG [WHATSAPP]: {to_number} -> {message}")
        return True
        
    try:
        client = Client(account_sid, auth_token)
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        client.messages.create(from_=from_number, body=message, to=to_number)
        return True
    except Exception as e:
        print(f"Failed to send WhatsApp: {e}")
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

def notify_booking_confirmation(appointment, lang='en'):
    # Email
    subject = get_message('confirmed_subject', lang, service=appointment.service.name)
    body = get_message('confirmed_body', lang, user=appointment.customer.username, 
                       business=appointment.business.name, time=appointment.start_time.strftime('%b %d at %H:%M'))
    send_email(appointment.customer.email, subject, body)
    
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
