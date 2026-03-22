import sqlite3

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cursor = conn.cursor()

# Check table schema
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()

print("📊 Users table schema:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Check a few users
print("\n📋 Sample users:")
cursor.execute('SELECT * FROM users LIMIT 3')
users = cursor.fetchall()
for user in users:
    print(f"  {user}")

conn.close()
