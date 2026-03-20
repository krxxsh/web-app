import os
from dotenv import load_dotenv
import pathlib

env_path = pathlib.Path(__file__).parent / ".env"
print(f"Checking .env at: {env_path}")
print(f"Exists: {env_path.exists()}")

loaded = load_dotenv(env_path)
print(f"Load result: {loaded}")
print(f"FIREBASE_API_KEY: {os.environ.get('FIREBASE_API_KEY')}")
