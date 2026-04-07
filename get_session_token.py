import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()
cursor.execute('SELECT session_token FROM user_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', ('23386f67-aeb4-4de2-98a7-33c1fced2755',))
result = cursor.fetchone()
print('Session Token:', result[0] if result else 'None')
conn.close()