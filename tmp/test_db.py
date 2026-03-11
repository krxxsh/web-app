import os
import socket
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv('DATABASE_URL')

def test_connection():
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment.")
        return

    url = urlparse(db_url)
    hostname = url.hostname
    port = url.port or 5432

    print(f"--- DIAGNOSTICS ---")
    print(f"Target Host: {hostname}")
    print(f"Target Port: {port}")

    # 1. DNS Check
    print("\n[1/3] Testing DNS Resolution...")
    try:
        ip_list = socket.getaddrinfo(hostname, port)
        for ip in ip_list:
            print(f"  Found address: {ip[4][0]}")
    except Exception as e:
        print(f"  DNS FAILED: {e}")

    # 2. Port Check
    print("\n[2/3] Testing Port Accessibility...")
    try:
        s = socket.create_connection((hostname, port), timeout=5)
        print(f"  Port {port} is OPEN.")
        s.close()
    except Exception as e:
        print(f"  PORT FAILED: {e}")

    # 3. Psycopg2 Check
    print("\n[3/3] Testing Driver Connection...")
    try:
        conn = psycopg2.connect(db_url)
        print("  CONNECTION SUCCESSFUL!")
        conn.close()
    except Exception as e:
        print(f"  DRIVER FAILED: {e}")

if __name__ == "__main__":
    test_connection()
