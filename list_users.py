from backend.app import create_app
from backend.extensions import db
from backend.models.models import User

app = create_app()
with app.app_context():
    users = User.query.all()
    for u in users:
        print(f"{u.email} - {u.username} - {u.role}")
