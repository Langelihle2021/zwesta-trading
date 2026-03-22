import sqlite3
from datetime import datetime, timedelta
import uuid

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Use existing user
existing_user_id = '6531812c-ae51-4f53-b16a-a346aae873a1'

print(f"🔄 Linking credentials and sessions to existing user: {existing_user_id}\n")

# Check if this user already has a broker credential
cursor.execute('SELECT credential_id FROM broker_credentials WHERE user_id = ?', (existing_user_id,))
existing_cred = cursor.fetchone()

credential_id = None
if existing_cred:
    credential_id = existing_cred['credential_id']
    print(f"✅ User already has credential: {credential_id}")
else:
    # Create new credential for this user
    credential_id = str(uuid.uuid4())
    try:
        cursor.execute('''
            INSERT INTO broker_credentials (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (credential_id, existing_user_id, 'Exness', '298997455', 'Zwesta@1985', 'Exness-MT5Trial9', 0, datetime.now().isoformat()))
        conn.commit()
        print(f"✅ Created new credential: {credential_id}")
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()

# Check if user has a session
cursor.execute('SELECT token FROM user_sessions WHERE user_id = ? AND is_active = 1', (existing_user_id,))
existing_session = cursor.fetchone()

session_token = None
if existing_session:
    session_token = existing_session['token']
    print(f"✅ User already has session token: {session_token[:40]}...")
else:
    # Create new session for this user
    session_token = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    try:
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, existing_user_id, session_token, datetime.now().isoformat(), 
              (datetime.now() + timedelta(days=30)).isoformat(), 1))
        conn.commit()
        print(f"✅ Created new session token: {session_token[:40]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()

print(f"\n🎯 Use these for bot creation:")
print(f"  Credential ID: {credential_id}")
print(f"  Session Token: {session_token}")
print(f"  User ID: {existing_user_id}")

conn.close()
