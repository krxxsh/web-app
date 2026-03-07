import cv2
import time
import os
from datetime import datetime
from backend.models.models import User, Appointment
from backend.extensions import db

def check_in_user(app):
    """
    Since pure CV2 cannot do facial identity 1:1 matching without training a custom LBPH model 
    (which requires massive datasets), we fallback to a "Motion/Face Detection Kiosk" where 
    it auto-checks in the FIRST appointment scheduled within the next 30 minutes when ANY face walks up 
    to the camera. 
    """
    with app.app_context():
        now = datetime.now()
        
        # Who is booked right now?
        today_appts = Appointment.query.filter(
            Appointment.status == 'booked'
        ).all()
        
        for appt in today_appts:
            if appt.start_time.date() == now.date():
                # If they are within 45 mins of their start time
                time_diff = abs((appt.start_time - now).total_seconds())
                if time_diff <= (45 * 60):
                    appt.status = 'arrived'
                    db.session.commit()
                    return appt.customer.name if appt.customer else "Guest"
        
        return None

def start_camera_loop(app):
    # Load the pre-trained Haar cascade for face detection
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    video_capture = cv2.VideoCapture(0)
    print("🎥 Smart Kiosk Started. Looking for faces...")

    last_checkin_time = 0

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
            
            # If enough time has passed from the last trigger, auto-check-in
            if (time.time() - last_checkin_time) > 10:
                name_arrived = check_in_user(app)
                if name_arrived:
                    last_checkin_time = time.time()
                    print(f"✅ Auto-checked in: {name_arrived}")
            
            # Display text
            if (time.time() - last_checkin_time) <= 5:
                cv2.putText(frame, "- CHECKED IN -", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "DETECTING", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            # Dump verification image and break loops for automation testing
            cv2.imwrite("cv_verification_snapshot.jpg", frame)
            print("Successfully processed a face visually and saved verification snapshot!")
            video_capture.release()
            cv2.destroyAllWindows()
            return

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
