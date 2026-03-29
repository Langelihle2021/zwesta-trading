import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all bots and their users
cursor.execute('SELECT bot_id, user_id FROM user_bots')
bots = cursor.fetchall()
print(f'All bots:')
for bot in bots:
    user_id = bot["user_id"]
    bot_id = bot["bot_id"]
    
    # Get user info
    cursor.execute('SELECT email, name, password_hash FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        has_pass = "YES" if user["password_hash"] else "NO"
        print(f'  - {bot_id}: {user["email"]} ({user_id}) [has password: {has_pass}]')
    else:
        print(f'  - {bot_id}: Unknown user {user_id}')

conn.close()
