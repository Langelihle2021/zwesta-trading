import sqlite3

path = r'C:\backend\zwesta_trading.db'
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM user_sessions LIMIT 10')
rows = cur.fetchall()
for row in rows:
    print(dict(row))
conn.close()
