#!/usr/bin/env python3
"""
Diagnostic script to test why BTC/Ethereum trades don't execute on Exness
"""

import sqlite3
import json
import time
import sys
import logging
from datetime import datetime

sys.path.insert(0, r'C:\zwesta-trader\Zwesta Flutter App')

logging.basicConfig(
    filename=r'C:\backend\test_exness_execution.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite log each time
)
logger = logging.getLogger(__name__)

def print_and_log(msg):
    print(msg.encode('utf-8', errors='replace').decode('utf-8'))
    logger.info(msg)

def test_exness_execution():
    """Main test function"""
    print_and_log("=" * 80)
    print_and_log("EXNESS BTC/ETH EXECUTION DIAGNOSTIC")
    print_and_log("=" * 80)
    
    # Step 1: Get Exness credentials
    print_and_log("\n[STEP 1] Retrieving Exness credentials...")
    try:
        conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT credential_id, user_id, broker_name, account_number, password, server, is_live 
            FROM broker_credentials 
            WHERE broker_name LIKE '%Exness%' 
            LIMIT 1
        """)
        cred_row = cursor.fetchone()
        
        if not cred_row:
            print_and_log("[FAIL] NO EXNESS CREDENTIALS FOUND")
            return False
        
        cred_id, user_id, broker_name, account, password, server, is_live = cred_row
        print_and_log("[OK] Found credential: Account=%s, Server=%s, Live=%s" % (account, server, bool(is_live)))
        
        # Build credential dict
        cred_data = {
            'broker_name': broker_name,
            'account_number': account,
            'password': password,
            'server': server,
            'is_live': bool(is_live)
        }
        
        conn.close()
    except Exception as e:
        print_and_log("[FAIL] ERROR getting credentials: %s" % str(e))
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Test MT5 connection
    print_and_log("\n[STEP 2] Testing MT5 connection...")
    try:
        from multi_broker_backend_updated import MT5Connection
        import MetaTrader5 as mt5
        
        mt5_conn = MT5Connection(cred_data)
        if not mt5_conn.connect():
            print_and_log(f"❌ FAILED to connect to MT5")
            print_and_log(f"   Account: {account}")
            print_and_log(f"   Server: {server}")
            return False
        
        print_and_log("✅ MT5 connection successful")
        print_and_log(f"   Terminal: {mt5.terminal_info()}")
        print_and_log("   Waiting for readiness...")
        
        if not mt5_conn.wait_for_mt5_ready(timeout_seconds=30):
            print_and_log("❌ MT5 NOT READY after 30 seconds")
            return False
        print_and_log("✅ MT5 is ready")
        
    except Exception as e:
        print_and_log(f"❌ ERROR with MT5 connection: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Check symbols availability
    print_and_log("\n[STEP 3] Checking if BTC/ETH symbols are available...")
    try:
        symbols_to_check = ['EURUSDm', 'BTCUSDm', 'ETHUSDm']
        
        for symbol in symbols_to_check:
            info = mt5.symbol_info(symbol)
            if info:
                print_and_log(f"   ✅ {symbol}: Available | Bid={info.bid}, Ask={info.ask}")
            else:
                print_and_log(f"   ❌ {symbol}: NOT available")
        
    except Exception as e:
        print_and_log(f"❌ ERROR checking symbols: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 4: Try placing a BTC trade
    print_and_log("\n[STEP 4] Attempting BTC trade placement...")
    btc_result = None
    try:
        print_and_log("   Placing 0.01 BTC BUY order...")
        btc_result = mt5_conn.place_order(
            symbol='BTCUSDm',
            order_type='BUY',
            volume=0.01,
            comment='TEST_BTC'
        )
        
        print_and_log(f"   Result: {btc_result}")
        
        if btc_result.get('success'):
            print_and_log("✅ BTC order placed successfully!")
            
            # Check if position exists
            positions = mt5_conn.get_positions()
            btc_pos = None
            for pos in positions:
                symbol = pos.get('symbol', str(pos)).upper()
                if 'BTC' in symbol:
                    btc_pos = pos
                    break
            
            if btc_pos:
                print_and_log(f"✅ BTC position confirmed:")
                print_and_log(f"     Ticket: {btc_pos.get('ticket')}")
                print_and_log(f"     Volume: {btc_pos.get('volume')}")
                print_and_log(f"     Entry: {btc_pos.get('openPrice')}")
                print_and_log(f"     Profit: ${btc_pos.get('profit', 0):.2f}")
            else:
                print_and_log("⚠️  Order succeeded but NO position found in account!")
                print_and_log(f"     All positions: {len(positions)}")
                for i, pos in enumerate(positions[:5]):
                    print_and_log(f"       {i}: {pos.get('symbol')} {pos.get('type', 'UNKNOWN')}")
        else:
            print_and_log(f"❌ BTC order FAILED: {btc_result.get('error', 'Unknown')}")
            
    except Exception as e:
        print_and_log(f"❌ ERROR placing BTC order: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Try placing an ETH trade
    print_and_log("\n[STEP 5] Attempting ETH trade placement...")
    eth_result = None
    try:
        print_and_log("   Placing 0.1 ETH BUY order...")
        eth_result = mt5_conn.place_order(
            symbol='ETHUSDm',
            order_type='BUY',
            volume=0.1,
            comment='TEST_ETH'
        )
        
        print_and_log(f"   Result: {eth_result}")
        
        if eth_result.get('success'):
            print_and_log("✅ ETH order placed successfully!")
            
            # Check if position exists
            positions = mt5_conn.get_positions()
            eth_pos = None
            for pos in positions:
                symbol = pos.get('symbol', str(pos)).upper()
                if 'ETH' in symbol:
                    eth_pos = pos
                    break
            
            if eth_pos:
                print_and_log(f"✅ ETH position confirmed:")
                print_and_log(f"     Ticket: {eth_pos.get('ticket')}")
                print_and_log(f"     Volume: {eth_pos.get('volume')}")
                print_and_log(f"     Entry: {eth_pos.get('openPrice')}")
                print_and_log(f"     Profit: ${eth_pos.get('profit', 0):.2f}")
            else:
                print_and_log("⚠️  Order succeeded but NO position found in account!")
        else:
            print_and_log(f"❌ ETH order FAILED: {eth_result.get('error', 'Unknown')}")
            
    except Exception as e:
        print_and_log(f"❌ ERROR placing ETH order: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 6: Summary and recommendations
    print_and_log("\n" + "=" * 80)
    print_and_log("DIAGNOSTIC SUMMARY")
    print_and_log("=" * 80)
    
    if btc_result and btc_result.get('success'):
        print_and_log("✅ BTC trades CAN be executed")
    else:
        print_and_log("❌ BTC trades CANNOT be executed - SEE ERROR ABOVE")
    
    if eth_result and eth_result.get('success'):
        print_and_log("✅ ETH trades CAN be executed")
    else:
        print_and_log("❌ ETH trades CANNOT be executed - SEE ERROR ABOVE")
    
    print_and_log("\nRECOMMENDATIONS:")
    print_and_log("1. If symbols not available: Enable crypto on your Exness account")
    print_and_log("2. If orders fail with 'symbol not found': Verify symbol names are BTCUSDm/ETHUSDm")
    print_and_log("3. If positions not visible after order: Check account permissions")
    print_and_log("4. Review full log at: C:\\backend\\test_exness_execution.log")
    
    return True

if __name__ == '__main__':
    test_exness_execution()
