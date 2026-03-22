import sqlite3
import uuid
from datetime import datetime, timedelta

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

test_session_token = 'test-session-token-123'
test_user_id = 'test-user-001'

# First create test user if not exists
cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, email, name, created_at)
    VALUES (?, ?, ?, ?)
''', (test_user_id, 'test@example.com', 'Test User', datetime.now().isoformat()))

# Create session
session_id = str(uuid.uuid4())
expiry = (datetime.now() + timedelta(hours=24)).isoformat()

cursor.execute('''
    INSERT OR REPLACE INTO user_sessions (session_id, user_id, token, created_at, expires_at, ip_address, user_agent, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', (session_id, test_user_id, test_session_token, datetime.now().isoformat(), expiry, '127.0.0.1', 'test-client', 1))

conn.commit()

# Verify
cursor.execute('SELECT * FROM user_sessions WHERE token = ?', (test_session_token,))
session = cursor.fetchone()

conn.close()

if session:
    print('[OK] Test session created successfully')
    print(f'    User ID: {test_user_id}')
    print(f'    Session Token: {test_session_token}')
    print(f'    Session ID: {session_id}')
    print(f'    Expires: {expiry}')
else:
    print('[ERROR] Failed to create test session')
