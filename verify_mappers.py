import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.extensions import db
from sqlalchemy.orm import configure_mappers
import traceback

print("Initializing application...")
try:
    app = create_app()
    print("Application initialized.")
except Exception as e:
    print("Failed to initialize application.")
    traceback.print_exc()
    sys.exit(1)

print("Configuring mappers...")
with app.app_context():
    try:
        configure_mappers()
        print("Mappers configured successfully!")
    except Exception as e:
        print("\n!!! Mapper Configuration Error Caught !!!")
        traceback.print_exc()
        
        # Try to find which relationship failed if possible
        # configure_mappers usually raises the first error it finds
        sys.exit(1)

print("\nAll good.")
