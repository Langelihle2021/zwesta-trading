#!/usr/bin/env python3
"""
Clear all bots from the database
This removes all user-created bots, keeping only the system initialization
"""



import os
import sqlite3
import sys
import importlib.util

# Dynamically import backend DB logic
backend_path = 'multi_broker_backend_updated.py'
spec = importlib.util.spec_from_file_location('backend', backend_path)
backend = importlib.util.module_from_spec(spec)
sys.modules['backend'] = backend
spec.loader.exec_module(backend)

get_db_connection = backend.get_db_connection
DB_PATH = backend.DATABASE_PATH

def clear_bots():
    """Delete all bots from the user_bots table"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    try:
        conn = get_db_connection()
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
