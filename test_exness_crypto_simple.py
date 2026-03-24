#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple diagnostic to test BTC/ETH execution on Exness
"""

import sqlite3
import sys
import logging

sys.path.insert(0, r'C:\zwesta-trader\Zwesta Flutter App')

logging.basicConfig(
    filename=r'C:\backend\test_exness_simple.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)
logger = logging.getLogger(__name__)

def log(msg):
    print(msg)
    logger.info(msg)

try:
    log("===============================================================")
    log("EXNESS BTC/ETH TEST START")
    log("===============================================================")
    
    # Get credentials
    log("\n[1] Loading Exness credentials...")
    conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT credential_id, account_number, password, server, is_live
        FROM broker_credentials
        WHERE broker_name LIKE '%Exness%' LIMIT 1
    """)
    cred_row = cursor.fetchone()
    conn.close()
    
    if not cred_row:
        log("FAIL: No Exness credentials found")
        sys.exit(1)
    
    cred_id, account, password, server, is_live = cred_row
    log("OK: Using account %s on server %s" % (account, server))
    
    cred_data = {
        'broker_name': 'Exness',
        'account_number': account,
        'password': password,
        'server': server,
        'is_live': bool(is_live)
    }
    
    # Connect MT5
    log("\n[2] Connecting to MT5...")
    from multi_broker_backend_updated import MT5Connection
    import MetaTrader5 as mt5
    
    mt5_conn = MT5Connection(cred_data)
    if not mt5_conn.connect():
        log("FAIL: Could not connect to MT5")
        sys.exit(1)
    
    log("OK: Connected to MT5")
    
    # Check readiness
    log("\n[3] Waiting for MT5 readiness...")
    if not mt5_conn.wait_for_mt5_ready(timeout_seconds=30):
        log("FAIL: MT5 not ready after 30 seconds")
        sys.exit(1)
    
    log("OK: MT5 is ready")
    
    # Check symbols
    log("\n[4] Checking BTC/ETH symbol availability...")
    for symbol in ['EURUSDm', 'BTCUSDm', 'ETHUSDm']:
        info = mt5.symbol_info(symbol)
        if info and info.bid > 0:
            log("   %s: AVAILABLE (bid=%.2f)" % (symbol, info.bid))
        else:
            log("   %s: NOT AVAILABLE" % symbol)
    
    # Try BTC trade
    log("\n[5] Testing BTC trade placement...")
    btc_result = mt5_conn.place_order(
        symbol='BTCUSDm',
        order_type='BUY',
        volume=0.01,
        comment='TEST'
    )
    
    log("   Result: %s" % btc_result)
    
    if btc_result.get('success'):
        log("OK: BTC order placed successfully")
        positions = mt5_conn.get_positions()
        btc_found = False
        for pos in positions:
            if 'BTC' in str(pos.get('symbol', '')):
                log("   Position ticket=%s volume=%.2f" % (pos.get('ticket'), pos.get('volume', 0)))
                btc_found = True
                break
        if not btc_found:
            log("WARN: Position not found after successful order")
    else:
        log("FAIL: BTC order failed - %s" % btc_result.get('error', 'unknown'))
    
    # Try ETH trade
    log("\n[6] Testing ETH trade placement...")
    eth_result = mt5_conn.place_order(
        symbol='ETHUSDm',
        order_type='BUY',
        volume=0.1,
        comment='TEST'
    )
    
    log("   Result: %s" % eth_result)
    
    if eth_result.get('success'):
        log("OK: ETH order placed successfully")
        positions = mt5_conn.get_positions()
        eth_found = False
        for pos in positions:
            if 'ETH' in str(pos.get('symbol', '')):
                log("   Position ticket=%s volume=%.2f" % (pos.get('ticket'), pos.get('volume', 0)))
                eth_found = True
                break
        if not eth_found:
            log("WARN: Position not found after successful order")
    else:
        log("FAIL: ETH order failed - %s" % eth_result.get('error', 'unknown'))
    
    log("\n===============================================================")
    log("TEST COMPLETE - See log for details: C:\\backend\\test_exness_simple.log")
    log("===============================================================")

except Exception as e:
    log("EXCEPTION: %s" % str(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)
