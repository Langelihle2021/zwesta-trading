import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Get table info
cursor.execute("PRAGMA table_info(user_bots)")
columns = cursor.fetchall()
print("user_bots columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()
