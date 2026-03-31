import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob

app = Flask(__name__)
app.secret_key = 'prc_sos_secret_key'
CORS(app, supports_credentials=True)

# --- NEW: ABSOLUTE PATH LOGIC ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'prc_crisis.db')


def get_empathetic_response(sentiment, severity):
    responses = {
        "EMERGENCY": {
            "msg": "🚨 CRITICAL: This is a medical emergency. Please stay calm and use the dial button below.",
            "link": "https://powayrecoverycenter.org/contact-us/",
            "label": "View PRC Emergency Info"
        },
        "DISTRESSED": {
            "msg": "😤 It sounds like you're struggling right now. You don't have to carry this weight alone.",
            "link": "https://powayrecoverycenter.org/",
            "label": "Return to PRC Home"
        },
        "STABLE": {
            "msg": "🌿 Thank you for checking in. Your honesty keeps your path clear.",
            "link": "https://powayrecoverycenter.org/resources/",
            "label": "Explore More Resources"
        }
    }
    
    # Selection Logic
    if severity == "EMERGENCY":
        return responses["EMERGENCY"]
    elif sentiment < 0:
        return responses["DISTRESSED"]
    else:
        return responses["STABLE"]

    
def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity 
    
    recommendations = []
    severity = "Stable"
    
    # 1. EMERGENCY OVERRIDE
    critical_keywords = ["breathe", "chest pain", "overdose", "die", "kill", "hurt", "suicide", "bleeding", "hospital"]
    
    if any(word in user_input.lower() for word in critical_keywords):
        severity = "EMERGENCY"
        sentiment = -1.0 # Force -1.0 for the Red Sidebar
    elif sentiment < 0:
        severity = "DISTRESSED"

    # 2. MULTI-PROGRAM MAPPING
    for prog in program_data:
        keywords = prog['keywords'].split(", ")
        if any(word in user_input.lower() for word in keywords):
            recommendations.append({"name": prog['name'], "url": prog['url']})

    # 3. GET AI RESPONSE (Fixed: Uses 'severity' correctly)
    ai_res = get_empathetic_response(sentiment, severity)

    return {
        "severity": severity, 
        "sentiment": sentiment, 
        "paths": recommendations, 
        "ai_response": ai_res
    }

def get_db_connection():
    # This forces Flask to use the DB in your actual folder
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['POST'])
def register():
    # Use get_json() to catch the data from React's JSON.stringify
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')  # Optional: If you want to store email as well

    print(f"\n--- REGISTRATIONDATA VERIFIED ---")
    print(f"User is trying to log in as: {username}")
        

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    hashed_pw = generate_password_hash(password)
    
    db = get_db_connection()
    try:
        db.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, hashed_pw, email))
        db.commit()
        db.close()
        return jsonify({"message": "User registered successfully"}), 201
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"message": "Username already exists!"}), 409

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    
    db = get_db_connection()
    user_row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db.close()

    if user_row and check_password_hash(user_row['password'], password):
        # IMPORTANT: Set session variables so /dashboard works
        session['user_id'] = user_row['id'] 
        session['username'] = user_row['username']
        
        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": {
                "id": user_row['id'], # <--- ADD THIS
                "username": user_row['username'],
                "email": user_row['email']  # <--- THIS IS THE KEY CHANGE
            }
        }), 200
    else:
        return jsonify({
            "status": "fail",
            "message": "Invalid username or password"
        }), 401
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db_connection()
    triage_result = None

    if request.method == 'POST':
        user_text = request.form.get('user_text')
        if user_text:
            prog_rows = db.execute('SELECT * FROM prc_programs').fetchall()
            programs_list = [dict(row) for row in prog_rows]
            
            # RUN THE ENGINE
            triage_result = sos_triage_engine(user_text, programs_list)
            
            # IMPORTANT: Save the TRIAGE sentiment, not the raw textblob sentiment
            db.execute('INSERT INTO logs (user_id, user_text, sentiment_score) VALUES (?, ?, ?)',
                       (session['user_id'], user_text, triage_result['sentiment']))
            db.commit()

    # Get History
    history = db.execute('SELECT * FROM logs WHERE user_id = ? ORDER BY timestamp DESC', 
                         (session['user_id'],)).fetchall()
    
    # Gamification Logic (Stay same)
    total_logs = len(history)
    elevation = min(total_logs * 200, 2800)
    location = "Lake Poway Trailhead"
    if total_logs > 12: location = "Potato Chip Rock Summit"
    elif total_logs > 5: location = "Mount Woodson Switchbacks"

    if triage_result and triage_result['severity'] == "EMERGENCY":
        trail_env = {"status": "Critical Storm", "color": "from-red-900 to-black", "icon": "⚡", "msg": "SEEK HELP IMMEDIATELY."}
    elif triage_result and triage_result['sentiment'] < 0:
        trail_env = {"status": "Rugged Terrain", "color": "from-stone-700 to-stone-900", "icon": "🌫️", "msg": "Visibility is low. Stay on the marked path."}
    else:
        trail_env = {"status": "Clear Skies", "color": "from-[#4a7c44] to-[#2d4f1e]", "icon": "☀️", "msg": "Your path is clear today."}

    db.close()
    return render_template('dashboard.html', username=session['username'], history=history, triage=triage_result, trail=trail_env, elevation=elevation, location=location)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 1. Route to SAVE a meeting to a user's calendar
@app.route('/add-meeting', methods=['POST'])
def add_meeting():
    data = request.get_json()
    
    # DEBUG: Check your Flask terminal after you click the button to see this:
    print(f"\n--- RECEIVED MEETING DATA ---")
    print(data) 

    user_id = data.get('user_id')
    name = data.get('name')      # React must send 'name'
    date = data.get('date')      # React must send 'date'
    time = data.get('time')      # React must send 'time'
    location = data.get('location', 'N/A')
    m_type = data.get('type', 'Open')

    # Safety Check: If name is missing, don't even try the database
    if not name:
        return jsonify({"message": "Error: Meeting name is missing in request"}), 400

    db = get_db_connection()
    try:
        db.execute('''
            INSERT INTO user_meetings (user_id, name, date, time, location, type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, name, date, time, location, m_type))
        db.commit()
        return jsonify({"status": "success", "message": f"Added {name} to calendar"}), 201
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        return jsonify({"message": "Database insertion failed"}), 500
    finally:
        db.close()

# 2. Route to FETCH all meetings for the logged-in user
@app.route('/get-user-meetings', methods=['GET'])
def get_user_meetings():
    # CHANGE: Look for user_id in the URL parameters (?user_id=...)
    # instead of session.get('user_id')
    user_id = request.args.get('user_id')
    
    # DEBUG PRINT: Check your Flask terminal to see this
    print(f"DEBUG: Fetching meetings for user_id: {user_id}")

    if not user_id:
        # If no ID is provided, return an error
        return jsonify({"message": "User ID is required"}), 400
        
    db = get_db_connection()
    # Fetch meetings for this specific ID
    rows = db.execute('SELECT * FROM user_meetings WHERE user_id = ? ORDER BY date ASC', (user_id,)).fetchall()
    db.close()
    
    meetings_list = [dict(row) for row in rows]
    return jsonify(meetings_list), 200

if __name__ == '__main__':
    app.run(debug=True, port=8323)