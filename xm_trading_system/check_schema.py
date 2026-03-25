import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Check users table columns
cursor.execute("PRAGMA table_info(users)")
users_columns = cursor.fetchall()
print("Columns in users table:")
for col in users_columns:
    print(f"  - {col[1]} ({col[2]})")

print("\n" + "="*50 + "\n")

# Check mt5_credentials table columns
cursor.execute("PRAGMA table_info(mt5_credentials)")
mt5_columns = cursor.fetchall()
print("Columns in mt5_credentials table:")
for col in mt5_columns:
    print(f"  - {col[1]} ({col[2]})")

print("\n" + "="*50 + "\n")

# Check profit_alerts table columns
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profit_alerts'")
if cursor.fetchone():
    cursor.execute("PRAGMA table_info(profit_alerts)")
    profit_columns = cursor.fetchall()
    print("Columns in profit_alerts table:")
    for col in profit_columns:
        print(f"  - {col[1]} ({col[2]})")
else:
    print("profit_alerts table does NOT exist")

conn.close()
