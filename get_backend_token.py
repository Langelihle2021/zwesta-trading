import sqlite3

# Get session from backend database
db_path = r'C:\backend\zwesta_trading.db'

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get a session token
    cursor.execute("SELECT token, user_id, is_active FROM user_sessions WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        token = row["token"]
        user_id = row["user_id"]
        print(f'Backend DB Session:')
        print(f'  Token: {token}')
        print(f'  User ID: {user_id}')
    else:
        print('No active sessions found in backend database')
    
    conn.close()
except FileNotFoundError:
    print(f'Database not found at {db_path}')
    print('Trying to create directory...')
    import os
    os.makedirs('C:\\backend', exist_ok=True)
    print('Created C:\\backend directory')
except Exception as e:
    print(f'Error: {e}')
