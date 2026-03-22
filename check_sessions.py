import sqlite3
from datetime import datetime

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Check user sessions
cursor.execute("SELECT COUNT(*) FROM user_sessions")
print(f"Total sessions: {cursor.fetchone()[0]}")

# Get the most recent sessions
cursor.execute("""
    SELECT user_id, session_token, is_active, created_at, last_activity 
    FROM user_sessions 
    ORDER BY last_activity DESC 
    LIMIT 5
""")

print("\nRecent sessions:")
for row in cursor.fetchall():
    print(f"  User: {row[0]}")
    print(f"  Token: {row[1][:50]}...")
    print(f"  Active: {row[2]}")
    print(f"  Last activity: {row[4]}")
    print()

conn.close()
