#!/usr/bin/env python3
"""
Database migration script - Adds new columns for withdrawal feature
Run this ONCE before starting the backend with withdrawal features
"""

import sqlite3
import sys

DB_PATH = 'zwesta_trading.db'

def migrate_database():
    """Add new columns to auto_withdrawal_settings and user_bots tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # ==================== Check and fix user_bots table ====================
        print("📋 Checking user_bots table...")
        cursor.execute("PRAGMA table_info(user_bots)")
        user_bots_columns = {row[1] for row in cursor.fetchall()}
        print(f"   Existing columns: {user_bots_columns}")
        
        # Add symbols column if missing (critical for bot creation)
        if 'symbols' not in user_bots_columns:
            try:
                cursor.execute("ALTER TABLE user_bots ADD COLUMN symbols TEXT DEFAULT 'EURUSD'")
                print(f"   ✅ Added column: symbols (DEFAULT='EURUSD')")
                conn.commit()
            except Exception as e:
                print(f"   ⚠️  Error adding symbols column: {e}")
        else:
            print(f"   ✓ Column already exists: symbols")
        
        # ==================== Check and fix auto_withdrawal_settings table ====================
        print("\n📋 Checking auto_withdrawal_settings table...")
        cursor.execute("PRAGMA table_info(auto_withdrawal_settings)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        print(f"   Existing columns: {existing_columns}")
        
        # List of new columns to add
        new_columns = {
            'withdrawal_mode': 'TEXT DEFAULT "fixed"',
            'min_profit': 'REAL DEFAULT 50',
            'max_profit': 'REAL DEFAULT 1000',
            'volatility_threshold': 'REAL DEFAULT 0.02',
            'win_rate_min': 'REAL DEFAULT 60',
            'trend_strength_min': 'REAL DEFAULT 0.5',
            'time_between_withdrawals_hours': 'INTEGER DEFAULT 24',
            'last_withdrawal_at': 'TEXT'
        }
        
        # Add missing columns
        columns_added = 0
        for col_name, col_def in new_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE auto_withdrawal_settings ADD COLUMN {col_name} {col_def}')
                    print(f"   ✅ Added column: {col_name}")
                    columns_added += 1
                except Exception as e:
                    print(f"   ⚠️  Error adding {col_name}: {e}")
            else:
                print(f"   ✓ Column already exists: {col_name}")
        
        if columns_added > 0:
            conn.commit()
            print(f"\n✅ Migration complete! Added {columns_added} columns to auto_withdrawal_settings")
        else:
            print(f"\n✓ auto_withdrawal_settings table already up to date")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == '__main__':
    print("🔄 Starting database migration...")
    success = migrate_database()
    sys.exit(0 if success else 1)
