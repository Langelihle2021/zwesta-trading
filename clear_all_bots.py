#!/usr/bin/env python3
"""
CLEAR ALL BOTS - Fresh Start Utility
=====================================

This script deletes ALL bots from the Zwesta system to allow a fresh start.
It removes:
  ✅ All bot configurations from database
  ✅ All trade histories
  ✅ All daily profit records
  ✅ All running bot threads

It KEEPS:
  ✅ Broker credentials (for reuse)
  ✅ Account balance (real broker balance)
  ✅ User account data
  ✅ Commission records

Usage:
  python clear_all_bots.py              # Clear all bots interactively
  python clear_all_bots.py --confirm    # Clear without confirmation
  python clear_all_bots.py --user USER_ID  # Clear only specific user's bots
  python clear_all_bots.py --dry-run    # Show what would be deleted
"""

import sqlite3
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'zwesta_trading.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def count_bots(user_id=None):
    """Count total bots, optionally for specific user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('SELECT COUNT(*) FROM user_bots WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('SELECT COUNT(*) FROM user_bots')
    
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_bots(user_id=None):
    """Get bot details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute('''
            SELECT bot_id, user_id, name, strategy, enabled, created_at 
            FROM user_bots WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
    else:
        cursor.execute('''
            SELECT bot_id, user_id, name, strategy, enabled, created_at 
            FROM user_bots
            ORDER BY created_at DESC
        ''')
    
    bots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return bots

def backup_database():
    """Create database backup before deletion"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return False
    
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'trading_bots_backup_{timestamp}.db')
    
    try:
        with open(DB_PATH, 'rb') as src:
            with open(backup_path, 'wb') as dst:
                dst.write(src.read())
        print(f"✅ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def clear_all_bots(user_id=None):
    """Delete all bots from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if user_id:
            print(f"\n🗑️  Deleting bots for user {user_id}...")
            # Delete bot_credentials first (foreign key)
            cursor.execute('DELETE FROM bot_credentials WHERE user_id = ?', (user_id,))
            # Delete trades for this user's bots
            cursor.execute('''
                DELETE FROM trades WHERE bot_id IN 
                (SELECT bot_id FROM user_bots WHERE user_id = ?)
            ''', (user_id,))
            # Delete bot configurations
            cursor.execute('DELETE FROM user_bots WHERE user_id = ?', (user_id,))
        else:
            print(f"\n🗑️  Deleting ALL bots from database...")
            # Delete all relationships
            cursor.execute('DELETE FROM bot_credentials')
            cursor.execute('DELETE FROM trades')
            cursor.execute('DELETE FROM user_bots')
        
        conn.commit()
        affected = cursor.total_changes
        conn.close()
        
        print(f"✅ Deleted successfully!")
        return True
    
    except Exception as e:
        print(f"❌ Deletion failed: {e}")
        return False

def show_bots_preview(bots_list):
    """Show preview of bots to be deleted"""
    if not bots_list:
        print("ℹ️  No bots found.")
        return
    
    print(f"\n📋 Found {len(bots_list)} bot(s) to delete:\n")
    
    # Group by user
    by_user = {}
    for bot in bots_list:
        user = bot['user_id']
        if user not in by_user:
            by_user[user] = []
        by_user[user].append(bot)
    
    for user_id in sorted(by_user.keys()):
        user_bots = by_user[user_id]
        print(f"  User: {user_id} ({len(user_bots)} bots)")
        for bot in user_bots:
            status = "🟢 ENABLED" if bot['enabled'] else "🔴 DISABLED"
            print(f"    • {bot['bot_id']}")
            print(f"      Name: {bot['name']}, Strategy: {bot['strategy']}, {status}")

def main():
    """Main function"""
    
    # Parse arguments
    dry_run = '--dry-run' in sys.argv
    confirm = '--confirm' in sys.argv
    user_id = None
    
    if '--user' in sys.argv:
        idx = sys.argv.index('--user')
        if idx + 1 < len(sys.argv):
            user_id = sys.argv[idx + 1]
    
    print("=" * 60)
    print("ZWESTA BOT CLEAR UTILITY - Fresh Start")
    print("=" * 60)
    
    # Check database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)
    
    # Count and preview
    count = count_bots(user_id)
    if count == 0:
        print(f"\n✅ No bots found to delete" + (f" for user {user_id}" if user_id else ""))
        sys.exit(0)
    
    bots = get_bots(user_id)
    show_bots_preview(bots)
    
    # Dry run mode
    if dry_run:
        print(f"\n🔍 DRY RUN: Would delete {count} bot(s)")
        print("Use --confirm to actually delete")
        sys.exit(0)
    
    # Confirmation
    if not confirm:
        print(f"\n⚠️  WARNING: This will DELETE {count} bot(s) PERMANENTLY!")
        print("   • All bot configurations will be removed")
        print("   • All trade histories will be deleted")
        print("   • All daily profits will be cleared")
        print("   • Running bots will be stopped")
        print("\n✅ Keep: Broker credentials, account balance, user data")
        response = input(f"\nType 'YES' to proceed: ").strip().upper()
        
        if response != 'YES':
            print("❌ Cancelled. No bots were deleted.")
            sys.exit(0)
    
    # Backup
    print("\n📦 Creating backup...")
    if not backup_database():
        print("❌ Backup failed - aborting to prevent data loss")
        sys.exit(1)
    
    # Delete
    if clear_all_bots(user_id):
        print(f"\n✅ COMPLETE: {count} bot(s) deleted successfully")
        print(f"📂 Backup saved in: backups/")
        print("\nYou can now start fresh with new bots!")
        sys.exit(0)
    else:
        print("❌ Deletion failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
