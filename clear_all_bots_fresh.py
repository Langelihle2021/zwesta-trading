#!/usr/bin/env python3
"""
Clear all trading bots to start fresh, but keep credentials intact
"""

import sqlite3
from datetime import datetime

DB_PATH = r"C:\backend\zwesta_trading.db"

def clear_all_bots():
    """Remove all bots from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("🧹 CLEARING ALL BOTS - FRESH START")
        print("=" * 70)
        
        # Check current state
        cursor.execute("SELECT COUNT(*) FROM user_bots")
        bot_count = cursor.fetchone()[0]
        print(f"\n📋 Current state:")
        print(f"   Bots: {bot_count}")
        
        cursor.execute("SELECT COUNT(*) FROM bot_credentials")
        bot_cred_count = cursor.fetchone()[0]
        print(f"   Bot-Credential Links: {bot_cred_count}")
        
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        print(f"   Trades: {trade_count}")
        
        cursor.execute("SELECT COUNT(*) FROM broker_credentials")
        cred_count = cursor.fetchone()[0]
        print(f"   Credentials: {cred_count} ✅ (keeping these)")
        
        if bot_count == 0:
            print("\n✅ Database already clean - 0 bots!")
            conn.close()
            return True
        
        # Delete all bots
        print(f"\n🗑️  Deleting all {bot_count} bots...")
        cursor.execute("DELETE FROM user_bots")
        
        # Delete bot-credential links
        print(f"🗑️  Deleting all {bot_cred_count} bot-credential links...")
        cursor.execute("DELETE FROM bot_credentials")
        
        # Delete all trades
        print(f"🗑️  Deleting all {trade_count} trades...")
        cursor.execute("DELETE FROM trades")
        
        conn.commit()
        
        # Verify
        print(f"\n✅ Verification after cleanup:")
        cursor.execute("SELECT COUNT(*) FROM user_bots")
        new_bot_count = cursor.fetchone()[0]
        print(f"   Bots: {new_bot_count} ✅")
        
        cursor.execute("SELECT COUNT(*) FROM bot_credentials")
        new_bot_cred_count = cursor.fetchone()[0]
        print(f"   Bot-Credential Links: {new_bot_cred_count} ✅")
        
        cursor.execute("SELECT COUNT(*) FROM trades")
        new_trade_count = cursor.fetchone()[0]
        print(f"   Trades: {new_trade_count} ✅")
        
        cursor.execute("SELECT credential_id, broker_name, account_number FROM broker_credentials")
        creds = cursor.fetchall()
        print(f"\n🔐 Preserved Credentials ({len(creds)}):")
        for cred_id, broker, account in creds:
            print(f"   • {cred_id} ({broker} account {account})")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ FRESH START COMPLETE - Ready to create new bots!")
        print("=" * 70)
        print("\n📝 Market Hours Configuration:")
        print("   🟢 CRYPTO (BTC, ETH, etc): All 7 days (00:00-24:00)")
        print("   🟢 FOREX: All 7 days (00:00-24:00)")
        print("   🟢 COMMODITIES (Gold, Oil, etc): All 7 days (01:00-23:59)")
        print("   🟠 STOCKS: Mon-Fri only (13:30-20:00)")
        print("   🟠 INDICES: Mon-Fri only (08:00-22:00)")
        print("\n✨ BTC and ETH will trade ALL 7 DAYS OF THE WEEK")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    clear_all_bots()
