from flask_login import UserMixin
from backend.extensions import db, login_manager
from datetime import datetime


class BusinessCategory(db.Model):
    """Predefined business categories selectable at registration."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # e.g. Health, Salon, Legal
    icon = db.Column(db.String(10), default='🏢')  # emoji icon
    description = db.Column(db.String(200), nullable=True)
    is_health_related = db.Column(db.Boolean, default=False)  # Enables emergency tab context

    businesses = db.relationship('Business', backref='category_obj', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'description': self.description,
            'is_health_related': self.is_health_related,
        }

class SubscriptionPlan(db.Model):
    """Tiered plans for Business Owners."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # Free, Monthly, Yearly
    price = db.Column(db.Float, default=0.0)
    duration_days = db.Column(db.Integer, default=30)
    features = db.Column(db.JSON, nullable=True) # {"ai_insights": true, "multi_branch": true, ...}

    subscriptions = db.relationship('Subscription', backref='plan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'duration_days': self.duration_days,
            'features': self.features
        }

class Subscription(db.Model):
    """Active subscriptions for users (Business Owners)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active') # active, cancelled, expired
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    auto_renew = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'auto_renew': self.auto_renew
        }

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='customer') # business_owner, staff, customer, platform_owner

    # Advanced Features Support
    membership_level = db.Column(db.String(20), default='free') # free, silver, gold, platinum
    loyalty_points = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(20), unique=True, nullable=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    preferred_language = db.Column(db.String(5), default='en') # en, hi

    # Security & Verification
    is_verified = db.Column(db.Boolean, default=False)
    is_platform_owner = db.Column(db.Boolean, default=False)
    email_otp = db.Column(db.String(6), nullable=True)
    phone_otp = db.Column(db.String(6), nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    phone_verified_at = db.Column(db.DateTime, nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    otp_created_at = db.Column(db.DateTime, nullable=True)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=True)
    fcm_token = db.Column(db.String(255), nullable=True)

    # Relationships
    oauth_tokens = db.relationship('OAuthToken', backref='user', lazy=True)
    subscriptions = db.relationship('Subscription', backref='user', lazy=True)
    businesses = db.relationship('Business', backref='owner', lazy=True, foreign_keys='Business.owner_id')

    # Marketplace Tracking
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    favorite_businesses = db.Column(db.String(500), default='') # Comma separated IDs

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'membership_level': self.membership_level,
            'loyalty_points': self.loyalty_points,
            'is_verified': self.is_verified,
            'phone_number': self.phone_number
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class OAuthToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(20), nullable=False) # google, outlook
    token_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'provider': self.provider,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    working_hours = db.Column(db.JSON, nullable=True)  # e.g. {"mon": ["09:00", "17:00"], ...}

    # Category & Location
    category_id = db.Column(db.Integer, db.ForeignKey('business_category.id'), nullable=True)
    category = db.Column(db.String(50), nullable=True) # Cache name for easy access
    address = db.Column(db.String(300), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    website = db.Column(db.String(255), nullable=True)

    # Advanced Features Support
    use_ai_recommendations = db.Column(db.Boolean, default=True)
    auto_notify_waitlist = db.Column(db.Boolean, default=True)
    queue_enabled = db.Column(db.Boolean, default=False)
    emergency_priority_enabled = db.Column(db.Boolean, default=False)
    typical_wait_time = db.Column(db.Integer, default=15) # in minutes
    avg_service_time_override = db.Column(db.Integer, nullable=True) # for queue estimations
    status = db.Column(db.String(20), default='pending') # pending, active, suspended

    # Multi-branch support
    parent_business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=True)
    is_main_branch = db.Column(db.Boolean, default=True)
    branches = db.relationship('Business', backref=db.backref('parent', remote_side=[id]))

    # White-Labeling Settings
    primary_color = db.Column(db.String(20), default='#1d76f2')
    logo_url = db.Column(db.String(255), nullable=True)

    # Relationships are handled via backrefs in Service, Staff, Appointment, Resource
    promotions = db.relationship('Promotion', backref='business', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'phone': self.phone,
            'website': self.website,
            'logo_url': self.logo_url,
            'primary_color': self.primary_color,
            'use_ai_recommendations': self.use_ai_recommendations,
            'queue_enabled': self.queue_enabled,
            'status': self.status
        }

class Resource(db.Model):
    """Rooms, equipment, or other limited assets required for services."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False) # Room, Laser Machine, etc.
    quantity = db.Column(db.Integer, default=1)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)

    # Relationships
    business = db.relationship('Business', backref=db.backref('resources', lazy=True))


    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'resource_type': self.resource_type,
            'quantity': self.quantity,
            'business_id': self.business_id
        }

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # If staff has login

    # Advanced Features Support
    zoom_link = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    business = db.relationship('Business', backref=db.backref('staff', lazy=True))
    user = db.relationship('User', backref=db.backref('staff_profile', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'business_id': self.business_id,
            'user_id': self.user_id,
            'is_active': self.is_active
        }

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False) # In minutes
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    business = db.relationship('Business', backref=db.backref('services', lazy=True))

    # Advanced Features Support
    requires_resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    is_virtual = db.Column(db.Boolean, default=False)
    upsell_services = db.Column(db.String(255), nullable=True) # Comma separated IDs
    member_only = db.Column(db.Boolean, default=False) # If true, restricted to premium members
    prep_instructions = db.Column(db.Text, nullable=True)
    is_group_allowed = db.Column(db.Boolean, default=False)
    max_group_size = db.Column(db.Integer, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'duration': self.duration,
            'price': self.price,
            'description': self.description,
            'business_id': self.business_id,
            'is_virtual': self.is_virtual
        }

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
    party_size = db.Column(db.Integer, default=1)
    group_details = db.Column(db.JSON, nullable=True) # list of names/IDs
    check_in_time = db.Column(db.DateTime, nullable=True)
    travel_time_est = db.Column(db.Integer, nullable=True) # in minutes
    is_priority = db.Column(db.Boolean, default=False)
    cancellation_reason = db.Column(db.String(255), nullable=True)
    checkin_pin = db.Column(db.String(6), nullable=True) # Secure check-in

    # Unified Relationship source of truth with explicit backrefs
    customer = db.relationship('User', backref=db.backref('appointments', lazy=True), foreign_keys=[customer_id])
    business = db.relationship('Business', backref=db.backref('appointments', lazy=True), foreign_keys=[business_id])
    service = db.relationship('Service', backref=db.backref('appointments', lazy=True), foreign_keys=[service_id])
    staff = db.relationship('Staff', backref=db.backref('appointments', lazy=True), foreign_keys=[staff_id])
    resource = db.relationship('Resource', backref=db.backref('appointments', lazy=True), foreign_keys=[resource_id])

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'business_id': self.business_id,
            'service_id': self.service_id,
            'staff_id': self.staff_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'payment_status': self.payment_status,
            'virtual_link': self.virtual_link
        }

class Waitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    request_date = db.Column(db.DateTime, nullable=False)
    notified = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active') # active, converted, expired

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'business_id': self.business_id,
            'service_id': self.service_id,
            'request_date': self.request_date.isoformat() if self.request_date else None,
            'status': self.status
        }

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1-5
    comment = db.Column(db.Text, nullable=True)
    ai_category = db.Column(db.String(50), nullable=True) # waiting time, service quality, staff behavior
    sentiment_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'user_id': self.user_id,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class AdminActivityLog(db.Model):
    """Audit trail for business management actions."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False) # e.g. "update_branding", "add_staff"
    details = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'business_id': self.business_id,
            'action': self.action,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

class Promotion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    discount_pct = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'title': self.title,
            'description': self.description,
            'discount_pct': self.discount_pct,
            'is_active': self.is_active
        }

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(20), default='pending') # pending, paid, failed, refunded
    payment_method = db.Column(db.String(50), nullable=True) # razorpay, stripe, cash
    gateway_transaction_id = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'subscription_id': self.subscription_id,
            'business_id': self.business_id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'payment_method': self.payment_method,
            'gateway_transaction_id': self.gateway_transaction_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

