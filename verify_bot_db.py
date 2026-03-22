import sqlite3

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

bot_id = 'bot_1774130460891_3c5cae0f'

# Check if bot exists in database
cursor.execute('SELECT * FROM user_bots WHERE bot_id = ?', (bot_id,))
bot = cursor.fetchone()

if bot:
    print(f"✅ Bot found in database!")
    print(f"  Bot ID: {bot['bot_id']}")
    print(f"  User ID: {bot['user_id']}")
    print(f"  Name: {bot['name']}")
    print(f"  Strategy: {bot.get('strategy', 'N/A')}")
    print(f"  Status: {bot.get('status', 'N/A')}")
    print(f"  Symbols: {bot.get('symbols', 'N/A')}")
    print(f"  Created: {bot.get('created_at', 'N/A')}")
else:
    print(f"❌ Bot NOT found in database")

conn.close()
