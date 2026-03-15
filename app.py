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

# --- AP CSP PROCEDURE: The Intelligent Triage Engine ---
def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity
    
    # We use a LIST to store multiple recommendations (AP CSP Requirement)
    recommendations = []
    severity = "Stable"
    
    # EMERGENCY DETECTION (Top Priority)
    emergency_keywords = ["overdose", "suicide", "hurt", "hospital", "kill", "die", "seizure"]
    if sentiment < -0.7 or any(word in user_input.lower() for word in emergency_keywords):
        severity = "EMERGENCY"
        recommendations.append({
            "name": "IMMEDIATE MEDICAL HELP",
            "url": "https://powayrecoverycenter.org/contact-us/",
            "note": "Please call 911 or go to the nearest ER immediately."
        })
        return {"severity": severity, "paths": recommendations}

    # MULTI-SUBSTANCE MAPPING
    for prog in program_data:
        keywords = prog['keywords'].split(", ")
        # Selection logic to see if user text matches this specific program
        if any(word in user_input.lower() for word in keywords):
            recommendations.append({
                "name": prog['name'],
                "url": prog['url'],
                "note": f"Based on your mention of {prog['name'].split(' ')[0]}."
            })

    # If nothing matched but sentiment is low
    if not recommendations and sentiment < 0:
        severity = "Needs Support"
        recommendations.append({
            "name": "General Recovery Support",
            "url": "https://powayrecoverycenter.org/about/",
            "note": "We recommend starting with a general about page to learn more."
        })

    return {"severity": severity, "paths": recommendations}


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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        
        db = get_db_connection()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
            db.commit()
            db.close()
            print(f"DEBUG: User {username} registered successfully.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            db.close()
            flash('Username already exists!')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = get_db_connection()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            print(f"DEBUG: User {username} logged in.")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
            
    return render_template('login.html')

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
            
            # RUN THE TRIAGE PROCEDURE
            triage_result = sos_triage_engine(user_text, programs_list)
            
            # SAVE HISTORY
            db.execute('INSERT INTO logs (user_id, user_text, sentiment_score) VALUES (?, ?, ?)',
                       (session['user_id'], user_text, TextBlob(user_text).sentiment.polarity))
            db.commit()

    history = db.execute('SELECT * FROM logs WHERE user_id = ? ORDER BY timestamp DESC', 
                         (session['user_id'],)).fetchall()
    db.close()
    
    return render_template('dashboard.html', username=session['username'], history=history, triage=triage_result)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)