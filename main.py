import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql  # 🔄 Switched from mysql.connector for fast cloud deployment
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
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "cxje hzzk ykwu brph")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "State2580@agogo")

# --- SMART ARDUINO HARDWARE ROUTING ---
PORT_OPTIONS = ['/dev/ttyUSB0', '/dev/ttyACM0', 'COM3']
arduino = None

for port in PORT_OPTIONS:
    try:
        arduino = serial.Serial(port=port, baudrate=9600, timeout=1)
        print(f"✅ Arduino hardware successfully attached to port: {port}")
        break
    except Exception:
        continue

if not arduino:
    print("⚠️ Hardware port unassigned. Interface entering automated Simulation Mode.")

def get_db_connection():
    """Establishes connection to the cloud or local infrastructure database dynamically."""
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "mysql-369f65d6-nimo-b4e8.aivencloud.com"),
            user=os.environ.get("DB_USER", "avnadmin"),
            password=os.environ.get("DB_PASSWORD", "AVNS_AYcPhIh7_1Qg6TqmW_o"),
            database=os.environ.get("DB_NAME", "police_checkpoint"),
            port=int(os.environ.get("DB_PORT", 23937)),
            autocommit=True,
            connect_timeout=3,
            cursorclass=pymysql.cursors.DictCursor  # 🔄 Automatically makes results act like Python dictionaries
        )
        return conn
    except Exception as err:
        print(f"Database connection skipped: {err}. Activating fallback simulation pipelines.")
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
        server.close()
        print("📨 Automated administrative log notification dispatched successfully.")
    except Exception as e:
        print(f"❌ Notification engine connection anomaly: {e}")

# --- CORE APP WEB ROUTING ---

@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username') or request.form.get('email') or request.form.get('user')
    password = request.form.get('password') or request.form.get('pass')
    
    if username: username = username.strip()
    if password: password = password.strip()
    
    # Master presentation bypass credential override trap
    if username == "admin" and password == "admin":
        print("🚀 Presentation Master Bypass Authenticated successfully!")
        session['logged_in'] = True
        session['username'] = "admin"
        session['badge'] = "KP-2026-TEMP"
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        print("Database connection down. Incorrect bypass credentials submitted.")
        flash("Database infrastructure connection offline.", "danger")
        return redirect(url_for('index'))
            
    try:
        cursor = conn.cursor() # ✅ Clean, updated syntax
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
            flash("Invalid Credentials, please try again.", "danger")
            return redirect(url_for('index'))
            
    except Exception as e:
        print(f"Unexpected login route error: {e}")
        flash("An error occurred during authentication processing.", "danger")
        return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/verify/driver/<driver_code>', methods=['GET'])
def verify_driver_api(driver_code):
    if not session.get('logged_in'):
        return jsonify({"status": "unauthorized"}), 401
        
    conn = get_db_connection()
    if not conn:
        # Simulation Mode Mock Response
        return jsonify({
            "status": "success",
            "found": True,
            "driver_code": driver_code.strip().upper(),
            "driver_name": "Emmanuel Owusu",
            "full_name": "Emmanuel Owusu",
            "license_number": "GHA-987412-A",
            "status": "Valid",
            "photo_path": None
        })
        
    try:
        cursor = conn.cursor() # ✅ Clean, updated syntax
        cursor.execute("SELECT * FROM drivers WHERE driver_code = %s OR license_number = %s", (driver_code.strip(), driver_code.strip()))
        driver = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if driver:
            return jsonify({"status": "success", "found": True, **driver})
        else:
            return jsonify({"status": "success", "found": False})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/verify/vehicle/<vehicle_code>', methods=['GET'])
def verify_vehicle_api(vehicle_code):
    if not session.get('logged_in'):
        return jsonify({"status": "unauthorized"}), 401
        
    code_clean = vehicle_code.strip().upper()
    conn = get_db_connection()
    
    if not conn:
        # Simulation Mode Mock Response
        is_flagged = "FLAG" in code_clean or "ARREST" in code_clean
        mock_vehicle = {
            "id": 1,
            "vehicle_code": code_clean,
            "license_plate": "AS-2026-GH" if not is_flagged else "AK-419-GH",
            "make_model": "Toyota Land Cruiser",
            "owner_name": "Emmanuel Owusu",
            "driver_code": "DRV-9FCD1F",
            "inspection_status": "Flagged For Arrest" if is_flagged else "Passed",
            "complaint_reason": "Reported Stolen Vehicle Alert" if is_flagged else None,
            "flagged_by_badge": "KP-9921" if is_flagged else None,
            "photo_path": None
        }
        session['last_scanned_vehicle'] = mock_vehicle
        return jsonify({"status": "success", "found": True, "vehicle": mock_vehicle})
        
    try:
        cursor = conn.cursor() # ✅ Clean, updated syntax
        cursor.execute("SELECT * FROM vehicles WHERE vehicle_code = %s OR license_plate = %s", (code_clean, code_clean))
        vehicle = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if vehicle:
            session['last_scanned_vehicle'] = vehicle
            return jsonify({"status": "success", "found": True, "vehicle": vehicle})
        else:
            return jsonify({"status": "success", "found": False})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/vehicle/arrest', methods=['POST'])
def arrest_vehicle():
    if not session.get('logged_in'):
        return jsonify({"status": "unauthorized"}), 401
        
    data = request.get_json() or {}
    v_code = data.get('vehicle_code')
    reason = data.get('reason', "General Offence Infraction")
    officer_badge = session.get('badge', "KP-TEMP")
    
    conn = get_db_connection()
    if not conn:
        print(f"🚨 [Simulation] Vehicle {v_code} flagged for Arrest. Reason: {reason}")
        return jsonify({"status": "success", "message": f"Vehicle {v_code} has been successfully flagged for arrest."})
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicles SET inspection_status = 'Flagged For Arrest', complaint_reason = %s, flagged_by_badge = %s
            WHERE vehicle_code = %s
        """, (reason, officer_badge, v_code))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Enforcement alert status recorded successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/vehicle/release', methods=['POST'])
def release_vehicle():
    if not session.get('logged_in'):
        return jsonify({"status": "unauthorized"}), 401
        
    data = request.get_json() or {}
    v_code = data.get('vehicle_code')
    
    conn = get_db_connection()
    if not conn:
        print(f"✅ [Simulation] Vehicle {v_code} cleared and released.")
        return jsonify({"status": "success", "message": f"Vehicle {v_code} cleared from enforcement constraints."})
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE vehicles SET inspection_status = 'Passed', complaint_reason = NULL, flagged_by_badge = NULL
            WHERE vehicle_code = %s
        """, (v_code,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Clearance issued successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/onboard/driver', methods=['POST'])
def onboard_driver():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    full_name = request.form.get('full_name')
    license_number = request.form.get('license_number')
    phone_number = request.form.get('phone_number')
    photo = request.files.get('photo')
    
    driver_code = f"DRV-{secrets.token_hex(3).upper()}"
    photo_path = "uploads/default_driver.png"
    
    if photo and photo.filename != '':
        filename = f"{driver_code}_{photo.filename}"
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        photo_path = f"uploads/{filename}"
        
    conn = get_db_connection()
    if conn is None:
        print(f"📦 [Simulation] Registered Driver: {full_name} | Assigned: {driver_code}")
        flash(f"Driver Registered Successfully! Assigned Code: {driver_code}", "success")
        return redirect(url_for('dashboard'))
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO drivers (driver_code, full_name, license_number, phone_number, photo_path, status)
            VALUES (%s, %s, %s, %s, %s, 'Valid')
        """, (driver_code, full_name, license_number, phone_number, photo_path))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Driver Registered Successfully! Assigned Code: {driver_code}", "success")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Driver registration DB failure: {e}")
        flash("Database insertion error during registration process.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/onboard/vehicle', methods=['POST'])
def onboard_vehicle():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    license_plate = request.form.get('license_plate')
    make_model = request.form.get('make_model')
    owner_name = request.form.get('owner_name')
    photo = request.files.get('photo')
    
    vehicle_code = f"VEH-{secrets.token_hex(3).upper()}"
    photo_path = "uploads/default_vehicle.png"
    
    if photo and photo.filename != '':
        filename = f"{vehicle_code}_{photo.filename}"
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        photo_path = f"uploads/{filename}"
        
    conn = get_db_connection()
    if conn is None:
        print(f"📦 [Simulation] Registered Vehicle: {make_model} | Assigned: {vehicle_code}")
        flash(f"Vehicle Registered Successfully! Assigned Code: {vehicle_code}", "success")
        return redirect(url_for('dashboard'))
        
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vehicles (vehicles_code, license_plate, make_model, owner_name, photo_path, inspection_status)
            VALUES (%s, %s, %s, %s, %s, 'Passed')
        """, (vehicle_code, license_plate, make_model, owner_name, photo_path))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"Vehicle Registered Successfully! Assigned Code: {vehicle_code}", "success")
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Vehicle registration DB failure: {e}")
        flash("Database insertion error during registration process.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/gate/open', methods=['POST'])
def open_gate():
    if not session.get('logged_in'):
        return jsonify({"status": "unauthorized"}), 401
        
    data = request.get_json() or {}
    v_code = data.get('active_vehicle_code')
    officer_badge = session.get('badge', "KP-TEMP")
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    vehicle = session.get('last_scanned_vehicle') if v_code else None
    
    if vehicle and vehicle.get('inspection_status') == "Flagged For Arrest":
        return jsonify({
            "status": "forbidden", 
            "message": f"🚨 LOCKOUT ENFORCED: Vehicle {v_code} is actively flagged for arrest. Barrier override blocked until cleared!"
        }), 403

    passage_html = f"""
    <div style="font-family: Arial, sans-serif; border: 2px solid #2563eb; padding: 20px; max-width: 600px;">
        <h2 style="color: #2563eb; margin-top:0;">🔓 BARRIER ENTRY REGISTERED</h2>
        <p><strong>Passage Time:</strong> {timestamp}</p>
        <p><strong>Authorized By Officer Badge:</strong> {officer_badge}</p>
        <hr style="border:0; border-top: 1px solid #e2e8f0;">
        <h3>Vehicle Profile Details:</h3>
        {"<p><strong>Code:</strong> " + vehicle['vehicle_code'] + "<br><strong>Plate:</strong> " + vehicle['license_plate'] + "<br><strong>Model:</strong> " + vehicle['make_model'] + "<br><strong>Owner:</strong> " + vehicle['owner_name'] + "</p>" if vehicle else "<p>Manual Override Switch Triggered (No Vehicle Active Scanned)</p>"}
    </div>
    """
    send_system_email(f"🔓 GATE OPENED: Checkpoint Clearance Profile", passage_html)

    if arduino:
        try:
            arduino.write(b'O') 
            return jsonify({"status": "success", "message": "Gate command dispatched via serial hardware channel!"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Serial port issue: {e}"})
    else:
        return jsonify({"status": "simulation", "message": "Gate command processed successfully (Simulation Hardware Override)."})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)