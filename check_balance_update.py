#!/usr/bin/env python3
"""
Force refresh balance from MT5 and compare with app cache
"""

import sqlite3
import requests
from datetime import datetime

DB_PATH = r'C:\backend\zwesta_trading.db'
BACKEND_URL = 'http://localhost:9000'

def check_balance_cache():
    """Check what the app has cached"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT broker_name, account_number, cached_balance, last_balance_update
            FROM broker_credentials
            WHERE broker_name = 'Exness'
        """)
        
        print("📊 CACHED BALANCE IN DATABASE:")
        for broker, account, cached_bal, last_update in cursor.fetchall():
            print(f"  {broker} {account}: ${cached_bal} (updated: {last_update})")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Cache check failed: {e}")
        return False

def trigger_balance_refresh():
    """Call an endpoint that should refresh the balance"""
    try:
        # This should trigger MT5 connection and refresh cache
        resp = requests.get(f'{BACKEND_URL}/api/broker/exness/account', timeout=10)
        print(f"\n🔄 BALANCE REFRESH ATTEMPT:")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Response: {data}")
            if 'balance' in data:
                print(f"  Fresh balance from MT5: ${data['balance']}")
            return True
        else:
            print(f"  ⚠️ Status {resp.status_code}: {resp.json()}")
            return False
    except Exception as e:
        print(f"  ❌ Refresh failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("BALANCE CACHE vs EXNESS LIVE COMPARISON")
    print("=" * 60)
    
    check_balance_cache()
    trigger_balance_refresh()
    
    # Check again after refresh
    print("\n" + "=" * 60)
    print("After refresh:")
    print("=" * 60)
    check_balance_cache()
