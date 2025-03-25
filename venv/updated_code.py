# Install required packages if not already installed
import subprocess
import sys

# List of required packages
required_packages = [
    "opencv-python",
    "streamlit",
    "numpy",
    "pandas",
    "pytz",
    "insightface",
    "openpyxl",
    "onnxruntime"
]

# Install missing packages
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", package])

# Import other required libraries
import cv2
import streamlit as st
import numpy as np
import pandas as pd
import os
import datetime
import pytz  # For Indian Standard Time (IST)
import pickle
import hashlib
from insightface.app import FaceAnalysis
from openpyxl import Workbook, load_workbook


# Paths for storing data
IMAGE_PATH = "registered_faces/"
ATTENDANCE_FILE = "attendance.xlsx"
ENCODINGS_FILE = "face_encodings.pkl"
USERS_FILE = "users.pkl"

# Create folders if they don't exist
os.makedirs(IMAGE_PATH, exist_ok=True)

# Set Indian Standard Time (IST)
IST = pytz.timezone("Asia/Kolkata")

# Initialize the face recognition model
face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
face_app.prepare(ctx_id=0, det_size=(1280, 1280))  # High resolution for better accuracy

# Load user data and face encodings if they exist
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "rb") as f:
        users = pickle.load(f)
else:
    users = {}

if os.path.exists(ENCODINGS_FILE):
    with open(ENCODINGS_FILE, "rb") as f:
        known_face_encodings = pickle.load(f)
else:
    known_face_encodings = {}

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to preprocess images for better face detection
def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # Convert to grayscale
    equalized = cv2.equalizeHist(gray)  # Improve contrast
    return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)  # Convert back to 3 channels

# Function to register an admin
def register_admin(name, password):
    if name in users:
        return "❌ User already registered!"

    users[name] = {
        "password": hash_password(password),
        "is_admin": True
    }

    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)

    return f"✅ Admin {name} registered successfully!"

# Function to register a user
def register_user(name, face_image, per_day_salary):
    try:
        if name in users:
            return "❌ User already registered!"

        # Preprocess the image
        processed_image = preprocess_image(face_image)

        # Detect faces in the image
        faces = face_app.get(processed_image)
        if len(faces) == 0:
            return "❌ No face detected in the image!"

        # Get the face embedding (unique features)
        face_embedding = faces[0].embedding
        known_face_encodings[name] = face_embedding

        # Save the face encodings
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump(known_face_encodings, f)

        # Save user details
        users[name] = {"is_admin": False, "per_day_salary": float(per_day_salary)}

        with open(USERS_FILE, "wb") as f:
            pickle.dump(users, f)

        return f"✅ User {name} registered successfully with a per day salary of ₹{per_day_salary}!"
    except Exception as e:
        return f"❌ Error during registration: {str(e)}"

# Function to initialize the attendance file
def initialize_attendance_file():
    if not os.path.exists(ATTENDANCE_FILE):
        df = pd.DataFrame(columns=["Name", "Date", "Timestamp", "Time", "Status"])
        df.to_excel(ATTENDANCE_FILE, index=False)
    else:
        df = pd.read_excel(ATTENDANCE_FILE)
        required_columns = ["Name", "Date", "Timestamp", "Time", "Status"]
        if not all(column in df.columns for column in required_columns):
            for column in required_columns:
                if column not in df.columns:
                    df[column] = None
            df.to_excel(ATTENDANCE_FILE, index=False)

# Function to mark attendance
def mark_attendance(image):
    try:
        # Preprocess the image
        processed_image = preprocess_image(image)

        # Detect faces
        faces = face_app.get(processed_image)
        if len(faces) == 0:
            return "❌ No face detected!"

        # Get the face embedding
        face_embedding = faces[0].embedding
        match_found = False
        recognized_name = None

        # Compare with known face encodings
        for name, known_face_encoding in known_face_encodings.items():
            similarity = np.dot(face_embedding, known_face_encoding) / (np.linalg.norm(face_embedding) * np.linalg.norm(known_face_encoding))
            if similarity > 0.7:  # Threshold for matching
                match_found = True
                recognized_name = name
                break

        if not match_found:
            return "❌ No matching face found!"

        # Get current time in IST
        now = datetime.datetime.now(IST)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        date_only = now.strftime("%Y-%m-%d")
        time_only = now.strftime("%H:%M:%S")

        # Define office timings
        office_start = datetime.time(12, 55, 0)  # 12:55 PM
        full_present_end = datetime.time(13, 5, 0)  # 1:05 PM
        late_punch_end = datetime.time(17, 0, 0)  # 5:00 PM
        half_day_end = datetime.time(17, 15, 0)  # 5:15 PM

        current_time = now.time()

        # Determine attendance status
        if office_start <= current_time <= full_present_end:
            status = "Full Day"
        elif full_present_end < current_time <= late_punch_end:
            status = "Late"
        elif late_punch_end < current_time <= half_day_end:
            status = "Half Day"
        elif current_time > half_day_end:
            status = "Half Day"
        else:
            status = "Absent"

        # Initialize attendance file if needed
        initialize_attendance_file()

        # Load attendance data
        df = pd.read_excel(ATTENDANCE_FILE)

        # Check if the user already has an entry for the same date
        existing_entry = df[(df["Name"] == recognized_name) & (df["Date"] == date_only)]
        if not existing_entry.empty:
            return f"✅ Attendance already marked for {recognized_name} on {date_only}!"

        # Add new attendance record
        new_row = pd.DataFrame({
            "Name": [recognized_name],
            "Date": [date_only],
            "Timestamp": [timestamp],
            "Time": [time_only],
            "Status": [status]
        })

        df = pd.concat([df, new_row], ignore_index=True)
        df.to_excel(ATTENDANCE_FILE, index=False)

        return f"✅ Attendance marked for {recognized_name} on {date_only} ({status})"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Function to calculate user summary
def calculate_user_summary(name, month):
    try:
        if not os.path.exists(ATTENDANCE_FILE):
            return "❌ No attendance records found!"

        # Load attendance data
        df = pd.read_excel(ATTENDANCE_FILE)

        # Filter records for the specified user and month
        user_attendance = df[(df["Name"] == name) & (df["Date"].str.startswith(month))]

        if user_attendance.empty:
            return f"❌ No attendance records found for {name} in {month}!"

        # Calculate full days, half days, and salary
        full_days = 0
        half_days = 0

        for _, row in user_attendance.iterrows():
            time = datetime.datetime.strptime(row["Time"], "%H:%M:%S").time()
            if time <= datetime.time(14, 0, 0):  # Before 2:00 PM
                full_days += 1
            else:
                half_days += 1

        # Get user's per day salary
        per_day_salary = users[name]["per_day_salary"]

        # Calculate total salary
        total_salary = (full_days * per_day_salary) + (half_days * (per_day_salary / 2))

        # Prepare summary
        summary = {
            "Full Days": full_days,
            "Half Days": half_days,
            "Total Salary": total_salary
        }

        return summary
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Function to download monthly attendance
def download_monthly_attendance(month, admin_username, admin_password):
    try:
        if admin_username not in users or users[admin_username]["password"] != hash_password(admin_password):
            return "❌ Invalid admin username or password!", None

        if not os.path.exists(ATTENDANCE_FILE):
            return "❌ No attendance records found!", None

        # Initialize attendance file if needed
        initialize_attendance_file()

        # Load attendance data
        df = pd.read_excel(ATTENDANCE_FILE)

        # Filter records for the specified month
        monthly_attendance = df[df["Date"].str.startswith(month)]

        if monthly_attendance.empty:
            return f"❌ No attendance records found for {month}!", None

        # Create a new Excel workbook
        wb = Workbook()
        ws = wb.active

        # Add headers
        headers = ["Name", "Date", "Timestamp", "Time", "Status"]
        ws.append(headers)

        # Add data
        for _, row in monthly_attendance.iterrows():
            ws.append([row["Name"], row["Date"], row["Timestamp"], row["Time"], row["Status"]])

        # Add summary for each user
        ws.append([])
        ws.append(["User Summary"])
        ws.append(["Name", "Full Days", "Half Days", "Total Salary"])

        for name in monthly_attendance["Name"].unique():
            user_summary = calculate_user_summary(name, month)
            if isinstance(user_summary, dict):
                ws.append([
                    name,
                    user_summary["Full Days"],
                    user_summary["Half Days"],
                    f"₹{user_summary['Total Salary']:.2f}"
                ])

        # Save the workbook
        output_file = f"attendance_summary_{month}.xlsx"
        wb.save(output_file)

        return f"✅ Attendance file generated successfully for {month}!", output_file
    except Exception as e:
        return f"❌ Error: {str(e)}", None

# Function to display user details
def display_users():
    try:
        if not users:
            return "❌ No users registered yet!", ""

        user_details = []
        admin_count = 0
        user_count = 0

        for name, details in users.items():
            role = "Admin" if details.get("is_admin", False) else "User"
            salary = f"₹{details.get('per_day_salary', 0)}/day" if not details.get("is_admin", False) else "N/A"
            user_details.append(f"Name: {name}, Role: {role}, Salary: {salary}")
            if role == "Admin":
                admin_count += 1
            else:
                user_count += 1

        summary = f"Total Admins: {admin_count}\nTotal Users: {user_count}"
        user_details_str = "\n".join(user_details)
        return summary, user_details_str
    except Exception as e:
        return f"❌ Error: {str(e)}", ""

# Function to delete a user
def delete_user(username, admin_username, admin_password):
    try:
        if admin_username not in users or users[admin_username]["password"] != hash_password(admin_password):
            return "❌ Invalid admin username or password!"

        if username not in users:
            return f"❌ User {username} not found!"

        # Remove user from users and face encodings
        users.pop(username)
        if username in known_face_encodings:
            known_face_encodings.pop(username)

        # Save updated data
        with open(USERS_FILE, "wb") as f:
            pickle.dump(users, f)

        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump(known_face_encodings, f)

        return f"✅ User {username} deleted successfully!"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Streamlit App
st.title("📸 Office Face Attendance System")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Admin Registration", "User Registration", "Mark Attendance", "Download Attendance", "Manage Users"])

if page == "Admin Registration":
    st.header("Admin Registration")
    admin_name = st.text_input("Admin Name")
    admin_password = st.text_input("Admin Password", type="password")
    if st.button("Register Admin"):
        result = register_admin(admin_name, admin_password)
        st.success(result)

elif page == "User Registration":
    st.header("User Registration")
    name = st.text_input("Enter Your Name")
    face_image = st.camera_input("Upload Your Face Image")
    per_day_salary = st.number_input("Per Day Salary (₹)", min_value=0.0)
    if st.button("Register User"):
        if face_image is not None:
            face_image = cv2.imdecode(np.frombuffer(face_image.read(), np.uint8), cv2.IMREAD_COLOR)
            result = register_user(name, face_image, per_day_salary)
            st.success(result)
        else:
            st.error("Please upload a face image!")

elif page == "Mark Attendance":
    st.header("Mark Attendance")
    face_image = st.camera_input("Upload Your Face Image")
    if st.button("Mark Attendance"):
        if face_image is not None:
            face_image = cv2.imdecode(np.frombuffer(face_image.read(), np.uint8), cv2.IMREAD_COLOR)
            result = mark_attendance(face_image)
            st.success(result)
        else:
            st.error("Please upload a face image!")

elif page == "Download Attendance":
    st.header("Download Monthly Attendance")
    month = st.text_input("Enter Month (YYYY-MM)")
    admin_username = st.text_input("Admin Username")
    admin_password = st.text_input("Admin Password", type="password")
    if st.button("Download Attendance"):
        result, file = download_monthly_attendance(month, admin_username, admin_password)
        if file:
            st.success(result)
            with open(file, "rb") as f:
                st.download_button("Download File", f, file_name=file)
        else:
            st.error(result)

elif page == "Manage Users":
    st.header("Manage Users")
    st.subheader("User Details")
    summary, user_details = display_users()
    st.text(summary)
    st.text_area("User Details", user_details, height=200)

    st.subheader("Delete User")
    delete_username = st.text_input("Username to Delete")
    delete_admin_username = st.text_input("Admin Username")
    delete_admin_password = st.text_input("Admin Password", type="password")
    if st.button("Delete User"):
        result = delete_user(delete_username, delete_admin_username, delete_admin_password)
        st.success(result)