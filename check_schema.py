import sqlite3
import uuid
from datetime import datetime, timedelta

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Get table info
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print('Users table columns:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

cursor.execute("PRAGMA table_info(sessions)")
columns = cursor.fetchall()
print('\nSessions table columns:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

conn.close()
