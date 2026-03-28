#!/usr/bin/env python3
"""
Check database integrity and bot counts
"""

import sqlite3
from pathlib import Path

DB_PATH = r'C:\backend\zwesta_trading.db'

def check_database():
    """Check database tables and record counts"""
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 Database Tables ({len(tables)}):")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count} records")
        
        # Check broker credentials details
        print(f"\n🔐 Broker Credentials:")
        cursor.execute("""SELECT credential_id, user_id, broker_name, account_number, 
                                 cached_balance, last_balance_update 
                          FROM broker_credentials ORDER BY broker_name""")
        for row in cursor.fetchall():
            cred_id, user_id, broker, acc, bal, last_update = row
            print(f"   {broker} acc={acc}")
            print(f"      Cred ID: {cred_id}")
            print(f"      User ID: {user_id}")
            print(f"      Balance: {bal} (updated: {last_update})")
        
        # Check user_bots
        print(f"\n🤖 User Bots:")
        cursor.execute("""SELECT bot_id, bot_name, user_id, enabled, status 
                          FROM user_bots LIMIT 20""")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                bot_id, bot_name, user_id, enabled, status = row
                print(f"   {bot_name} (ID: {bot_id})")
                print(f"      Enabled: {enabled}, Status: {status}")
        else:
            print("   ❌ No bots found in database")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    check_database()
