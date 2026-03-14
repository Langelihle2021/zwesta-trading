#!/usr/bin/env python3
"""
Clear all bots from the database
This removes all user-created bots, keeping only the system initialization
"""

import sqlite3
import os

DB_PATH = 'zwesta_trading.db'

def clear_bots():
    """Delete all bots from the user_bots table"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute('SELECT COUNT(*) as count FROM user_bots')
        before_count = cursor.fetchone()['count']
        print(f"📊 Current bots in database: {before_count}")
        
        # Delete all bots
        cursor.execute('DELETE FROM user_bots')
        conn.commit()
        
        # Get count after deletion
        cursor.execute('SELECT COUNT(*) as count FROM user_bots')
        after_count = cursor.fetchone()['count']
        
        print(f"✅ Cleared database!")
        print(f"   Before: {before_count} bots")
        print(f"   After:  {after_count} bots")
        print(f"\n🔄 The system is now clean and ready for new bots")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error clearing bots: {e}")
        return False

if __name__ == '__main__':
    clear_bots()
