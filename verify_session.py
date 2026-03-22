import sqlite3
from datetime import datetime

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if session exists
test_token = 'test-session-token-123'
cursor.execute('''
    SELECT * FROM user_sessions WHERE token = ?
''', (test_token,))

session = cursor.fetchone()

if session:
    print('[OK] Session found in database')
    print(f'    Token: {session["token"]}')
    print(f'    User ID: {session["user_id"]}')
    print(f'    Created: {session["created_at"]}')
    print(f'    Expires: {session["expires_at"]}')
    print(f'    Active: {session["is_active"]}')
    
    # Check if it's expired
    expires_at = datetime.fromisoformat(session['expires_at'])
    now = datetime.now()
    
    print(f'\n   Now: {now}')
    print(f'   Expires: {expires_at}')
    print(f'   Is Expired: {expires_at < now}')
    print(f'   Time Until Expiry: {expires_at - now}')
else:
    print('[ERROR] Session not found')
    print('\n   All sessions in database:')
    cursor.execute('SELECT token, user_id, is_active FROM user_sessions')
    for row in cursor.fetchall():
        print(f'       {row["token"]} - {row["user_id"]} (Active: {row["is_active"]})')

conn.close()
