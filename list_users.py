import sqlite3

conn = sqlite3.connect('C:\\backend\\zwesta_trading.db')
cursor = conn.cursor()

cursor.execute('SELECT user_id, email FROM users')
users = cursor.fetchall()
print('Users:')
for u in users:
    print(u)

conn.close()