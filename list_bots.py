import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

cursor.execute('SELECT user_id, name FROM user_bots')
bots = cursor.fetchall()
print('All bots:')
for b in bots:
    print(b)

conn.close()