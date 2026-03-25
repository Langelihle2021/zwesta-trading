#!/usr/bin/env python3
"""
Verify Zwesta Trading System is working correctly
"""
import requests
import json
import sqlite3
from datetime import datetime

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings()

def test_dashboard():
    """Test if dashboard loads"""
    try:
        response = requests.get('https://192.168.0.137:5000/', verify=False, timeout=5)
        if response.status_code == 200 and '<!DOCTYPE html>' in response.text:
            print("✅ Dashboard HTML: LOADING SUCCESSFULLY")
            print(f"   └─ Response size: {len(response.text)} bytes")
            return True
        else:
            print(f"❌ Dashboard returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Dashboard error: {str(e)}")
        return False

def test_login():
    """Test login endpoint"""
    try:
        response = requests.post(
            'https://192.168.0.137:5000/api/auth/login',
            json={'username': 'demo', 'password': 'demo123'},
            verify=False,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                token = data.get('token', '')[:16]
                print(f"✅ Login Authentication: SUCCESS")
                print(f"   └─ Token issued: {token}...")
                return True, data.get('token')
            else:
                print(f"❌ Login failed: {data.get('error')}")
                return False, None
        else:
            print(f"❌ Login returned: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return False, None

def test_accounts():
    """Test accounts API"""
    try:
        response = requests.get(
            'https://192.168.0.137:5000/api/user/accounts?user_id=1',
            verify=False,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('data', [])
            if accounts:
                total_balance = sum(acc['current_balance'] for acc in accounts)
                print(f"✅ Accounts API: {len(accounts)} accounts found")
                for acc in accounts:
                    print(f"   └─ {acc['account_name']}: ${acc['current_balance']:,.2f}")
                print(f"   └─ Total Balance: ${total_balance:,.2f}")
                return True
            else:
                print("⚠️  No accounts found")
                return False
        else:
            print(f"❌ Accounts API returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Accounts API error: {str(e)}")
        return False

def test_database():
    """Test database connectivity"""
    try:
        conn = sqlite3.connect('zwesta_trading.db')
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        # Check accounts table
        cursor.execute('SELECT COUNT(*) FROM accounts')
        account_count = cursor.fetchone()[0]
        
        # Check trades table
        cursor.execute('SELECT COUNT(*) FROM trades')
        trade_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"✅ Database Connected: zwesta_trading.db")
        print(f"   ├─ Users: {user_count}")
        print(f"   ├─ Accounts: {account_count}")
        print(f"   └─ Trades: {trade_count}")
        return True
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("ZWESTA TRADING SYSTEM - VERIFICATION REPORT")
    print("="*60 + "\n")
    
    results = []
    
    print("1. Dashboard Loading...")
    results.append(test_dashboard())
    
    print("\n2. Database Connectivity...")
    results.append(test_database())
    
    print("\n3. Authentication...")
    success, token = test_login()
    results.append(success)
    
    print("\n4. Live Data API...")
    results.append(test_accounts())
    
    print("\n" + "="*60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"RESULT: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ ALL SYSTEMS OPERATIONAL - Dashboard ready to use!")
        print("\n🚀 Next Steps:")
        print("   1. Open: https://192.168.0.137:5000")
        print("   2. Login: demo / demo123")
        print("   3. View dashboard with live account data")
        print("   4. Install APK 'Zwesta trader.apk' on Android device")
    else:
        print("⚠️  Some systems need attention - check errors above")
    
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
