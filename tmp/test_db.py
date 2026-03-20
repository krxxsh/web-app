import os
from sqlalchemy import create_engine, text

db_url = "postgresql://neondb_owner:npg_PLsQ2ceJ3piu@ep-super-shadow-a5pab3o3-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
print(f"Testing connection to: {db_url}")

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Basic Connection successful:", result.scalar())
        
        # Check if users table exists
        tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
        print("Existing tables:", [t[0] for t in tables])
except Exception as e:
    print("Database error:", str(e))
