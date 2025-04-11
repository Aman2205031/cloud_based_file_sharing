import sqlite3

# Connect to the database
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Add the 'share_link' column if it doesn't already exist
cursor.execute("PRAGMA table_info(user_files);")
columns = [col[1] for col in cursor.fetchall()]
if "share_link" not in columns:
    cursor.execute("ALTER TABLE user_files ADD COLUMN share_link TEXT;")
    print("✅ Column 'share_link' added successfully.")
else:
    print("ℹ️ Column 'share_link' already exists.")

conn.commit()
conn.close()