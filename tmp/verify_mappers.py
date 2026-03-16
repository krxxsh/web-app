from backend.app import app, db
import sqlalchemy
from sqlalchemy.orm import configure_mappers

try:
    with app.app_context():
        configure_mappers()
        print("SQLAlchemy mappers configured successfully!")
except Exception as e:
    print(f"Error configuring mappers: {e}")
    exit(1)
