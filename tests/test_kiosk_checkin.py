import pytest
from backend.services.scheduling_service import check_in_with_pin
from backend.models.models import Appointment, User, Business, Service
from backend.extensions import db
from datetime import datetime, timedelta, timezone

def test_check_in_with_pin_success(app):
    """Test successful check-in with a valid PIN."""
    with app.app_context():
        # Create a test customer
        customer = User(username="testuser", email="test@example.com", password="hash", role="customer")
        db.session.add(customer)
        db.session.commit()
        
        # Create a business
        business = Business(name="Test Spa", category="Salon", address="123 Street", owner_id=customer.id)
        db.session.add(business)
        db.session.commit()
        
        # Create a service
        service = Service(name="Massage", duration=30, price=50.0, business_id=business.id)
        db.session.add(service)
        db.session.commit()

        # Create a scheduled appointment for today
        now = datetime.now(timezone.utc)
        pin = "123456"
        appt = Appointment(
            customer_id=customer.id,
            business_id=business.id,
            service_id=service.id,
            start_time=now + timedelta(minutes=10),
            end_time=now + timedelta(minutes=40),
            status="booked",
            checkin_pin=pin
        )
        db.session.add(appt)
        db.session.commit()

        # Perform check-in
        success, message = check_in_with_pin(pin)
        
        assert success is True
        assert "Successfully checked in" in message
        
        # Verify status in DB
        db.session.refresh(appt)
        assert appt.status == "arrived"
        assert appt.check_in_time is not None

def test_check_in_with_pin_invalid(app):
    """Test check-in with an invalid PIN."""
    with app.app_context():
        success, message = check_in_with_pin("000000")
        assert success is False
        assert "Invalid PIN or appointment not found today" in message

def test_check_in_with_pin_wrong_day(app):
    """Test check-in with a valid PIN but for a different day."""
    with app.app_context():
        customer = User(username="otheruser", email="other@example.com", password="hash", role="customer")
        db.session.add(customer)
        db.session.commit()
        
        # Create a business
        business = Business(name="Other Spa", category="Salon", address="456 Street", owner_id=customer.id)
        db.session.add(business)
        db.session.commit()
        
        # Create a service
        service = Service(name="Facial", duration=30, price=60.0, business_id=business.id)
        db.session.add(service)
        db.session.commit()

        # Create a scheduled appointment for tomorrow
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        pin = "654321"
        appt = Appointment(
            customer_id=customer.id,
            business_id=business.id,
            service_id=service.id,
            start_time=tomorrow,
            end_time=tomorrow + timedelta(minutes=30),
            status="booked",
            checkin_pin=pin
        )
        db.session.add(appt)
        db.session.commit()

        success, message = check_in_with_pin(pin)
        assert success is False
        assert "Invalid PIN or appointment not found today" in message
