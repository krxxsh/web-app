from datetime import datetime, timedelta
from backend.app import create_app
from backend.models.models import Appointment
from backend.services.notifications import send_email

def check_and_send_reminders():
    """
    Checks for upcoming appointments and sends reminders.
    Target: 24h and 1h before start_time.
    """
    app = create_app()
    with app.app_context():
        now = datetime.now()
        
        # 1. 24-hour Reminders
        target_24h = now + timedelta(hours=24)
        appts_24h = Appointment.query.filter(
            Appointment.start_time >= target_24h - timedelta(minutes=5),
            Appointment.start_time <= target_24h + timedelta(minutes=5),
            Appointment.status == 'booked'
        ).all()
        
        for appt in appts_24h:
            subject = "Reminder: Appointment in 24 Hours"
            body = f"Hello {appt.customer.username},\n\nJust a reminder that you have an appointment with {appt.business.name} tomorrow at {appt.start_time.strftime('%H:%M')}.\n\nSee you then!"
            send_email(appt.customer.email, subject, body)

        # 2. 1-hour Reminders
        target_1h = now + timedelta(hours=1)
        appts_1h = Appointment.query.filter(
            Appointment.start_time >= target_1h - timedelta(minutes=5),
            Appointment.start_time <= target_1h + timedelta(minutes=5),
            Appointment.status == 'booked'
        ).all()
        
        for appt in appts_1h:
            subject = "Reminder: Appointment in 1 Hour"
            body = f"Hello {appt.customer.username},\n\nYour appointment with {appt.business.name} starts in 1 hour ({appt.start_time.strftime('%H:%M')}).\n\nDon't be late!"
            send_email(appt.customer.email, subject, body)

if __name__ == "__main__":
    check_and_send_reminders()
