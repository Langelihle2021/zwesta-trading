#!/usr/bin/env python3
"""
Monitor bot trading execution - watch for trades being placed
"""

import sqlite3
import time
from datetime import datetime, timedelta

DB_PATH = r"C:\backend\zwesta_trading.db"

def monitor_trades():
    """Watch for trades being placed"""
    print("=" * 70)
    print("📊 BOT TRADING EXECUTION MONITOR")
    print("=" * 70)
    print("\nWatching for trade execution in real-time...")
    print("Update interval: Every 10 seconds\n")
    
    last_trade_count = 0
    check_interval = 10  # seconds
    
    try:
        while True:
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                # Get current bot status
                cursor.execute('''
                    SELECT bot_id, status, enabled 
                    FROM user_bots 
                    WHERE bot_id LIKE 'bot_demo%'
                    ORDER BY bot_id
                ''')
                bots = cursor.fetchall()
                
                # Count trades
                cursor.execute('SELECT COUNT(*) FROM trades')
                trade_count = cursor.fetchone()[0]
                
                # Get recent trades
                cursor.execute('''
                    SELECT trade_id, bot_id, symbol, action, price, quantity, 
                           status, pnl, created_at 
                    FROM trades 
                    ORDER BY created_at DESC 
                    LIMIT 5
                ''')
                recent_trades = cursor.fetchall()
                
                conn.close()
                
                # Print status
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status Update:")
                print(f"  🤖 Active Bots:")
                for bot_id, status, enabled in bots:
                    status_emoji = "✅" if status == "running" else "⏸️"
                    enabled_emoji = "🟢" if enabled else "⛔"
                    print(f"     {enabled_emoji} {bot_id}: {status_emoji} {status}")
                
                print(f"\n  💰 Trades Executed: {trade_count}")
                if trade_count > last_trade_count:
                    print(f"     ✨ NEW TRADES DETECTED! (+{trade_count - last_trade_count})")
                    last_trade_count = trade_count
                
                if recent_trades:
                    print(f"\n  📈 Recent Trades:")
                    for trade_id, bot_id, symbol, action, price, qty, status, pnl, created_at in recent_trades:
                        arrow = "📈" if action == "BUY" else "📉"
                        pnl_emoji = "✅" if pnl and pnl > 0 else "❌" if pnl and pnl < 0 else "⏳"
                        print(f"     {arrow} {trade_id}: {bot_id} {action} {qty} {symbol} @ {price} | {status} | P&L={pnl} {pnl_emoji}")
                
                time.sleep(check_interval)
                
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  DB locked (bot is trading): {str(e)[:40]}...")
                time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 Monitoring stopped by user")
        print("=" * 70)

if __name__ == '__main__':
    monitor_trades()
