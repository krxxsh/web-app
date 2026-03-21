from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
from flask_login import login_required, current_user
from backend.extensions import db
from backend.models.models import Business, Appointment, Service
from sqlalchemy.orm import joinedload
from backend.services.scheduling_service import get_rebook_suggestion
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
@main_bp.route("/home")
def home():
    businesses = Business.query.filter_by(status='active').all()
    return render_template('home.html', businesses=businesses)

@main_bp.route("/select-role", methods=['GET', 'POST'])
@login_required
def select_role():
    if request.method == 'POST':
        data = request.get_json() or {}
        role = data.get('role')
        phone = data.get('phone')
        business_name = (data.get('business_name') or '').strip()

        # --- Validate first, mutate nothing yet ---
        if role not in ['customer', 'business_owner']:
            return jsonify({"success": False, "message": "Invalid role"}), 400

        if role == 'business_owner' and not business_name:
            return jsonify({"success": False, "message": "Business name is required"}), 400

        # --- All valid: apply changes ---
        current_user.role = role
        if phone:
            current_user.phone_number = phone

        if role == 'business_owner':
            from backend.models.models import BusinessCategory
            default_category = BusinessCategory.query.first()
            business = Business(
                name=business_name,
                owner_id=current_user.id,
                status='pending',
                category_id=default_category.id if default_category else None,
            )
            db.session.add(business)

        db.session.commit()

        return jsonify({
            "success": True,
            "redirect": "/admin/dashboard" if role == 'business_owner' else "/",
        })

    if current_user.role != 'pending':
        return redirect(url_for('main.home'))
    return render_template('select_role.html')


@main_bp.route("/business/<int:business_id>")
def business_page(business_id):
    from backend.config import Config
    business = Business.query.get_or_404(business_id)
    today_str = datetime.now().strftime('%Y-%m-%d')
    return render_template('business_public.html', 
                          business=business, 
                          today_str=today_str, 
                          razorpay_key_id=Config.RAZORPAY_KEY_ID)

@main_bp.route("/account")
@login_required
def my_account():
    # Fetch user appointments
    upcoming = Appointment.query.options(joinedload(Appointment.business), joinedload(Appointment.service)).filter(
        Appointment.customer_id == current_user.id,
        Appointment.start_time >= datetime.now(),
        Appointment.status != 'cancelled'
    ).order_by(Appointment.start_time).all()

    past = Appointment.query.options(joinedload(Appointment.business), joinedload(Appointment.service)).filter(
        Appointment.customer_id == current_user.id,
        Appointment.start_time < datetime.now()
    ).order_by(Appointment.start_time.desc()).limit(5).all()

    suggestion = get_rebook_suggestion(current_user.id)

    return render_template("my_account.html", 
                           upcoming=upcoming, 
                           past=past, 
                           suggestion=suggestion)

@main_bp.route("/rebook/<int:service_id>", methods=['POST'])
@login_required
def rebook(service_id):
    service = Service.query.get_or_404(service_id)
    # Redirect to business page with service selected
    flash(f"Rebooking {service.name}. Please select a new time slot.", "info")
    return redirect(url_for('main.business_page', business_id=service.business_id, service_id=service.id))

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
    
    if appt.status not in ['booked', 'arrived']:
        flash("This appointment is not active.", "warning")
        return redirect(url_for('main.my_account'))

    pos = calculate_queue_pos(appt)
    return render_template('customer_queue.html', appointment=appt, pos=pos)

@main_bp.route("/waiting-room/data/<int:appt_id>")
@login_required
def waiting_room_data(appt_id):
    appt = Appointment.query.get_or_404(appt_id)
    if appt.customer_id != current_user.id:
        return jsonify({"success": False}), 403
        
    if appt.status not in ['booked', 'arrived']:
        return jsonify({"success": False, "message": "Appointment not active"}), 400

    pos = calculate_queue_pos(appt)
    return jsonify({
        "success": True,
        "pos": pos,
        "status": appt.status
    })
@main_bp.route("/about")
def about():
    return render_template('about.html')

@main_bp.route("/services")
def services():
    return render_template('services.html')

@main_bp.route("/support")
def support():
    return render_template('support.html')

@main_bp.route("/chaos")
@login_required
def chaos():
    if current_user.role != 'admin':
        return "Unauthorized", 403
    return render_template('chaos_dashboard.html')
