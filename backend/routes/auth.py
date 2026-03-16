from flask import Blueprint, render_template, url_for, redirect, request, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from backend.extensions import db, bcrypt
from backend.models.models import User
from backend.services.notifications import send_password_reset_otp
from backend.services.firebase_config import verify_firebase_token
from datetime import datetime, timezone, timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/dev-register", methods=['POST'])
def dev_register():
    """Local development fallback for registration when Firebase is missing."""
    data = request.get_json()
    email = data.get('email')
    username = data.get('username')
    role = data.get('role', 'customer')
    phone = data.get('phone')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user:
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            password=hashed_pw,
            role='business_owner' if role in ['admin', 'business_owner'] else 'customer',
            phone_number=phone,
            is_verified=True,
            is_platform_owner=False
        )
        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)
    return jsonify({"success": True})

@auth_bp.route("/dev-login", methods=['POST'])
def dev_login():
    """Local development fallback for login when Firebase is missing."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password, password):
        login_user(user, remember=True)
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid local credentials"}), 401

@auth_bp.route("/register", methods=['GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('register.html', title='Register')

@auth_bp.route("/login", methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('login.html', title='Customer Login')

@auth_bp.route("/admin/login", methods=['GET'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'business_owner' or current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'staff':
            return redirect(url_for('staff.dashboard'))
        return redirect(url_for('main.home'))
    return render_template('login_admin.html', title='Admin Login')

@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@auth_bp.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            # Rate limiting: only send OTP every 60 seconds
            if user.otp_created_at:
                now = datetime.now(timezone.utc)
                last_otp = user.otp_created_at.replace(tzinfo=timezone.utc)
                if now - last_otp < timedelta(seconds=60):
                    return jsonify({"success": False, "message": "Please wait before requesting another OTP."}), 429
            
            if send_password_reset_otp(user):
                return jsonify({"success": True, "message": "OTP sent to your email."})
            
            # Internal logging for failure tracking
            logger.error(f"Failed to dispatch password reset OTP for user: {user.email}")
            return jsonify({
                "success": False, 
                "message": "We're experiencing temporary issues with our notification service. Please try again in a few minutes or contact support if the issue persists."
            }), 503
        return jsonify({"success": False, "message": "Email not found."}), 404
    return render_template('forgot_password.html', title='Forgot Password')

@auth_bp.route("/google-auth", methods=['POST'])
def google_auth():
    """Handles Google/External auth by verifying the ID token."""
    data = request.get_json()
    id_token = data.get('idToken')
    
    if not id_token:
        # Fallback for manual data if token is missing (useful for dev-login patterns if needed)
        email = data.get('email')
        username = data.get('username')
        uid = data.get('uid')
        if not email:
            return jsonify({"success": False, "message": "idToken or Email is required"}), 400
    else:
        decoded_token = verify_firebase_token(id_token)
        if not decoded_token:
            return jsonify({"success": False, "message": "Invalid or expired token"}), 401
        
        email = decoded_token.get('email')
        username = decoded_token.get('name') or email.split('@')[0]
        uid = decoded_token.get('uid')

    user = User.query.filter_by(email=email).first()
    if not user:
        # Create user if it doesn't exist
        user = User(
            username=username,
            email=email,
            password='EXTERNAL_AUTH', # Placeholder
            role='customer',
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
    
    login_user(user, remember=True)
    return jsonify({"success": True})

@auth_bp.route("/reset-password", methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        otp = data.get('otp')
        new_password = data.get('password')

        user = User.query.filter_by(email=email).first()
        if not user or user.email_otp != otp:
            return jsonify({"success": False, "message": "Invalid email or OTP."}), 400

        # Check OTP expiration (10 minutes)
        if user.otp_created_at:
            if datetime.now(timezone.utc) - user.otp_created_at.replace(tzinfo=timezone.utc) > timedelta(minutes=10):
                return jsonify({"success": False, "message": "OTP expired."}), 400

        # Update password
        user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.email_otp = None  # Clear OTP after use
        db.session.commit()
        return jsonify({"success": True, "message": "Password reset successful."})

    email = request.args.get('email', '')
    return render_template('reset_password.html', title='Reset Password', email=email)

