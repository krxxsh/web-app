import subprocess
import os

KIOSK_PROCESS = None

def start_kiosk():
    global KIOSK_PROCESS
    if KIOSK_PROCESS is None or KIOSK_PROCESS.poll() is not None:
        try:
            # Start the CV Check-in script completely independently
            KIOSK_PROCESS = subprocess.Popen(["python", "cv_checkin.py"])
            return True
        except Exception as e:
            print(f"Failed to start kiosk: {e}")
            return False
    return False

def stop_kiosk():
    global KIOSK_PROCESS
    if KIOSK_PROCESS and KIOSK_PROCESS.poll() is None:
        KIOSK_PROCESS.terminate()
        KIOSK_PROCESS = None
        return True
    return False

def is_kiosk_running():
    global KIOSK_PROCESS
    return KIOSK_PROCESS is not None and KIOSK_PROCESS.poll() is None
