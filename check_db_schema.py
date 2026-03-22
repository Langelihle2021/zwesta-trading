import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)
print('bot_credentials exists:', 'bot_credentials' in tables)

# Check bot_credentials schema if it exists
if 'bot_credentials' in tables:
    cursor.execute("PRAGMA table_info(bot_credentials)")
    cols = cursor.fetchall()
    print('bot_credentials columns:', [col[1] for col in cols])
else:
    print("⚠️  bot_credentials table NOT FOUND!")

conn.close()
