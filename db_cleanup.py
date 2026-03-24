import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check broker_credentials columns
c.execute("PRAGMA table_info(broker_credentials)")
cols = c.fetchall()
print("broker_credentials columns:")
for col in cols:
    print(f"  {col['name']} ({col['type']})")

print()
c.execute('SELECT * FROM broker_credentials')
creds = c.fetchall()
print(f'=== {len(creds)} CREDENTIALS ===')
for cr in creds:
    d = dict(cr)
    for k, v in d.items():
        if k != 'password':
            print(f"  {k}: {v}")
    print()

# Check trades columns  
c.execute("PRAGMA table_info(trades)")
cols = c.fetchall()
print("trades columns:")
for col in cols:
    print(f"  {col['name']} ({col['type']})")

print()
c.execute('SELECT COUNT(*) as cnt FROM trades')
print(f"Total trades: {c.fetchone()['cnt']}")

# Delete all user_bots
print("\n--- Deleting all existing bots ---")
c.execute('DELETE FROM user_bots')
conn.commit()
print(f"Deleted all bots. Remaining: ", end="")
c.execute('SELECT COUNT(*) as cnt FROM user_bots')
print(c.fetchone()['cnt'])

conn.close()
