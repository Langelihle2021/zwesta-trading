#!/usr/bin/env python3
"""Check database schema and identify the problem"""

import sqlite3
import os

db_path = r"C:\backend\zwesta_trading.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("=== DATABASE TABLES ===")
    print(f"Total tables: {len(tables)}\n")
    
    for (table_name,) in tables:
        # Get row count
        try:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name:30s} | Rows: {count}")
        except:
            print(f"  {table_name:30s} | (error reading count)")
    
    # Check specifically for key bot-related tables
    print("\n=== KEY TABLES STATUS ===")
    key_tables = ['user_bots', 'broker_credentials', 'trades', 'users']
    for table in key_tables:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        exists = cursor.fetchone()
        if exists:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✓ {table:25s } | {count:5d} rows")
        else:
            print(f"  ✗ {table:25s } | MISSING")
    
    # Check database file info
    print(f"\n=== DATABASE FILE INFO ===")
    file_stat = os.stat(db_path)
    print(f"  File size: {file_stat.st_size:,} bytes")
    print(f"  Last modified: {os.path.getmtime(db_path)}")
    
    from datetime import datetime
    mod_time = datetime.fromtimestamp(os.path.getmtime(db_path))
    print(f"  Modified at: {mod_time.isoformat()}")
    print(f"  Modified today: {mod_time.date() == datetime.now().date()}")
    
    conn.close()
    
except Exception as e:
    import traceback
    print(f"❌ Error: {e}")
    traceback.print_exc()
