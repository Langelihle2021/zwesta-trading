#!/usr/bin/env python3
"""Quick script to check broker credentials in database"""

import sqlite3
import sys

db_path = "c:/backend/broker_manager.db"

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check credentials table
    cursor.execute('''
        SELECT credential_id, user_id, broker_name, account_number, server, is_live, is_active
        FROM broker_credentials
        ORDER BY broker_name, account_number
    ''')
    
    print("=" * 100)
    print("BROKER CREDENTIALS IN DATABASE")
    print("=" * 100)
    
    creds = cursor.fetchall()
    if not creds:
        print("No credentials found!")
    else:
        print(f"{'ID':<36} | {'Broker':<15} | {'Account':<12} | {'Server':<25} | {'Live':<4} | {'Active':<6}")
        print("-" * 100)
        for row in creds:
            print(f"{row['credential_id']:<36} | {row['broker_name']:<15} | {row['account_number']:<12} | {(row['server'] or ''):<25} | {'Y' if row['is_live'] else 'N':<4} | {'Y' if row['is_active'] else 'N':<6}")
    
    # Check bots table
    cursor.execute('SELECT COUNT(*) as cnt FROM user_bots WHERE is_enabled = 1')
    bot_count = cursor.fetchone()['cnt']
    print(f"\n✅ Enabled bots: {bot_count}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
