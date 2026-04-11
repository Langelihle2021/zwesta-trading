import sqlite3
import os

def print_rows(cur, query, label):
    print('---', label, '---')
    try:
        cur.execute(query)
        rows = cur.fetchall()
        if rows:
            for row in rows:
                print(dict(row))
        else:
            print('(none)')
    except Exception as e:
        print('ERROR', query, e)

path = r'C:\backend\zwesta_trading.db'
print('DB', path, 'exists', os.path.exists(path))
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
print_rows(cur, "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%';", 'TABLES')
print_rows(cur, 'SELECT * FROM user_trading_settings LIMIT 20;', 'TRADING_SETTINGS')
print_rows(cur, 'SELECT * FROM user_bots LIMIT 20;', 'BOTS')
print_rows(cur, 'SELECT user_id, email, name FROM users LIMIT 20;', 'USERS')
print_rows(cur, 'SELECT * FROM user_trading_settings LIMIT 20;', 'TRADING_SETTINGS')
print_rows(cur, 'SELECT * FROM user_bots LIMIT 20;', 'BOTS')
conn.close()
