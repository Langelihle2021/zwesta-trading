import sqlite3

flutter_db = r'c:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db'

conn = sqlite3.connect(flutter_db)
cur = conn.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables in Flutter App database:")
for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cur.fetchone()[0]
    print(f"  {table[0]}: {count} rows")

conn.close()
