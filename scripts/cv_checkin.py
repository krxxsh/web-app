import cv2
import logging
import sys
from datetime import datetime
from backend.models.models import Appointment
from backend.extensions import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('kiosk.log')
    ]
)
logger = logging.getLogger(__name__)

def verify_pin_and_checkin(app, pin):
    """
    Verifies the entered 6-digit PIN using the scheduling service.
    """
    from backend.services.scheduling_service import check_in_with_pin
    with app.app_context():
        success, message = check_in_with_pin(pin)
        if success:
            logger.info(f"✅ {message}")
            return "Customer" # Message contains details
        
        logger.warning(f"❌ {message}")
        return None

def start_camera_loop(app):
    # Load the pre-trained Haar cascade for face detection
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        logger.error(f"Failed to load cascade classifier from {cascade_path}")
        return

    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        logger.error("Could not open video capture device.")
        return

    logger.info("🎥 Smart Kiosk Started. Looking for faces...")
    
    try:
        while True:
            ret, frame = video_capture.read()
            if not ret:
                logger.warning("Failed to grab frame from camera.")
                break

            # Convert to grayscale for Haar detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(60, 60)
            )

            for (x, y, w, h) in faces:
                # Draw rectangle around face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # SECURITY HARDENING: Replace "Press C" with "Enter 6-Digit PIN"
                cv2.putText(frame, "ENTER 6-DIGIT PIN TO CHECK-IN", (x, y - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                # Simple simulation of numeric PIN entry via keyboard
                key = cv2.waitKey(1) & 0xFF
                if key in range(ord('0'), ord('9') + 1):
                    # Start PIN buffer simulation
                    logger.info("⌨️ PIN Entry started...")
                    pin_input = chr(key)
                    for _ in range(5):
                        k = cv2.waitKey(2000) & 0xFF # Wait up to 2s for each digit
                        if k in range(ord('0'), ord('9') + 1):
                            pin_input += chr(k)
                            print(f"Captured: {'*' * len(pin_input)}")
                        else:
                            break # Timeout or invalid key
                    
                    if len(pin_input) == 6:
                        name_arrived = verify_pin_and_checkin(app, pin_input)
                        if name_arrived:
                            logger.info(f"✅ PIN Verified. Welcome {name_arrived}")
                            # In a real app, we might display "Welcome" on frame for 3s
                            return
                        else:
                            logger.warning("❌ Invalid PIN entered.")

            # Show the video feed
            cv2.imshow('AI Sched - Kiosk Camera', frame)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.info("Quitting kiosk...")
                break

    except KeyboardInterrupt:
        logger.info("Kiosk interrupted by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in the kiosk loop: {e}")
    finally:
        video_capture.release()
        cv2.destroyAllWindows()
        logger.info("Kiosk resources released.")

if __name__ == '__main__':
    from backend.app import create_app
    app = create_app()
    start_camera_loop(app)
