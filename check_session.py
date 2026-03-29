import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get valid session tokens
cursor.execute('SELECT token, user_id, is_active FROM user_sessions WHERE is_active = 1 LIMIT 1')
session = cursor.fetchone()

if session:
    print(f'✅ Found active session:')
    print(f'   Token: {session["token"][:50]}...')
    print(f'   User ID: {session["user_id"]}')
    
    # Get user info
    cursor.execute('SELECT email, name FROM users WHERE user_id = ?', (session["user_id"],))
    user = cursor.fetchone()
    if user:
        print(f'   User: {user["email"]} ({user["name"]})')
else:
    print('❌ No active sessions found')

# Check broker credentials
cursor.execute('SELECT credential_id, broker_name, account_number, is_live, server FROM broker_credentials LIMIT 1')
cred = cursor.fetchone()
if cred:
    print(f'\n✅ Found broker credential:')
    print(f'   Broker: {cred["broker_name"]}')
    print(f'   Account: {cred["account_number"]}')
    print(f'   Mode: {"Live" if cred["is_live"] else "Demo"}')
    print(f'   Server: {cred["server"]}')

conn.close()
