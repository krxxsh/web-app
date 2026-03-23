from flask import Blueprint, render_template, jsonify, request
from flask_login import current_user
from sqlalchemy import or_
from backend.models.models import Business, BusinessCategory

explore_bp = Blueprint('explore', __name__)

@explore_bp.route("/explore")
def explore():
    categories = BusinessCategory.query.all()
    # Show active businesses + the current user's own businesses (any status)
    if current_user.is_authenticated:
        businesses = Business.query.filter(
            or_(Business.status == 'active', Business.owner_id == current_user.id)
        ).all()
    else:
        businesses = Business.query.filter_by(status='active').all()
    return render_template('explore.html', categories=categories, businesses=businesses)

@explore_bp.route("/fastest-near-me")
def fastest_search():
    categories = BusinessCategory.query.all()
    return render_template('fastest_search.html', categories=categories)

@explore_bp.route("/api/businesses")
def get_businesses():
    category_name = request.args.get('category')
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', 50, type=float) # Default 50km

    # Include user's own businesses alongside active ones
    if current_user.is_authenticated:
        query = Business.query.filter(
            or_(Business.status == 'active', Business.owner_id == current_user.id)
        )
    else:
        query = Business.query.filter_by(status='active')

    if category_name and category_name != 'All':
        # Support both category name and ID
        if category_name.isdigit():
            query = query.filter_by(category_id=int(category_name))
        else:
            query = query.filter_by(category=category_name)

    businesses = query.all()

    results = []
    for b in businesses:
        biz_data = b.to_dict()

        # Simple Euclidean distance for 'Nearby' search (basic MVP approach)
        if lat is not None and lng is not None and b.latitude is not None and b.longitude is not None:
            dist = ((b.latitude - lat)**2 + (b.longitude - lng)**2)**0.5 * 111 # Approx km
            if dist > radius:
                continue
            biz_data['distance'] = round(dist, 1)

        # Mock availability for V3 Marketplace UI testing
        # Actual logic will use the AI Engine service soon
        biz_data['has_slots_today'] = True 
        biz_data['next_available'] = "Today, 2:30 PM"

        results.append(biz_data)

    # Sort by distance if location provided
    if lat and lng:
        results.sort(key=lambda x: x.get('distance', 999))

    return jsonify(results)

@explore_bp.route("/api/categories")
def get_categories():
    categories = BusinessCategory.query.all()
    return jsonify([c.to_dict() for c in categories])
