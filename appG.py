import streamlit as st
import cv2
import face_recognition
import numpy as np
import os
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import time

# Database for storing registered users
DATA_DIR = "registered_faces"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Attendance DataFrame
attendance_file = "attendance.xlsx"
if not os.path.exists(attendance_file):
    df = pd.DataFrame(columns=["ID", "Name", "Role", "Email", "Face ID In Time", "Face ID Out Time", "Date"])
    df.to_excel(attendance_file, index=False)

# Load registered faces
known_face_encodings = []
known_face_names = []

def load_registered_faces():
    global known_face_encodings, known_face_names
    known_face_encodings = []
    known_face_names = []
    
    for file in os.listdir(DATA_DIR):
        if file.endswith(".jpg") or file.endswith(".png"):
            image_path = os.path.join(DATA_DIR, file)
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)[0]  
            known_face_encodings.append(encoding)
            known_face_names.append(file.split(".")[0])  

load_registered_faces()

# Function to send email
def send_email(email, name):
    sender_email = "your_email@gmail.com"  # Change this
    sender_password = "your_password"  # Change this (Use App Passwords for Gmail)
    
    msg = EmailMessage()
    msg["Subject"] = "Face Registration Successful"
    msg["From"] = sender_email
    msg["To"] = email
    msg.set_content(f"Hello {name},\n\nYour face has been successfully registered in our system.\n\nBest Regards,\nSecurity Team")
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        st.success(f"Email sent to {email}")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# Streamlit UI
st.title("🔍 Face Identification System")
st.sidebar.header("Options")

# Webcam Capture
video_capture = cv2.VideoCapture(0)

frame_placeholder = st.empty()

while True:
    ret, frame = video_capture.read()
    if not ret:
        st.error("Camera Not Detected!")
        break

    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)  
    rgb_small_frame = small_frame[:, :, ::-1]  

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    recognized = False
    name = "Unknown"

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.5)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        
        best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else None
        
        if best_match_index is not None and matches[best_match_index]:
            name = known_face_names[best_match_index]
            recognized = True
            st.success(f"✅ Welcome {name}")
        else:
            recognized = False
            st.warning("⚠️ Unrecognized Face! Please Register.")

    # Display frame
    frame_placeholder.image(frame, channels="BGR")

    if not recognized:
        new_name = st.text_input("Enter Name:")
        new_role = st.text_input("Enter Role:")
        new_email = st.text_input("Enter Email (Optional):")
        register_btn = st.button("Register")

        if register_btn and new_name and new_role:
            id_number = len(known_face_names) + 1
            face_image_path = os.path.join(DATA_DIR, f"{new_name}.jpg")
            cv2.imwrite(face_image_path, frame)
            load_registered_faces()
            st.success(f"🎉 {new_name} Registered Successfully!")
            
            if new_email:
                send_email(new_email, new_name)

            # Save to attendance
            df = pd.read_excel(attendance_file)
            new_entry = pd.DataFrame({
                "ID": [id_number],
                "Name": [new_name],
                "Role": [new_role],
                "Email": [new_email],
                "Face ID In Time": [datetime.now().strftime("%H:%M:%S")],
                "Face ID Out Time": [""],
                "Date": [datetime.today().strftime("%Y-%m-%d")]
            })
            df = pd.concat([df, new_entry], ignore_index=True)
            df.to_excel(attendance_file, index=False)

    # Mark Out Time
    if recognized:
        if st.button("Mark Exit Time"):
            df = pd.read_excel(attendance_file)
            df.loc[df["Name"] == name, "Face ID Out Time"] = datetime.now().strftime("%H:%M:%S")
            df.to_excel(attendance_file, index=False)
            st.success(f"⏳ Exit Time Marked for {name}")

    # Exit
    if st.button("Exit"):
        break

# Allow downloading attendance
st.sidebar.subheader("📥 Download Attendance Sheet")
with open(attendance_file, "rb") as f:
    st.sidebar.download_button("Download Excel", f, file_name="attendance.xlsx")

# Release Camera
video_capture.release()
cv2.destroyAllWindows()
