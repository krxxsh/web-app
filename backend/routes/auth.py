import logging
from flask import Blueprint, render_template, url_for, redirect, request, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from backend.extensions import db, bcrypt
from backend.models.models import User, Business
from backend.services.notifications import send_password_reset_otp
from backend.services.firebase_config import verify_firebase_token
from datetime import datetime, timezone, timedelta
import jwt
import secrets
from flask import current_app, session
from backend.services.calendar_sync import get_google_flow

logger = logging.getLogger(__name__)

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
    # Determine redirect based on user role
    if role in ['admin', 'business_owner']:
        return jsonify({"success": True, "redirect": url_for('admin.setup_business')})
    else:
        return jsonify({"success": True, "redirect": url_for('main.home')})

@auth_bp.route("/dev-login", methods=['POST'])
def dev_login():
    """Local development fallback for login when Firebase is missing."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password, password):
        login_user(user, remember=True)
        # Determine redirect based on user role
        if user.role == 'business_owner':
            # Check if user has a business setup
            business = Business.query.filter_by(owner_id=user.id).first()
            if business:
                return jsonify({"success": True, "redirect": url_for('admin.dashboard')})
            else:
                return jsonify({"success": True, "redirect": url_for('admin.setup_business')})
        elif user.role == 'pending':
            return jsonify({"success": True, "redirect": url_for('main.select_role')})
        else:
            return jsonify({"success": True, "redirect": url_for('main.home')})
    return jsonify({"success": False, "message": "Invalid local credentials"}), 401@auth_bp.route("/register", methods=['GET'])
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

@auth_bp.route("/google/login")
def google_login():
    """Initiate Google OAuth flow"""
    if not current_app.config.get("GOOGLE_CLIENT_ID") or not current_app.config.get("GOOGLE_CLIENT_SECRET"):
        return jsonify({"error": "Google OAuth not configured"}), 500
    
    flow = get_google_flow()
    # Generate state token to prevent CSRF
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state
    )
    
    return redirect(authorization_url)


@auth_bp.route("/google/callback")
def google_callback():
    """Handle Google OAuth callback"""
    try:
        # Get parameters from request
        error = request.args.get("error")
        if error:
            return jsonify({"error": f"Google OAuth error: {error}"}), 400
            
        code = request.args.get("code")
        state = request.args.get("state")
        
        # Validate state to prevent CSRF
        if not state or state != session.get("oauth_state"):
            session.pop("oauth_state", None)
            return jsonify({"error": "Invalid state parameter"}), 400
        
        if not code:
            return jsonify({"error": "Missing authorization code"}), 400
        
        # Exchange code for tokens
        flow = get_google_flow()
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Verify the ID token
        id_info = jwt.decode(
            credentials.id_token,
            current_app.config["GOOGLE_CLIENT_ID"],
            algorithms=["RS256"],
            audience=current_app.config["GOOGLE_CLIENT_ID"]
        )
        
        # Extract user info
        email = id_info.get("email")
        if not email:
            return jsonify({"error": "No email in token"}), 400
            
        email_verified = id_info.get("email_verified", False)
        name = id_info.get("name", "")
        picture = id_info.get("picture", "")
        google_user_id = id_info.get("sub")
        
        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Create new user
            username = email.split("@")[0]
            # Ensure username is unique
            counter = 1
            original_username = username
            while User.query.filter_by(username=username).first():
                username = f"{original_username}{counter}"
                counter += 1
            
            user = User(
                username=username,
                email=email,
                password=secrets.token_urlsafe(32),  # Random unusable password
                role="customer",
                is_verified=email_verified
            )
            db.session.add(user)
        else:
            # Update existing user
            if email_verified and not user.is_verified:
                user.is_verified = True
            # Optionally update name/picture if needed
        
        db.session.commit()
        
        # Generate JWT token
        jwt_payload = {
            "user_id": user.id,
            "exp": datetime.utcnow() + timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])
        }
        access_token = jwt.encode(jwt_payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")
        
        # Clear OAuth state
        session.pop("oauth_state", None)
        
        # Redirect to frontend with token
        frontend_url = current_app.config.get("FRONTEND_URL", "https://management-one-gilt.vercel.app")
        redirect_url = f"{frontend_url}/dashboard?token={access_token}"
        
        return redirect(redirect_url)
        
    except Exception as e:
        # Clear OAuth state on error
        session.pop("oauth_state", None)
        logger.error(f"Google OAuth callback error: {str(e)}")
        return jsonify({"error": "Authentication failed"}), 500


