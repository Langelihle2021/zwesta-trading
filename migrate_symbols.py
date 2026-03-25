#!/usr/bin/env python3
import sqlite3

db_path = "c:\\backend\\zwesta_trading.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check current schema
cursor.execute("PRAGMA table_info(user_bots);")
columns = [col[1] for col in cursor.fetchall()]

print(f"Current user_bots columns: {columns}\n")

if 'symbols' not in columns:
    print("Adding 'symbols' column...")
    try:
        cursor.execute("ALTER TABLE user_bots ADD COLUMN symbols TEXT DEFAULT 'EURUSD'")
        conn.commit()
        print("✅ Column added!")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("✅ 'symbols' column already exists!")

conn.close()
