#!/usr/bin/env python3
"""Diagnose why bots stopped trading on March 27-28, 2026"""

import os
import sqlite3
from datetime import datetime, timedelta

# Check backend file
backend_path = r"C:\zwesta-trader\Zwesta Flutter App\multi_broker_backend_updated.py"
print(f"✓ Backend exists: {os.path.exists(backend_path)}")

# Check database
db_path = r"C:\backend\zwesta_trading.db"
print(f"✓ Database exists: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check active bots
        print("\n=== BOTS STATUS ===")
        cursor.execute("""
            SELECT bot_id, user_id, status, enabled, symbols, created_at 
            FROM user_bots 
            ORDER BY created_at DESC 
            LIMIT 15
        """)
        rows = cursor.fetchall()
        print(f"Total bots in database: {len(rows)}\n")
        
        for row in rows:
            created = row['created_at'][:10] if row['created_at'] else 'N/A'
            print(f"  Bot: {row['bot_id'][:20]:20s} | Status: {row['status']:10s} | Enabled: {row['enabled']} | Created: {created}")
            print(f"       Symbols: {row['symbols']}")
        
        # Check bots from yesterday
        print("\n=== YESTERDAY'S BOTS (March 27) ===")
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT bot_id, status, enabled FROM user_bots 
            WHERE created_at LIKE ? 
            ORDER BY created_at DESC
        """, (f'{yesterday}%',))
        yesterday_bots = cursor.fetchall()
        print(f"Created yesterday: {len(yesterday_bots)}")
        for bot in yesterday_bots:
            print(f"  {bot['bot_id'][:30]:30s} | {bot['status']:10s} | Enabled: {bot['enabled']}")
        
        # Check credentials
        print("\n=== BROKER CREDENTIALS ===")
        cursor.execute("""
            SELECT credential_id, broker_name, account_number, is_active, is_live 
            FROM broker_credentials 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        creds = cursor.fetchall()
        for cred in creds:
            print(f"  {cred['broker_name']:15s} | Account: {cred['account_number'][:20]:20s} | Active: {cred['is_active']} | Live: {cred['is_live']}")
        
        # Check if any errors in trade history
        print("\n=== TRADE HISTORY (Last 5) ===")
        cursor.execute("""
            SELECT bot_id, symbol, created_at, profit 
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        trades = cursor.fetchall()
        if trades:
            for trade in trades:
                print(f"  Bot: {trade['bot_id'][:20]:20s} | Symbol: {trade['symbol']:10s} | Time: {trade['created_at'][:19]} | Profit: ${trade['profit']:.2f}")
        else:
            print("  ❌ NO TRADES FOUND - This is the problem!")
        
        # Check pause events
        print("\n=== BOT PAUSE EVENTS (Last 3) ===")
        cursor.execute("""
            SELECT bot_id, pause_type, error_message, created_at 
            FROM bot_pause_events 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        pause_events = cursor.fetchall()
        if pause_events:
            for event in pause_events:
                print(f"  Bot: {event['bot_id'][:20]:20s} | Type: {event['pause_type'][:20]:20s} | {event['created_at'][:19]}")
                print(f"       Error: {event['error_message'][:100]}")
        else:
            print("  No pause events recorded")
        
        conn.close()
        print("\n✓ Database check complete")
    except Exception as e:
        import traceback
        print(f"❌ Database error: {e}")
        traceback.print_exc()
else:
    print(f"❌ Database not found at: {db_path}")
