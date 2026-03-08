
import sqlite3
import os

DB_PATH = 'database/app.db'

def fix_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Fix Staff Table
        cursor.execute("PRAGMA table_info(staff)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_active' not in columns:
            print("Adding 'is_active' to 'staff' table...")
            cursor.execute("ALTER TABLE staff ADD COLUMN is_active BOOLEAN DEFAULT 1")

        # Fix Appointment Table (Check common missed columns like checkin_pin)
        cursor.execute("PRAGMA table_info(appointment)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'checkin_pin' not in columns:
            print("Adding 'checkin_pin' to 'appointment' table...")
            cursor.execute("ALTER TABLE appointment ADD COLUMN checkin_pin VARCHAR(6)")

        # Fix Service Table (Check common missed columns)
        cursor.execute("PRAGMA table_info(service)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_active' not in columns:
            print("Adding 'is_active' to 'service' table...")
            cursor.execute("ALTER TABLE service ADD COLUMN is_active BOOLEAN DEFAULT 1")
            
        conn.commit()
        print("Database schema synchronization complete.")
    except Exception as e:
        print(f"Error fixing database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_db()
