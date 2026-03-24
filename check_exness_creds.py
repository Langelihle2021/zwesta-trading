#!/usr/bin/env python3
"""Check Exness credentials in database"""

import sqlite3
import json

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cursor = conn.cursor()

# Check table structure
print("=== BROKER_CREDENTIALS TABLE STRUCTURE ===")
cursor.execute("PRAGMA table_info(broker_credentials)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Check for Exness data
print("\n=== EXNESS CREDENTIALS IN DATABASE ===")
try:
    cursor.execute("SELECT * FROM broker_credentials WHERE broker_name LIKE '%Exness%' LIMIT 5")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} Exness records")
    
    if rows:
        # Get column names
        cursor.execute("SELECT * FROM broker_credentials WHERE broker_name LIKE '%Exness%' LIMIT 1")
        col_names = [description[0] for description in cursor.description]
        print(f"\nColumns: {col_names}")
        
        for row in rows:
            print(f"\nRecord: {row}")
            
except Exception as e:
    print(f"Error: {e}")

conn.close()
