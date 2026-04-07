
import sqlite3
conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\
table\')
tables = cursor.fetchall()
print('All tables:')
for table in tables:
    print(table[0])
print('\\nChecking for trades...')
try:
    cursor.execute('SELECT COUNT(*) FROM trades')
    count = cursor.fetchone()[0]
    print(f'Trades: {count}')
except:
    print('No trades table')
conn.close()

