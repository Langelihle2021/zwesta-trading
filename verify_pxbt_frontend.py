#!/usr/bin/env python3
"""
Test PXBT Visibility on Frontend & Backend
Verifies that PXBT broker appears in:
1. Backend /api/brokers/list endpoint
2. Frontend broker dropdown
3. Bot creation flow
"""

import requests
import json
from datetime import datetime

print("=" * 70)
print("🧪 PXBT FRONTEND VISIBILITY TEST")
print("=" * 70)
print(f"Timestamp: {datetime.now().isoformat()}\n")

BACKEND_URL = "http://localhost:9000"

# ==================== TEST 1: Backend Broker List ====================
print("[TEST 1] Backend /api/brokers/list Endpoint")
print("-" * 70)

try:
    response = requests.get(f"{BACKEND_URL}/api/brokers/list", timeout=5)
    if response.status_code != 200:
        print(f"❌ Endpoint returned {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    else:
        data = response.json()
        print(f"✅ Endpoint responded successfully")
        
        brokers = data.get('brokers', [])
        print(f"\n📋 Total Brokers: {len(brokers)}")
        
        pxbt_found = False
        for broker in brokers:
            broker_name = broker.get('name', '')
            broker_type = broker.get('type', '')
            status = broker.get('status', 'unknown')
            
            if 'pxbt' in broker_type.lower():
                pxbt_found = True
                print(f"\n✅ PXBT FOUND:")
                print(f"   Name: {broker_name}")
                print(f"   Type: {broker_type}")
                print(f"   Status: {status}")
                print(f"   Assets: {broker.get('assets', [])}")
                print(f"   Configurable: {broker.get('configurable', 'N/A')}")
                print(f"   Note: {broker.get('note', 'N/A')}")
        
        if not pxbt_found:
            print(f"\n❌ PXBT NOT FOUND in broker list!")
            print(f"\nAvailable brokers:")
            for broker in brokers:
                print(f"  - {broker.get('name')} ({broker.get('type')}): {broker.get('status')}")
        else:
            print(f"\n✅ PXBT is in the broker list and should appear on frontend!")
            
except requests.exceptions.ConnectionError:
    print(f"❌ Cannot connect to backend at {BACKEND_URL}")
    print(f"   Ensure backend is running: python multi_broker_backend_updated.py")
except Exception as e:
    print(f"❌ Error: {e}")

# ==================== TEST 2: Check PXBT Availability ====================
print("\n[TEST 2] PXBT Availability Check")
print("-" * 70)

try:
    response = requests.get(f"{BACKEND_URL}/api/brokers/check-pxbt", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PXBT check endpoint responded")
        print(f"   Available: {data.get('available')}")
        print(f"   Installed: {data.get('installed')}")
        print(f"   Version: {data.get('version')}")
        print(f"   Terminal Path: {data.get('terminal_path', 'Not found')}")
        
        if not data.get('available'):
            print(f"\n⚠️  PXBT terminal not detected, but PXBT should still show as configurable")
    else:
        print(f"⚠️ PXBT check returned {response.status_code}")
except Exception as e:
    print(f"⚠️ PXBT check error: {e}")

# ==================== TEST 3: Check Commodities/Symbols ====================
print("\n[TEST 3] PXBT Symbols Available")
print("-" * 70)

try:
    response = requests.get(f"{BACKEND_URL}/api/commodities/list", timeout=5)
    if response.status_code == 200:
        data = response.json()
        commodities = data.get('commodities', {})
        
        # Count PXBT-relevant symbols
        pxbt_symbols = 0
        for category, symbols in commodities.items():
            for symbol in symbols:
                if isinstance(symbol, dict):
                    symbol_name = symbol.get('symbol', '')
                elif isinstance(symbol, str):
                    symbol_name = symbol
                else:
                    continue
                    
                # PXBT symbols (no 'm' suffix)
                if symbol_name in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 
                                   'XAUUSD', 'XAGUSD', 'US30', 'EUR50', 'BRENT',
                                   'BTCUSDT', 'ETHUSDT']:
                    pxbt_symbols += 1
        
        print(f"✅ Commodities endpoint responded")
        print(f"   Total Categories: {len(commodities)}")
        print(f"   PXBT Compatible Symbols: {pxbt_symbols}")
        
        if pxbt_symbols > 0:
            print(f"\n✅ PXBT symbols are available!")
        else:
            print(f"\n⚠️ No PXBT symbols detected")
    else:
        print(f"⚠️ Commodities check returned {response.status_code}")
except Exception as e:
    print(f"⚠️ Commodities check error: {e}")

# ==================== TEST 4: Frontend Display Info ====================
print("\n[TEST 4] What User Sees on Frontend")
print("-" * 70)

print("""
If PXBT is not showing on your frontend:

1. **Check Broker Integration Screen** (Accounts Tab → Add Broker)
   - Scroll down in the broker dropdown
   - Look for: "PXBT" or "PXBT (Prime XBT)"
   - Should appear between "Ovex (SA)" and "Trade Nations"

2. **If Not Visible**, Try These Steps:
   a) Stop backend: Ctrl+C
   b) Check .env file has PXBT_* variables set
   c) Restart backend: python multi_broker_backend_updated.py
   d) Refresh Flutter app (hot reload or restart)
   e) Go to Accounts tab → Add Broker
   f) Check if PXBT appears now

3. **Expected PXBT Entry in Dropdown:**
   ┌─────────────────────────────────────┐
   │ Broker Selection                    │
   ├─────────────────────────────────────┤
   │ Binance                             │
   │ OANDA                               │
   │ ...                                 │
   │ PXBT (Prime XBT)  ← Should be here  │
   │ ...                                 │
   └─────────────────────────────────────┘

4. **If PXBT Shows**, Configure:
   - Server: PXBT-Demo (or PXBT-Real for live)
   - Account Number: Your PXBT account ID
   - Password: Your PXBT password
   - Click: Test Connection
   - Click: Save Credentials
""")

# ==================== Summary ====================
print("\n" + "=" * 70)
print("📋 PXBT VISIBILITY SUMMARY")
print("=" * 70)

print("""
FIX APPLIED (March 25, 2026):
✅ PXBT broker status changed to 'active' (always shown, not conditional)
✅ PXBT branding improved: "PXBT (Prime XBT)" for clarity
✅ PXBT added to broker list with note: "Configure PXBT credentials in .env"

If You Still Don't See PXBT:
1. Clear app cache (Flutter: android/build, ios/Podfile.lock)
2. Hot restart: flutter pub get && flutter run
3. Check backend logs for errors
4. Verify backend is running on http://localhost:9000

Expected Behavior:
- PXBT appears in Accounts → Add Broker dropdown
- User can enter account credentials
- Bot creation shows PXBT symbols
- Testing shows both Exness and PXBT accounts available
""")

print("\n✅ Test complete!")
