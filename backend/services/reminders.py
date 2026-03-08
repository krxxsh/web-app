import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import logging
from backend.app import create_app
from backend.extensions import db
from backend.models.models import Appointment
from backend.services.notifications import notify_appointment_reminder

logger = logging.getLogger(__name__)

def run_reminder_worker():
    app = create_app()
    with app.app_context():
        logger.info("Checking for upcoming appointments...")
        # Get appointments in the next 24 hours that haven't been reminded
        tomorrow = datetime.now() + timedelta(days=1)
        datetime.now() + timedelta(hours=1)

        # 24h reminders
        remind_24 = Appointment.query.filter(
            Appointment.start_time <= tomorrow,
            Appointment.start_time > datetime.now(),
            Appointment.status == 'booked',
            not Appointment.is_reminder_sent
        ).all()

        for appt in remind_24:
            logger.info(f"Sending 24h reminder to {appt.customer.username} for {appt.service.name}")
            notify_appointment_reminder(appt)
            appt.is_reminder_sent = True

        db.session.commit()
        logger.info(f"Reminders sent: {len(remind_24)}")

if __name__ == "__main__":
    run_reminder_worker()
