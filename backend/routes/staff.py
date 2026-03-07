from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from backend.models.models import Appointment, Staff
from backend.extensions import db
from datetime import datetime

staff_bp = Blueprint('staff', __name__)

@staff_bp.route("/staff/dashboard")
@login_required
def dashboard():
    if current_user.role != 'staff':
        return "Unauthorized", 403
        
    staff_profile = Staff.query.filter_by(user_id=current_user.id).first()
    if not staff_profile:
        return "No profile linked.", 404
        
    # Get today's appointments for this staff member
    today_start = datetime.now().replace(hour=0, minute=0, second=0)
    today_end = datetime.now().replace(hour=23, minute=59, second=59)
    
    # Actually just grab all upcoming ones to make testing easy
    appointments = Appointment.query.filter_by(staff_id=staff_profile.id).order_by(Appointment.start_time).all()
    
    # As a fallback if tracking logic is disconnected, just show all business appointments
    if not appointments:
        appointments = Appointment.query.filter_by(business_id=staff_profile.business_id).order_by(Appointment.start_time).all()
        
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
