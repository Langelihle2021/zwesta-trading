#!/usr/bin/env python3
"""
Switch credentials between LIVE and DEMO modes
Supports Exness and PXBT brokers
Usage: python set_bots_to_demo.py [--live] [--broker=exness|pxbt|all]
"""

import sqlite3
from datetime import datetime
import sys

DB_PATH = r"C:\backend\zwesta_trading.db"

# Broker-specific server configurations
BROKERS = {
    'Exness': {
        'demo': 'Exness-MT5Trial9',
        'live': 'Exness-Real',
    },
    'PXBT': {
        'demo': 'PXBT-Demo',
        'live': 'PXBT-Real',
    }
}

def switch_broker_mode(broker_name, target_mode='demo', dry_run=False):
    """
    Switch broker credentials between LIVE and DEMO
    Args:
        broker_name: 'Exness', 'PXBT', or 'all'
        target_mode: 'demo' or 'live'
        dry_run: Show what would change without committing
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Determine which brokers to update
        brokers_to_update = list(BROKERS.keys()) if broker_name.lower() == 'all' else [broker_name]
        
        total_updated = 0
        
        for broker in brokers_to_update:
            if broker not in BROKERS:
                print(f"⚠️  Unknown broker: {broker}")
                continue
            
            # Find credentials for this broker
            cursor.execute('''
                SELECT credential_id, user_id, account_number, server, is_live
                FROM broker_credentials
                WHERE broker_name = ?
            ''', (broker,))
            
            credentials = cursor.fetchall()
            
            if not credentials:
                print(f"⚠️  No {broker} credentials found")
                continue
            
            print(f"\n🔄 {broker} Credentials ({len(credentials)} found):\n")
            broker_updated = 0
            
            for cred_id, user_id, account_num, server, is_live in credentials:
                current_mode = "LIVE" if is_live == 1 else "DEMO"
                target_server = BROKERS[broker][target_mode]
                target_is_live = 1 if target_mode == 'live' else 0
                
                print(f"   Account: {account_num}")
                print(f"   Current:  {server} ({current_mode})")
                print(f"   Target:   {target_server} ({target_mode.upper()})")
                
                # Skip if already in target mode
                if server == target_server and is_live == target_is_live:
                    print(f"   ⏭️  Already in {target_mode.upper()} mode\n")
                    continue
                
                if not dry_run:
                    # Update to target mode
                    cursor.execute('''
                        UPDATE broker_credentials
                        SET server = ?, is_live = ?, updated_at = ?
                        WHERE credential_id = ?
                    ''', (target_server, target_is_live, datetime.now().isoformat(), cred_id))
                    
                    print(f"   ✅ Updated to {target_mode.upper()}\n")
                else:
                    print(f"   📋 Would update to {target_mode.upper()}\n")
                
                broker_updated += 1
            
            if not dry_run and broker_updated > 0:
                total_updated += broker_updated
        
        if not dry_run:
            conn.commit()
        conn.close()
        
        print("=" * 60)
        if dry_run:
            print(f"📋 DRY RUN: Would update {total_updated} credential(s)")
        else:
            print(f"✅ SUCCESS: {total_updated} credential(s) switched to {target_mode.upper()}")
        print("=" * 60)
        
        if target_mode == 'demo' and total_updated > 0:
            print("\n⚡ NEXT STEPS (DEMO MODE):")
            print("   1. Restart backend: python multi_broker_backend_updated.py")
            print("   2. Create test bot via Flutter app or API")
            print("   3. Monitor trades in MT5 Terminal (Demo)")
            print("   4. Verify signals execute correctly")
            print("   5. Check balances update in real-time\n")
        elif target_mode == 'live' and total_updated > 0:
            print("\n⚠️  LIVE MODE ENABLED - REAL MONEY TRADING ACTIVE!")
            print("   ⚡ NEXT STEPS:")
            print("   1. Verify LIVE account credentials are correct")
            print("   2. Check available balance in backend")
            print("   3. Restart backend: python multi_broker_backend_updated.py")
            print("   4. Create bot with SMALL position size")
            print("   5. Monitor first few trades very carefully")
            print("   6. Check MT5 Terminal (Live) for execution\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Parse arguments
    target_mode = 'demo'
    broker = 'all'
    dry_run = False
    
    for arg in sys.argv[1:]:
        if arg == '--live':
            target_mode = 'live'
        elif arg == '--demo':
            target_mode = 'demo'
        elif arg == '--dry-run':
            dry_run = True
        elif arg.startswith('--broker='):
            broker = arg.split('=')[1]
    
    print("=" * 60)
    print(f"🔄 CREDENTIAL MODE SWITCHER")
    print(f"   Mode: {target_mode.upper()}")
    print(f"   Broker: {broker.upper()}")
    if dry_run:
        print("   ⚠️  DRY RUN - No changes will be made")
    print("=" * 60)
    
    switch_broker_mode(broker, target_mode, dry_run)
