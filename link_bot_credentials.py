#!/usr/bin/env python3
"""
Link existing demo bots to their Exness credentials
This fixes the missing bot_credentials table entries that prevent trading
"""

import sqlite3
from datetime import datetime
import os

DB_PATH = r"C:\backend\zwesta_trading.db"

def link_bot_credentials():
    """Add bot-credential linkages"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("🔗 LINKING BOTS TO CREDENTIALS")
        print("=" * 70)
        
        # Check existing bots
        cursor.execute("SELECT bot_id, user_id FROM user_bots WHERE bot_id LIKE 'bot_demo%'")
        bots = cursor.fetchall()
        print(f"\n📋 Found {len(bots)} demo bots:")
        for bot_id, user_id in bots:
            print(f"   • {bot_id} (user: {user_id})")
        
        # Check existing credentials
        cursor.execute("SELECT credential_id, broker_name FROM broker_credentials WHERE credential_id LIKE 'cred_demo%'")
        creds = cursor.fetchall()
        print(f"\n📋 Found {len(creds)} demo credentials:")
        for cred_id, broker_name in creds:
            print(f"   • {cred_id} ({broker_name})")
        
        # Clear existing bot_credentials (if any)
        cursor.execute("DELETE FROM bot_credentials WHERE bot_id LIKE 'bot_demo%'")
        print(f"\n🧹 Cleared existing demo bot linkages")
        
        # Link each bot to the Exness credential
        now = datetime.now().isoformat()
        bot_cred_links = [
            ('bot_demo_1', 'cred_demo_exness_1', 'user_demo_1', now),
            ('bot_demo_2', 'cred_demo_exness_1', 'user_demo_1', now),
        ]
        
        print(f"\n🔗 Creating bot-credential linkages:")
        for bot_id, cred_id, user_id, created_at in bot_cred_links:
            cursor.execute('''
                INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (bot_id, cred_id, user_id, created_at))
            print(f"   ✅ {bot_id} → {cred_id}")
        
        conn.commit()
        
        # Verify
        print(f"\n✅ Verification:")
        cursor.execute('''
            SELECT bc.bot_id, bc.credential_id, br.broker_name, br.account_number 
            FROM bot_credentials bc
            JOIN broker_credentials br ON bc.credential_id = br.credential_id
            WHERE bc.bot_id LIKE 'bot_demo%'
        ''')
        links = cursor.fetchall()
        print(f"   Found {len(links)} active bot-credential links:")
        for bot_id, cred_id, broker, account in links:
            print(f"   • {bot_id} → {cred_id} ({broker} account {account})")
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ LINKAGE COMPLETE - Bots can now access credentials!")
        print("=" * 70)
        print("\n⏭️  Next step: Restart backend to pick up the new linkages")
        print("   Command: python multi_broker_backend_updated.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    link_bot_credentials()
