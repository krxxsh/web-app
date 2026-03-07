from flask_login import UserMixin
from backend.extensions import db, login_manager
from datetime import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer') # admin, staff, customer
    
    # Advanced Features Support
    membership_level = db.Column(db.String(20), default='free') # free, silver, gold, platinum
    loyalty_points = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(20), unique=True, nullable=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    preferred_language = db.Column(db.String(5), default='en') # en, hi
    
    # Relationships
    businesses = db.relationship('Business', backref='owner', lazy=True)
    appointments = db.relationship('Appointment', backref='customer', lazy=True, foreign_keys='Appointment.customer_id')
    oauth_tokens = db.relationship('OAuthToken', backref='user', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class OAuthToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(20), nullable=False) # google, outlook
    token_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    working_hours = db.Column(db.JSON, nullable=True) # e.g. {"mon": ["09:00", "17:00"], ...}
    
    # Advanced Features Support
    use_ai_recommendations = db.Column(db.Boolean, default=True)
    auto_notify_waitlist = db.Column(db.Boolean, default=True)
    
    # White-Labeling Settings
    primary_color = db.Column(db.String(20), default='#6366f1')
    logo_url = db.Column(db.String(255), nullable=True)
    
    # Relationships
    services = db.relationship('Service', backref='business', lazy=True)
    staff = db.relationship('Staff', backref='business', lazy=True)
    appointments = db.relationship('Appointment', backref='business', lazy=True)
    resources = db.relationship('Resource', backref='business', lazy=True)

class Resource(db.Model):
    """Rooms, equipment, or other limited assets required for services."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False) # Room, Laser Machine, etc.
    quantity = db.Column(db.Integer, default=1)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # If staff has login
    
    # Advanced Features Support
    zoom_link = db.Column(db.String(255), nullable=True)
    
    # Relationships
    appointments = db.relationship('Appointment', backref='staff', lazy=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False) # In minutes
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    
    # Advanced Features Support
    requires_resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    is_virtual = db.Column(db.Boolean, default=False)
    upsell_services = db.Column(db.String(255), nullable=True) # Comma separated IDs
    member_only = db.Column(db.Boolean, default=False) # If true, restricted to premium members

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='booked') # booked, pending, cancelled, completed
    payment_status = db.Column(db.String(20), nullable=False, default='pending') # pending, paid, refunded
    
    # Advanced Features Support
    google_event_id = db.Column(db.String(255), nullable=True)
    virtual_link = db.Column(db.String(255), nullable=True)
    is_reminder_sent = db.Column(db.Boolean, default=False)

class Waitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    request_date = db.Column(db.DateTime, nullable=False)
    notified = db.Column(db.Boolean, default=False)
