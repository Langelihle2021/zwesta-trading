import sqlite3

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if test-user-001 has active sessions
cursor.execute('SELECT token, is_active, expires_at FROM user_sessions WHERE user_id = ? AND is_active = 1 LIMIT 3', ('test-user-001',))
rows = cursor.fetchall()

if rows:
    print(f"✅ Found {len(rows)} active session(s) for test-user-001:")
    for row in rows:
        print(f"  Token: {row['token'][:40]}...")
        print(f"  Expires: {row['expires_at']}")
else:
    print("❌ No active sessions for test-user-001")
    print("\n📋 Creating one now...")
    
    import uuid
    from datetime import datetime, timedelta
    
    token = "test-backend-token"
    session_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    
    try:
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, 'test-user-001', token, created_at, expires_at, 1))
        
        conn.commit()
        print(f"✅ Created session token: {token}")
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        conn.rollback()

conn.close()
