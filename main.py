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
from db_population_helper import populate_demo_data

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

    # 1. Create users table
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            fname TEXT,
            lname TEXT,
            joined_program TEXT
        )
    ''')

    # 2. Create program_chats table
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

    # 3. Create logs table
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_text TEXT NOT NULL,
            sentiment_score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Create user_meetings table
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS user_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            location TEXT,
            type TEXT
        )
    ''')

    db_conn.commit()
    db_conn.close()

    # Trigger the population helper
    populate_demo_data(SENTRI_DB_PATH)


# --- 3. SENTRI TRIAGE ENGINE ---
def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity
    severity = "EMERGENCY" if any(w in user_input.lower() for w in ["suicide", "die", "overdose"]) else "Stable"
    return {"severity": severity, "sentiment": sentiment}


# --- 4. REGISTER BLUEPRINTS ---
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
from machinelearning.program_match_model import ProgramMatchModel

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

program_match_model = ProgramMatchModel()


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

        print("DEBUG: Received data from frontend:", data)

        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        fname = data.get('fname')
        lname = data.get('lname')

        print(f"DEBUG: Extracted fname: {fname}, lname: {lname}")
        hashed_pw = generate_password_hash(password)
        db_conn = get_sentri_db_connection()
        try:
            db_conn.execute(
                'INSERT INTO users (username, password, email, fname, lname) VALUES (?, ?, ?, ?, ?)',
                (username, hashed_pw, email, fname, lname),
            )
            db_conn.commit()
            return jsonify({"message": "User registered"}), 201
        except Exception:
            return jsonify({"message": "Error"}), 409
        finally:
            db_conn.close()

    return render_template("login.html")


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
            print("\n--- DEBUG STEP 1: BACKEND DB CHECK ---")
            print(f"User found: {user_row['username']}")
            print(f"Fname in DB: {user_row['fname']}")
            print(f"Lname in DB: {user_row['lname']}")

            # If it's a React request, return JSON
            if request.is_json:
                return jsonify(
                    {
                        "status": "success",
                        "user": {
                            "id": user_row['id'],
                            "username": user_row['username'],
                            "email": user_row['email'],
                            "fname": user_row['fname'],
                            "lname": user_row['lname'],
                            "joined_program": user_row['joined_program'],
                        },
                    }
                ), 200

            # If it's a browser form request, use flask-login
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

    print("\n--- RECEIVED MEETING DATA ---")
    print(data)

    user_id = data.get('user_id')
    name = data.get('name')
    date = data.get('date')
    time = data.get('time')
    location = data.get('location', 'N/A')
    m_type = data.get('type', 'Open')

    if not name:
        return jsonify({"message": "Error: Meeting name is missing in request"}), 400

    db_conn = get_sentri_db_connection()
    try:
        db_conn.execute(
            '''
            INSERT INTO user_meetings (user_id, name, date, time, location, type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''',
            (user_id, name, date, time, location, m_type),
        )
        db_conn.commit()
        return jsonify({"status": "success", "message": f"Added {name} to calendar"}), 201
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        return jsonify({"message": "Database insertion failed"}), 500
    finally:
        db_conn.close()


@app.route('/get-user-meetings', methods=['GET'])
def get_user_meetings():
    user_id = request.args.get('user_id')
    print(f"DEBUG: Fetching meetings for user_id: {user_id}")

    if not user_id:
        return jsonify({"message": "User ID is required"}), 400

    db_conn = get_sentri_db_connection()
    rows = db_conn.execute(
        'SELECT * FROM user_meetings WHERE user_id = ? ORDER BY date ASC',
        (user_id,),
    ).fetchall()
    db_conn.close()

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
    db_conn.execute(
        'INSERT INTO program_chats (program_id, user_id, username, message) VALUES (?, ?, ?, ?)',
        (data.get('program_id'), data.get('user_id'), data.get('username'), data.get('message')),
    )
    db_conn.commit()
    db_conn.close()
    return jsonify({"status": "success"}), 201


@app.route('/get-chat-history/<program_id>', methods=['GET'])
def get_chat_history(program_id):
    db_conn = get_sentri_db_connection()
    rows = db_conn.execute(
        'SELECT * FROM program_chats WHERE program_id = ? ORDER BY timestamp ASC LIMIT 50',
        (program_id,),
    ).fetchall()
    db_conn.close()
    return jsonify([dict(row) for row in rows]), 200


@app.route('/get-user-community-chats', methods=['GET'])
def get_user_community_chats():
    u_id = request.args.get('user_id')
    db_conn = get_sentri_db_connection()
    rows = db_conn.execute(
        'SELECT * FROM program_chats WHERE user_id = ? ORDER BY timestamp DESC',
        (u_id,),
    ).fetchall()
    db_conn.close()
    return jsonify([dict(row) for row in rows]), 200


@app.route('/get-user-details', methods=['GET'])
def get_user_details():
    user_id = request.args.get('user_id')
    db_conn = get_sentri_db_connection()
    user_row = db_conn.execute(
        'SELECT username, email, fname, lname, joined_program FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()
    db_conn.close()

    if user_row:
        return jsonify(dict(user_row)), 200
    return jsonify({"message": "User not found"}), 404


@app.route('/join-program', methods=['POST'])
def join_program():
    data = request.get_json(silent=True) or {}

    user_id = data.get('user_id')
    program_id = data.get('program_id')

    if not user_id or not program_id:
        return jsonify({"message": "user_id and program_id are required"}), 400

    db_conn = get_sentri_db_connection()

    try:
        # Make sure the joined_program column exists
        db_conn.execute('ALTER TABLE users ADD COLUMN joined_program TEXT')
        db_conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    try:
        user_row = db_conn.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()

        if not user_row:
            return jsonify({"message": "User not found"}), 404

        db_conn.execute(
            'UPDATE users SET joined_program = ? WHERE id = ?',
            (program_id, user_id),
        )
        db_conn.commit()

        return jsonify(
            {
                "status": "success",
                "message": f"Joined program '{program_id}' successfully",
                "joined_program": program_id,
            }
        ), 200

    except Exception as e:
        print(f"JOIN PROGRAM ERROR: {e}")
        return jsonify({"message": "Failed to join program"}), 500

    finally:
        db_conn.close()


@app.route('/leave-program', methods=['POST'])
def leave_program():
    data = request.get_json(silent=True) or {}

    user_id = data.get('user_id')
    program_id = data.get('program_id')

    if not user_id:
        return jsonify({"message": "user_id is required"}), 400

    db_conn = get_sentri_db_connection()

    try:
        user_row = db_conn.execute(
            'SELECT id, joined_program FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()

        if not user_row:
            return jsonify({"message": "User not found"}), 404

        if program_id and user_row['joined_program'] != program_id:
            return jsonify({"message": "User is not joined to that program"}), 409

        db_conn.execute('UPDATE users SET joined_program = NULL WHERE id = ?', (user_id,))
        db_conn.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Left program successfully",
                "joined_program": None,
            }
        ), 200

    except Exception as e:
        print(f"LEAVE PROGRAM ERROR: {e}")
        return jsonify({"message": "Failed to leave program"}), 500

    finally:
        db_conn.close()


@app.route('/api/ml/match', methods=['POST'])
def match_programs():
    payload = request.get_json(silent=True) or {}
    scores = program_match_model.predict_probabilities(payload)
    return jsonify(scores), 200


@app.route('/api/ml/match-programs', methods=['POST'])
def match_programs_legacy():
    payload = request.get_json(silent=True) or {}
    scores = program_match_model.predict_probabilities(payload)
    return jsonify({"match_scores": scores}), 200

# Add Meeting model
class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)

# Add bulk-load-meetings route
@app.route('/bulk-load-meetings', methods=['POST'])
def bulk_load_meetings():
    try:
        data = request.get_json()
        meetings = data.get('meetings', [])

        if not meetings:
            return jsonify({"error": "No meetings provided"}), 400

        for meeting in meetings:
            new_meeting = Meeting(
                name=meeting['name'],
                date=meeting['date'],
                time=meeting['time'],
                location=meeting['location'],
                type=meeting['type']
            )
            db.session.add(new_meeting)

        db.session.commit()
        return jsonify({"message": "Meetings successfully added"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 6. STARTUP ---
with app.app_context():
    init_sentri_db()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8323
    CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
    app.run(debug=True, host=host, port=port, use_reloader=False)