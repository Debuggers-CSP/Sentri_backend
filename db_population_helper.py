import sqlite3
import random
from datetime import datetime, timedelta

def populate_demo_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear old data for a fresh demo
    cursor.execute("DELETE FROM program_chats")
    cursor.execute("DELETE FROM logs")

    print("Populating professional recovery program data...")

    # --- PROGRAM SLUGS (Matching your React slugs) ---
    # Key: Slug, Value: (Program Name, list of role-players, specific topics)
    program_configs = {
        "aa": ("AA", ["Sponsor_Bill", "Dave_R", "Mary_W", "Newcomer_Mike"], 
               ["One day at a time.", "Is there a 12-step meeting tonight?", "Just got my 6-month chip!", "The Big Book really helped me today."]),
        
        "na": ("NA", ["Recovery_Jan", "Sponsor_Chris", "Leo_S", "Alex_K"], 
               ["Just for today.", "Recovery is possible.", "Anyone available for a call? Feeling triggered.", "Gratitude is the attitude."]),
        
        "aca": ("ACA", ["Counselor_Jane", "InnerChild_Focus", "Growth_Pat", "Sarah_M"], 
                ["Working through the laundry list.", "Focusing on reparenting today.", "I finally set a boundary with my family.", "Identifying my triggers from childhood."]),
        
        "alateen": ("Alateen", ["Peer_Mentor_Justin", "Chloe_99", "Jake_Free", "Support_Bot"], 
                    ["It's not my fault my parents drink.", "Found a great meeting for teens.", "School has been stressful but I'm staying strong.", "Does anyone want to talk?"]),
        
        "al-anon": ("Al-Anon", ["Family_Support_Sue", "Robert_L", "Boundary_Builder", "Peaceful_Heart"], 
                    ["Detaching with love.", "I am not responsible for their choices.", "Focusing on my own serenity today.", "Has anyone read the daily reader yet?"]),
        
        "ca": ("CA", ["CocaineAnon_Mod", "Tony_T", "Vegas_Recovery", "Clean_Slate"], 
               ["Staying away from the people, places, and things.", "The fellowship here is amazing.", "Anyone heading to the Friday night speaker meeting?", "Mind-altering substances are behind me."]),
        
        "ga": ("GA", ["Finances_First", "BetFree_Brian", "Amends_Alice", "Support_Leader"], 
               ["I didn't place a bet today.", "Making amends for my financial mistakes.", "The urge to gamble was high today but I called my sponsor.", "Step 4 is proving difficult but necessary."]),
        
        "sa": ("SA", ["Sobriety_Coach", "Healthy_Relat_101", "Member_XYZ", "Path_Forward"], 
               ["Working towards sexual sobriety.", "Focusing on healthy relationships.", "Today I chose self-care over old habits.", "The meeting tonight was very eye-opening."])
    }

    current_time = datetime.now()
    
    # Generate ~15 messages for EVERY program (Total 120+)
    for slug, config in program_configs.items():
        prog_name, users, messages = config
        
        for i in range(15):
            username = random.choice(users)
            user_id = random.randint(1000, 9999)
            
            # Mix specific topics with general support messages
            generic_support = [
                "Thanks for sharing that.",
                "I can really relate to what you're going through.",
                "Keep coming back, it works!",
                "Does anyone have the link for the Zoom session?",
                "Proud of everyone here."
            ]
            message = random.choice(messages + generic_support)
            
            # Randomize time over the last 3 days
            minutes_ago = random.randint(1, 4320)
            timestamp = (current_time - timedelta(minutes=minutes_ago)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO program_chats (program_id, user_id, username, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (slug, user_id, username, message, timestamp))

    # --- SENTIMENT LOGS ---
    log_samples = [
        (202, "I feel like I'm finally getting my life back.", 0.8),
        (505, "I am really struggling with cravings today.", -0.6),
        (707, "Found a great sponsor in the AA group.", 0.7),
        (909, "I hit rock bottom and need urgent help.", -0.9),
    ]

    for u_id, text, score in log_samples:
        cursor.execute('''
            INSERT INTO logs (user_id, user_text, sentiment_score, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (u_id, text, score, current_time.strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()
    print(f"Successfully populated database with slugs: {', '.join(program_configs.keys())}")