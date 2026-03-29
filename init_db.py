import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'prc_crisis.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Ensure core tables exist
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE NOT NULL, 
                     email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER NOT NULL, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                  user_text TEXT NOT NULL, 
                  sentiment_score REAL,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')

    # 2. Re-initialize Programs with SPECIFIC slugs
    c.execute('DROP TABLE IF EXISTS prc_programs')
    c.execute('''CREATE TABLE prc_programs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT NOT NULL, 
                  url TEXT NOT NULL,
                  keywords TEXT)''')

    # Data mapped exactly to PRC sub-pages
    programs = [
        ("AA (Alcoholics Anonymous)", "https://powayrecoverycenter.org/aa/", "alcohol, drinking, beer, liquor, whiskey, wine, drunk, vodka, scotch"),
        ("NA (Narcotics Anonymous)", "https://powayrecoverycenter.org/na/", "drugs, pills, fentanyl, meth, heroin, speed, oxys, weed"),
        ("CA (Cocaine Anonymous)", "https://powayrecoverycenter.org/ca/", "cocaine, coke, snow, blow, crack, white"),
        ("GA (Gamblers Anonymous)", "https://powayrecoverycenter.org/ga/", "gambling, betting, money, cards, casino, lotto, debt"),
        ("ACA (Adult Children of Alcoholics)", "https://powayrecoverycenter.org/aca/", "childhood, parents, upbringing, trauma, family history"),
        ("Al-Anon (Family Support)", "https://powayrecoverycenter.org/al-anon/", "husband, wife, partner, spouse, son, daughter, someone else"),
        ("Alateen (Teen Support)", "https://powayrecoverycenter.org/alateen/", "teenager, young, high school, parents drinking, youth"),
        ("SAA (Sex Addicts Anonymous)", "https://powayrecoverycenter.org/saa/", "porn, sex, intimacy, relationship addiction")
    ]
    
    c.executemany('INSERT INTO prc_programs (name, url, keywords) VALUES (?, ?, ?)', programs)
    
    conn.commit()
    conn.close()
    print(f"✅ Success! PRC Deep Links initialized in: {DB_PATH}")

if __name__ == '__main__':
    init_db()