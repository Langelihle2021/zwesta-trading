#!/usr/bin/env python3
"""
Fix: Update Exness credentials from DEMO to LIVE
This script updates credentials to trade on the LIVE Exness-Real server instead of trial
"""

import sqlite3
from datetime import datetime

DB_PATH = r"C:\backend\zwesta_trading.db"

def update_exness_to_live():
    """Update all Exness credentials to use LIVE server"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find all Exness credentials still on DEMO
        cursor.execute('''
            SELECT credential_id, user_id, account_number, server, is_live
            FROM broker_credentials
            WHERE broker_name = 'Exness'
        ''')
        
        credentials = cursor.fetchall()
        
        if not credentials:
            print("❌ No Exness credentials found in database")
            return
        
        print(f"📋 Found {len(credentials)} Exness credential(s)\n")
        
        for cred_id, user_id, account_num, server, is_live in credentials:
            print(f"   Credential ID: {cred_id}")
            print(f"   Account: {account_num}")
            print(f"   Current Server: {server}")
            print(f"   Is Live: {'✅ YES' if is_live else '❌ NO (DEMO)'}")
            
            # Update to live
            cursor.execute('''
                UPDATE broker_credentials
                SET server = 'Exness-Real', is_live = 1, updated_at = ?
                WHERE credential_id = ?
            ''', (datetime.now().isoformat(), cred_id))
            
            print(f"   ✅ Updated to Exness-Real (LIVE)")
            print()
        
        conn.commit()
        conn.close()
        
        print("✅ SUCCESS: All Exness credentials updated to LIVE trading!")
        print("\n⚡ NEXT STEPS:")
        print("   1. Restart your bot")
        print("   2. Check your live Exness account for new trades")
        print("   3. Bot orders will now appear in Exness-Real, not Exness-MT5Trial9")
        
    except Exception as e:
        print(f"❌ Error updating credentials: {e}")

if __name__ == '__main__':
    update_exness_to_live()
