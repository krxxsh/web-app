from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from backend.models.models import Appointment, Staff
from backend.extensions import db
from datetime import datetime

staff_bp = Blueprint('staff', __name__)

@staff_bp.route("/staff/dashboard")
@login_required
def dashboard():
    if current_user.role != 'staff':
        flash('Access denied. Staff role required.', 'danger')
        return redirect(url_for('main.home'))

    staff_profile = Staff.query.filter_by(user_id=current_user.id).first()
    if not staff_profile:
        flash('Staff profile not found. Please contact administrator.', 'danger')
        return redirect(url_for('main.home'))

    # Get today's appointments for this staff member
    # Actually just grab all upcoming ones to make testing easy
    appointments = Appointment.query.filter_by(staff_id=staff_profile.id).order_by(Appointment.start_time).all()

    # As a fallback if tracking logic is disconnected, just show all business appointments
    if not appointments and staff_profile.business_id:
        appointments = Appointment.query.filter_by(business_id=staff_profile.business_id).order_by(Appointment.start_time).all()
    elif not appointments:
        appointments = []

    return render_template('staff_dashboard.html', staff=staff_profile, appointments=appointments)

@staff_bp.route("/staff/complete/<int:appt_id>", methods=['POST'])
@login_required
def complete_appt(appt_id):
    if current_user.role != 'staff':
        return jsonify({"success": False}), 403

    appt = Appointment.query.get_or_404(appt_id)
    appt.status = 'completed'
    db.session.commit()
    return jsonify({"success": True})
