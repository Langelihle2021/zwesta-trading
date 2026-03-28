#!/usr/bin/env python3
"""
ZWESTA BOT RECOVERY SCRIPT
Helps restore bots from backup or recreate them

Usage:
  python restore_bots.py --check-backups      # Look for backups in common locations
  python restore_bots.py --restore-from-backup <path>   # Restore specific backup
  python restore_bots.py --create-sample-bots  # Create sample bots to get trading again
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = r"C:\backend\zwesta_trading.db"

print("=" * 70)
print("🤖 ZWESTA BOT RECOVERY TOOL")
print("=" * 70)

def check_common_backup_locations():
    """Search for database backups in common locations"""
    print("\n📁 Searching for backups in common locations...")
    
    backup_locations = [
        "C:\\Users\\{user}\\Backups\\".format(user=os.environ.get('USERNAME', '*')),
        "C:\\Users\\{user}\\Documents\\".format(user=os.environ.get('USERNAME', '*')),
        "C:\\Users\\{user}\\Desktop\\".format(user=os.environ.get('USERNAME', '*')),
        r"C:\Windows\System32\config\RegBack",
        r"D:\Backups",
        r"E:\Backups",
        r"C:\Zwesta_Backups",
        r"C:\backend",
    ]
    
    found_backups = []
    for loc_pattern in backup_locations:
        # Expand environment variables
        try:
            loc = os.path.expandvars(loc_pattern)
            if not os.path.exists(loc):
                continue
                
            for file in os.listdir(loc):
                if 'zwesta' in file.lower() and (file.endswith('.db') or file.endswith('.sql')):
                    full_path = os.path.join(loc, file)
                    size = os.path.getsize(full_path)
                    if size > 0:  # Skip empty files
                        found_backups.append((full_path, size))
                        print(f"  ✓ Found: {file} ({size:,} bytes)")
        except:
            continue
    
    if not found_backups:
        print("  ❌ No valid backups found in common locations")
        print("\n   💡 SUGGESTIONS:")
        print("     1. Check cloud storage (Google Drive, OneDrive, Dropbox)")
        print("     2. Check NAS or external drives")
        print("     3. Check system restore points (Windows)")
        print("     4. Contact your hosting provider for server backups")
    else:
        print(f"\n  ✅ Found {len(found_backups)} potential backups")
        return found_backups
    
    return None

def verify_backup(backup_path):
    """Check if backup contains valid bot data"""
    print(f"\n🔍 Verifying backup: {backup_path}")
    
    if backup_path.endswith('.sql'):
        print("  📄 SQL backup detected")
        try:
            with open(backup_path, 'r') as f:
                content = f.read()
                if 'user_bots' in content and 'SELECT' in content:
                    print("  ✅ Contains user_bots table")
                    # Count bots in the SQL
                    insert_count = content.count("INSERT INTO `user_bots`") + content.count('INSERT INTO "user_bots"')
                    if insert_count > 0:
                        print(f"  ✅ Contains {insert_count} bot records")
                        return True
        except:
            pass
        return False
    
    else:  # .db file
        try:
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            
            # Check for user_bots
            cursor.execute("SELECT COUNT(*) FROM user_bots")
            bot_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM broker_credentials")
            cred_count = cursor.fetchone()[0]
            
            conn.close()
            
            if bot_count > 0:
                print(f"  ✅ Found {bot_count} bots, {user_count} users, {cred_count} credentials")
                return True
            else:
                print(f"  ⚠️ Backup is empty (0 bots)")
                return False
        except Exception as e:
            print(f"  ❌ Not a valid database: {e}")
            return False

def restore_from_backup(backup_path):
    """Restore database from backup"""
    print(f"\n🔄 Restoring database from backup...")
    print(f"   Source: {backup_path}")
    print(f"   Target: {DB_PATH}")
    
    if not os.path.exists(backup_path):
        print(f"❌ Backup not found: {backup_path}")
        return False
    
    # Create safety backup of current DB
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    current_backup = f"{DB_PATH}.cleared_{timestamp}"
    
    try:
        print(f"\n   📦 Backing up current cleared database...")
        shutil.copy(DB_PATH, current_backup)
        print(f"   ✅ Saved to: {current_backup}")
        
        print(f"\n   🔄 Restoring from backup...")
        shutil.copy(backup_path, DB_PATH)
        print(f"   ✅ Restored successfully!")
        
        # Verify
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_bots")
        bot_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"\n   ✅ Verification: {bot_count} bots restored")
        print(f"\n   ⚠️  REMEMBER: Restart your backend service for changes to take effect")
        print(f"   Restart command: systemctl restart zwesta-backend  (or your service name)")
        
        return True
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False

def create_sample_bots():
    """Create sample bots to get trading again quickly"""
    print("\n🤖 Creating sample bots...")
    
    sample_data = {
        'users': [
            ('user_demo_1', 'demo@zwesta.com', 'Demo User', None, None, datetime.now().isoformat(), 0.0),
        ],
        'broker_credentials': [
            ('cred_demo_exness_1', 'user_demo_1', 'Exness', '123456789', 'password123', 'Exness-MT5Trial9', 0, 1, datetime.now().isoformat()),
        ],
        'user_bots': [
            ('bot_demo_1', 'user_demo_1', 'Demo Bot - EUR/USD', 'Trend Following', 'active', 1, 'Exness_123456789', 'EURUSDm', 0, datetime.now().isoformat(), datetime.now().isoformat()),
            ('bot_demo_2', 'user_demo_1', 'Demo Bot - Gold', 'Trend Following', 'active', 1, 'Exness_123456789', 'XAUUSDm', 0, datetime.now().isoformat(), datetime.now().isoformat()),
        ]
    }
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert users
        for user_data in sample_data['users']:
            cursor.execute('''
                INSERT INTO users (user_id, email, name, referrer_id, referral_code, created_at, total_commission)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', user_data)
        print("  ✅ Created sample user")
        
        # Insert credentials
        for cred_data in sample_data['broker_credentials']:
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', cred_data)
        print("  ✅ Created sample broker credential")
        
        # Insert bots
        for bot_data in sample_data['user_bots']:
            cursor.execute('''
                INSERT INTO user_bots 
                (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, is_live, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', bot_data)
        print("  ✅ Created 2 sample trading bots")
        
        # INSERT THE CRITICAL LINK: bot_credentials
        # This is what was missing - bots need to be linked to their credentials!
        bot_cred_links = [
            ('bot_demo_1', 'cred_demo_exness_1', 'user_demo_1', datetime.now().isoformat()),
            ('bot_demo_2', 'cred_demo_exness_1', 'user_demo_1', datetime.now().isoformat()),
        ]
        for link_data in bot_cred_links:
            cursor.execute('''
                INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', link_data)
        print("  ✅ Linked bots to broker credentials")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Sample bots created successfully!")
        print("\n📝 Sample login details:")
        print("  Email: demo@zwesta.com")
        print("  Broker: Exness")
        print("  Account: 123456789")
        print("  Password: password123")
        print("  Bots: EUR/USD and Gold trading bots (demo mode)")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create sample bots: {e}")
        return False


# Main menu
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("\n⚠️  No arguments provided. Available options:\n")
        print("  1. Check for backups:")
        print("     python restore_bots.py --check-backups\n")
        print("  2. Restore from specific backup:")
        print("     python restore_bots.py --restore-from-backup <path/to/backup.db>\n")
        print("  3. Create sample bots to resume trading:")
        print("     python restore_bots.py --create-sample-bots\n")
        sys.exit(1)
    
    if '--check-backups' in sys.argv:
        backups = check_common_backup_locations()
        if backups:
            print("\n📋 Checking backup validity...")
            for backup_path, _ in backups:
                if verify_backup(backup_path):
                    print(f"\n✅ Valid backup found: {backup_path}")
                    print(f"   Use: python restore_bots.py --restore-from-backup \"{backup_path}\"")
    
    elif '--restore-from-backup' in sys.argv:
        if len(sys.argv) < 3:
            print("❌ Please provide backup path")
            print(f"   Usage: python restore_bots.py --restore-from-backup <path>")
            sys.exit(1)
        backup_path = sys.argv[2]
        if verify_backup(backup_path):
            restore_from_backup(backup_path)
        else:
            print("❌ Backup contains no valid data")
    
    elif '--create-sample-bots' in sys.argv:
        create_sample_bots()
    
    else:
        print("❌ Unknown argument")
        sys.exit(1)

print("\n" + "=" * 70)
