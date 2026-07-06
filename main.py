import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import serial
import time

app = Flask(__name__)
app.secret_key = "guardgate_secret_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- EMAIL CONFIGURATION ---
TARGET_EMAIL = "nimojoseph490@gmail.com"
SENDER_EMAIL = "nimojoseph490@gmail.com" # Can be the same email or a separate sender account
EMAIL_PASSWORD = "cxje hzzk ykwu brph"   # Paste your 16-character Google App Password here

def send_system_email(subject, body_content):
    """Background helper to route secure emails to the administrator account"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = TARGET_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body_content, 'html'))
        
        # Connect securely using SSL to Gmail's standard server
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        server.quit()
        print(f"📧 System Notification Email dispatched successfully: {subject}")
    except Exception as e:
        print(f"⚠️ Email routing error: {e}")

# --- ARDUINO SERIAL SETUP ---
try:
    arduino = serial.Serial(port='/dev/ttyUSB0', baudrate=9600, timeout=1)
    time.sleep(2) 
    print("Arduino successfully connected!")
except Exception as e:
    arduino = None
    print(f"Arduino not connected: {e}. Running in simulation mode.")

# --- DATABASE CONNECTION HELPER ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",      
        password="State2580@agogo",      
        database="police_checkpoint"
    )

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM police_officers WHERE username = %s AND password = %s", (username, password))
    officer = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if officer:
        session['logged_in'] = True
        session['username'] = officer['username']
        session['badge'] = officer['badge_number']
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid Credentials, please try again.")
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

# --- ONBOARDING SECTIONS ---
@app.route('/onboard/driver', methods=['POST'])
def onboard_driver():
    if 'logged_in' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    name = request.form['full_name']
    license_num = request.form['license_number']
    phone = request.form['phone_number']
    file = request.files.get('photo')
    
    driver_code = f"DRV-{secrets.token_hex(3).upper()}"
    filename = None
    if file and file.filename != '':
        filename = f"{driver_code}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        filename = f"uploads/{filename}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO drivers (driver_code, full_name, license_number, phone_number, photo_path) VALUES (%s, %s, %s, %s, %s)",
            (driver_code, name, license_num, phone, filename)
        )
        conn.commit()
        flash(f"Driver successfully onboarded! Unique Code: {driver_code}")
    except mysql.connector.Error as err:
        flash(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/onboard/vehicle', methods=['POST'])
def onboard_vehicle():
    if 'logged_in' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    plate = request.form['license_plate']
    model = request.form['make_model']
    owner = request.form['owner_name']
    file = request.files.get('photo')
    
    vehicle_code = f"VEH-{secrets.token_hex(3).upper()}"
    filename = None
    if file and file.filename != '':
        filename = f"{vehicle_code}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        filename = f"uploads/{filename}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO vehicles (vehicle_code, license_plate, make_model, owner_name, photo_path) VALUES (%s, %s, %s, %s, %s)",
            (vehicle_code, plate, model, owner, filename)
        )
        conn.commit()
        flash(f"Vehicle successfully onboarded! Unique Code: {vehicle_code}")
    except mysql.connector.Error as err:
        flash(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('dashboard'))

# --- INSPECTION AND VERIFICATION LOGIC ---
@app.route('/verify/driver/<code_or_license>')
def verify_driver(code_or_license):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drivers WHERE driver_code = %s OR license_number = %s", (code_or_license, code_or_license))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(result if result else {"found": False})

@app.route('/verify/vehicle/<code_or_plate>')
def verify_vehicle(code_or_plate):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vehicles WHERE vehicle_code = %s OR license_plate = %s", (code_or_plate, code_or_plate))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(result if result else {"found": False})

# --- ARREST EVENT AND EMAIL DISPATCH ---
@app.route('/vehicle/arrest', methods=['POST'])
def arrest_vehicle():
    if 'logged_in' not in session: return jsonify({"status": "unauthorized"}), 401
    
    data = request.json
    vehicle_code = data.get('vehicle_code')
    reason = data.get('reason')
    officer_badge = session.get('badge')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch vehicle details first to include in the email report
        cursor.execute("SELECT * FROM vehicles WHERE vehicle_code = %s", (vehicle_code,))
        vehicle_details = cursor.fetchone()
        
        cursor.execute("""
            UPDATE vehicles 
            SET inspection_status = 'Flagged For Arrest', complaint_reason = %s, flagged_by_badge = %s 
            WHERE vehicle_code = %s
        """, (reason, officer_badge, vehicle_code))
        conn.commit()
        
        # Build Email Notification Layout
        email_html = f"""
        <div style="font-family: Arial, sans-serif; border: 2px solid #dc2626; padding: 20px; max-width: 600px;">
            <h2 style="color: #dc2626; margin-top:0;">🚨 ARREST NOTICE - VEHICLE FLAG TRIGGERED</h2>
            <p><strong>Time of Action:</strong> {timestamp}</p>
            <p><strong>Vehicle Code:</strong> {vehicle_code}</p>
            <p><strong>License Plate:</strong> {vehicle_details['license_plate'] if vehicle_details else 'N/A'}</p>
            <p><strong>Make & Model:</strong> {vehicle_details['make_model'] if vehicle_details else 'N/A'}</p>
            <p><strong>Registered Owner:</strong> {vehicle_details['owner_name'] if vehicle_details else 'N/A'}</p>
            <p style="background: #fee2e2; padding: 10px; border-left: 5px solid #dc2626; color: #991b1b;">
                <strong>Reason for Detention:</strong> {reason}
            </p>
            <p><strong>Flagged By Officer Badge:</strong> {officer_badge}</p>
        </div>
        """
        send_system_email(f"🚨 FLAG ARREST DETECTED: {vehicle_code}", email_html)
        
        return jsonify({"status": "success", "message": f"Vehicle {vehicle_code} successfully placed under arrest."})
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": str(err)})
    finally:
        cursor.close()
        conn.close()

# --- RELEASE EVENT AND EMAIL DISPATCH ---
@app.route('/vehicle/release', methods=['POST'])
def release_vehicle():
    if 'logged_in' not in session: return jsonify({"status": "unauthorized"}), 401
    
    data = request.json
    vehicle_code = data.get('vehicle_code')
    officer_badge = session.get('badge')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE vehicles 
            SET inspection_status = 'Passed', complaint_reason = NULL, flagged_by_badge = NULL 
            WHERE vehicle_code = %s
        """, (vehicle_code,))
        conn.commit()
        
        email_html = f"""
        <div style="font-family: Arial, sans-serif; border: 2px solid #16a34a; padding: 20px; max-width: 600px;">
            <h2 style="color: #16a34a; margin-top:0;">✅ VEHICLE REGISTRATION RELEASED</h2>
            <p><strong>Clearance Time:</strong> {timestamp}</p>
            <p><strong>Vehicle System Code:</strong> {vehicle_code}</p>
            <p><strong>Status Update:</strong> Passed / Restored to Clear Clearance Profile</p>
            <p><strong>Authorized By Officer Badge:</strong> {officer_badge}</p>
        </div>
        """
        send_system_email(f"✅ LOCKOUT CLEARANCE RELEASE: {vehicle_code}", email_html)
        
        return jsonify({"status": "success", "message": f"Vehicle {vehicle_code} released successfully."})
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": str(err)})
    finally:
        cursor.close()
        conn.close()

# --- SMART BARRIER & GATE LOCKOUT REPORT DISPATCH ---
@app.route('/gate/open', methods=['POST'])
def open_gate():
    if 'logged_in' not in session: return jsonify({"status": "unauthorized"}), 401
    
    data = request.json or {}
    active_vehicle_code = data.get('active_vehicle_code')
    officer_badge = session.get('badge')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    vehicle = None
    if active_vehicle_code:
        cursor.execute("SELECT * FROM vehicles WHERE vehicle_code = %s", (active_vehicle_code,))
        vehicle = cursor.fetchone()
        
    cursor.close()
    conn.close()
    
    # 1. HANDLE GATE SECURITY LOCKOUT EMAIL
    if vehicle and vehicle['inspection_status'] == 'Flagged For Arrest':
        lockout_html = f"""
        <div style="font-family: Arial, sans-serif; border: 3px solid #b91c1c; background-color: #fef2f2; padding: 20px; max-width: 600px;">
            <h2 style="color: #b91c1c; margin-top:0;">🛑 CRITICAL ALERT: SYSTEM LOCKOUT ACCESSED</h2>
            <p><strong>Attempted Time:</strong> {timestamp}</p>
            <p><strong>Action:</strong> An officer tried to open the barrier, but the system **DENIED PASSAGE** due to active vehicle arrest.</p>
            <hr style="border:0; border-top:1px dashed #b91c1c;">
            <p><strong>Vehicle Code:</strong> {vehicle['vehicle_code']} | <strong>Plate:</strong> {vehicle['license_plate']}</p>
            <p><strong>Make & Model:</strong> {vehicle['make_model']} | <strong>Owner:</strong> {vehicle['owner_name']}</p>
            <p style="color: #991b1b; font-weight:bold;"><strong>Arrest Offence Reason:</strong> {vehicle['complaint_reason']}</p>
            <p><strong>Attempted By Officer Badge:</strong> {officer_badge}</p>
        </div>
        """
        send_system_email(f"🛑 LOCKOUT DENIAL REPORT: {active_vehicle_code}", lockout_html)
        
        return jsonify({
            "status": "security_lockout", 
            "message": f"🛑 SECURITY BLOCK: Cannot raise barrier! This vehicle is currently ARRESTED for: '{vehicle['complaint_reason']}'."
        }), 403

    # 2. HANDLE SUCCESSFUL GATE OPENING PASSAGE EMAIL
    driver_info = "No driver data verified during this sequence"
    # If a driver tab was open, let's grab their details from active dashboard elements if needed
    
    passage_html = f"""
    <div style="font-family: Arial, sans-serif; border: 2px solid #2563eb; padding: 20px; max-width: 600px;">
        <h2 style="color: #2563eb; margin-top:0;">🔓 BARRIER ENTRY REGISTERED</h2>
        <p><strong>Passage Time:</strong> {timestamp}</p>
        <p><strong>Authorized By Officer Badge:</strong> {officer_badge}</p>
        <hr style="border:0; border-top: 1px solid #e2e8f0;">
        <h3>Vehicle Profile Details:</h3>
        {f"<p><strong>Code:</strong> {vehicle['vehicle_code']}<br><strong>Plate:</strong> {vehicle['license_plate']}<br><strong>Model:</strong> {vehicle['make_model']}<br><strong>Owner:</strong> {vehicle['owner_name']}</p>" if vehicle else "<p>No explicit vehicle checked before raising gate (Manual Override Switch)</p>"}
    </div>
    """
    send_system_email(f"🔓 GATE OPENED: Checkpoint Alpha Clearance", passage_html)

    if arduino:
        try:
            arduino.write(b'O') 
            return jsonify({"status": "success", "message": "Gate command sent to Arduino!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "simulated", "message": "No hardware attached. Gate opened simulated!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)