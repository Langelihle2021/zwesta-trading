import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# First check user_sessions schema
cursor.execute("PRAGMA table_info(user_sessions)")
columns = cursor.fetchall()
print('user_sessions table columns:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

conn.close()
