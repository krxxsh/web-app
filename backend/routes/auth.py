from flask import Blueprint, render_template, url_for, redirect, request, jsonify
from flask_login import login_user, current_user, logout_user
from backend.extensions import db, bcrypt
from backend.models.models import User

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
