import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all sessions with details
cursor.execute('SELECT token, user_id, is_active, created_at, expires_at FROM user_sessions')
sessions = cursor.fetchall()

print(f'All sessions ({len(sessions)} total):')
for session in sessions:
    token = session["token"]
    user_id = session["user_id"]
    is_active = session["is_active"]
    print(f'  Token: {token[:30]}...')
    print(f'    User ID: {user_id}, Active: {is_active}')
    print()

conn.close()
