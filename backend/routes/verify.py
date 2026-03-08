from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from backend.extensions import db
from datetime import datetime

verify_bp = Blueprint('verify', __name__)

@verify_bp.route("/verify", methods=['GET', 'POST'])
@login_required
def verify_account():
    if current_user.is_verified:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        email_code = request.form.get('email_otp')
        phone_code = request.form.get('phone_otp')

        # In a real app, we'd verify each individually or together
        if email_code == current_user.email_otp and phone_code == current_user.phone_otp:
            current_user.is_verified = True
            current_user.email_verified_at = datetime.utcnow()
            current_user.phone_verified_at = datetime.utcnow()
            db.session.commit()
            flash('Your account has been verified! Welcome to AI Sched.', 'success')
            return redirect(url_for('main.home'))
        else:
            flash('Invalid OTP codes. Please try again.', 'danger')

    return render_template('verify.html')

@verify_bp.route("/resend_otp")
@login_required
def resend_otp():
    from backend.services.notifications import send_verification_otp
    send_verification_otp(current_user)
    flash('New verification codes have been sent!', 'info')
    return redirect(url_for('verify.verify_account'))
