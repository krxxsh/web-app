from flask import Blueprint, render_template, jsonify, request
from backend.models.models import Business, BusinessCategory

explore_bp = Blueprint('explore', __name__)

@explore_bp.route("/explore")
def explore():
    categories = BusinessCategory.query.all()
    # Default to all businesses
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
        if lat and lng and b.latitude and b.longitude:
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
