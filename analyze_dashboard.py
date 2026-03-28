#!/usr/bin/env python3
"""
Debug dashboard balance calculation
"""

import sqlite3

DB_PATH = r'C:\backend\zwesta_trading.db'

def analyze_dashboard_data():
    """See where the $352k balance comes from"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("1️⃣ BROKER CREDENTIALS:")
        cursor.execute("""
            SELECT broker_name, account_number, cached_balance, last_balance_update
            FROM broker_credentials
        """)
        for row in cursor.fetchall():
            print(f"   {row['broker_name']} {row['account_number']}: ${row['cached_balance']} (updated: {row['last_balance_update']})")
        
        print("\n2️⃣ USER BOTS (active):")
        cursor.execute("""
            SELECT bot_id, user_id, broker_name, status, 
                   total_profit, total_loss, total_trades
            FROM user_bots
        """)
        count = 0
        for row in cursor.fetchall():
            count += 1
            print(f"   Bot {row['bot_id']}: {row['broker_name']} - {row['status']}")
            print(f"      Trades: {row['total_trades']}, Profit: ${row['total_profit']}, Loss: ${row['total_loss']}")
        if count == 0:
            print("   (No bots)")
        
        print("\n3️⃣ TRADE HISTORY (last 10):")
        cursor.execute("""
            SELECT bot_id, symbol, entry_time, profit, loss
            FROM trade_history
            ORDER BY entry_time DESC
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"   {row['symbol']} on bot {row['bot_id']}: Profit ${row['profit']}, Loss ${row['loss']}")
        
        print("\n4️⃣ TOTAL INVESTED ACROSS ALL BOTS:")
        cursor.execute("""
            SELECT SUM(initial_investment) as total_inv
            FROM user_bots
        """)
        row = cursor.fetchone()
        total_inv = row['total_inv'] or 0
        print(f"   ${total_inv}")
        
        print("\n5️⃣ TOTAL PROFIT/LOSS:")
        cursor.execute("""
            SELECT 
                SUM(total_profit) as total_profit,
                SUM(total_loss) as total_loss,
                SUM(total_profit) - SUM(total_loss) as net_profit
            FROM user_bots
        """)
        row = cursor.fetchone()
        print(f"   Total Profit: ${row['total_profit'] or 0}")
        print(f"   Total Loss: ${row['total_loss'] or 0}")
        print(f"   Net P/L: ${row['net_profit'] or 0}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("DASHBOARD BALANCE CALCULATION ANALYSIS")
    print("=" * 60)
    analyze_dashboard_data()
