#!/usr/bin/env python3
import sqlite3
import os

# Check parent database
parent_db = r'c:\zwesta-trader\zwesta_trading.db'
flutter_db = r'c:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db'

print(f"Parent DB exists: {os.path.exists(parent_db)}")
print(f"Flutter DB exists: {os.path.exists(flutter_db)}")
print()

# Check parent database
try:
    conn = sqlite3.connect(parent_db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM user_bots')
    count = cur.fetchone()[0]
    print(f'✓ Parent DB: {count} bots')
    
    if count > 0:
        cur.execute('SELECT bot_id, name, created_at FROM user_bots LIMIT 5')
        for row in cur.fetchall():
            print(f"  - {row[1]} ({row[0]})")
    conn.close()
except Exception as e:
    print(f'✗ Parent DB error: {e}')

print()

# Check Flutter app database  
try:
    conn = sqlite3.connect(flutter_db)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM user_bots')
    count = cur.fetchone()[0]
    print(f'✓ Flutter DB: {count} bots')
    
    if count > 0:
        cur.execute('SELECT bot_id, name, created_at FROM user_bots LIMIT 5')
        for row in cur.fetchall():
            print(f"  - {row[1]} ({row[0]})")
    conn.close()
except Exception as e:
    print(f'✗ Flutter DB error: {e}')
