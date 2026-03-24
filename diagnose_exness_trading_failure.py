#!/usr/bin/env python3
"""
Diagnostic script to identify why Exness bots aren't executing trades
Latest: 2026-03-23

Issue: Bots create but don't execute trades on Exness
Last worked: May 19-20, 2025
Current date: March 23, 2026
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

DB_PATH = r"C:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db"

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def check_bot_status():
    """Check if bots exist and their status"""
    print_section("BOT STATUS CHECK")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM user_bots")
        total_bots = cursor.fetchone()[0]
        print(f"✓ Total bots in system: {total_bots}")
        
        cursor.execute("SELECT COUNT(*) as enabled FROM user_bots WHERE enabled=1")
        enabled_bots = cursor.fetchone()[0]
        print(f"✓ Enabled bots: {enabled_bots}")
        
        cursor.execute("SELECT bot_id, name, status, enabled, symbols FROM user_bots WHERE enabled=1 LIMIT 5")
        for bot_id, name, status, enabled, symbols in cursor.fetchall():
            print(f"\n  Bot: {name}")
            print(f"    ID: {bot_id}")
            print(f"    Status: {status}")
            print(f"    Symbols: {symbols}")
        
        conn.close()
        return total_bots > 0 and enabled_bots > 0
    except Exception as e:
        print(f"✗ Error checking bot status: {e}")
        return False

def check_trades():
    """Check if any trades have been executed"""
    print_section("TRADE EXECUTION CHECK")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM trades")
        total_trades = cursor.fetchone()[0]
        print(f"✓ Total trades executed: {total_trades}")
        
        if total_trades == 0:
            print("  ⚠️  WARNING: No trades have been executed at all!")
            print("  This indicates the bot trading loop is not running or cannot place orders")
        else:
            cursor.execute("SELECT MAX(timestamp) FROM trades")
            last_trade = cursor.fetchone()[0]
            if last_trade:
                from datetime import datetime
                dt = datetime.fromtimestamp(last_trade/1000)
                print(f"✓ Last trade: {dt}")
        
        conn.close()
        return total_trades > 0
    except Exception as e:
        print(f"✗ Error checking trades: {e}")
        return False

def check_exness_credentials():
    """Check Exness broker credentials"""
    print_section("EXNESS CREDENTIALS CHECK")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT credential_id, user_id, account_number, password, server, is_live 
            FROM broker_credentials 
            WHERE broker_name LIKE '%Exness%'
        """)
        
        creds = cursor.fetchall()
        if not creds:
            print("✗ No Exness credentials found in database!")
            return False
        
        print(f"✓ Found {len(creds)} Exness credential(s)")
        
        for cred_id, user_id, account_num, password, server, is_live in creds:
            print(f"\n  Credential ID: {cred_id}")
            print(f"  Account: {account_num}")
            print(f"  Server: {server}")
            print(f"  Mode: {'🔴 LIVE' if is_live else '🟢 DEMO'}")
            
            # Check if account exists in user_accounts
            cursor.execute("SELECT COUNT(*) FROM user_accounts WHERE account_number=?", (account_num,))
            account_exists = cursor.fetchone()[0] > 0
            print(f"  Account in system: {'✓ Yes' if account_exists else '✗ No'}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Error checking credentials: {e}")
        return False

def check_mt5_configuration():
    """Check MT5 installation and configuration"""
    print_section("MT5 INSTALLATION CHECK")
    try:
        import MetaTrader5 as mt5
        print("✓ MetaTrader5 Python module is installed")
        
        mt5_paths = [
            r'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe',
            r'C:\Program Files\Exness MT5\terminal64.exe',
            r'C:\Program Files (x86)\Exness MT5\terminal64.exe',
            r'C:\MT5\Exness\terminal64.exe',
            r'C:\Program Files\XM Global MT5\terminal.exe',
            r'C:\Program Files\MetaTrader 5\terminal64.exe',
        ]
        
        exness_found = False
        for path in mt5_paths:
            if os.path.exists(path):
                print(f"✓ Found MT5: {path}")
                exness_found = True
                break
        
        if not exness_found:
            print("✗ Exness MT5 terminal not found! Expected at:")
            for path in mt5_paths:
                print(f"   - {path}")
        
        return exness_found
    except ImportError:
        print("✗ MetaTrader5 module not installed!")
        print("  Install with: pip install MetaTrader5")
        return False
    except Exception as e:
        print(f"✗ Error checking MT5: {e}")
        return False

def check_bot_credentials_table():
    """Check if bot credentials are properly stored"""
    print_section("BOT CREDENTIALS CHECK")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM bot_credentials")
        total = cursor.fetchone()[0]
        print(f"✓ Bot credentials stored: {total}")
        
        cursor.execute("SELECT bot_id, credential_id FROM bot_credentials LIMIT 5")
        for bot_id, cred_id in cursor.fetchall():
            print(f"  Bot {bot_id[:20]}... -> Credential {cred_id}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Error checking bot credentials: {e}")
        return False

def print_recommendations():
    """Print recommended fixes"""
    print_section("RECOMMENDED FIXES")
    print("""
1. VERIFY BACKEND SERVICE IS RUNNING:
   - Check if Flask backend is active
   - Start with: python multi_broker_backend_updated.py
   - Should see log messages about starting bots

2. VERIFY MT5 TERMINAL IS RUNNING:
   - Exness MT5 terminal must be open and logged in
   - Run: C:\\Program Files\\Exness MT5\\terminal64.exe

3. CHECK CREDENTIALS:
   - Verify Exness account is properly configured
   - Test connection via: /api/broker/test-connection endpoint
   - Use: POST with accountId, password, server

4. RESTART BOT:
   - Stop the current bot
   - Clear bot cache/state files
   - Start fresh

5. VERIFY SYMBOLS:
   - Exness uses symbol suffixes: EURUSDm, BTCUSDm, ETHUSDm
   - Check that bot symbols match Exness format
   - Run: /api/commodities/list to verify available symbols

6. CHECK LOGS:
   - Monitor: multi_broker_backend_updated.log
   - Look for MT5 connection errors
   - Look for "CONTINUOUS TRADING LOOP" messages
    """)

def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "EXNESS BOT TRADING DIAGNOSTIC" + " "*30 + "║")
    print("║" + " "*20 + "Generated: 2026-03-23" + " "*40 + "║")
    print("╚" + "="*78 + "╝")
    
    results = []
    results.append(("Bot Status", check_bot_status()))
    results.append(("Trades Executed", check_trades()))
    results.append(("Exness Credentials", check_exness_credentials()))
    results.append(("MT5 Installation", check_mt5_configuration()))
    results.append(("Bot Credentials", check_bot_credentials_table()))
    
    print_section("DIAGNOSTIC SUMMARY")
    all_ok = True
    for check_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {check_name:.<40} {status}")
        if not result:
            all_ok = False
    
    print("\n")
    if all_ok:
        print("✓ All checks passed! Bot should be trading.")
        print("  If trades still aren't executing, check the backend log for details.")
    else:
        print("✗ Some checks failed. See recommendations below:")
    
    print_recommendations()
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    main()
