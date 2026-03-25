#!/usr/bin/env python3
"""
Cleanup script to remove old test/mock bots from the database
Run this ONCE to clean up all accumulated bots from before going live
"""

import sqlite3
from datetime import datetime
import os

# Database location - in Flutter App directory where the backend reads from
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'Zwesta Flutter App',
    'zwesta_trading.db'
)

def cleanup_old_bots(dry_run=False):
    """Delete all old bots from database - PERMANENT"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_bots'")
        if not cursor.fetchone():
            print("❌ user_bots table not found")
            return
        
        # Count existing bots
        cursor.execute('SELECT COUNT(*) as count FROM user_bots')
        total_bots = cursor.fetchone()['count']
        print(f"\n📊 Total bots in database: {total_bots}")
        
        if total_bots == 0:
            print("✅ No bots to clean up")
            conn.close()
            return
        
        # List all bots being deleted
        cursor.execute('SELECT bot_id, user_id, name, created_at FROM user_bots ORDER BY created_at DESC')
        bots = cursor.fetchall()
        
        print(f"\n🗑️  Bots to be DELETED:")
        for bot in bots:
            print(f"   - {bot['bot_id']}: {bot['name']} (user: {bot['user_id']}) created: {bot['created_at']}")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN MODE - No changes made. Run with dry_run=False to actually delete")
            conn.close()
            return
        
        # Confirm deletion
        response = input(f"\n⚠️  THIS WILL DELETE ALL {total_bots} BOTS. Type 'YES' to confirm: ")
        if response != 'YES':
            print("❌ Cancelled - no bots deleted")
            conn.close()
            return
        
        # Delete all bots and related data
        cursor.execute('DELETE FROM user_bots')
        cursor.execute('DELETE FROM bot_credentials')
        cursor.execute('DELETE FROM bot_deletion_tokens')
        cursor.execute('DELETE FROM bot_activation_pins')
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ SUCCESSFULLY DELETED ALL {total_bots} BOTS")
        print("✅ All bot-related data has been cleaned up")
        print("✅ Database is ready for fresh start")
        
    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        print(f"   Make sure backend is NOT running (it locks the database)")

if __name__ == '__main__':
    print("=" * 60)
    print("ZWESTA BOT CLEANUP UTILITY")
    print("=" * 60)
    
    # First do a dry run to show what will be deleted
    print("\n[STEP 1] Checking what would be deleted...")
    cleanup_old_bots(dry_run=True)
    
    # Then ask for confirmation before deleting
    print("\n[STEP 2] Running actual deletion...")
    cleanup_old_bots(dry_run=False)
