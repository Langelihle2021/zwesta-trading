#!/usr/bin/env python3
"""Check if backup has the bot data we need"""

import sqlite3
import os

backup_files = [
    r"C:\backend\trading_data - Copy.db",
    r"C:\backend\trading_data.db",
    r"C:\backend\trading_system.db",
]

for backup_path in backup_files:
    if not os.path.exists(backup_path):
        print(f"❌ Not found: {backup_path}\n")
        continue
    
    size = os.path.getsize(backup_path)
    if size == 0:
        print(f"❌ Empty (0 bytes): {backup_path}\n")
        continue
    
    print(f"✓ Checking: {backup_path} ({size:,} bytes)")
    
    try:
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()
        
        # Check for user_bots table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_bots'")
        if not cursor.fetchone():
            print("  ❌ No user_bots table\n")
            conn.close()
            continue
        
        # Count bots
        cursor.execute("SELECT COUNT(*) FROM user_bots")
        bot_count = cursor.fetchone()[0]
        print(f"  ✓ Found {bot_count} bots in this backup")
        
        if bot_count > 0:
            cursor.execute("SELECT bot_id, status, enabled, created_at FROM user_bots LIMIT 3")
            rows = cursor.fetchall()
            for row in rows:
                print(f"    - {row[0][:30]:30s} | Status: {row[1]:10s} | Enabled: {row[2]} | Created: {row[3][:10]}")
        
        # Count users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"  ✓ Found {user_count} users")
        
        # Count broker_credentials
        cursor.execute("SELECT COUNT(*) FROM broker_credentials")
        cred_count = cursor.fetchone()[0]
        print(f"  ✓ Found {cred_count} broker credentials")
        
        conn.close()
        print()  # Blank line
        
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
