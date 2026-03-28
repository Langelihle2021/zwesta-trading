#!/usr/bin/env python3
"""
Diagnose why bots aren't executing trades on Exness
Check: MT5 connection, signal generation, order placement
"""

import sys
import os
import time
import sqlite3
from datetime import datetime

# Add backend to path
sys.path.insert(0, 'c:\\zwesta-trader\\Zwesta Flutter App')

print("=" * 80)
print("🔍 BOT TRADING EXECUTION DIAGNOSTIC")
print("=" * 80)

# 1. Check database has everything needed
print("\n[1/5] DATABASE INTEGRITY CHECK")
try:
    db_path = r"C:\backend\zwesta_trading.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check bots
    cursor.execute("SELECT COUNT(*) FROM user_bots")
    bot_count = cursor.fetchone()[0]
    print(f"  ✓ Bots in database: {bot_count}")
    
    # Check credentials
    cursor.execute("SELECT COUNT(*) FROM broker_credentials")
    cred_count = cursor.fetchone()[0]
    print(f"  ✓ Broker credentials: {cred_count}")
    
    # Check if any trades were placed
    cursor.execute("SELECT COUNT(*) FROM trades WHERE created_at > date('now', '-1 day')")
    today_trades = cursor.fetchone()[0]
    print(f"  ✓ Trades today: {today_trades}")
    
    if bot_count > 0 and cred_count > 0:
        print("  ✅ Database looks good")
    conn.close()
except Exception as e:
    print(f"  ❌ Database error: {e}")
    sys.exit(1)

# 2. Check backend imports
print("\n[2/5] BACKEND IMPORTS CHECK")
try:
    # Try to import key modules
    import MetaTrader5 as mt5
    print("  ✓ MetaTrader5 SDK available")
    
    # Check if MT5 is available
    if mt5.terminal_info():
        print("  ✓ MT5 terminal detected (running)")
    else:
        print("  ⚠️  MT5 terminal not responding")
    
    print("  ✅ Imports successful")
except ImportError as e:
    print(f"  ❌ Import error: {e}")
    print("     MT5 SDK not installed or not in Python path")
except Exception as e:
    print(f"  ⚠️  MT5 check failed: {e}")

# 3. Check if backend service is running
print("\n[3/5] BACKEND SERVICE CHECK")
try:
    import requests
    time.sleep(1)
    
    # Try to connect to Flask backend
    response = requests.get('http://localhost:5000/api/health', timeout=5)
    if response.status_code == 200:
        print("  ✓ Backend service running on port 5000")
        print(f"  ✓ Health status: {response.json()}")
        print("  ✅ Backend is online")
    else:
        print(f"  ⚠️  Backend returned status {response.status_code}")
except requests.exceptions.ConnectionError:
    print("  ❌ Backend not running on localhost:5000")
    print("     Start the backend with: python multi_broker_backend_updated.py")
except Exception as e:
    print(f"  ⚠️  Backend check failed: {e}")

# 4. Check trade signal generation
print("\n[4/5] TRADE SIGNAL CHECK")
try:
    # Check if commodity_market_data is being updated
    # This is global in the backend
    print("  ℹ️  Signal generation happens IN the backend process")
    print("  ℹ️  Check backend logs for:")
    print("      - 'evaluate_trade_signal_strength'")
    print("      - 'BUY' or 'SELL' signals")
    print("      - 'Trade cycle' log messages")
    print("  ✓ Use: tail -f backend.log | grep -i signal")
except Exception as e:
    print(f"  ⚠️  {e}")

# 5. Check MT5 trading capability
print("\n[5/5] MT5 TRADING CHECK")
try:
    # Try to get account info
    import MetaTrader5 as mt5
    
    acct_info = mt5.account_info()
    if acct_info:
        print(f"  ✓ MT5 Account: {acct_info.login}")
        print(f"  ✓ Balance: ${acct_info.balance:.2f}")
        print(f"  ✓ Equity: ${acct_info.equity:.2f}")
        print(f"  ✓ Server: {acct_info.server}")
        print("  ✅ MT5 trading ready")
    else:
        print("  ❌ MT5 not logged in - no account info")
        print("     Need to login with credentials first")
except Exception as e:
    print(f"  ⚠️  MT5 check failed: {e}")

print("\n" + "=" * 80)
print("DIAGNOSIS SUMMARY")
print("=" * 80)

print("""
If bots aren't trading, check these in order:

1. ❌ Backend not running
   → Start: python multi_broker_backend_updated.py

2. ❌ MT5 terminal not running  
   → Start: MetaTrader5 (or PXBT terminal if using that)

3. ❌ MT5 not logged in
   → Check backend logs for login errors
   → May need to re-enter credentials

4. ⚠️  No trade signals being generated
   → Check commodity_market_data is being updated
   → Check signal thresholds in bot config
   → May need to wait for signal strength to meet threshold

5. ⚠️  Trades executing but not showing
   → Check if positions are being closed automatically
   → Check trade history in Exness platform

NEXT STEPS:
1. Restart the backend service
2. Watch backend logs for errors
3. Check if bots start placing trades
4. If still failing, run: python diagnose_execution_errors.py
""")

print("=" * 80)
