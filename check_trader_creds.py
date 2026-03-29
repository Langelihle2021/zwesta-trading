import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

user_id = "23386f67-aeb4-4de2-98a7-33c1fced2755"
cursor.execute('SELECT credential_id, broker_name, account_number, is_live, server FROM broker_credentials WHERE user_id = ?', (user_id,))
creds = cursor.fetchall()
print(f'Found {len(creds)} broker credentials for trader2@example.com:')
for cred in creds:
    print(f'  - {cred["broker_name"]}: {cred["account_number"]} ({"Live" if cred["is_live"] else "Demo"}) on {cred["server"]}')

# Also get bots
cursor.execute('SELECT bot_id, is_live, broker_account_id, status FROM user_bots WHERE user_id = ?', (user_id,))
bots = cursor.fetchall()
print(f'\nFound {len(bots)} bots for trader2@example.com:')
for bot in bots:
    print(f'  - {bot["bot_id"]}: Account {bot["broker_account_id"]} ({"Live" if bot["is_live"] else "Demo"}) - Status: {bot["status"]}')

conn.close()
