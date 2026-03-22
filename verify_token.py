import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if the token exists
token = 'test-session-token-123'
cursor.execute('SELECT user_id, expires_at, is_active FROM user_sessions WHERE token = ? AND is_active = 1', (token,))
result = cursor.fetchone()

if result:
    print('✅ Token found!')
    print(f'  User: {result["user_id"]}')
    print(f'  Active: {result["is_active"]}')
    print(f'  Expires: {result["expires_at"]}')
else:
    print('❌ Token NOT found with that query')
    
# Check all tokens
print('\n📋 All tokens in database:')
cursor.execute('SELECT token, is_active FROM user_sessions LIMIT 10')
for row in cursor.fetchall():
    print(f'  Token: {row["token"][:30]}... Active: {row["is_active"]}')

conn.close()
