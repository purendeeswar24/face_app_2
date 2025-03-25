# Install required libraries
# Run these commands in your terminal or Colab:
# pip install gradio pandas openpyxl

# Import libraries
import os
import pandas as pd
from datetime import datetime
import gradio as gr

# Create necessary directories
os.makedirs("attendance_records", exist_ok=True)

# Mark attendance
def mark_attendance(name):
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join("attendance_records", f"attendance_{today}.csv")
    
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=["Name", "Time", "Date"])
    else:
        df = pd.read_csv(file_path)
    
    if name not in df["Name"].values:
        new_entry = {"Name": name, "Time": datetime.now().strftime("%H:%M:%S"), "Date": today}
        df = df.append(new_entry, ignore_index=True)
        df.to_csv(file_path, index=False)
        return f"Attendance marked for {name}!"
    else:
        return f"{name} is already marked present."

# Generate Excel sheet for the attendance records
def generate_excel_sheet():
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join("attendance_records", f"attendance_{today}.csv")
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        excel_file_path = os.path.join("attendance_records", f"attendance_{today}.xlsx")
        df.to_excel(excel_file_path, index=False)
        return excel_file_path
    else:
        return None

# Gradio Interface
with gr.Blocks() as demo:
    gr.Markdown("# Simple Attendance System")
    
    with gr.Tab("Mark Attendance"):
        name_input = gr.Textbox(label="Enter Your Name")
        attendance_output = gr.Textbox(label="Attendance Status")
        mark_attendance_button = gr.Button("Mark Attendance")
        mark_attendance_button.click(mark_attendance, name_input, attendance_output)
    
    with gr.Tab("Download Attendance"):
        download_button = gr.Button("Generate Excel Sheet")
        download_output = gr.File(label="Download Excel Sheet")
        download_button.click(generate_excel_sheet, None, download_output)

# Launch the app
demo.launch()