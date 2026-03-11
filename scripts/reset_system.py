import os
import sqlite3
import firebase_admin
from firebase_admin import auth, credentials

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'app.db')
SA_PATH = os.path.join(BASE_DIR, 'serviceAccountKey.json')

def reset_local_db():
    if os.path.exists(DB_PATH):
        print(f"Deleting local database at {DB_PATH}...")
        try:
            os.remove(DB_PATH)
            print("Successfully deleted local database.")
        except Exception as e:
            print(f"Error deleting database: {e}")
    else:
        print("No local database found to delete.")

def clear_firebase_users():
    if not os.path.exists(SA_PATH):
        print("Skipping Firebase User cleanup: serviceAccountKey.json not found in root.")
        return

    print("Initializing Firebase for user cleanup...")
    try:
        cred = credentials.Certificate(SA_PATH)
        firebase_admin.initialize_app(cred)
        
        # Batch delete all users from Firebase auth
        users = auth.list_users().iterate_all()
        user_uids = [user.uid for user in users]
        
        if user_uids:
            print(f"Deleting {len(user_uids)} users from Firebase...")
            auth.delete_users(user_uids)
            print("Successfully cleared all Firebase users.")
        else:
            print("No users found in Firebase to delete.")
            
    except Exception as e:
        print(f"Error during Firebase cleanup: {e}")

if __name__ == "__main__":
    print("--- SYSTEM RESET INITIATED ---")
    reset_local_db()
    # Optional: Uncomment below if you want to wipe Firebase users too during reset
    # clear_firebase_users() 
    print("--- RESET COMPLETE ---")
