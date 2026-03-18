import logging
from flask import Blueprint, render_template, url_for, redirect, request, jsonify, current_app, session
from flask_login import login_user, current_user, logout_user, login_required
from backend.extensions import db, bcrypt
from backend.models.models import User, Business
from datetime import datetime, timezone, timedelta
import secrets

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

    if request.method == 'POST':
        return jsonify({"success": False, "message": "Please use the Firebase reset flow."}), 400
    return render_template('forgot_password.html', title='Forgot Password')

@auth_bp.route("/reset-password", methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        return jsonify({"success": False, "message": "Please use the Firebase reset flow."}), 400
    return render_template('reset_password.html', title='Reset Password')


