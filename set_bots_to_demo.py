#!/usr/bin/env python3
"""
Set system bots to use DEMO account for testing
Updates Exness credentials to use demo server (Exness-MT5Trial9)
"""

import sqlite3
from datetime import datetime

DB_PATH = r"C:\backend\zwesta_trading.db"

def set_bots_to_demo():
    """Update Exness credentials to use DEMO for testing"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find all Exness credentials
        cursor.execute('''
            SELECT credential_id, user_id, account_number, server, is_live
            FROM broker_credentials
            WHERE broker_name = 'Exness'
        ''')
        
        credentials = cursor.fetchall()
        
        if not credentials:
            print("❌ No Exness credentials found")
            return
        
        print("📋 Exness Credentials Found:\n")
        demo_updated = 0
        
        for cred_id, user_id, account_num, server, is_live in credentials:
            current_mode = "LIVE" if server == "Exness-Real" else "DEMO"
            print(f"   Account: {account_num}")
            print(f"   Current: {server} ({current_mode})")
            
            # Update to demo
            cursor.execute('''
                UPDATE broker_credentials
                SET server = 'Exness-MT5Trial9', is_live = 0, updated_at = ?
                WHERE credential_id = ?
            ''', (datetime.now().isoformat(), cred_id))
            
            print(f"   ✅ Updated to DEMO for testing\n")
            demo_updated += 1
        
        conn.commit()
        conn.close()
        
        print("=" * 50)
        print(f"✅ SUCCESS: {demo_updated} credential(s) set to DEMO")
        print("=" * 50)
        print("\n⚡ NEXT STEPS:")
        print("   1. Restart your bot")
        print("   2. Test strategy on DEMO account (no real money)")
        print("   3. Monitor trades in Exness MT5 Demo Terminal")
        print("   4. When confident, switch back to LIVE\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    set_bots_to_demo()
