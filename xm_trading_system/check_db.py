import sqlite3

db = sqlite3.connect('zwesta_trading.db')
cursor = db.cursor()

print('=== DATABASE SCHEMA ===\n')
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    print(f'Table: {table_name}')
    cursor.execute(f'PRAGMA table_info({table_name})')
    columns = cursor.fetchall()
    for col in columns:
        print(f'  ├─ {col[1]:20} ({col[2]})')
    
    # Count rows
    cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
    count = cursor.fetchone()[0]
    print(f'  └─ Records: {count}\n')

db.close()
