import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# List all user_bots
c.execute('SELECT * FROM user_bots')
bots = c.fetchall()
print(f'=== {len(bots)} USER BOTS ===')
for b in bots:
    d = dict(b)
    print(f"  ID: {d.get('bot_id','?')}")
    print(f"    Name: {d.get('name','?')} | Status: {d.get('status','?')}")
    print(f"    Symbols: {d.get('symbols','?')} | Trades: {d.get('total_trades',0)}")
    print(f"    Enabled: {d.get('enabled','?')}")
    print()

# List credentials
c.execute('SELECT credential_id, broker, account_number, server, is_live FROM broker_credentials')
creds = c.fetchall()
print(f'=== {len(creds)} CREDENTIALS ===')
for cr in creds:
    d = dict(cr)
    print(f"  ID: {d.get('credential_id','?')} | Broker: {d.get('broker','?')} | Account: {d.get('account_number','?')} | Server: {d.get('server','?')} | Live: {d.get('is_live','?')}")

# List trades
c.execute('SELECT COUNT(*) as cnt FROM trades')
trade_count = c.fetchone()['cnt']
print(f'\n=== {trade_count} RECORDED TRADES ===')
if trade_count > 0:
    c.execute('SELECT * FROM trades ORDER BY rowid DESC LIMIT 5')
    for t in c.fetchall():
        d = dict(t)
        print(f"  {d.get('symbol','?')} | {d.get('order_type','?')} | Vol: {d.get('volume','?')} | Profit: {d.get('profit','?')} | Time: {d.get('created_at','?')}")

conn.close()
