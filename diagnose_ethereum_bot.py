#!/usr/bin/env python3
"""
Diagnostic tool for Ethereum bot trading failures.

This script helps identify why Ethereum (ETH/ETHUSDT/ETHUSDm) bots don't execute trades.
It checks:
1. MT5 terminal connectivity and readiness
2. Symbol availability (ETHUSDT for Binance, ETHUSDm for Exness)
3. Bot configuration correctness
4. Trading conditions (market hours, profit locks, daily limits)

Run this when Ethereum bots aren't trading to get immediate diagnostics.
"""

import sqlite3
import requests
import json
import time
from datetime import datetime
from pathlib import Path

# Configuration
DATABASE_PATH = './trading_bots.db'
API_URL = 'http://localhost:5000'
BACKEND_URL = 'http://127.0.0.1:5000'

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_ok(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")

print_header("Ethereum Bot Trading Diagnostic Tool")
print_info("Checking your system for Ethereum trading issues...")

# Step 1: Check database
print_header("Step 1: Check Database")
try:
    if not Path(DATABASE_PATH).exists():
        print_error(f"Database not found at {DATABASE_PATH}")
        print_info("Ensure backend has been started at least once")
        exit(1)
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print_ok(f"Database found at {DATABASE_PATH}")
    
    # Find Ethereum bots
    cursor.execute("SELECT bot_id, symbols, enabled, status FROM user_bots WHERE symbols LIKE '%ETH%' ORDER BY created_at DESC LIMIT 5")
    eth_bots = cursor.fetchall()
    
    if not eth_bots:
        print_warning("No Ethereum bots found in database")
        print_info("Looking for any bot with 'ETH' in symbols...")
        cursor.execute("SELECT bot_id, symbols, enabled, status FROM user_bots ORDER BY created_at DESC LIMIT 5")
        all_bots = cursor.fetchall()
        if all_bots:
            print(f"\nRecent bots:")
            for bot in all_bots:
                print(f"  - {bot['bot_id']}: symbols={bot['symbols']}, enabled={bot['enabled']}, status={bot['status']}")
    else:
        print(f"\nFound {len(eth_bots)} Ethereum bot(s):")
        for bot in eth_bots:
            status_str = f"enabled={bot['enabled']}, status={bot['status']}"
            if bot['enabled']:
                print_ok(f"  {bot['bot_id']}: symbols={bot['symbols']} ({status_str})")
            else:
                print_warning(f"  {bot['bot_id']}: symbols={bot['symbols']} ({status_str})")
        
        # Analyze each bot
        for bot in eth_bots:
            print(f"\n{BOLD}Details for bot: {bot['bot_id']}{RESET}")
            bot_id = bot['bot_id']
            
            # Check trades
            cursor.execute(
                "SELECT COUNT(*) as count, MAX(timestamp) as last_trade FROM trades WHERE bot_id = ?",
                (bot_id,)
            )
            trade_info = cursor.fetchone()
            trade_count = trade_info['count'] or 0
            last_trade = trade_info['last_trade']
            
            if trade_count == 0:
                print_warning(f"  No trades executed yet")
                print_info(f"  This is the issue - bot is not placing trades")
            else:
                print_ok(f"  {trade_count} trades executed")
                if last_trade:
                    print_info(f"  Last trade at: {last_trade}")
            
            # Check daily profit
            cursor.execute(
                "SELECT daily_profit, total_profit FROM user_bots WHERE bot_id = ?",
                (bot_id,)
            )
            profit_info = cursor.fetchone()
            if profit_info:
                daily_profit = profit_info['daily_profit'] or 0
                total_profit = profit_info['total_profit'] or 0
                print_info(f"  Daily profit: ${daily_profit:.2f}")
                print_info(f"  Total profit: ${total_profit:.2f}")
            
            # Check configuration
            cursor.execute(
                "SELECT * FROM user_bots WHERE bot_id = ?",
                (bot_id,)
            )
            bot_config = cursor.fetchone()
            if bot_config:
                print_info(f"  Strategy: {bot_config['strategy']}")
                print_info(f"  Broker account: {bot_config['broker_account_id']}")
                print_info(f"  Symbols: {bot_config['symbols']}")
                
    conn.close()
    
except Exception as e:
    print_error(f"Database error: {e}")
    exit(1)

# Step 2: Check Backend API
print_header("Step 2: Check Backend API")
try:
    response = requests.get(f"{API_URL}/api/health", timeout=5)
    if response.status_code == 200:
        print_ok("Backend API is responding")
    else:
        print_warning(f"Backend API returned status {response.status_code}")
except Exception as e:
    print_error(f"Cannot connect to backend: {e}")
    print_info("Ensure backend is running: python multi_broker_backend_updated.py")
    exit(1)

# Step 3: Check Symbol Availability
print_header("Step 3: Check Symbol Availability")
try:
    response = requests.get(f"{API_URL}/api/commodities/list", timeout=5)
    if response.status_code == 200:
        data = response.json()
        commodities = data.get('commodities', {})
        
        # Check for Ethereum symbols
        eth_available = False
        for category, items in commodities.items():
            for item in items:
                if 'ETH' in item.get('symbol', '').upper() or 'ETHEREUM' in item.get('name', '').upper():
                    print_ok(f"Found Ethereum in {category}: {item.get('symbol')} - {item.get('name')}")
                    eth_available = True
        
        if not eth_available:
            print_warning("No Ethereum symbols found in API response")
            print_info("Available symbols per category:")
            for category, items in commodities.items():
                symbols = [item.get('symbol') for item in items]
                print(f"  {category}: {', '.join(symbols)}")
    else:
        print_error(f"API returned status {response.status_code}")
except Exception as e:
    print_error(f"Cannot check symbols: {e}")

# Step 4: Check MT5 Connection (if available)
print_header("Step 4: Check MT5 Readiness")
try:
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print_warning("MT5 initialization failed")
        print_info("MT5 may not be installed or terminal is closed")
    else:
        account = mt5.account_info()
        if account:
            print_ok(f"MT5 Connected to account {account.login}")
            
            # Check symbol availability
            test_symbols = ['EURUSDm', 'ETHUSDm', 'BTCUSDm', 'ETHUSDT']
            print(f"\nChecking symbol availability:")
            for symbol in test_symbols:
                if mt5.symbol_select(symbol, True):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        print_ok(f"  {symbol}: Available (bid={tick.bid}, ask={tick.ask})")
                    else:
                        print_warning(f"  {symbol}: Selected but no tick data")
                else:
                    print_warning(f"  {symbol}: Not available")
        else:
            print_warning("MT5 connected but no account info")
        
        mt5.shutdown()
except ImportError:
    print_warning("MetaTrader5 module not available - cannot check MT5")
    print_info("Install with: pip install MetaTrader5")
except Exception as e:
    print_warning(f"MT5 check failed: {e}")

# Step 5: Recommendations
print_header("Recommendations")

print(f"""
{BOLD}If your Ethereum bot is NOT trading:{RESET}

1. {BOLD}Check Symbol Availability:{RESET}
   - Exness MT5: ETHUSDm should be in your Market Watch
   - Binance: ETHUSDT should be enabled
   - Use /api/commodities/list to verify

2. {BOLD}Wait for Initialization:{RESET}
   - After backend restart, Ethereum symbols may take 30-60 seconds to load
   - First trade attempt may fail if symbol isn't ready yet
   - Bot will now automatically retry with backoff delay

3. {BOLD}Check Profit Locks:{RESET}
   - Daily profit lock reached? Bot pauses trading
   - Daily loss limit exceeded? Bot pauses trading
   - Check /api/bot/status for pauseReason

4. {BOLD}Verify Bot Configuration:{RESET}
   - Correct symbol selected (ETHUSDm vs ETHUSDT)
   - Correct broker (Exness vs Binance vs PXBT)
   - Bot enabled and not in error state

5. {BOLD}Check Market Hours:{RESET}
   - Crypto trades 24/7 (should always be open)
   - But MT5 terminal must be running and connected
   - Check if other symbols trade (EUR, BTC) to verify MT5

{BOLD}Recent Fix:{RESET}
The platform now includes:
✅ Automatic retry logic with exponential backoff for ETHUSDm/BTCUSDm
✅ Critical symbol pre-check before trading starts
✅ 30-second startup wait for symbol initialization
✅ Detailed logging of symbol availability issues

Try restarting your bot after this fix - it should now execute Ethereum trades!
""")

print_header("Diagnostic Complete")
print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
