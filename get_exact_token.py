import sqlite3
conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the exact token value
cursor.execute("SELECT token FROM user_sessions WHERE user_id = 'test-user-001' LIMIT 1")
row = cursor.fetchone()
if row:
    exact_token = row["token"]
    print(f'Exact token: "{exact_token}"')
    print(f'Token length: {len(exact_token)}')
    print(f'Token repr: {repr(exact_token)}')

conn.close()
