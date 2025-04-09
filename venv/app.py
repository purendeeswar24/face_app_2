import cv2
import numpy as np
import pandas as pd
import os
import datetime
import pytz
import pickle
import hashlib
from insightface.app import FaceAnalysis
from openpyxl import Workbook
from dateutil.relativedelta import relativedelta
import streamlit as st
from streamlit.components.v1 import html

# ================= Configuration =================
IMAGE_PATH = "registered_faces/"
ATTENDANCE_FILE = "attendance.xlsx"
ENCODINGS_FILE = "face_encodings.pkl"
USERS_FILE = "users.pkl"
CONFIG_FILE = "config.pkl"
IST = pytz.timezone("Asia/Kolkata")
DEFAULT_MASTER_ADMIN_ID = "masteradmin"
DEFAULT_MASTER_ADMIN_PASSWORD = "Master@123"

# Initialize face recognition
face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
face_app.prepare(ctx_id=0, det_size=(1280, 1280))

# Create necessary directories
os.makedirs(IMAGE_PATH, exist_ok=True)

# Load or initialize user data and config
def load_data():
    global users, known_face_encodings, config
    users = {}
    known_face_encodings = {}
    config = {"max_master_admins": 3}

    try:
        with open(USERS_FILE, "rb") as f:
            users = pickle.load(f)
    except FileNotFoundError:
        users[DEFAULT_MASTER_ADMIN_ID] = {
            "password": hash_password(DEFAULT_MASTER_ADMIN_PASSWORD),
            "is_master_admin": True,
            "is_admin": False,
            "unique_id": DEFAULT_MASTER_ADMIN_ID
        }
        with open(USERS_FILE, "wb") as f:
            pickle.dump(users, f)

    try:
        with open(ENCODINGS_FILE, "rb") as f:
            known_face_encodings = pickle.load(f)
    except FileNotFoundError:
        pass

    try:
        with open(CONFIG_FILE, "rb") as f:
            config = pickle.load(f)
    except FileNotFoundError:
        with open(CONFIG_FILE, "wb") as f:
            pickle.dump(config, f)

load_data()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_auth(username, password, require_master=False, require_admin=False):
    if not username or not password:
        return False, "❌ Username or password cannot be empty!"
    if username not in users:
        return False, "❌ User not found!"
    if users[username]["password"] != hash_password(password):
        return False, "❌ Incorrect password!"
    if require_master and not users[username].get("is_master_admin", False):
        return False, "❌ Master Admin privileges required!"
    if require_admin and not (users[username].get("is_admin", False) or users[username].get("is_master_admin", False)):
        return False, "❌ Admin privileges required!"
    return True, "✅ Authentication successful!"

def is_unique_id(unique_id):
    return not any(user.get("unique_id") == unique_id for user in users.values())

def count_master_admins():
    return sum(1 for user in users.values() if user.get("is_master_admin", False))

def initialize_attendance_file():
    if not os.path.exists(ATTENDANCE_FILE):
        columns = ["Name", "Employee ID", "Designation", "Date", "In Time", "Out Time", "Status", "User Type"]
        pd.DataFrame(columns=columns).to_excel(ATTENDANCE_FILE, index=False)

def parse_office_time(office_time_str):
    try:
        return datetime.datetime.strptime(office_time_str, "%H:%M").time()
    except ValueError:
        return datetime.time(9, 0)

def calculate_working_hours(in_time, out_time):
    try:
        in_dt = datetime.datetime.strptime(in_time, "%H:%M:%S")
        out_dt = datetime.datetime.strptime(out_time, "%H:%M:%S")
        if out_dt < in_dt:
            out_dt += datetime.timedelta(days=1)
        delta = out_dt - in_dt
        return delta.total_seconds() / 3600
    except:
        return 0

# Session state for logged-in admin
if 'logged_in_admin' not in st.session_state:
    st.session_state.logged_in_admin = None
if 'current_section' not in st.session_state:
    st.session_state.current_section = "Mark Attendance"

# Custom CSS and HTML
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

    /* Global Styling */
    body {
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #e0eafc, #cfdef3);
        margin: 0;
        padding: 0;
    }

    /* Sidebar Styling */
    .sidebar {
        height: 100%;
        width: 250px;
        position: fixed;
        top: 0;
        left: -250px;
        background: linear-gradient(135deg, #1e3c72, #2a5298);
        padding-top: 20px;
        transition: 0.5s;
        box-shadow: 2px 0 5px rgba(0, 0, 0, 0.2);
        z-index: 1000;
    }
    .sidebar.active {
        left: 0;
    }
    .sidebar .nav-item {
        padding: 15px 20px;
        color: white;
        text-decoration: none;
        display: block;
        transition: 0.3s;
    }
    .sidebar .nav-item:hover {
        background: #ffcc00;
        color: #1e3c72;
        transform: translateX(10px);
    }
    .toggle-btn {
        font-size: 30px;
        cursor: pointer;
        color: white;
        position: absolute;
        top: 10px;
        left: 10px;
        z-index: 1001;
    }

    /* Main Content */
    .content {
        margin-left: 0;
        padding: 20px;
        transition: margin-left 0.5s;
    }
    .sidebar.active ~ .content {
        margin-left: 250px;
    }

    /* Grid Layout */
    .grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
        padding: 20px;
    }

    /* Card Styling */
    .card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        animation: slideIn 0.8s ease-out;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
    }
    @keyframes slideIn {
        from { transform: translateY(50px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }

    /* Modal Styling */
    .modal {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
    }
    .modal-content {
        background: white;
        margin: 15% auto;
        padding: 20px;
        border-radius: 10px;
        width: 70%;
        animation: zoomIn 0.3s ease;
    }
    @keyframes zoomIn {
        from { transform: scale(0); }
        to { transform: scale(1); }
    }
    .close {
        color: #aaa;
        float: right;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
    }
    .close:hover {
        color: #000;
    }

    /* Button Styling */
    .stButton>button {
        background: linear-gradient(45deg, #1e3c72, #2a5298);
        color: white;
        border: none;
        padding: 12px 25px;
        border-radius: 25px;
        font-size: 16px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(45deg, #2a5298, #1e3c72);
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(42, 82, 152, 0.4);
    }

    /* Responsive Design */
    @media (max-width: 600px) {
        .grid-container {
            grid-template-columns: 1fr;
        }
        .sidebar {
            width: 200px;
            left: -200px;
        }
        .sidebar.active ~ .content {
            margin-left: 200px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Custom JS for Sidebar Toggle and Modal
js_code = """
<script>
    // Sidebar Toggle
    document.addEventListener("DOMContentLoaded", function() {
        const sidebar = document.querySelector('.sidebar');
        const toggleBtn = document.querySelector('.toggle-btn');
        const content = document.querySelector('.content');

        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            content.classList.toggle('active');
        });

        // Modal Control
        const modal = document.getElementById('myModal');
        const btns = document.querySelectorAll('.modal-btn');
        const span = document.getElementsByClassName("close")[0];

        btns.forEach(btn => {
            btn.onclick = function() {
                modal.style.display = "block";
            }
        });

        span.onclick = function() {
            modal.style.display = "none";
        }

        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = "none";
            }
        }
    });
</script>
"""
html(js_code, height=0)

# Main Application
st.markdown('<div class="content">', unsafe_allow_html=True)
st.markdown('<h1 style="text-align: center; color: #1e3c72; font-family: Poppins, sans-serif; animation: fadeIn 1s ease;">🎉 Wonderful Attendance System</h1>', unsafe_allow_html=True)

# Sidebar
st.markdown(
    """
    <div class="sidebar">
        <div class="toggle-btn">☰</div>
        <a class="nav-item" href="#" onclick="window.parent.location.hash='Mark Attendance'; window.parent.location.reload();">Mark Attendance</a>
        <a class="nav-item" href="#" onclick="window.parent.location.hash='Admin Panel'; window.parent.location.reload();">Admin Panel</a>
    </div>
    """,
    unsafe_allow_html=True
)

# Modal for Forms
st.markdown(
    """
    <div id="myModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <div id="modal-content"></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Section Logic
if st.session_state.current_section == "Mark Attendance" or st.session_state.logged_in_admin is None:
    st.session_state.current_section = "Mark Attendance"
    st.markdown('<div class="grid-container">', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("📸 Mark Attendance")
    attend_image = st.camera_input("Capture/Upload Face", key="attend_image")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏰ In Punch", key="in_btn", help="Record your in-time"):
            if attend_image:
                result = mark_attendance(attend_image, True)
                st.success(result)
            else:
                st.error("❌ No image provided!")
    with col2:
        if st.button("🚪 Out Punch", key="out_btn", help="Record your out-time"):
            if attend_image:
                result = mark_attendance(attend_image, False)
                st.success(result)
            else:
                st.error("❌ No image provided!")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.current_section == "Admin Panel":
    if st.session_state.logged_in_admin is None:
        st.markdown('<div class="grid-container">', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.header("🔒 Admin Panel Login")
        login_id = st.text_input("Admin ID", key="login_id")
        login_pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login", key="login_btn"):
            auth_status, message = check_auth(login_id, login_pw, require_admin=True)
            if auth_status:
                st.session_state.logged_in_admin = login_id
                st.success(message)
                st.experimental_rerun()
            else:
                st.error(message)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="grid-container">', unsafe_allow_html=True)
        tab = st.tabs(["👤 Register User", "📊 Manage", "👑 Admin Management"])

        # Register User Tab
        with tab[0]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            with st.form(key="register_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name_input = st.text_input("Full Name")
                    unique_id_input = st.text_input("Unique ID")
                with col2:
                    designation_input = st.text_input("Designation")
                    face_image = st.camera_input("Face Image", key="face_image")
                col3, col4 = st.columns(2)
                with col3:
                    salary_input = st.number_input("Per Day Salary (₹)", min_value=0.0)
                    user_type = st.radio("Employment Type", ["Full-time", "Intern"])
                with col4:
                    office_time = st.text_input("Office Time (HH:MM)", value="09:00")
                    auth_id = st.text_input("Your Admin ID")
                    auth_pw = st.text_input("Your Password", type="password")
                if st.form_submit_button("Register User", help="Register a new user with face recognition"):
                    if face_image:
                        result = register_user(name_input, unique_id_input, designation_input, face_image, salary_input, user_type, office_time, auth_id, auth_pw)
                        st.success(result)
                    else:
                        st.error("❌ No image provided!")
            st.markdown('</div>', unsafe_allow_html=True)

        # Manage Tab
        with tab[1]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔄 Refresh Data", key="refresh_btn"):
                    st.text_area("Registered Users", refresh_users(), height=200, key="user_list")
            with col2:
                download_month = st.text_input("Month (YYYY-MM)", placeholder="2025-04")
                download_auth_id = st.text_input("Your Admin ID")
                download_auth_pw = st.text_input("Your Password", type="password")
            with col3:
                if st.button("📥 Download Attendance", key="download_btn"):
                    result, file = download_attendance(download_month, download_auth_id, download_auth_pw)
                    st.write(result)
                    if file:
                        with open(file, "rb") as f:
                            st.download_button(label="Download Report", data=f, file_name=file, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with st.expander("❌ Delete User"):
                del_name = st.text_input("Username to Delete")
                del_auth_id = st.text_input("Your Admin ID")
                del_auth_pw = st.text_input("Your Password", type="password")
                if st.button("Delete User", key="del_btn"):
                    result = delete_user(del_name, del_auth_id, del_auth_pw)
                    st.write(result)
            st.markdown('</div>', unsafe_allow_html=True)

        # Admin Management Tab
        with tab[2]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            with st.expander("Create New Master Admin"):
                new_master_id = st.text_input("New Master Admin Unique ID")
                new_master_pw = st.text_input("New Master Admin Password", type="password")
                auth_master_id = st.text_input("Your Master Admin ID")
                auth_master_pw = st.text_input("Your Master Admin Password", type="password")
                if st.button("Create Master Admin", key="create_master_btn"):
                    result = create_master_admin(new_master_id, new_master_pw, auth_master_id, auth_master_pw)
                    st.write(result)

            with st.expander("Create New Admin"):
                new_admin_id = st.text_input("New Admin Unique ID")
                new_admin_pw = st.text_input("New Admin Password", type="password")
                auth_master_id_admin = st.text_input("Your Master Admin ID")
                auth_master_pw_admin = st.text_input("Your Master Admin Password", type="password")
                if st.button("Create Admin", key="create_admin_btn"):
                    result = create_admin(new_admin_id, new_admin_pw, auth_master_id_admin, auth_master_pw_admin)
                    st.write(result)

            with st.expander("Set Master Admin Limit"):
                max_master_input = st.number_input("Max Master Admins", min_value=1, value=config["max_master_admins"])
                max_master_auth_id = st.text_input("Your Master Admin ID")
                max_master_auth_pw = st.text_input("Your Master Admin Password", type="password")
                if st.button("Set Limit", key="set_max_btn"):
                    result = set_max_master_admins(max_master_input, max_master_auth_id, max_master_auth_pw)
                    st.write(result)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Core Functions
def create_master_admin(new_id, new_pw, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_master=True)
    if not auth_status:
        return message
    if count_master_admins() >= config["max_master_admins"]:
        return f"❌ Maximum Master Admins ({config['max_master_admins']}) reached!"
    if not is_unique_id(new_id):
        return "❌ ID already exists!"
    if new_id in users:
        return "❌ User already exists!"
    users[new_id] = {
        "password": hash_password(new_pw),
        "is_master_admin": True,
        "is_admin": False,
        "unique_id": new_id
    }
    if auth_id == DEFAULT_MASTER_ADMIN_ID and count_master_admins() > 1:
        users.pop(DEFAULT_MASTER_ADMIN_ID, None)
    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)
    return f"✅ Master Admin {new_id} created successfully!"

def create_admin(unique_id, new_pw, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_master=True)
    if not auth_status:
        return message
    if not is_unique_id(unique_id):
        return "❌ ID already exists!"
    if unique_id in users:
        return "❌ User already exists!"
    users[unique_id] = {
        "password": hash_password(new_pw),
        "is_master_admin": False,
        "is_admin": True,
        "unique_id": unique_id
    }
    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)
    return f"✅ Admin {unique_id} created successfully!"

def set_max_master_admins(max_count, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_master=True)
    if not auth_status:
        return message
    if not isinstance(max_count, (int, float)) or max_count < 1:
        return "❌ Invalid max count value!"
    if max_count < count_master_admins():
        return f"❌ Cannot set limit below current count ({count_master_admins()})!"
    config["max_master_admins"] = int(max_count)
    with open(CONFIG_FILE, "wb") as f:
        pickle.dump(config, f)
    return f"✅ Master Admin limit set to {max_count}"

def register_user(name, unique_id, designation, image, salary, u_type, office_time, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_admin=True)
    if not auth_status:
        return message
    if not name or not unique_id or not designation or not salary or not u_type or not office_time:
        return "❌ All fields are required!"
    if not is_unique_id(unique_id):
        return "❌ ID already exists!"
    if unique_id in users:
        return "❌ User already exists!"
    if not isinstance(salary, (int, float)) or salary <= 0:
        return "❌ Invalid salary value!"

    if image is None:
        return "❌ No image provided!"
    processed = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # Convert Streamlit image to OpenCV format
    faces = face_app.get(processed)
    if len(faces) == 0:
        return "❌ No face detected!"

    users[name] = {
        "employee_id": unique_id,
        "designation": designation,
        "per_day_salary": float(salary),
        "user_type": u_type,
        "office_time": office_time,
        "is_admin": False,
        "is_master_admin": False,
        "unique_id": unique_id
    }
    known_face_encodings[name] = faces[0].embedding

    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(known_face_encodings, f)

    return f"✅ {name} registered successfully!"

def mark_attendance(image, is_in_punch):
    if image is None:
        return "❌ No image provided!"
    processed = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # Convert Streamlit image to OpenCV format
    faces = face_app.get(processed)
    if len(faces) == 0:
        return "❌ No face detected!"

    face_embedding = faces[0].embedding
    recognized_name = None

    for name, encoding in known_face_encodings.items():
        similarity = np.dot(face_embedding, encoding) / (
            np.linalg.norm(face_embedding) * np.linalg.norm(encoding))
        if similarity > 0.7:
            recognized_name = name
            break

    if not recognized_name:
        return "❌ Unknown user!"

    now = datetime.datetime.now(IST)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    try:
        df = pd.read_excel(ATTENDANCE_FILE)
    except FileNotFoundError:
        initialize_attendance_file()
        df = pd.read_excel(ATTENDANCE_FILE)

    today_entries = df[df["Date"] == date_str]
    user_entry = today_entries[today_entries["Name"] == recognized_name]

    if is_in_punch:
        if not user_entry.empty:
            return f"✅ In-punch already recorded for {recognized_name} today!"

        office_time = parse_office_time(users[recognized_name].get("office_time", "09:00"))
        in_time = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
        late_threshold = (datetime.datetime.combine(datetime.date.today(), office_time) +
                        datetime.timedelta(minutes=5)).time()

        status = "Half Day" if in_time > late_threshold else "Pending"

        new_row = {
            "Name": recognized_name,
            "Employee ID": users[recognized_name].get("unique_id", "N/A"),
            "Designation": users[recognized_name].get("designation", "N/A"),
            "Date": date_str,
            "In Time": time_str,
            "Out Time": None,
            "Status": status,
            "User Type": users[recognized_name].get("user_type", "N/A")
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(ATTENDANCE_FILE, index=False)
        return f"✅ In-punch recorded for {recognized_name} at {time_str}"
    else:
        if user_entry.empty:
            return f"❌ No in-punch found for {recognized_name} today!"

        idx = user_entry.index[0]
        if pd.notna(df.at[idx, "Out Time"]):
            return f"✅ Out-punch already recorded for {recognized_name} today!"

        df.at[idx, "Out Time"] = time_str

        if df.at[idx, "Status"] == "Pending":
            working_hours = calculate_working_hours(df.at[idx, "In Time"], time_str)
            df.at[idx, "Status"] = "Full Day" if working_hours >= 4 else "Half Day"

        df.to_excel(ATTENDANCE_FILE, index=False)
        return f"✅ Out-punch recorded for {recognized_name} at {time_str}"

def refresh_users():
    load_data()
    if not users:
        return "ℹ️ No users registered yet!"
    user_details = []
    for name, data in users.items():
        role = "Master Admin" if data.get("is_master_admin", False) else \
              "Admin" if data.get("is_admin", False) else "User"
        details = f"• {name} ({role})\n"
        details += f"  Unique ID: {data.get('unique_id', 'N/A')}\n"
        details += f"  Designation: {data.get('designation', 'N/A')}\n"
        details += f"  Per Day Salary: ₹{data.get('per_day_salary', 0)}\n"
        user_details.append(details)
    return "\n".join(user_details)

def download_attendance(month, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_admin=True)
    if not auth_status:
        return message, None

    if not month:
        return "❌ Month cannot be empty!", None

    try:
        df = pd.read_excel(ATTENDANCE_FILE)
        if df.empty:
            # Generate empty table with headers if no data
            empty_df = pd.DataFrame(columns=["Name", "Employee ID", "Designation", "Date", "In Time", "Out Time", "Status", "User Type"])
            filename = f"attendance_report_{month}.xlsx"
            empty_df.to_excel(filename, index=False)
            return f"ℹ️ No attendance data available, empty table generated for {month}!", filename
        df['Date'] = pd.to_datetime(df['Date'])
        monthly_data = df[df['Date'].dt.strftime('%Y-%m') == month]
    except FileNotFoundError:
        # Generate empty table with headers if file not found
        empty_df = pd.DataFrame(columns=["Name", "Employee ID", "Designation", "Date", "In Time", "Out Time", "Status", "User Type"])
        filename = f"attendance_report_{month}.xlsx"
        empty_df.to_excel(filename, index=False)
        return f"ℹ️ No attendance data available, empty table generated for {month}!", filename
    except Exception as e:
        return f"❌ Error loading attendance file: {str(e)}!", None

    if monthly_data.empty:
        # Generate empty table with headers if no data for the month
        empty_df = pd.DataFrame(columns=["Name", "Employee ID", "Designation", "Date", "In Time", "Out Time", "Status", "User Type"])
        filename = f"attendance_report_{month}.xlsx"
        empty_df.to_excel(filename, index=False)
        return f"ℹ️ No attendance data available for {month}, empty table generated!", filename

    try:
        # Calculate summary for each user
        summary_data = []
        for name, data in users.items():
            if data.get('is_admin') or data.get('is_master_admin'):
                continue
            user_data = monthly_data[monthly_data['Name'] == name]
            full_days = len(user_data[user_data['Status'] == "Full Day"])
            half_days = len(user_data[user_data['Status'] == "Half Day"])
            total_present_days = full_days + half_days
            monthly_salary = (full_days * data.get('per_day_salary', 0)) + (half_days * data.get('per_day_salary', 0) / 2)

            summary_data.append({
                "Name": name,
                "Employee ID": data.get('unique_id', 'N/A'),
                "Designation": data.get('designation', 'N/A'),
                "User Type": data.get('user_type', 'N/A'),
                "Full Days": full_days,
                "Half Days": half_days,
                "Total Present Days": total_present_days,
                "Monthly Salary": monthly_salary
            })

        summary_df = pd.DataFrame(summary_data)

        # Combine with detailed attendance data
        combined_df = pd.concat([monthly_data, summary_df], ignore_index=True)

        # Write to Excel
        filename = f"attendance_report_{month}.xlsx"
        combined_df.to_excel(filename, index=False, sheet_name="Attendance Summary")

        if not os.path.exists(filename):
            return "❌ File generation failed - file not found!", None

        return f"✅ Report generated for {month}", filename

    except Exception as e:
        return f"❌ Error generating Excel sheet: {str(e)}!", None

def delete_user(username, auth_id, auth_pw):
    auth_status, message = check_auth(auth_id, auth_pw, require_admin=True)
    if not auth_status:
        return message
    if not username:
        return "❌ Username cannot be empty!"
    if username not in users:
        return "❌ User not found!"

    del users[username]
    if username in known_face_encodings:
        del known_face_encodings[username]

    with open(USERS_FILE, "wb") as f:
        pickle.dump(users, f)
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(known_face_encodings, f)

    return f"✅ User {username} deleted successfully!"

# Initialize attendance system
initialize_attendance_file()

# Run the app
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Wonderful Attendance System")
    st.experimental_rerun()
