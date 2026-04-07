import sqlite3

try:
    conn = sqlite3.connect(r'c:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables:", tables)
    
    # Count bots
    cursor.execute("SELECT COUNT(*) FROM user_bots")
    bot_count = cursor.fetchone()[0]
    print("Bot count:", bot_count)
    
    # Show first few bots
    cursor.execute("SELECT bot_id, bot_name, status FROM user_bots LIMIT 5")
    bots = cursor.fetchall()
    print("\nFirst 5 bots:")
    for bot in bots:
        print(f"  - {bot[0]}: {bot[1]} ({bot[2]})")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
