import sqlite3
from datetime import datetime, timedelta
import uuid

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Use existing test user
user_id = "test-user-001"

# Create a new session
session_id = str(uuid.uuid4())
token = f"debug_token_{uuid.uuid4().hex[:32]}"
now = datetime.now().isoformat()
expires = (datetime.now() + timedelta(days=30)).isoformat()

cursor.execute("""
    INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, ip_address, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (session_id, user_id, token, now, expires, "127.0.0.1", 1))

conn.commit()
print(f"✅ Session created for test user!")
print(f"User ID: {user_id}")
print(f"Token: {token}")
print()
print(f"Use this header in API requests:")
print(f"X-Session-Token: {token}")

conn.close()
