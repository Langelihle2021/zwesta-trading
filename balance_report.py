#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cur = conn.cursor()

print('=== BOTS (count) ===')
cur.execute('SELECT COUNT(*) FROM user_bots')
print(f'Total bots: {cur.fetchone()[0]}')

print('\n=== TRADES (count) ===')
cur.execute('SELECT COUNT(*) FROM trades')
total_trades = cur.fetchone()[0]
print(f'Total trades: {total_trades}')

if total_trades > 0:
    cur.execute('SELECT SUM(profit) FROM trades')
    total_pl = cur.fetchone()[0] or 0
    print(f'Total Profit from trades: ${total_pl}')

print('\n=== BROKER CREDENTIALS ===')
cur.execute('SELECT broker_name, account_number, cached_balance, cached_equity, last_balance_update FROM broker_credentials')
for row in cur.fetchall():
    print(f'{row[0]} {row[1]}: Balance=${row[2]}, Equity=${row[3]}, Updated={row[4]}')

print('\n=== LAST 5 TRADES ===')
cur.execute('SELECT symbol, price, profit, created_at FROM trades ORDER BY created_at DESC LIMIT 5')
for row in cur.fetchall():
    print(f'{row[0]}: P/L ${row[2]} @ {row[3]}')
