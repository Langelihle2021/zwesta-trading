import sqlite3
from datetime import datetime, timedelta
import uuid

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Target user
user_id = "3a8f7a0c-4c68-4ace-97b3-221c1f971e29"

# First, ensure user exists
cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
if not cursor.fetchone():
    print(f"❌ User {user_id} does not exist!")
    conn.close()
    exit(1)

# Create a new session
session_id = str(uuid.uuid4())
token = f"test_token_{uuid.uuid4().hex[:32]}"
now = datetime.now().isoformat()
expires = (datetime.now() + timedelta(days=30)).isoformat()

cursor.execute("""
    INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, ip_address, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (session_id, user_id, token, now, expires, "127.0.0.1", 1))

conn.commit()
print(f"✅ Session created!")
print(f"User ID: {user_id}")
print(f"Token: {token}")
print(f"Use header: X-Session-Token={token}")

conn.close()
