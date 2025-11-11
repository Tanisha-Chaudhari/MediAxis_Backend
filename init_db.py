import sqlite3

conn = sqlite3.connect("mediaxis.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT,
    email TEXT UNIQUE,
    phone TEXT,
    password TEXT,
    reset_token TEXT,
    reset_expiry TEXT
)
""")

conn.commit()
conn.close()
print("✅ SQLite DB ready: mediaxis.db")
