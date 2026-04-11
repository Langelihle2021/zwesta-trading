import sqlite3
import os

# Path to the database
db_path = r'C:\backend\zwesta_trading.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if password_hash column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'password_hash' not in columns:
        print("Adding password_hash column to users table...")
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
            conn.commit()
            print("✅ Successfully added password_hash column")
        except Exception as e:
            print(f"❌ Failed to add column: {e}")
    else:
        print("✅ password_hash column already exists")

    conn.close()
else:
    print(f"Database not found at {db_path}")