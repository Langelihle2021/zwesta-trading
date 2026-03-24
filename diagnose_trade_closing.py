#!/usr/bin/env python3
"""
Comprehensive diagnostic: Check if bot trades are closing and syncing
"""

import sqlite3
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, r'C:\zwesta-trader\Zwesta Flutter App')

print("=" * 80)
print("BOT TRADES: PLACEMENT vs CLOSING vs EXNESS PORTAL SYNC DIAGNOSTIC")
print("=" * 80)

# Step 1: Check backend database for recent trade records
print("\n[STEP 1] Backend Database - Recent Executed Trades")
print("-" * 80)

try:
    conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
    cursor = conn.cursor()
    
    # Get recent trades
    cursor.execute("""
        SELECT bot_id, trade_data, timestamp
        FROM trades
        WHERE timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 15
    """, (int((datetime.now() - timedelta(hours=2)).timestamp() * 1000),))
    
    backend_trades = cursor.fetchall()
    
    if backend_trades:
        print(f"Found {len(backend_trades)} trades in last 2 hours:\n")
        
        btc_count = 0
        eth_count = 0
        
        for bot_id, trade_json, ts in backend_trades[:10]:
            try:
                trade = json.loads(trade_json)
                symbol = trade.get('symbol', '?')
                profit = trade.get('profit', 0)
                
                if 'BTC' in symbol:
                    btc_count += 1
                if 'ETH' in symbol:
                    eth_count += 1
                
                ts_dt = datetime.fromtimestamp(ts / 1000) if ts > 1000000000000 else datetime.fromtimestamp(ts)
                print(f"  {ts_dt.strftime('%H:%M:%S')} | {symbol:10s} | P&L: ${profit:8.2f} | Bot: {bot_id[:8]}...")
            except Exception as e:
                print(f"  [ERROR parsing trade: {e}]")
        
        print(f"\nSummary: {btc_count} BTC trades, {eth_count} ETH trades")
    else:
        print("No backend trades found in last 2 hours")
    
    conn.close()
    
except Exception as e:
    print(f"ERROR accessing backend database: {e}")

# Step 2: Check MT5 terminal for recent closed trades
print("\n\n[STEP 2] MT5 Terminal - Trade History (Last 24 hours)")
print("-" * 80)

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
        print("ERROR: Could not connect to MT5 terminal")
    else:
        if not mt5_conn.wait_for_mt5_ready(timeout_seconds=10):
            print("ERROR: MT5 not ready")
        else:
            # Get deals from last 24 hours
            deals = mt5.history_deals_get(datetime.utcnow() - timedelta(hours=24))
            
            if deals:
                print(f"Found {len(deals)} deals in MT5 history:\n")
                
                # Organize by entry/exit
                entries = []
                exits = []
                
                for deal in deals:
                    deal_time = datetime.fromtimestamp(deal.time).strftime('%H:%M:%S')
                    deal_type = "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL"
                    
                    if deal.entry == mt5.DEAL_ENTRY_IN:
                        entries.append({
                            'time': deal_time,
                            'symbol': deal.symbol,
                            'type': deal_type,
                            'volume': deal.volume,
                            'price': deal.price,
                            'ticket': deal.ticket
                        })
                    else:
                        exits.append({
                            'time': deal_time,
                            'symbol': deal.symbol,
                            'type': deal_type,
                            'volume': deal.volume,
                            'price': deal.price,
                            'profit': deal.profit,
                            'ticket': deal.ticket
                        })
                
                print(f"Entry Orders (OPEN): {len(entries)}")
                for e in entries[-5:]:
                    print(f"  {e['time']} | {e['symbol']:10s} {e['type']:4s} | vol={e['volume']:.2f} | price={e['price']:8.2f}")
                
                print(f"\nExit Orders (CLOSED): {len(exits)}")
                for e in exits[-5:]:
                    print(f"  {e['time']} | {e['symbol']:10s} {e['type']:4s} | vol={e['volume']:.2f} | P&L: ${e['profit']:.2f}")
                
                if len(exits) > 0:
                    print(f"\n✅ CONFIRMED: Trades ARE being closed in MT5 terminal!")
                    print(f"   {len(exits)} exit orders found in terminal history")
                else:
                    print(f"\n❌ WARNING: No exit orders found in MT5 history")
                    print(f"   This means close_position() is NOT placing exit orders")
                    
            else:
                print("No deals found in MT5 history")
                
except Exception as e:
    print(f"ERROR checking MT5: {e}")
    import traceback
    traceback.print_exc()

# Step 3: Recommendations
print("\n\n[STEP 3] Diagnostics & Next Steps")
print("-" * 80)

print("""
✅ IF YOU SEE:
   - Backend trades with profits > 0 (Step 1)
   - Exit orders in MT5 history (Step 2)
   
THEN: Trades ARE closing correctly!

NEXT: Check Exness portal for sync issues:
   1. Log into Exness web: https://my.exness.com
   2. Go to: History → Closed Positions
   3. Filter by last 24 hours
   4. If you see the trades: Exness is syncing (may take 5-30 min)
   5. If you DON'T see trades: Possible Exness API sync issue

---

❌ IF YOU SEE:
   - Backend trades with profits (Step 1)
   - NO exit orders in MT5 history (Step 2)
   
THEN: Problem - close_position() is failing silently

FIX: Restart backend to use new IOC-based closing:
   python multi_broker_backend_updated.py
   
Then check logs for:
   "MT5 close failed" or "MT5 retry"
   
These will show you exact error codes.

---

⏳ IF TRADES SHOW IN MT5 BUT NOT IN EXNESS WEB:

This is normal! Exness web portal sync delays:
   - Typically 5-15 minutes
   - Can be up to 30 minutes during high load
   
Just wait and refresh: https://my.exness.com/history
""")

print("=" * 80)
