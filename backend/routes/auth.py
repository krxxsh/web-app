import logging
from flask import Blueprint, render_template, url_for, redirect, request, jsonify, current_app, session
from flask_login import login_user, current_user, logout_user, login_required
from backend.extensions import db, bcrypt
from backend.models.models import User, Business
from datetime import datetime, timezone, timedelta
import secrets

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# DELETED: dev-login and dev-register (Replaced by Firebase Client SDK)


@auth_bp.route("/register", methods=['GET'])
def register():
    if current_user.is_authenticated:
        if current_user.role == 'pending':
            return redirect(url_for('main.select_role'))
        return redirect(url_for('main.home'))
    return render_template('register.html', title='Register')

@auth_bp.route("/login", methods=['GET'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'pending':
            return redirect(url_for('main.select_role'))
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
        return jsonify({"success": False, "message": "Please use the Firebase reset flow."}), 400
    return render_template('forgot_password.html', title='Forgot Password')

@auth_bp.route("/reset-password", methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        return jsonify({"success": False, "message": "Please use the Firebase reset flow."}), 400
    return render_template('reset_password.html', title='Reset Password')


