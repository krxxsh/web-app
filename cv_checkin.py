import cv2
from datetime import datetime
from backend.models.models import Appointment
from backend.extensions import db

def verify_pin_and_checkin(app, pin):
    """
    Verifies the entered 6-digit PIN against active appointments.
    """
    with app.app_context():
        now = datetime.now()
        # Find any booked appointment today with this PIN
        appt = Appointment.query.filter(
            Appointment.checkin_pin == pin,
            Appointment.status == 'booked'
        ).first()

        if appt and appt.start_time.date() == now.date():
            # Verify they are within a reasonable arrival window (60 mins)
            time_diff = abs((appt.start_time - now).total_seconds())
            if time_diff <= (60 * 60):
                appt.status = 'arrived'
                appt.check_in_time = now
                db.session.commit()
                return appt.customer.username or "Customer"
        
        return None

def start_camera_loop(app):
    # Load the pre-trained Haar cascade for face detection
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    video_capture = cv2.VideoCapture(0)
    print("🎥 Smart Kiosk Started. Looking for faces...")

    while True:
        ret, frame = video_capture.read()
        if not ret:
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
            # In a real kiosk, this would be a touchscreen or physical keypad
            pin_input = ""
            key = cv2.waitKey(1) & 0xFF
            if key in range(ord('0'), ord('9') + 1):
                # Start PIN buffer simulation
                print("⌨️ PIN Entry started...")
                pin_input = chr(key)
                for _ in range(5):
                    k = cv2.waitKey(2000) & 0xFF # Wait for each digit
                    if k in range(ord('0'), ord('9') + 1):
                        pin_input += chr(k)
                        print(f"Captured: {'*' * len(pin_input)}")
                
                if len(pin_input) == 6:
                    name_arrived = verify_pin_and_checkin(app, pin_input)
                    if name_arrived:
                        print(f"✅ PIN Verified. Welcome {name_arrived}")
                        # ... success feedback ...
                        return
                    else:
                        print("❌ Invalid PIN")

        # Show the video feed
        cv2.imshow('AI Sched - Kiosk Camera', frame)


        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    from backend.app import create_app
    app = create_app()
    start_camera_loop(app)
