import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT user_id, email, name FROM users')
users = cursor.fetchall()
print(f'Found {len(users)} users:')
for user in users:
    print(f'  - {user["email"]}: {user["name"]} ({user["user_id"]})')
conn.close()
