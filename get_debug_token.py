import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the debug token
cursor.execute("SELECT token FROM user_sessions WHERE token LIKE 'debug%' LIMIT 1")
row = cursor.fetchone()
if row:
    debug_token = row["token"]
    print(f'Debug token: {debug_token}')
    
    # Get the user for this token
    cursor.execute("SELECT user_id FROM user_sessions WHERE token = ?", (debug_token,))
    user = cursor.fetchone()
    if user:
        print(f'User ID: {user["user_id"]}')
else:
    print('No debug token found')

conn.close()
