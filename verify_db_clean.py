import sqlite3

# Clean up test bot
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Delete test bot
cursor.execute("DELETE FROM user_bots WHERE bot_id = 'test_bot_12345'")
conn.commit()

# Check total bots
cursor.execute("SELECT COUNT(*) FROM user_bots")
total = cursor.fetchone()[0]
print(f"Total bots BEFORE new creation attempt: {total}")

# List any bots
cursor.execute("SELECT bot_id, name FROM user_bots LIMIT 10")
bots = cursor.fetchall()
print(f"\nExisting bots:")
for bot in bots:
    print(f"  - {bot[1]} ({bot[0]})")

conn.close()
