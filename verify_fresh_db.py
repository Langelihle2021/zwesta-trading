#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]

print(f'✅ Database initialized with {len(tables)} tables')
print(f'✅ bot_credentials exists: {"bot_credentials" in tables}')
print(f'✅ user_bots exists: {"user_bots" in tables}')
print(f'✅ trades exists: {"trades" in tables}')
print(f'✅ broker_credentials exists: {"broker_credentials" in tables}')

conn.close()
