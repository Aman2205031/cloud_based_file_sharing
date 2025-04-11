from flask import Flask, session
from flask_session import Session
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # You can use a fixed secure key in production

# Optional (depending on session storage)
app.config['SESSION_TYPE'] = 'filesystem'  # Add this for safer file-based sessions
Session(app)  # Initialize Flask-Session

def init_db():
    """Initializes the database by creating necessary tables."""
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Create users tablez
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)
        # Create messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Create files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            uploader TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Create user_files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT,
            share_link TEXT
        )
        """)
        conn.commit()

def get_files_for_user(username):
    """Fetch files and their upload timestamps for a specific user from the database."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename, uploaded_at FROM user_files WHERE username = ?", (username,))
    rows = cursor.fetchall()
    conn.close()
    
    # Return list of dictionaries with filename and uploaded_at
    return [{"filename": row[0], "uploaded_at": row[1]} for row in rows]

def save_file_for_user(user_id, filename, filepath):
    """Save file information for a specific user in the database."""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO user_files (user_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
        (user_id, filename, filepath, uploaded_at)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
