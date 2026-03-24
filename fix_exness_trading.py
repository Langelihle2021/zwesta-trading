#!/usr/bin/env python3
"""
Fix Exness trading execution for Zwesta bot
- Test MT5 connection with demo credentials
- Verify symbol availability
- Restart bot trading loop
- Monitor trade execution
"""

import sqlite3
import json
import time
import MetaTrader5 as mt5
from datetime import datetime

DB_PATH = r"C:\zwesta-trader\Zwesta Flutter App\trading_bot.db"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def test_mt5_connection():
    """Test MT5 connection to Exness demo"""
    print("\n" + "="*60)
    print("TESTING MT5 CONNECTION TO EXNESS DEMO")
    print("="*60)
    
    # Ensure MT5 is initialized
    if not mt5.initialize():
        print(f"❌ MT5 initialization failed: {mt5.last_error()}")
        return False
    
    print("✓ MT5 initialized")
    
    # Get MT5 terminals
    terminals = mt5.terminal_info()
    print(f"\nAvailable terminals:")
    for term in terminals:
        print(f"  - {term}")
    
    # Try to login to Exness demo
    account_num = 1001770  # From your bot config
    password = "Zwesta@1985"
    server = "Exness-MT5Trial9"  # Demo server
    
    print(f"\nAttempting login:")
    print(f"  Account: {account_num}")
    print(f"  Server: {server}")
    
    login_result = mt5.login(account_num, password, server)
    
    if not login_result:
        print(f"❌ Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    
    print("✓ Login successful")
    
    # Check account info
    account_info = mt5.account_info()
    if account_info:
        print(f"\n✓ Account Info:")
        print(f"  Balance: ${account_info.balance}")
        print(f"  Equity: ${account_info.equity}")
        print(f"  Free Margin: ${account_info.margin_free}")
    
    # Test symbol availability
    test_symbols = ["EURUSDm", "GBPUSDm", "ETHUSDm", "BITCOINm"]
    print(f"\nTesting symbol availability:")
    for symbol in test_symbols:
        info = mt5.symbol_info(symbol)
        if info:
            print(f"  ✓ {symbol}: bid={info.bid}, ask={info.ask}")
        else:
            print(f"  ❌ {symbol}: NOT FOUND")
    
    mt5.shutdown()
    return True

def check_bot_status():
    """Check bot configuration and status"""
    print("\n" + "="*60)
    print("CHECKING BOT CONFIGURATION")
    print("="*60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get bot info
    cursor.execute("SELECT * FROM bots WHERE id = 'test_bot_1774129348175'")
    bot = cursor.fetchone()
    
    if bot:
        print(f"✓ Bot found: {bot['name']}")
        print(f"  Status: {bot['status']}")
        print(f"  Symbol: {bot['symbol']}")
        print(f"  Type: {bot['type']}")
        print(f"  Enabled: {bot['enabled']}")
        
        config = json.loads(bot['config'])
        print(f"\nBot Config:")
        print(f"  Entry Amount: {config.get('entry_amount', 'N/A')}")
        print(f"  Stop Loss: {config.get('stop_loss', 'N/A')}")
        print(f"  Take Profit: {config.get('take_profit', 'N/A')}")
    else:
        print("❌ Bot not found")
        conn.close()
        return False
    
    # Check trades
    cursor.execute("SELECT COUNT(*) as count FROM trades WHERE bot_id = 'test_bot_1774129348175'")
    trade_count = cursor.fetchone()['count']
    print(f"\n✓ Trades Executed: {trade_count}")
    
    if trade_count > 0:
        cursor.execute("""
            SELECT * FROM trades 
            WHERE bot_id = 'test_bot_1774129348175' 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        trades = cursor.fetchall()
        print("\nLast 3 trades:")
        for trade in trades:
            print(f"  - Type: {trade['type']}, Status: {trade['status']}, Created: {trade['created_at']}")
    
    conn.close()
    return True

def enable_bot_trading():
    """Ensure bot is enabled and ready"""
    print("\n" + "="*60)
    print("ENABLING BOT FOR TRADING")
    print("="*60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update bot status
    cursor.execute("""
        UPDATE bots 
        SET status = 'active', enabled = 1, updated_at = datetime('now')
        WHERE id = 'test_bot_1774129348175'
    """)
    
    conn.commit()
    print("✓ Bot enabled and status set to 'active'")
    
    # Verify
    cursor.execute("SELECT status, enabled FROM bots WHERE id = 'test_bot_1774129348175'")
    row = cursor.fetchone()
    print(f"  Status: {row['status']}, Enabled: {row['enabled']}")
    
    conn.close()
    return True

def main():
    """Run all diagnostics and fixes"""
    print("\n" + "█"*60)
    print("█  ZWESTA TRADER - EXNESS TRADING FIX")
    print("█"*60)
    
    print("\nStep 1: Testing MT5 Connection...")
    if not test_mt5_connection():
        print("\n⚠️  MT5 connection test failed. Check your credentials.")
        return False
    
    print("\nStep 2: Checking Bot Configuration...")
    if not check_bot_status():
        print("\n⚠️  Bot status check failed.")
        return False
    
    print("\nStep 3: Enabling Bot for Trading...")
    if not enable_bot_trading():
        print("\n⚠️  Failed to enable bot.")
        return False
    
    print("\n" + "="*60)
    print("✓ ALL CHECKS PASSED")
    print("="*60)
    print("\nNext steps:")
    print("1. Start the Flask backend: python multi_broker_backend_updated.py")
    print("2. The bot trading loop will begin automatically")
    print("3. Monitor trades in the database or Flutter app")
    print("\nWatch for trades starting within 30-60 seconds of backend startup")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
