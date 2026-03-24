#!/usr/bin/env python3
"""
Diagnostic: Check if trades are being properly closed and synced to Exness
"""

import sqlite3
import sys
from datetime import datetime, timedelta

sys.path.insert(0, r'C:\zwesta-trader\Zwesta Flutter App')

# Check recent trades in backend database
print("=" * 70)
print("CHECKING RECENT TRADES IN BACKEND DB")
print("=" * 70)

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
cursor = conn.cursor()

# Check trades table
print("\n[1] Recent trades in backend database:")
cursor.execute("""
    SELECT bot_id, user_id, trade_data, timestamp
    FROM trades
    ORDER BY timestamp DESC
    LIMIT 10
""")

trades = cursor.fetchall()
print(f"Found {len(trades)} recent trades\n")

for bot_id, user_id, trade_json, ts in trades[:5]:
    import json
    try:
        trade = json.loads(trade_json)
        symbol = trade.get('symbol', '?')
        profit = trade.get('profit', 0)
        order_type = trade.get('type', '?')
        
        ts_dt = datetime.fromtimestamp(ts / 1000) if ts > 1000000000000 else datetime.fromtimestamp(ts)
        time_str = ts_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"  {time_str} | {symbol} {order_type} | Profit: ${profit:.2f} | Bot: {bot_id[:12]}...")
    except:
        pass

conn.close()

# Now check MT5 trade history directly
print("\n[2] Checking MT5 trade history via terminal:")
try:
    from multi_broker_backend_updated import MT5Connection
    import MetaTrader5 as mt5
    
    cred_data = {
        'broker_name': 'Exness',
        'account_number': '298997455',
        'password': 'Password123!',
        'server': 'Exness-MT5Trial9',
        'is_live': False
    }
    
    mt5_conn = MT5Connection(cred_data)
    if not mt5_conn.connect():
        print("  ERROR: Could not connect to MT5")
    else:
        print("  Connected to MT5")
        
        # Get recent deals from history
        if not mt5_conn.wait_for_mt5_ready(timeout_seconds=10):
            print("  MT5 not ready")
        else:
            print("  MT5 ready, fetching trade history...")
            
            # Get last N deals
            deals = mt5.history_deals_get(datetime.utcnow() - timedelta(hours=24))
            
            if deals:
                print(f"  Found {len(deals)} deals in last 24 hours:\n")
                
                for deal in deals[-10:]:
                    deal_type = "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL"
                    status = "OPEN" if deal.entry == mt5.DEAL_ENTRY_IN else "CLOSED"
                    entry_type = "ENTRY" if deal.entry == mt5.DEAL_ENTRY_IN else "EXIT"
                    
                    deal_time = datetime.fromtimestamp(deal.time).strftime('%H:%M:%S')
                    print(f"    {deal_time} | {deal.symbol} {deal_type} | Volume: {deal.volume} | Profit: ${deal.profit:.2f} | {entry_type}")
            else:
                print("  No deals found in history")
                
except Exception as e:
    print(f"  ERROR checking MT5: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("POSSIBLE CAUSES:")
print("=" * 70)
print("""
1. EXNESS SYNC DELAY (Most Likely)
   - Trades ARE closed in MT5 terminal
   - But Exness web portal takes 5-30 minutes to sync
   - Check MT5 terminal "Trades" tab to confirm they appear there

2. CLOSE POSITION NOT WORKING
   - Order sends but closing returns error
   - Check backend logs for: "MT5 close failed" or "Could not close position"
   
3. POSITION TICKET MISMATCH
   - Code is closing wrong ticket
   - Position placed but wrong one closed

4. ORDER_FILLING_FOK (Fill or Kill)
   - Close order fails if market doesn't have liquidity
   - Try ORDER_FILLING_IOC (Immediate or Cancel) instead
""")

print("\nTO VERIFY:")
print("1. Open Exness MT5 terminal")
print("2. Click 'View' → 'Terminal'")  
print("3. Click 'Trades' tab")
print("4. Check if your recent BTC/ETH trades appear there")
print("5. If yes: Wait 30 min for web portal to sync")
print("6. If no: Close orders aren't being sent successfully")
