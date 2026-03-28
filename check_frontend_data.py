#!/usr/bin/env python3
"""
Check what trade/position data the backend is returning
"""

import requests
import json
from datetime import datetime

BACKEND_URL = "http://localhost:9000"

def check_backend_endpoints():
    """Test all trade/position endpoints"""
    print("=" * 70)
    print("📊 BACKEND DATA DIAGNOSTIC - Checking all endpoints")
    print("=" * 70)
    print(f"\n📡 Testing endpoints on {BACKEND_URL}\n")
    
    # Test 1: Get positions
    print("1️⃣  Testing /api/positions/all (LIVE MT5 positions)")
    print("-" * 70)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/positions/all", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            positions = data.get('positions', [])
            print(f"✅ Status: {resp.status_code}")
            print(f"📍 Open Positions Found: {len(positions)}")
            if positions:
                for pos in positions:
                    pnl = pos.get('profit', 0)
                    pnl_pct = pos.get('profitPercent', 0)
                    print(f"\n   🔹 {pos['symbol']} ({pos['type']})")
                    print(f"      Volume: {pos['volume']} lots")
                    print(f"      Open: ${pos['openPrice']:.5f} | Current: ${pos['currentPrice']:.5f}")
                    print(f"      P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")
            else:
                print("   ⚠️  No positions found in MT5")
        else:
            print(f"❌ Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test 2: Get trades from database
    print("\n\n2️⃣  Testing /api/trades (Database stored trades)")
    print("-" * 70)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/trades", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get('trades', [])
            print(f"✅ Status: {resp.status_code}")
            print(f"📋 Stored Trades Found: {len(trades)}")
            if trades:
                for trade in trades[:3]:  # Show first 3
                    print(f"\n   {trade}")
            else:
                print("   ⚠️  No trades stored in database")
        else:
            print(f"❌ Status: {resp.status_code}")
            print(f"Response: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test 3: Get trades history
    print("\n\n3️⃣  Testing /api/trades/history (Trade history)")
    print("-" * 70)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/trades/history", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get('trades', [])
            print(f"✅ Status: {resp.status_code}")
            print(f"📜 Historical Trades Found: {len(trades)}")
        else:
            print(f"❌ Status: {resp.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    # Test 4: Account info
    print("\n\n4️⃣  Testing /api/account/info (Account details)")
    print("-" * 70)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/account/info", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            account = data.get('account', {})
            print(f"✅ Status: {resp.status_code}")
            print(f"   Account Number: {account.get('accountNumber')}")
            print(f"   Broker: {account.get('broker')}")
            print(f"   Balance: ${account.get('balance', 0):,.2f}")
            print(f"   Equity: ${account.get('equity', 0):,.2f}")
            print(f"   Margin Used: ${account.get('margin', 0):,.2f}")
            print(f"   Free Margin: ${account.get('freeMargin', 0):,.2f}")
        else:
            print(f"❌ Status: {resp.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print("\n\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print("""
Your Flutter app should:
  🟢 /api/positions/all     → For LIVE open positions (BAC, WFC)
  🟢 /api/trades/history    → For closed trade history
  🟢 /api/account/info      → For account balance & margin

If BAC/WFC don't show:
  1. Check if /api/positions/all returns them (this endpoint)
  2. Check that your Flutter app is calling /api/positions/all
  3. NOT /api/trades (that only shows database trades, not MT5 positions)
""")
    
if __name__ == '__main__':
    check_backend_endpoints()
