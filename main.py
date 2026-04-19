# --- IMPORTS ---
from datetime import datetime
from urllib.parse import urljoin, urlparse
from flask import abort, redirect, render_template, request, send_from_directory, url_for, jsonify, current_app, g
from flask_login import current_user, login_user, logout_user, login_required
from flask.cli import AppGroup
from dotenv import load_dotenv
import json
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

PROGRAMS = [
    {"program_id": "aa", "fullName": "Alcoholics Anonymous"},
    {"program_id": "aca", "fullName": "Adult Children of Alcoholics"},
    {"program_id": "alateen", "fullName": "Alateen Support Group"},
    {"program_id": "alanon", "fullName": "Al-Anon Family Groups"},
    {"program_id": "na", "fullName": "Narcotics Anonymous"},
    {"program_id": "ca", "fullName": "Cocaine Anonymous"},
    {"program_id": "ga", "fullName": "Gamblers Anonymous"},
    {"program_id": "sa", "fullName": "Sexaholics Anonymous"},
]


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


def _parse_joined_programs(raw_joined_program):
    if not raw_joined_program:
        return []

    raw_joined_program = raw_joined_program.strip()
    if not raw_joined_program:
        return []

    try:
        parsed = json.loads(raw_joined_program)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    return [value.strip() for value in raw_joined_program.split(',') if value.strip()]


def _get_user_joined_programs(db_conn, user_id):
    rows = db_conn.execute(
        'SELECT program_id FROM user_programs WHERE user_id = ? ORDER BY id ASC',
        (user_id,),
    ).fetchall()
    return [row['program_id'] for row in rows]


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

    # 1b. Create user_programs table for multi-program joins
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS user_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            program_id TEXT NOT NULL,
            UNIQUE(user_id, program_id)
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

    # 2b. Create program_reviews table
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS program_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            rating REAL NOT NULL,
            comment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2c. Create program_bulletin_notes table
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS program_bulletin_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            color TEXT DEFAULT '#DCFCE7',
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

    # Migrate existing users.joined_program into user_programs if present
    user_rows = db_conn.execute('SELECT id, joined_program FROM users').fetchall()
    for row in user_rows:
        for program_id in _parse_joined_programs(row['joined_program']):
            db_conn.execute(
                'INSERT OR IGNORE INTO user_programs (user_id, program_id) VALUES (?, ?)',
                (row['id'], program_id),
            )

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

        if user_row and check_password_hash(user_row['password'], password):
            print("\n--- DEBUG STEP 1: BACKEND DB CHECK ---")
            print(f"User found: {user_row['username']}")
            print(f"Fname in DB: {user_row['fname']}")
            print(f"Lname in DB: {user_row['lname']}")

            joined_programs = _get_user_joined_programs(db_conn, user_row['id'])
            joined_program_value = ','.join(joined_programs) if joined_programs else user_row['joined_program']

            db_conn.close()

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
                            "joined_program": joined_program_value,
                        },
                    }
                ), 200

            # If it's a browser form request, use flask-login
            user_obj = User.query.get(user_row['id'])
            if user_obj:
                login_user(user_obj)
                return redirect(url_for('index'))

        db_conn.close()

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


@app.route('/get-dashboard-summary/<int:user_id>', methods=['GET'])
def get_dashboard_summary(user_id):
    db_conn = get_sentri_db_connection()

    programs = []
    for program in PROGRAMS:
        last_message_row = db_conn.execute(
            '''
            SELECT message, timestamp
            FROM program_chats
            WHERE program_id = ?
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT 1
            ''',
            (program['program_id'],),
        ).fetchone()

        programs.append(
            {
                "program_id": program['program_id'],
                "fullName": program['fullName'],
                "last_message": {
                    "text": last_message_row['message'] if last_message_row else "",
                    "timestamp": last_message_row['timestamp'] if last_message_row else None,
                },
            }
        )

    meetings_rows = db_conn.execute(
        '''
        SELECT *
        FROM user_meetings
        WHERE user_id = ?
        ORDER BY datetime(
            CASE
                WHEN instr(time, '-') > 0 THEN date || ' ' || TRIM(substr(time, 1, instr(time, '-') - 1))
                ELSE date || ' ' || time
            END
        ) ASC
        ''',
        (user_id,),
    ).fetchall()

    db_conn.close()

    return jsonify({
        "programs": programs,
        "meetings": [dict(row) for row in meetings_rows],
    }), 200


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
        'SELECT id, username, email, fname, lname, joined_program FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()

    if user_row:
        user_data = dict(user_row)
        joined_programs = _get_user_joined_programs(db_conn, user_row['id'])
        user_data['joined_program'] = ','.join(joined_programs) if joined_programs else user_data.get('joined_program')
        db_conn.close()
        return jsonify(user_data), 200

    db_conn.close()
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
        user_row = db_conn.execute('SELECT id, joined_program FROM users WHERE id = ?', (user_id,)).fetchone()

        if not user_row:
            return jsonify({"message": "User not found"}), 404

        db_conn.execute(
            'INSERT OR IGNORE INTO user_programs (user_id, program_id) VALUES (?, ?)',
            (user_id, program_id),
        )

        joined_programs = _get_user_joined_programs(db_conn, user_id)
        joined_program_value = ','.join(joined_programs)

        db_conn.execute(
            'UPDATE users SET joined_program = ? WHERE id = ?',
            (joined_program_value, user_id),
        )
        db_conn.commit()

        return jsonify(
            {
                "status": "success",
                "message": f"Joined program '{program_id}' successfully",
                "joined_program": joined_program_value,
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

    if not user_id or not program_id:
        return jsonify({"message": "user_id and program_id are required"}), 400

    db_conn = get_sentri_db_connection()

    try:
        user_row = db_conn.execute(
            'SELECT id FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()

        if not user_row:
            return jsonify({"message": "User not found"}), 404

        db_conn.execute(
            'DELETE FROM user_programs WHERE user_id = ? AND program_id = ?',
            (user_id, program_id),
        )

        joined_programs = _get_user_joined_programs(db_conn, user_id)
        joined_program_value = ','.join(joined_programs) if joined_programs else None

        db_conn.execute('UPDATE users SET joined_program = ? WHERE id = ?', (joined_program_value, user_id))
        db_conn.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Left program successfully",
                "joined_program": joined_program_value,
            }
        ), 200

    except Exception as e:
        print(f"LEAVE PROGRAM ERROR: {e}")
        return jsonify({"message": "Failed to leave program"}), 500

    finally:
        db_conn.close()

# --- START: NEW BULLETIN BOARD AND REVIEW ROUTES ---

@app.route('/add-program-review', methods=['POST'])
def add_program_review():
    data = request.get_json()
    program_id = data.get('program_id')
    user_id = data.get('user_id')
    username = data.get('username')
    rating = data.get('rating')
    comment = data.get('comment')

    if not all([program_id, user_id, username, rating is not None, comment]):
        return jsonify({"message": "Missing required fields"}), 400

    db_conn = get_sentri_db_connection()
    try:
        cursor = db_conn.cursor()
        cursor.execute(
            '''
            INSERT INTO program_reviews (program_id, user_id, username, rating, comment)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (program_id, user_id, username, rating, comment)
        )
        new_review_id = cursor.lastrowid
        db_conn.commit()

        new_review_row = db_conn.execute(
            'SELECT * FROM program_reviews WHERE id = ?',
            (new_review_id,)
        ).fetchone()
        
        db_conn.close()

        if new_review_row:
            return jsonify(dict(new_review_row)), 201
        else:
            return jsonify({"status": "success", "id": new_review_id}), 201

    except Exception as e:
        db_conn.close()
        print(f"DATABASE ERROR (add_program_review): {e}")
        return jsonify({"message": "Database insertion failed"}), 500


@app.route('/get-program-reviews', methods=['GET'])
def get_program_reviews():
    program_id = request.args.get('program_id')
    if not program_id:
        return jsonify({"message": "program_id is required"}), 400

    db_conn = get_sentri_db_connection()
    rows = db_conn.execute(
        'SELECT * FROM program_reviews WHERE program_id = ? ORDER BY timestamp DESC',
        (program_id,),
    ).fetchall()
    db_conn.close()

    reviews_list = [dict(row) for row in rows]
    return jsonify(reviews_list), 200


@app.route('/add-program-bulletin-note', methods=['POST'])
def add_program_bulletin_note():
    data = request.get_json()
    program_id = data.get('program_id')
    user_id = data.get('user_id')
    username = data.get('username')
    message = data.get('message')
    color = data.get('color', '#fef08a') 

    if not all([program_id, user_id, username, message]):
        return jsonify({"message": "Missing required fields"}), 400

    db_conn = get_sentri_db_connection()
    try:
        cursor = db_conn.cursor()
        cursor.execute(
            '''
            INSERT INTO program_bulletin_notes (program_id, user_id, username, message, color)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (program_id, user_id, username, message, color)
        )
        new_note_id = cursor.lastrowid
        db_conn.commit()

        new_note_row = db_conn.execute(
            'SELECT * FROM program_bulletin_notes WHERE id = ?',
            (new_note_id,)
        ).fetchone()
        db_conn.close()
        
        if new_note_row:
            return jsonify(dict(new_note_row)), 201
        else:
            return jsonify({"status": "success", "id": new_note_id}), 201

    except Exception as e:
        db_conn.close()
        print(f"DATABASE ERROR (add_program_bulletin_note): {e}")
        return jsonify({"message": "Database insertion failed"}), 500


@app.route('/get-program-bulletin-notes', methods=['GET'])
def get_program_bulletin_notes():
    program_id = request.args.get('program_id')
    if not program_id:
        return jsonify({"message": "program_id is required"}), 400

    db_conn = get_sentri_db_connection()
    rows = db_conn.execute(
        'SELECT * FROM program_bulletin_notes WHERE program_id = ? ORDER BY timestamp DESC',
        (program_id,),
    ).fetchall()
    db_conn.close()

    notes_list = [dict(row) for row in rows]
    return jsonify(notes_list), 200

# --- END: NEW BULLETIN BOARD AND REVIEW ROUTES ---


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