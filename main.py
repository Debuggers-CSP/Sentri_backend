# --- ORIGINAL main.py IMPORTS ---
from datetime import datetime
from urllib.parse import urljoin, urlparse
from flask import abort, redirect, render_template, request, send_from_directory, url_for, jsonify, current_app, g 
from flask_login import current_user, login_user, logout_user
from flask.cli import AppGroup
from flask_login import current_user, login_required
from flask import current_app
from dotenv import load_dotenv
import os
import requests
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob

# import "objects" from "this" project
from __init__ import app, db, login_manager  

# --- NEW: SENTRI DATABASE LOGIC (from your app.py) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENTRI_DB_PATH = os.path.join(BASE_DIR, 'prc_crisis.db')

def get_sentri_db_connection():
    conn = sqlite3.connect(SENTRI_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sentri_db():
    db_conn = get_sentri_db_connection()
    # Create chat table
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
    # Ensure logs table exists (from your app.py)
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

# --- SENTRI TRIAGE ENGINE (from your app.py) ---
def get_empathetic_response(sentiment, severity):
    responses = {
        "EMERGENCY": {"msg": "🚨 CRITICAL: Medical emergency. Please use the dial button below.", "link": "https://powayrecoverycenter.org/contact-us/"},
        "DISTRESSED": {"msg": "😤 You don't have to carry this weight alone.", "link": "https://powayrecoverycenter.org/"},
        "STABLE": {"msg": "🌿 Thank you for checking in.", "link": "https://powayrecoverycenter.org/resources/"}
    }
    if severity == "EMERGENCY": return responses["EMERGENCY"]
    return responses["DISTRESSED"] if sentiment < 0 else responses["STABLE"]

def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity 
    recommendations = []
    severity = "Stable"
    critical_keywords = ["breathe", "chest pain", "overdose", "die", "kill", "hurt", "suicide", "hospital"]
    if any(word in user_input.lower() for word in critical_keywords):
        severity = "EMERGENCY"
        sentiment = -1.0
    elif sentiment < 0:
        severity = "DISTRESSED"
    for prog in program_data:
        if any(kw in user_input.lower() for kw in prog['keywords'].split(", ")):
            recommendations.append({"name": prog['name'], "url": prog['url']})
    return {"severity": severity, "sentiment": sentiment, "paths": recommendations, "ai_response": get_empathetic_response(sentiment, severity)}

# --- REGISTER BLUEPRINTS & ORIGINAL ROUTES ---
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

app.register_blueprint(python_exec_api)
app.register_blueprint(javascript_exec_api)
app.register_blueprint(user_api)
app.register_blueprint(section_api)
app.register_blueprint(persona_api)
app.register_blueprint(pfp_api) 
app.register_blueprint(groq_api)
app.register_blueprint(gemini_api)
app.register_blueprint(microblog_api)
app.register_blueprint(analytics_api)
app.register_blueprint(student_api)
app.register_blueprint(study_api)
app.register_blueprint(classroom_api)
app.register_blueprint(feedback_api)
app.register_blueprint(data_export_import_api)
app.register_blueprint(joke_api)
app.register_blueprint(post_api)
app.register_blueprint(titanic_api)

# --- NEW SENTRI ROUTES (Integrated) ---

@app.route('/register', methods=['POST'])
def sentri_register():
    data = request.get_json()
    username, password, email = data.get('username'), data.get('password'), data.get('email')
    if not username or not password: return jsonify({"message": "Username and password required"}), 400
    hashed_pw = generate_password_hash(password)
    db_conn = get_sentri_db_connection()
    try:
        db_conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', (username, hashed_pw, email))
        db_conn.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except sqlite3.IntegrityError: return jsonify({"message": "Username already exists!"}), 409
    finally: db_conn.close()

@app.route('/login', methods=['POST']) # Overwrites old main.py login for React
def sentri_login():
    data = request.get_json(silent=True) or {}
    username, password = data.get('username'), data.get('password')
    db_conn = get_sentri_db_connection()
    user_row = db_conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    db_conn.close()
    if user_row and check_password_hash(user_row['password'], password):
        return jsonify({"status": "success", "user": {"id": user_row['id'], "username": user_row['username'], "email": user_row['email']}}), 200
    return jsonify({"status": "fail", "message": "Invalid credentials"}), 401

@app.route('/send-chat-message', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    p_id, u_id, msg, u_name = data.get('program_id'), data.get('user_id'), data.get('message'), data.get('username')
    db_conn = get_sentri_db_connection()
    try:
        db_conn.execute('INSERT INTO program_chats (program_id, user_id, username, message) VALUES (?, ?, ?, ?)', (p_id, u_id, u_name, msg))
        db_conn.commit()
        return jsonify({"status": "success"}), 201
    finally: db_conn.close()

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

# (Add other routes like /add-meeting, /get-user-meetings here if needed...)

# --- ORIGINAL main.py APP STARTUP ---
if __name__ == "__main__":
    with app.app_context():
        from hacks.jokes import initJokes
        initJokes()
        init_sentri_db() # Initialize Sentri tables
    
    host = "0.0.0.0"
    port = app.config.get('FLASK_PORT', 8323)
    print(f"** Server running: http://localhost:{port}")
    app.run(debug=True, host=host, port=port, use_reloader=False)