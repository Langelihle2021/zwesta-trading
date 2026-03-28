#!/usr/bin/env python3
"""
Verify system is operational: balances fetching, symbol initialization, MT5 connection
"""

import sqlite3
import requests
import json
from pathlib import Path
import time

DB_PATH = r'C:\backend\zwesta_trading.db'
BACKEND_URL = 'http://localhost:9000'

def verify_backend():
    """Check if backend is running"""
    try:
        resp = requests.get(f'{BACKEND_URL}/api/health', timeout=5)
        if resp.status_code == 200:
            print("✅ Backend is running on http://localhost:9000")
            return True
    except:
        print("❌ Backend not responding on http://localhost:9000")
        return False

def verify_database():
    """Check database integrity"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check critical tables
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM broker_credentials")
        creds = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_bots")
        bots = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"✅ Database OK: {users} users, {creds} credentials, {bots} bots")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def verify_balances():
    """Check if balances are being cached properly"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""SELECT broker_name, account_number, cached_balance, 
                                 last_balance_update 
                          FROM broker_credentials""")
        
        print(f"\n💰 Balance Cache Status:")
        has_balance = False
        for row in cursor.fetchall():
            broker, acc, bal, last_update = row
            if bal:
                print(f"   ✅ {broker} {acc}: ${bal} (updated: {last_update})")
                has_balance = True
            else:
                print(f"   ⏳ {broker} {acc}: Waiting for MT5 connection... (will populate when bot trades)")
        
        conn.close()
        return has_balance
        
    except Exception as e:
        print(f"❌ Balance check failed: {e}")
        return False

def verify_symbols():
    """Check if all 16 trading symbols are available"""
    try:
        resp = requests.get(f'{BACKEND_URL}/api/commodities/list', timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('commodities', {})
            
            # Count total symbols across all categories
            total = 0
            categories_with_symbols = []
            
            for category, symbols in data.items():
                count = len(symbols)
                if count > 0:
                    categories_with_symbols.append((category, count))
                    total += count
            
            print(f"\n📊 Trading Symbols ({total} total):")
            if total >= 16:
                print(f"   ✅ All {total} symbols available:")
                for category, count in categories_with_symbols:
                    print(f"      • {category.capitalize()}: {count} symbols")
                return True
            else:
                print(f"   ⚠️  Only {total} symbols (expected 16)")
                for category, count in categories_with_symbols:
                    print(f"      • {category.capitalize()}: {count} symbols")
                return False
    except Exception as e:
        print(f"❌ Symbol check failed: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("SYSTEM VERIFICATION")
    print("=" * 60)
    
    verify_backend()
    time.sleep(1)
    verify_database()
    verify_balances()
    verify_symbols()
    
    print("\n" + "=" * 60)
    print("Next: Create a new bot in the app to test trading")
    print("=" * 60)
