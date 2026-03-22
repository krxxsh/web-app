import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)

KIOSK_PROCESS = None

# Resolve the absolute path to cv_checkin.py relative to this file's location
CV_CHECKIN_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "cv_checkin.py")

def start_kiosk():
    global KIOSK_PROCESS
    if KIOSK_PROCESS is None or KIOSK_PROCESS.poll() is not None:
        try:
            # Start the CV Check-in script completely independently
            KIOSK_PROCESS = subprocess.Popen(
                [sys.executable, CV_CHECKIN_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start kiosk: {e}")
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
