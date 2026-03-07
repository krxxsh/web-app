from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from backend.models.models import Business, Appointment
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
@main_bp.route("/home")
def home():
    businesses = Business.query.all()
    return render_template('home.html', businesses=businesses)

@main_bp.route("/business/<int:business_id>")
def business_page(business_id):
    business = Business.query.get_or_404(business_id)
    return render_template('business_public.html', business=business)

@main_bp.route("/account")
@login_required
def my_account():
    return render_template("my_account.html")

def calculate_queue_pos(appt):
    # Find all 'booked' or 'arrived' appointments today for this business that are BEFORE this appointment
    start_of_day = appt.start_time.replace(hour=0, minute=0, second=0)
    ahead = Appointment.query.filter(
        Appointment.business_id == appt.business_id,
        Appointment.status.in_(['booked', 'arrived']),
        Appointment.start_time >= start_of_day,
        Appointment.start_time < appt.start_time
    ).count()
    return ahead

@main_bp.route("/waiting-room/<int:appt_id>")
@login_required
def waiting_room(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return "Unauthorized", 403
    
    pos = calculate_queue_pos(appt)
    return render_template('waiting_room.html', appointment=appt, pos=pos)

@main_bp.route("/waiting-room/data/<int:appt_id>")
@login_required
def waiting_room_data(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"success": False}), 403
        
    pos = calculate_queue_pos(appt)
    return jsonify({
        "success": True,
        "pos": pos,
        "status": appt.status
    })
