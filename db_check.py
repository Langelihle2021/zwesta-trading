import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# List tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print('Tables:', tables)

# List all bots
c.execute('SELECT * FROM bots')
bots = c.fetchall()
print(f'\n=== {len(bots)} BOTS ===')
for b in bots:
    d = dict(b)
    print(f"  ID: {d.get('bot_id','?')} | Name: {d.get('name','?')} | Status: {d.get('status','?')} | Symbols: {d.get('symbols','?')} | Trades: {d.get('total_trades',0)}")

# List credentials
c.execute('SELECT * FROM credentials')
creds = c.fetchall()
print(f'\n=== {len(creds)} CREDENTIALS ===')
for cr in creds:
    d = dict(cr)
    print(f"  ID: {d.get('credential_id','?')} | Broker: {d.get('broker','?')} | Account: {d.get('account_number','?')} | Server: {d.get('server','?')}")

conn.close()
