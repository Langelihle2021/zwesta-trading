import sqlite3
import re

path = r'C:\backend\zwesta_trading.db'
uid = '1323553f-1294-4280-9932-1c21a9c41879'
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
for table in tables:
    try:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if 'user_id' in cols:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (uid,))
            cnt = cur.fetchone()[0]
            if cnt:
                print(table, cnt)
    except Exception as e:
        pass
conn.close()
