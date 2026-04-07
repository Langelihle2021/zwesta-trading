import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()
cursor.execute('SELECT user_id FROM users LIMIT 1')
result = cursor.fetchone()
print('User ID:', result[0] if result else 'None')
conn.close()