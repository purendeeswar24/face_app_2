import streamlit as st
import cv2
import face_recognition
import numpy as np
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Initialize the database
if not os.path.exists('face_data.csv'):
    df = pd.DataFrame(columns=["Name", "Role", "ID Number", "Face ID", "In Time", "Out Time", "Date", "Email"])
    df.to_csv('face_data.csv', index=False)

# Load known faces
def load_known_faces():
    if os.path.exists('face_data.csv'):
        df = pd.read_csv('face_data.csv')
        known_face_encodings = []
        known_face_names = []
        for index, row in df.iterrows():
            face_id = row['Face ID']
            if os.path.exists(f'faces/{face_id}.npy'):
                encoding = np.load(f'faces/{face_id}.npy')
                known_face_encodings.append(encoding)
                known_face_names.append(row['Name'])
        return known_face_encodings, known_face_names
    return [], []

# Save new face
def save_new_face(name, role, id_number, email, face_encoding):
    face_id = f"{name}_{id_number}"
    np.save(f'faces/{face_id}.npy', face_encoding)
    df = pd.read_csv('face_data.csv')
    df = df.append({
        "Name": name,
        "Role": role,
        "ID Number": id_number,
        "Face ID": face_id,
        "In Time": "",
        "Out Time": "",
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Email": email
    }, ignore_index=True)
    df.to_csv('face_data.csv', index=False)
    if email:
        send_email(email, name)

# Send email
def send_email(email, name):
    sender_email = "your_email@example.com"
    sender_password = "your_password"
    receiver_email = email

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Registration Confirmation"

    body = f"Hello {name},\n\nYou have been successfully registered in our face recognition system."
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())

# Face recognition
def recognize_faces(frame, known_face_encodings, known_face_names):
    rgb_frame = frame[:, :, ::-1]
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"

        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            name = known_face_names[best_match_index]
            update_attendance(name)

        cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
        cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame

# Update attendance
def update_attendance(name):
    df = pd.read_csv('face_data.csv')
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%Y-%m-%d")

    if name in df['Name'].values:
        if df.loc[df['Name'] == name, 'In Time'].values[0] == "":
            df.loc[df['Name'] == name, 'In Time'] = current_time
        else:
            df.loc[df['Name'] == name, 'Out Time'] = current_time
        df.loc[df['Name'] == name, 'Date'] = current_date
    df.to_csv('face_data.csv', index=False)

# Streamlit app
st.title("Face Identification System")

# Load known faces
known_face_encodings, known_face_names = load_known_faces()

# Video capture
video_capture = cv2.VideoCapture(0)

# Streamlit sidebar for registration
st.sidebar.title("Registration")
name = st.sidebar.text_input("Name")
role = st.sidebar.text_input("Role")
id_number = st.sidebar.text_input("ID Number")
email = st.sidebar.text_input("Email (Optional)")
timings = st.sidebar.text_input("Timings (Optional)")

if st.sidebar.button("Register"):
    if name and role and id_number:
        ret, frame = video_capture.read()
        rgb_frame = frame[:, :, ::-1]
        face_locations = face_recognition.face_locations(rgb_frame)
        if face_locations:
            face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
            save_new_face(name, role, id_number, email, face_encoding)
            st.sidebar.success("Registration Successful!")
        else:
            st.sidebar.error("No face detected. Please try again.")
    else:
        st.sidebar.error("Please fill all mandatory fields.")

# Live face recognition
stframe = st.empty()
while True:
    ret, frame = video_capture.read()
    if not ret:
        st.error("Failed to capture video.")
        break

    frame = recognize_faces(frame, known_face_encodings, known_face_names)
    stframe.image(frame, channels="BGR")

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()

# Download Excel sheet
if st.button("Download Attendance Sheet"):
    df = pd.read_csv('face_data.csv')
    df.to_excel('attendance.xlsx', index=False)
    with open('attendance.xlsx', 'rb') as f:
        st.download_button('Download Excel', f, file_name='attendance.xlsx')
        