import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("All tables in database:")
for table in tables:
    print(f"  - {table[0]}")

conn.close()
