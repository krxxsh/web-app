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
    query = Business.query.filter_by(status='active')
    if category_name and category_name != 'All':
        query = query.filter_by(category=category_name)
    
    businesses = query.all()
    return jsonify([b.to_dict() for b in businesses])

@explore_bp.route("/api/categories")
def get_categories():
    categories = BusinessCategory.query.all()
    return jsonify([c.to_dict() for c in categories])
