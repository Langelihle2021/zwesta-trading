import sqlite3

conn = sqlite3.connect('C:\\backend\\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the most recently created bot
cursor.execute('SELECT bot_id, user_id, broker_account_id, symbols FROM user_bots ORDER BY created_at DESC LIMIT 1')
bot = cursor.fetchone()

if bot:
    print('Latest Bot:')
    print(f'  ID: {bot["bot_id"]}')
    print(f'  User: {bot["user_id"]}')
    print(f'  Account: {bot["broker_account_id"]}')
    print(f'  Symbols: {bot["symbols"]}')
    
    # Check if bot_credentials exists for this bot
    cursor.execute('SELECT credential_id FROM bot_credentials WHERE bot_id = ?', (bot['bot_id'],))
    cred = cursor.fetchone()
    if cred:
        print(f'  ✅ Credential ID: {cred["credential_id"]}')
    else:
        print('  ❌ ERROR: NO CREDENTIAL LINKED!')
else:
    print('❌ No bots found')

conn.close()
