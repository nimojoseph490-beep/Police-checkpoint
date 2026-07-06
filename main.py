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
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "guardgate_secret_key")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- SECURE CREDENTIALS SETUP ---
TARGET_EMAIL = "nimojoseph490@gmail.com"
SENDER_EMAIL = "nimojoseph490@gmail.com"
# Pulls from Render configuration settings, falls back to raw string locally
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "cxje hzzk ykwu brph")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "State2580@agogo")

# --- SMART ARDUINO HARDWARE ROUTING ---
# Detects your Unix port system locally, or bypasses gracefully on Render cloud
PORT_OPTIONS = ['/dev/ttyUSB0', '/dev/ttyACM0', 'COM3']
arduino = None

for port in PORT_OPTIONS:
    try:
        arduino = serial.Serial(port=port, baudrate=9600, timeout=1)
        time.sleep(2) 
        print(f"Arduino successfully connected on port: {port}!")
        break
    except Exception:
        continue

if not arduino:
    print("Arduino hardware not detected physically. Running safely in simulation mode.")

# --- DATABASE CONNECTION HELPER ---
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),      
            password=DB_PASSWORD,      
            database="police_checkpoint",
            connect_timeout=3
        )
    except mysql.connector.Error as err:
        print(f"Database unavailable: {err}. Proceeding with interface rendering.")
        return None

def send_system_email(subject, body_content):
    """Background helper to route secure emails to the administrator account"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = TARGET_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body_content, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        server.quit()
        print("Notification dispatch completed successfully.")
    except Exception as e:
        print(f"Email delivery anomaly encountered: {e}")

# --- SYSTEM SCHEMATICS INITIALIZATION ---
# Safely handles modifications without throwing a 'Duplicate Column' crash
conn = get_db_connection()
if conn:
    try:
        cursor = conn.cursor()
        # We query the schema layout directly to verify structural compliance
        cursor.execute("SHOW COLUMNS FROM vehicles LIKE 'inspection_status'")
        exists = cursor.fetchone()
        
        if not exists:
            print("Applying dynamic schema alterations to 'vehicles' table...")
            cursor.execute("""
                ALTER TABLE vehicles 
                ADD COLUMN inspection_status ENUM('Passed', 'Flagged For Arrest') DEFAULT 'Passed',
                ADD COLUMN complaint_reason VARCHAR(255) DEFAULT NULL,
                ADD COLUMN flagged_by_badge VARCHAR(50) DEFAULT NULL;
            """)
            conn.commit()
        else:
            print("Database core structural schema is already optimized.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Schema optimization bypassed: {e}")

# --- WEB APPLICATION ROUTES ---

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    # Supports 'username', 'email', or 'user' input names from your HTML form
    username = request.form.get('username') or request.form.get('email') or request.form.get('user')
    password = request.form.get('password') or request.form.get('pass')
    
    # Strip whitespace to prevent accidental typos during entry
    if username: username = username.strip()
    if password: password = password.strip()
    
    # 1. Immediate Hardcoded Master Bypass for Presentation Flow
    if username == "admin" and password == "admin":
        print("🚀 Presentation Master Bypass Authenticated successfully!")
        session['logged_in'] = True
        session['username'] = "admin"
        session['badge'] = "KP-2026-TEMP"
        return redirect(url_for('dashboard'))

    # 2. Database Connection Check
    conn = get_db_connection()
    if conn is None:
        print("Database connection down. Incorrect bypass credentials submitted.")
        flash("Database infrastructure connection offline.", "danger")
        return redirect(url_for('index'))
            
    # 3. Standard Production Database Path
    try:
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
            
    except Exception as e:
        print(f"Unexpected login route error: {e}")
        flash("An error occurred during authentication processing.", "danger")
        return redirect(url_for('index'))
            
    except Exception as e:
        # 🛡️ EMERGENCY SAFETY NET: If database connection fails, trigger local bypass
        print(f"Database offline fallback activated: {e}")
        
        if username == "admin" and password == "admin":
            session['logged_in'] = True
            session['username'] = "admin"
            session['badge'] = "KP-2026-TEMP"
            return redirect(url_for('dashboard'))
        else:
            flash("Database infrastructure connection offline.", "danger")
            return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', badge_number=session.get('badge'), officer_name=session.get('username'))

@app.route('/inspect', methods=['POST'])
def inspect_vehicle():
    if 'logged_in' not in session:
        return jsonify({"status": "unauthorized"}), 401
        
    search_code = request.form.get('vehicle_code', '').strip()
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database link unavailable."})
        
    cursor = conn.cursor(dictionary=True)
    
    # Check for matched vehicle registry profile
    cursor.execute("SELECT * FROM vehicles WHERE vehicle_code = %s OR license_plate = %s", (search_code, search_code))
    vehicle = cursor.fetchone()
    
    if vehicle:
        # Cache scanned information inside session store for multi-stage processing
        session['last_scanned_vehicle'] = vehicle
        
        # Pull associated driver record matching vehicle ownership key link
        cursor.execute("SELECT * FROM drivers WHERE driver_code = %s", (vehicle['driver_code'],))
        driver = cursor.fetchone()
        
        cursor.close()
        conn.close()
        return jsonify({
            "status": "success",
            "found": True,
            "vehicle": vehicle,
            "driver": driver
        })
    else:
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "found": False})

@app.route('/flag_vehicle', methods=['POST'])
def flag_vehicle():
    if 'logged_in' not in session:
        return redirect(url_for('index'))
        
    complaint_reason = request.form.get('complaint_reason')
    vehicle = session.get('last_scanned_vehicle')
    officer_badge = session.get('badge_number')
    
    if not vehicle:
        flash("No active vehicle profiling record in stream context.", "warning")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicles 
            SET inspection_status = 'Flagged For Arrest', 
                complaint_reason = %s, 
                flagged_by_badge = %s 
            WHERE id = %s
        """, (complaint_reason, officer_badge, vehicle['id']))
        conn.commit()
        cursor.close()
        conn.close()
        
    # Send Emergency dispatch notice regarding criminal tracking flag update
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    alert_html = f"""
    <div style="font-family: Arial, sans-serif; border: 2px solid #dc2626; padding: 20px; max-width: 600px;">
        <h2 style="color: #dc2626; margin-top:0;">🚨 SYSTEM CRIMINOLOGY INTERCEPT ALERT</h2>
        <p><strong>Incident Datetime:</strong> {timestamp}</p>
        <p><strong>Flagged By Officer Badge:</strong> {officer_badge}</p>
        <p><strong>Infraction Reason:</strong> <span style="color:#dc2626; font-weight:bold;">{complaint_reason}</span></p>
        <hr style="border:0; border-top: 1px solid #e2e8f0;">
        <h3>Target Vehicle Specifications:</h3>
        <p><strong>Plate Reg:</strong> {vehicle['license_plate']}<br>
           <strong>Make/Model:</strong> {vehicle['make_model']}<br>
           <strong>Owner Identity:</strong> {vehicle['owner_name']}</p>
    </div>
    """
    send_system_email(f"🚨 CRITICAL ALERT: Vehicle Flagged for Arrest!", alert_html)
    
    flash("Target profile updated to criminal alert flag successfully.", "danger")
    return redirect(url_for('dashboard'))

@app.route('/gate/open', methods=['POST'])
def open_gate():
    if 'logged_in' not in session: 
        return jsonify({"status": "unauthorized"}), 401
        
    officer_badge = session.get('badge_number', 'Unknown Officer')
    vehicle = session.get('last_scanned_vehicle', None)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    passage_html = f"""
    <div style="font-family: Arial, sans-serif; border: 2px solid #2563eb; padding: 20px; max-width: 600px;">
        <h2 style="color: #2563eb; margin-top:0;">🔓 BARRIER ENTRY REGISTERED</h2>
        <p><strong>Passage Time:</strong> {timestamp}</p>
        <p><strong>Authorized By Officer Badge:</strong> {officer_badge}</p>
        <hr style="border:0; border-top: 1px solid #e2e8f0;">
        <h3>Vehicle Profile Details:</h3>
        {f"<p><strong>Code:</strong> {vehicle['vehicle_code']}<br><strong>Plate:</strong> {vehicle['license_plate']}<br><strong>Model:</strong> {vehicle['make_model']}<br><strong>Owner:</strong> {vehicle['owner_name']}</p>" if vehicle else "<p>Manual Override Switch Triggered (No Vehicle Scanned)</p>"}
    </div>
    """
    send_system_email(f"🔓 GATE OPENED: Checkpoint Clearance Profile", passage_html)

    if arduino:
        try:
            arduino.write(b'O') 
            return jsonify({"status": "success", "message": "Gate command dispatched via serial hardware channel!"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Serial port write issue: {e}"})
    else:
        return jsonify({"status": "simulation", "message": "Gate command processed successfully (Simulation Mode Active)."})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))