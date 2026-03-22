import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('=== DATABASE TABLES ===')
for table in tables:
    print(f'  - {table[0]}')

# Check bots
print('\n=== USER BOTS ===')
cursor.execute('SELECT bot_id, name, status, enabled, symbols FROM user_bots')
bots = cursor.fetchall()
print(f'Total bots: {len(bots)}')
for bot in bots:
    print(f'  {bot[1]} (ID: {bot[0]}) | Status: {bot[2]} | Enabled: {bot[3]} | Symbols: {bot[4]}')

# Check trades table
print('\n=== RECENT TRADES ===')
cursor.execute('SELECT symbol, type, volume, entry_price, exit_price FROM trades ORDER BY entry_time DESC LIMIT 5')
trades = cursor.fetchall()
print(f'Recent trades found: {len(trades)}')
for trade in trades:
    print(f'  {trade[0]} {trade[1]} | Vol: {trade[2]} | Entry: {trade[3]} | Exit: {trade[4]}')

conn.close()
