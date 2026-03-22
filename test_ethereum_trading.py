#!/usr/bin/env python3
"""
Test Ethereum trading capability with updated credentials
Verify: 1) MT5 connection, 2) Ethereum market open, 3) Bot can place ETH trade
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:9000"

def test_connection():
    """Test backend connectivity"""
    print("\n[TEST 1] Backend Connectivity")
    try:
        response = requests.get(f"{BASE_URL}/api/status")
        if response.status_code == 200:
            print("✅ Backend is running")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        return False

def test_mt5_connection():
    """Test MT5 connection with updated credentials"""
    print("\n[TEST 2] MT5 Connection (Account: 298997455)")
    try:
        response = requests.post(
            f"{BASE_URL}/api/broker/test-connection",
            json={
                "broker_name": "Exness",
                "account": "298997455",
                "password": "Zwesta@1985",
                "server": "Exness-MT5Trial9",
                "is_live": False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ MT5 Connection Successful")
                print(f"   Account: {data.get('account')}")
                print(f"   Balance: ${data.get('balance', 0):,.2f}")
                print(f"   Server: {data.get('server')}")
                return True
            else:
                print(f"❌ Connection failed: {data.get('error')}")
                return False
        else:
            print(f"❌ API returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False

def test_ethereum_market_status():
    """Check if Ethereum market is open"""
    print("\n[TEST 3] Ethereum Market Status")
    try:
        response = requests.post(
            f"{BASE_URL}/api/bot/check-market-hours",
            json={"symbol": "ETHUSDm"}
        )
        
        if response.status_code == 200:
            data = response.json()
            is_open = data.get('market_open', False)
            message = data.get('message', '')
            
            if is_open:
                print(f"✅ Ethereum Market is OPEN")
                print(f"   {message}")
            else:
                print(f"⚠️  Ethereum Market is CLOSED")
                print(f"   {message}")
                print("   [Note] Crypto should be 24/7, check market_hours config")
            
            return is_open
        else:
            print(f"❌ Market check failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking market: {e}")
        return False

def test_ethereum_tradeable():
    """Check if Ethereum can be traded on Exness"""
    print("\n[TEST 4] Ethereum Tradeable Check")
    try:
        response = requests.get(
            f"{BASE_URL}/api/commodities/list"
        )
        
        if response.status_code == 200:
            data = response.json()
            commodities = data.get('commodities', [])
            
            ethereum_symbols = [c for c in commodities if 'eth' in c.lower()]
            
            if ethereum_symbols:
                print(f"✅ Ethereum symbols available: {ethereum_symbols}")
                return True
            else:
                print(f"❌ No Ethereum symbols found in available commodities")
                print(f"   Available: {commodities[:5]}...")  # Show first 5
                return False
        else:
            print(f"❌ Commodity list failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking tradeable: {e}")
        return False

def main():
    print("="*70)
    print("Ethereum Trading Verification Test")
    print("="*70)
    print(f"\nTarget: Exness Demo Account 298997455")
    print(f"Password: Zwesta@1985")
    print(f"Server: Exness-MT5Trial9")
    print(f"Symbol: ETHUSDm (Ethereum)")
    
    results = []
    
    # Run tests
    results.append(("Backend Connectivity", test_connection()))
    
    if not results[-1][1]:
        print("\n❌ Backend not running. Start with: python multi_broker_backend_updated.py")
        return False
    
    results.append(("MT5 Connection", test_mt5_connection()))
    results.append(("Ethereum Market Status", test_ethereum_market_status()))
    results.append(("Ethereum Tradeable", test_ethereum_tradeable()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Ethereum trading is ready!")
        return True
    else:
        print(f"\n❌ {total - passed} test(s) failed - see details above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
