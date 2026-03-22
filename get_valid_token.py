import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Get all active sessions
cursor.execute("""
    SELECT user_id, token, is_active, created_at
    FROM user_sessions 
    WHERE is_active = 1
    ORDER BY created_at DESC 
    LIMIT 10
""")

print("Active sessions:")
for row in cursor.fetchall():
    print(f"  User: {row[0]}")
    print(f"  Token: {row[1]}")
    print(f"  Active: {row[2]}")
    print()

conn.close()
