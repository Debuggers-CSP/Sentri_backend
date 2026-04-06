# --- IMPORTS ---
from datetime import datetime
from urllib.parse import urljoin, urlparse
from flask import abort, redirect, render_template, request, send_from_directory, url_for, jsonify, current_app, g 
from flask_login import current_user, login_user, logout_user, login_required
from flask.cli import AppGroup
from dotenv import load_dotenv
import os
import requests
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob
from flask_cors import CORS

# Import objects from your project's __init__

from __init__ import app, db, login_manager  
# Import the User model for the user_loader
from model.user import User

# --- 1. LOGIN MANAGER CONFIGURATION (Fixes the crash) ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

login_manager.login_view = "login"

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('login', next=request.path))

# --- 2. SENTRI DATABASE LOGIC ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENTRI_DB_PATH = os.path.join(BASE_DIR, 'prc_crisis.db')

def get_sentri_db_connection():
    conn = sqlite3.connect(SENTRI_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sentri_db():
    db_conn = get_sentri_db_connection()
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS program_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_text TEXT NOT NULL,
            sentiment_score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db_conn.commit()
    db_conn.close()

# --- 3. SENTRI TRIAGE ENGINE ---
def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity 
    severity = "EMERGENCY" if any(w in user_input.lower() for w in ["suicide", "die", "overdose"]) else "Stable"
    return {"severity": severity, "sentiment": sentiment}

# --- 4. REGISTER BLUEPRINTS ---
# (Keeping your existing registrations)
from api.user import user_api 
from api.python_exec_api import python_exec_api
from api.javascript_exec_api import javascript_exec_api
from api.section import section_api
from api.persona_api import persona_api
from api.pfp import pfp_api
from api.analytics import analytics_api
from api.student import student_api
from api.groq_api import groq_api
from api.gemini_api import gemini_api
from api.microblog_api import microblog_api
from api.classroom_api import classroom_api
from api.data_export_import_api import data_export_import_api
from hacks.joke import joke_api 
from api.post import post_api  
from api.study import study_api
from api.feedback_api import feedback_api
from machinelearning.api.titanic_api import titanic_api

app.register_blueprint(python_exec_api); app.register_blueprint(javascript_exec_api)
app.register_blueprint(user_api); app.register_blueprint(section_api)
app.register_blueprint(persona_api); app.register_blueprint(pfp_api) 
app.register_blueprint(groq_api); app.register_blueprint(gemini_api)
app.register_blueprint(microblog_api); app.register_blueprint(analytics_api)
app.register_blueprint(student_api); app.register_blueprint(study_api)
app.register_blueprint(classroom_api); app.register_blueprint(feedback_api)
app.register_blueprint(data_export_import_api); app.register_blueprint(joke_api)
app.register_blueprint(post_api); app.register_blueprint(titanic_api)

# --- 5. ROUTES ---

@app.route('/')
def index():
    # If the request asks for JSON, send the health check
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({"status": "online"}), 200
    # Otherwise show the home page
    return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username, password, email = data.get('username'), data.get('password'), data.get('email')
        hashed_pw = generate_password_hash(password)
        db_conn = get_sentri_db_connection()
        try:
            db_conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, hashed_pw, email))
            db_conn.commit()
            return jsonify({"message": "User registered"}), 201
        except: return jsonify({"message": "Error"}), 409
        finally: db_conn.close()
    return render_template("login.html") # Show login/register page for humans

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        username = data.get('username') or request.form.get('username')
        password = data.get('password') or request.form.get('password')

        db_conn = get_sentri_db_connection()
        user_row = db_conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db_conn.close()

        if user_row and check_password_hash(user_row['password'], password):
            # If it's a React request, return JSON
            if request.is_json:
                return jsonify({
                    "status": "success", 
                    "user": {"id": user_row['id'], "username": user_row['username'], "email": user_row['email']}
                }), 200
            
            # If it's a browser form request, use flask-login
            from model.user import User
            user_obj = User.query.get(user_row['id'])
            if user_obj:
                login_user(user_obj)
                return redirect(url_for('index'))

        if request.is_json:
            return jsonify({"status": "fail"}), 401
        return render_template("login.html", error="Invalid credentials")
        
    return render_template("login.html")

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

    db = get_sentri_db_connection()
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
        
    db = get_sentri_db_connection()
    # Fetch meetings for this specific ID
    rows = db.execute('SELECT * FROM user_meetings WHERE user_id = ? ORDER BY date ASC', (user_id,)).fetchall()
    db.close()
    
    meetings_list = [dict(row) for row in rows]
    return jsonify(meetings_list), 200

@app.route('/logout')
def logout():
    requests.session.clear()
    return redirect(url_for('login'))


@app.route('/send-chat-message', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    db_conn = get_sentri_db_connection()
    db_conn.execute('INSERT INTO program_chats (program_id, user_id, username, message) VALUES (?, ?, ?, ?)', 
                    (data.get('program_id'), data.get('user_id'), data.get('username'), data.get('message')))
    db_conn.commit()
    db_conn.close()
    return jsonify({"status": "success"}), 201

@app.route('/get-chat-history/<program_id>', methods=['GET'])
def get_chat_history(program_id):
    db_conn = get_sentri_db_connection()
    rows = db_conn.execute('SELECT * FROM program_chats WHERE program_id = ? ORDER BY timestamp ASC LIMIT 50', (program_id,)).fetchall()
    db_conn.close()
    return jsonify([dict(row) for row in rows]), 200

@app.route('/get-user-community-chats', methods=['GET'])
def get_user_community_chats():
    u_id = request.args.get('user_id')
    db_conn = get_sentri_db_connection()
    rows = db_conn.execute('SELECT * FROM program_chats WHERE user_id = ? ORDER BY timestamp DESC', (u_id,)).fetchall()
    db_conn.close()
    return jsonify([dict(row) for row in rows]), 200

# --- 6. STARTUP ---
with app.app_context():
    init_sentri_db()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8323
    CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
    app.run(debug=True, host=host, port=port, use_reloader=False)
