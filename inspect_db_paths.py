import sqlite3
import os

for path in [r'C:\backend\zwesta_trading.db', r'C:\Users\zwexm\zwesta_trading.db']:
    print('DB', path, 'exists', os.path.exists(path))
    if not os.path.exists(path):
        continue
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        print('TABLES =', [row['name'] for row in cur.fetchall()])
    except Exception as e:
        print('TABLES ERROR', e)
    for q, label in [
        ("SELECT COUNT(*) as c FROM users;", 'USERS_COUNT'),
        ("SELECT COUNT(*) as c FROM user_bots;", 'BOTS_COUNT'),
        ("SELECT COUNT(*) as c FROM user_preferences;", 'PREFERENCES_COUNT'),
    ]:
        try:
            cur.execute(q)
            print(label, cur.fetchone()['c'])
        except Exception as e:
            print(label, 'ERROR', e)
    try:
        cur.execute('SELECT * FROM user_preferences LIMIT 5')
        for row in cur.fetchall():
            print('PREF', dict(row))
    except Exception as e:
        print('PREF QUERY ERROR', e)
    conn.close()
    print()
