import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Get tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)

# Check user_sessions
if 'user_sessions' in tables:
    cursor.execute('PRAGMA table_info(user_sessions)')
    cols = [row[1] for row in cursor.fetchall()]
    print('user_sessions columns:', cols)

    # Get latest session
    cursor.execute('SELECT * FROM user_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', ('23386f67-aeb4-4de2-98a7-33c1fced2755',))
    result = cursor.fetchone()
    if result:
        print('Latest session:', dict(zip(cols, result)))
    else:
        print('No sessions found')

conn.close()