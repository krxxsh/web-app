import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from backend.app import create_app
from backend.extensions import db
from backend.models.models import User, Business, Appointment, Staff, Service
from backend.config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True
    TALISMAN_FORCE_HTTPS = False

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def _seed_data(app):
    with app.app_context():
        # Create Owner
        owner = User(
            username='owner',
            email='owner@example.com',
            password='hashed_password',
            role='business_owner'
        )
        db.session.add(owner)
        db.session.commit()
        owner_id = owner.id

        # Create Business
        business = Business(
            name='Test Salon',
            owner_id=owner_id,
            category='Salon'
        )
        db.session.add(business)
        db.session.commit()
        business_id = business.id

        # Create Service
        service = Service(
            name='Haircut',
            duration=30,
            price=50.0,
            business_id=business_id
        )
        db.session.add(service)
        db.session.commit()
        service_id = service.id

        # Create Staff
        staff = Staff(
            name='John Staff',
            business_id=business_id,
            is_active=True
        )
        db.session.add(staff)
        db.session.commit()
        staff_id = staff.id

        # Create Appointments
        now = datetime.now(timezone.utc)
        
        # 1. Completed
        apt1 = Appointment(
            business_id=business_id,
            customer_id=owner_id, 
            service_id=service_id,
            staff_id=staff_id,
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1, minutes=-30),
            status='completed'
        )
        # 2. Booked (Pending in dashboard)
        apt2 = Appointment(
            business_id=business_id,
            customer_id=owner_id,
            service_id=service_id,
            staff_id=staff_id,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1, minutes=30),
            status='booked'
        )
        # 3. Booked (Another pending)
        apt3 = Appointment(
            business_id=business_id,
            customer_id=owner_id,
            service_id=service_id,
            staff_id=staff_id,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, minutes=30),
            status='booked'
        )
        # 4. Cancelled
        apt4 = Appointment(
            business_id=business_id,
            customer_id=owner_id,
            service_id=service_id,
            staff_id=staff_id,
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=2, minutes=-30),
            status='cancelled'
        )

        db.session.add_all([apt1, apt2, apt3, apt4])
        db.session.commit()

        return {
            "owner_id": owner_id,
            "business_id": business_id
        }

def test_dashboard_stats_success(app, client):
    """Stats endpoint returns correct aggregated data for the business owner."""
    ids = _seed_data(app)
    
    with patch('backend.routes.api.current_user') as mock_user:
        mock_user.id = ids["owner_id"]
        mock_user.role = 'business_owner'
        
        response = client.get(f'/api/dashboard/stats/{ids["business_id"]}')
        assert response.status_code == 200
        data = response.get_json()
        
        # total_bookings = completed(1) + booked(2) + cancelled(1) = 4
        assert data['total_bookings'] == 4
        assert data['completed_bookings'] == 1
        assert data['pending_bookings'] == 2
        assert data['cancelled_bookings'] == 1
        # total_revenue = Service.price for completed only = 50.0
        assert data['total_revenue'] == 50.0
        assert data["active_staff"] == 1
        assert "booking_trend" in data
        assert len(data["booking_trend"]["data"]) == 7

def test_dashboard_stats_unauthorized(app, client):
    """Fails if user is not the owner of the business."""
    ids = _seed_data(app)
    
    with patch('backend.routes.api.current_user') as mock_user:
        mock_user.id = 999 
        mock_user.role = 'business_owner'
        
        response = client.get(f'/api/dashboard/stats/{ids["business_id"]}')
        assert response.status_code == 403

def test_dashboard_stats_business_not_found(app, client):
    """Returns 404 if business_id does not exist."""
    ids = _seed_data(app)
    
    with patch('backend.routes.api.current_user') as mock_user:
        mock_user.id = ids["owner_id"]
        mock_user.role = 'business_owner'
        
        response = client.get('/api/dashboard/stats/9999')
        assert response.status_code == 404
