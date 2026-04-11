import sqlite3

path = r'C:\backend\zwesta_trading.db'
conn = sqlite3.connect(path)
cur = conn.cursor()
tables = ['user_bots', 'bot_strategies', 'bot_credentials', 'broker_credentials', 'user_sessions']
print('DB', path)
for t in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        print(t, cur.fetchone()[0])
    except Exception as e:
        print(t, 'ERROR', e)
conn.close()
