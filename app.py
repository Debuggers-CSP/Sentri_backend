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
    # Every response level now has a 'msg' and a 'link'
    responses = {
        "EMERGENCY": {
            "msg": "🚨 CRITICAL: We have detected a medical or safety emergency. Immediate intervention is required.",
            "link": "https://powayrecoverycenter.org/contact-us/",
            "label": "View PRC Emergency Info"
        },
        "FRUSTRATED": {
            "msg": "😤 It sounds like you're feeling a lot of pressure or anger right now. You don't have to fight this alone.",
            "link": "https://powayrecoverycenter.org/", # Mandatory Homepage link for general frustration
            "label": "Return to PRC Home"
        },
        "SAD": {
            "msg": "😔 I can feel the weight in your words. PRC is a community built on healing through connection.",
            "link": "https://powayrecoverycenter.org/about/",
            "label": "Learn About Our Community"
        },
        "STABLE": {
            "msg": "🌿 Thank you for checking in. Consistency is the key to a long-term journey. Explore our resources to stay strong.",
            "link": "https://powayrecoverycenter.org/resources/",
            "label": "Explore More Resources"
        }
    }
    
    if severity == "EMERGENCY":
        return responses["EMERGENCY"]
    elif sentiment < -0.4:
        return responses["FRUSTRATED"]
    elif sentiment < 0:
        return responses["SAD"]
    else:
        return responses["STABLE"]
    
def sos_triage_engine(user_input, program_data):
    analysis = TextBlob(user_input)
    sentiment = analysis.sentiment.polarity
    
    recommendations = []
    severity = "Stable"
    
    # 1. EMERGENCY KEYWORD DETECTION
    critical_keywords = ["breathe", "chest pain", "overdose", "die", "kill", "hurt", "suicide", "bleeding", "hospital"]
    if sentiment < -0.8 or any(word in user_input.lower() for word in critical_keywords):
        severity = "EMERGENCY"
        # Emergency doesn't need multi-path; it needs 911 (Handled in UI)
        res = get_empathetic_response(sentiment, severity)
        return {"severity": severity, "sentiment": sentiment, "paths": [], "ai_response": res}

    # 2. MULTI-PROGRAM MAPPING (The List logic)
    for prog in program_data:
        keywords = prog['keywords'].split(", ")
        if any(word in user_input.lower() for word in keywords):
            recommendations.append({
                "name": prog['name'],
                "url": prog['url'],
                "note": f"Direct link to {prog['name'].split(' ')[0]} support."
            })

    # 3. SET SEVERITY FOR NON-EMERGENCY
    if sentiment < 0:
        severity = "Distressed"
    
    # 4. GET THE MANDATORY AI RESPONSE & LINK
    res = get_empathetic_response(sentiment, severity)

    return {
        "severity": severity, 
        "sentiment": sentiment, 
        "paths": recommendations, 
        "ai_response": res
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
            triage_result = sos_triage_engine(user_text, programs_list)
            
            db.execute('INSERT INTO logs (user_id, user_text, sentiment_score) VALUES (?, ?, ?)',
                       (session['user_id'], user_text, triage_result['sentiment']))
            db.commit()

    # --- POWAY THEMED GAMIFICATION: THE EXPEDITION ---
    history = db.execute('SELECT * FROM logs WHERE user_id = ? ORDER BY timestamp DESC', 
                         (session['user_id'],)).fetchall()
    
    total_logs = len(history)
    
    # 1. Calculate Elevation (Progress up the mountain)
    # 0 logs = Lake Poway Trailhead | 15 logs = Potato Chip Rock Summit
    elevation = min(total_logs * 200, 2800) 
    
    if total_logs == 0:
        location = "Lake Poway Trailhead"
    elif total_logs < 5:
        location = "Blue Sky Reserve"
    elif total_logs < 12:
        location = "Mount Woodson Switchbacks"
    else:
        location = "Potato Chip Rock Summit"

    # 2. Trail Visibility (ML Sentiment Analysis)
    if total_logs > 0:
        avg_sentiment = sum([log['sentiment_score'] for log in history[:3]]) / len(history[:3])
    else:
        avg_sentiment = 0

    if avg_sentiment < -0.4:
        trail_env = {"status": "Rugged Storm", "color": "from-stone-700 to-stone-900", "icon": "⛈️", "msg": "The trail is steep and the chaparral is thick. Take it one step at a time."}
    elif avg_sentiment < 0:
        trail_env = {"status": "Morning Mist", "color": "from-[#8b7355] to-stone-500", "icon": "🌫️", "msg": "Visibility is low on the switchbacks. Lean on your PRC community."}
    else:
        trail_env = {"status": "Clear Skies", "color": "from-[#4a7c44] to-[#2d4f1e]", "icon": "☀️", "msg": "The 'City in the Country' is beautiful today. Your path is clear."}

    db.close()
    
    return render_template('dashboard.html', 
                           username=session['username'], 
                           history=history, 
                           triage=triage_result,
                           trail=trail_env,
                           elevation=elevation,
                           location=location)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)