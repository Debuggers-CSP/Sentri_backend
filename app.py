import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'prc_sos_secret_key'
CORS(app, supports_credentials=True)

# --- NEW: ABSOLUTE PATH LOGIC ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'prc_crisis.db')

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

    # IF THE USER SUBMITS THE TEXT BOX:
    if request.method == 'POST':
        user_text = request.form.get('user_text')
        if user_text:
            # Insert the log into the DB
            db.execute('INSERT INTO logs (user_id, user_text, sentiment_score) VALUES (?, ?, ?)',
                       (session['user_id'], user_text, 0.5)) # 0.5 is placeholder score
            db.commit()
            flash('Entry saved to your history!')

    # FETCH HISTORY TO SHOW ON SCREEN
    history = db.execute('SELECT * FROM logs WHERE user_id = ? ORDER BY timestamp DESC', 
                         (session['user_id'],)).fetchall()
    db.close()
    
    return render_template('dashboard.html', username=session['username'], history=history)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)