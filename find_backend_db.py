import sqlite3

# Try different possible database locations
db_paths = [
    r'C:\zwesta-trader\Zwesta Flutter App\backend.db',
    r'C:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db',
    r'C:\backend\zwesta_trading.db'
]

for db_path in db_paths:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if user_sessions table exists
        cursor.execute("SELECT count(*) FROM user_sessions")
        count = cursor.fetchone()[0]
        
        print(f'✅ {db_path}: {count} sessions')
        
        # Get first session
        cursor.execute("SELECT token, user_id, is_active FROM user_sessions LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f'  First session token: {row["token"][:30]}...')
        
        conn.close()
    except Exception as e:
        print(f'❌ {db_path}: {e}')

