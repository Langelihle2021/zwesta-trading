#!/usr/bin/env python3
"""
Fix balance cache corruption after detecting stale/duplicate balances
Run this before restarting backend to clear cached values
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = r'C:\backend\zwesta_trading.db'

def fix_balance_cache():
    """Clear balance cache entries and reset broker credential balances"""
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check broker credentials table
        cursor.execute("PRAGMA table_info(broker_credentials)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"✅ broker_credentials columns: {columns}")
        
        # Reset cached balance columns to NULL so they'll be fetched fresh
        cursor.execute("""UPDATE broker_credentials 
                         SET cached_balance = NULL, 
                             cached_equity = NULL, 
                             cached_margin_free = NULL,
                             last_balance_update = NULL""")
        affected = cursor.rowcount
        print(f"✅ Reset {affected} broker credential cached balances to NULL")
        
        # Show current credentials
        cursor.execute("SELECT credential_id, broker_name, account_number, cached_balance FROM broker_credentials")
        rows = cursor.fetchall()
        print(f"\n📊 Current Broker Credentials:")
        for row in rows:
            print(f"   ID {row[0]}: {row[1]} acc={row[2]} bal={row[3]}")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Balance cache cleared - backend will fetch fresh balances on next MT5 connection")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    fix_balance_cache()
