import sqlite3
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def populate_demo_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear old data for a fresh demo
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM user_programs")
    cursor.execute("DELETE FROM program_chats")
    cursor.execute("DELETE FROM program_reviews")
    cursor.execute("DELETE FROM program_bulletin_notes")
    cursor.execute("DELETE FROM logs")

    print("Populating Users, Reviews, Notes, and Chats...")

    # --- 1. CORE USERS ---
    # We create a set of consistent users to act as authors across all tables
    core_users = [
        {"id": 1, "username": "Sponsor_Bill", "fname": "Bill", "lname": "W", "email": "bill@recovery.org", "programs": ["aa", "alateen"]},
        {"id": 2, "username": "Recovery_Jan", "fname": "Jan", "lname": "S", "email": "jan@recovery.org", "programs": ["na", "ca"]},
        {"id": 3, "username": "Mary_W", "fname": "Mary", "lname": "W", "email": "mary@recovery.org", "programs": ["aa", "al-anon"]},
        {"id": 4, "username": "Newcomer_Mike", "fname": "Mike", "lname": "R", "email": "mike@recovery.org", "programs": ["aa", "ga"]},
        {"id": 5, "username": "Counselor_Jane", "fname": "Jane", "lname": "D", "email": "jane@recovery.org", "programs": ["aca", "sa"]},
        {"id": 6, "username": "Tony_T", "fname": "Tony", "lname": "V", "email": "tony@recovery.org", "programs": ["ca", "na"]},
    ]

    hashed_pw = generate_password_hash("password123")

    for u in core_users:
        # Insert into users table
        cursor.execute('''
            INSERT INTO users (id, username, password, email, fname, lname, joined_program)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (u['id'], u['username'], hashed_pw, u['email'], u['fname'], u['lname'], ",".join(u['programs'])))
        
        # Insert into user_programs link table
        for prog in u['programs']:
            cursor.execute('INSERT INTO user_programs (user_id, program_id) VALUES (?, ?)', (u['id'], prog))

    # --- 2. PROGRAM CONFIGURATION ---
    program_configs = {
        "aa": "Alcoholics Anonymous",
        "na": "Narcotics Anonymous",
        "aca": "Adult Children of Alcoholics",
        "alateen": "Alateen",
        "al-anon": "Al-Anon",
        "ca": "Cocaine Anonymous",
        "ga": "Gamblers Anonymous",
        "sa": "Sexaholics Anonymous"
    }

    current_time = datetime.now()

    # --- 3. POPULATE DATA PER PROGRAM ---
    for slug in program_configs.keys():
        # A. Random Chats (10 per program)
        chat_messages = [
            "One day at a time.", "Is there a meeting tonight?", "Just got my chip!", 
            "Feeling grateful today.", "Keep coming back, it works.", "Anyone want to grab coffee after?",
            "The steps are changing my life.", "Hard day, but stayed sober.", "Welcome to the newcomers!"
        ]
        
        for _ in range(10):
            user = random.choice(core_users)
            msg = random.choice(chat_messages)
            ts = (current_time - timedelta(minutes=random.randint(1, 3000))).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO program_chats (program_id, user_id, username, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (slug, user['id'], user['username'], msg, ts))

        # B. Program Reviews (2 per program)
        review_comments = [
            "Life saving fellowship. Highly recommend.",
            "The community here is so supportive and non-judgmental.",
            "Found a great sponsor within a week of joining.",
            "A bit crowded on Friday nights, but the energy is amazing.",
            "This program literally saved my family relationships."
        ]
        
        for _ in range(2):
            user = random.choice(core_users)
            comment = random.choice(review_comments)
            rating = random.choice([4.0, 4.5, 5.0])
            ts = (current_time - timedelta(days=random.randint(1, 10))).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO program_reviews (program_id, user_id, username, rating, comment, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (slug, user['id'], user['username'], rating, comment, ts))

        # C. Bulletin Notes (3 per program)
        note_messages = [
            "Service Opportunity: Need help setting up chairs on Tuesday!",
            "Daily Quote: Courage is not the absence of fear, but the mastery of it.",
            "Potluck next Saturday! Bring a dish to share.",
            "New Big Books available at the back desk.",
            "Reminder: We are a self-supporting community."
        ]
        colors = ["#fef08a", "#DCFCE7", "#E0F2FE", "#FFEDD5", "#F3E8FF"] # Yellow, Green, Blue, Orange, Purple

        for _ in range(3):
            user = random.choice(core_users)
            msg = random.choice(note_messages)
            color = random.choice(colors)
            ts = (current_time - timedelta(hours=random.randint(1, 48))).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO program_bulletin_notes (program_id, user_id, username, message, color, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (slug, user['id'], user['username'], msg, color, ts))

    # --- 4. SENTIMENT LOGS ---
    log_samples = [
        (1, "I feel like I'm finally getting my life back.", 0.8),
        (4, "I am really struggling with cravings today.", -0.6),
        (3, "Found a great sponsor in the AA group.", 0.7),
    ]

    for u_id, text, score in log_samples:
        cursor.execute('''
            INSERT INTO logs (user_id, user_text, sentiment_score, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (u_id, text, score, current_time.strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()
    print("Database population complete.")