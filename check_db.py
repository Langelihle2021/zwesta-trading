import sqlite3

db_path = r'C:\backend\zwesta_trading.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
output = []
output.append(f"Database: {db_path}")
output.append(f"Tables count: {len(tables)}")

if 'user_bots' in tables:
    cursor.execute('SELECT COUNT(*) FROM user_bots')
    count = cursor.fetchone()[0]
    output.append(f"Total bots: {count}")
    if count > 0:
        cursor.execute('SELECT id, user_id, bot_name FROM user_bots LIMIT 10')
        output.append("\nFirst 10 bots:")
        for row in cursor.fetchall():
            output.append(f"  - Bot ID {row[0]}: {row[2]} (User: {row[1]})")

conn.close()
for line in output:
    print(line)
