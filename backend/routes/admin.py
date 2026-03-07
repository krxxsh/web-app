from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_required, current_user
from backend.extensions import db
from backend.models.models import Business, Service, Staff, Appointment, Resource

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('Access denied. Admin role required.', 'danger')
        return redirect(url_for('main.home'))
    
    business = Business.query.filter_by(owner_id=current_user.id).first()
    if not business:
        return redirect(url_for('admin.setup_business'))
    
    appointments = Appointment.query.filter_by(business_id=business.id).all()
    return render_template('admin/dashboard.html', business=business, appointments=appointments)

@admin_bp.route("/setup_business", methods=['GET', 'POST'])
@login_required
def setup_business():
    if request.method == 'POST':
        name = request.form.get('name')
        business = Business(name=name, owner_id=current_user.id)
        db.session.add(business)
        db.session.commit()
        flash('Business profile created!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/setup.html')

@admin_bp.route("/service/add", methods=['GET', 'POST'])
@login_required
def add_service():
    business = Business.query.filter_by(owner_id=current_user.id).first()
    if request.method == 'POST':
        name = request.form.get('name')
        duration = int(request.form.get('duration'))
        price = float(request.form.get('price'))
        description = request.form.get('description')
        
        service = Service(name=name, duration=duration, price=price, 
                         description=description, business_id=business.id,
                         member_only='member_only' in request.form,
                         is_virtual='is_virtual' in request.form)
        db.session.add(service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/add_service.html')

@admin_bp.route("/add_staff", methods=['POST'])
@login_required
def add_staff():
    if current_user.role not in ['business', 'admin']:
        return "Unauthorized", 403
    name = request.form.get('name')
    business = current_user.businesses[0]
    
    # Create an auto-generated login for this staff member
    from backend.extensions import bcrypt
    from backend.models.models import User
    
    temp_email = f"{name.lower().replace(' ', '')}{business.id}@staff.local"
    temp_password = "staffpassword"
    
    hashed_pw = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    staff_user = User(username=name, email=temp_email, password=hashed_pw, role='staff')
    db.session.add(staff_user)
    db.session.commit()
    
    member = Staff(name=name, business_id=business.id, user_id=staff_user.id)
    db.session.add(member)
    db.session.commit()
    
    flash(f'Staff added! Login: {temp_email} / {temp_password}', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/update_branding", methods=['POST'])
@login_required
def update_branding():
    if current_user.role not in ['business', 'admin']:
        return "Unauthorized", 403
        
    business = current_user.businesses[0]
    business.primary_color = request.form.get('primary_color')
    business.logo_url = request.form.get('logo_url')
    db.session.commit()
    flash('Branding updated successfully! Your public page will now use these settings.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/resources", methods=['GET', 'POST'])
@login_required
def manage_resources():
    business = Business.query.filter_by(owner_id=current_user.id).first()
    if request.method == 'POST':
        name = request.form.get('name')
        r_type = request.form.get('type')
        qty = request.form.get('quantity', type=int)
        
        res = Resource(name=name, resource_type=r_type, quantity=qty, business_id=business.id)
        db.session.add(res)
        db.session.commit()
        flash('Resource added!', 'success')
        return redirect(url_for('admin.manage_resources'))
        
    resources = Resource.query.filter_by(business_id=business.id).all()
    return render_template("admin/resources.html", business=business, resources=resources)
    return redirect(url_for('admin.dashboard'))
