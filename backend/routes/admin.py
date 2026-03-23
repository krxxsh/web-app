from flask import Blueprint, render_template, redirect, url_for, flash, request
from backend.config import Config
from flask_login import current_user, login_required
from backend.extensions import db, limiter
from backend.models.models import Business, Service, Staff, Appointment, Resource, BusinessCategory, User, AdminActivityLog
from backend.services.geocoding import geocode_address
from backend.services.logging_service import log_admin_action

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/dashboard")
@admin_bp.route("/dashboard/<int:business_id>")
@login_required
def dashboard(business_id=None):
    if current_user.role not in ['admin', 'business_owner']:
        flash('Access denied. Business owner role required.', 'danger')
        return redirect(url_for('main.home'))

    if business_id:
        business = Business.query.get_or_404(business_id)
        if business.owner_id != current_user.id and current_user.role != 'admin':
            return "Unauthorized", 403
    else:
        business = Business.query.filter_by(owner_id=current_user.id, is_main_branch=True).first()
        if not business:
            # Fallback to any business they own if no main branch marked
            business = Business.query.filter_by(owner_id=current_user.id).first()

    if not business:
        return redirect(url_for('admin.setup_business'))

    # Get all branches including main
    all_branches = Business.query.filter((Business.owner_id == current_user.id) | (Business.parent_business_id == business.id)).all()

    # Filter appointments by the SELECTED business only for the interactive view, 
    # but maybe show stats for ALL in the overview? Let's stick to selected for now.
    appointments = Appointment.query.filter_by(business_id=business.id).all()

    return render_template('admin/dashboard.html', business=business, branches=all_branches, appointments=appointments)

@admin_bp.route("/setup_business", methods=['GET', 'POST'])
@login_required
def setup_business():
    if request.method == 'POST':
        name = request.form.get('name')
        category_name = request.form.get('category')
        address = request.form.get('address')
        phone = request.form.get('phone')
        website = request.form.get('website')
        parent_id = request.form.get('parent_business_id') # For multi-branch

        cat_obj = BusinessCategory.query.filter_by(name=category_name).first()
        lat, lng = geocode_address(address)

        # If user is already verified by platform owner, auto-activate their new business profile
        status = 'active' if current_user.is_verified else 'pending'

        business = Business(
            name=name, 
            owner_id=current_user.id,
            category=category_name, # cached name
            category_id=cat_obj.id if cat_obj else None,
            address=address,
            phone=phone,
            website=website,
            latitude=lat,
            longitude=lng,
            status=status,
            parent_business_id=parent_id,
            is_main_branch=not bool(parent_id)
        )
        db.session.add(business)
        db.session.commit()
        flash('Business profile created!', 'success')
        return redirect(url_for('admin.dashboard'))

    categories = BusinessCategory.query.all()
    return render_template('admin/setup.html', categories=categories)

@admin_bp.route("/map")
@login_required
def map_overview():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.home'))
    businesses = Business.query.all()
    categories = BusinessCategory.query.all()
    return render_template('admin/map.html', businesses=businesses, categories=categories)

@admin_bp.route("/categories", methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        icon = request.form.get('icon', '🏢')
        is_health = 'is_health_related' in request.form

        if not BusinessCategory.query.filter_by(name=name).first():
            new_cat = BusinessCategory(name=name, icon=icon, is_health_related=is_health)
            db.session.add(new_cat)
            db.session.commit()
            flash('Category added!', 'success')
        else:
            flash('Category already exists.', 'warning')

    categories = BusinessCategory.query.all()
    return render_template('admin/categories.html', categories=categories)

@admin_bp.route("/service/add", methods=['GET', 'POST'])
@login_required
def add_service():
    business_id = request.args.get('business_id', type=int)
    if business_id:
        business = Business.query.get_or_404(business_id)
        if business.owner_id != current_user.id and current_user.role != 'admin':
            return "Unauthorized", 403
    else:
        business = Business.query.filter_by(owner_id=current_user.id).first()
    
    if not business:
        flash('Please setup a business first.', 'warning')
        return redirect(url_for('admin.setup_business'))

    if request.method == 'POST':
        name = request.form.get('name')
        try:
            duration = int(request.form.get('duration'))
            price = float(request.form.get('price'))
        except (TypeError, ValueError):
            flash('Invalid duration or price value.', 'danger')
            return redirect(url_for('admin.add_service'))
        description = request.form.get('description')

        service = Service(name=name, duration=duration, price=price, 
                         description=description, business_id=business.id,
                         member_only='member_only' in request.form,
                         is_virtual='is_virtual' in request.form,
                         is_group_allowed='is_group_allowed' in request.form,
                         max_group_size=int(request.form.get('max_group_size', 1)),
                         prep_instructions=request.form.get('prep_instructions'))
        db.session.add(service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/add_service.html')

@admin_bp.route("/add_staff", methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def add_staff():
    if current_user.role not in ['business_owner', 'admin']:
        return "Unauthorized", 403
    name = request.form.get('name')
    business = Business.query.filter_by(owner_id=current_user.id).first()
    if not business:
        flash('Please set up a business first.', 'warning')
        return redirect(url_for('admin.setup_business'))

    # Log Action
    log_admin_action(current_user.id, "add_staff", business_id=business.id, details={"staff_name": name})

    # Create an auto-generated login for this staff member
    from backend.extensions import bcrypt
    from backend.models.models import User

    temp_email = f"{name.lower().replace(' ', '')}{business.id}@staff.local"
    temp_password = Config.DEFAULT_STAFF_PASSWORD

    hashed_pw = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    staff_user = User(username=name, email=temp_email, password=hashed_pw, role='staff')
    db.session.add(staff_user)
    db.session.commit()

    member = Staff(name=name, business_id=business.id, user_id=staff_user.id)
    db.session.add(member)
    db.session.commit()

    flash(f'Staff added successfully! Details sent securely.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/update_branding", methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def update_branding():
    if current_user.role not in ['business_owner', 'admin']:
        return "Unauthorized", 403

    business = Business.query.filter_by(owner_id=current_user.id).first()
    if not business:
        flash('Please set up a business first.', 'warning')
        return redirect(url_for('admin.setup_business'))
    primary_color = request.form.get('primary_color')
    logo_url = request.form.get('logo_url')

    # Log Action
    log_admin_action(current_user.id, "update_branding", business_id=business.id, details={
        "primary_color": primary_color,
        "logo_url": logo_url
    })

    business.primary_color = primary_color
    business.logo_url = logo_url
    db.session.commit()
    flash('Branding updated successfully! Your public page will now use these settings.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/resources", methods=['GET', 'POST'])
@login_required
def manage_resources():
    business = Business.query.filter_by(owner_id=current_user.id).first()
    if not business:
        flash('Please set up a business first.', 'warning')
        return redirect(url_for('admin.setup_business'))
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

@admin_bp.before_request
@login_required
def check_verification():
    # Allow access to waiting room, business setup, and platform dashboard (if platform owner or moderator)
    allowed_endpoints = [
        'admin.pending_verification', 
        'admin.setup_business',
        'admin.platform_dashboard', 
        'admin.approve_business', 
        'admin.reject_business', 
        'admin.manage_team', 
        'admin.invite_moderator'
    ]
    if request.endpoint in allowed_endpoints:
        return None

    if current_user.role == 'business_owner' and not current_user.is_verified:
        return redirect(url_for('admin.pending_verification'))

@admin_bp.route("/pending_verification")
@login_required
def pending_verification():
    if current_user.is_verified:
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/pending_verification.html')

@admin_bp.route("/platform/verify")
@login_required
def platform_dashboard():
    if not current_user.is_platform_owner and current_user.role != 'moderator':
        flash('Access denied. Level 0 or Moderator clearance required.', 'danger')
        return redirect(url_for('main.home'))

    pending_users = User.query.filter_by(role='business_owner', is_verified=False).all()

    active_businesses = Business.query.all()
    return render_template('admin/platform_owner.html', pending_users=pending_users, businesses=active_businesses)

@admin_bp.route("/platform/team")
@login_required
def manage_team():
    if not current_user.is_platform_owner:
        flash('Access denied. Platform Owner clearance required to manage team.', 'danger')
        return redirect(url_for('admin.platform_dashboard'))
    moderators = User.query.filter_by(role='moderator').all()
    return render_template('admin/manage_team.html', moderators=moderators)

@admin_bp.route("/platform/team/invite", methods=['POST'])
@login_required
def invite_moderator():
    if not current_user.is_platform_owner:
        flash("Unauthorized to invite moderators", "danger")
        return redirect(url_for('admin.manage_team'))

    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found. They must register an account first.", "warning")
        return redirect(url_for('admin.manage_team'))

    user.role = 'moderator'

    log = AdminActivityLog(user_id=current_user.id, action="promoted_moderator", details={"assigned_user_id": user.id, "email": email})
    db.session.add(log)
    db.session.commit()

    flash(f"{user.username} is now a Platform Moderator.", "success")
    return redirect(url_for('admin.manage_team'))

@admin_bp.route("/platform/approve/<int:user_id>", methods=['POST'])
@login_required
def approve_business(user_id):
    if not current_user.is_platform_owner and current_user.role != 'moderator':
        return "Unauthorized", 403

    user = User.query.get_or_404(user_id)
    user.is_verified = True

    # Activate ALL associated businesses
    businesses = Business.query.filter_by(owner_id=user.id).all()
    business_id = None
    for business in businesses:
        business.status = 'active'
        if not business_id:
            business_id = business.id

    # Log the action
    log = AdminActivityLog(
        user_id=current_user.id, 
        business_id=business_id,
        action="approved_business", 
        details={"approved_userId": user_id, "approved_by": current_user.email}
    )
    db.session.add(log)

    db.session.commit()
    flash(f'User {user.username} and their business have been verified by {current_user.username}!', 'success')
    return redirect(url_for('admin.platform_dashboard'))

@admin_bp.route("/platform/reject/<int:user_id>", methods=['POST'])
@login_required
def reject_business(user_id):
    if not current_user.is_platform_owner and current_user.role != 'moderator':
        return "Unauthorized", 403

    user = User.query.get_or_404(user_id)

    log = AdminActivityLog(
        user_id=current_user.id, 
        action="rejected_business", 
        details={"rejected_email": user.email, "rejected_by": current_user.email}
    )
    db.session.add(log)

    # Logic for rejection (e.g., delete or suspend)
    db.session.delete(user)
    db.session.commit()
    flash('Registration rejected and account removed.', 'warning')
    return redirect(url_for('admin.platform_dashboard'))
