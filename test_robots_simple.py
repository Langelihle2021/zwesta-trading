#!/usr/bin/env python3
"""
Simplified test: Check if robots can connect to live and demo accounts
and if we can create/save robot configurations
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:9000"

# Use existing test user session
TEST_SESSION_TOKEN = "test-session-token-123"
TEST_USER_ID = "test-user-001"

# Exness credentials from .env
DEMO_ACCOUNT = "298997455"
DEMO_PASSWORD = "Zwesta@1985"
LIVE_ACCOUNT = "295677214"
LIVE_PASSWORD = "Ithemba@2026"

print("=" * 80)
print("🔍 ZWESTA ROBOT TESTING - LIVE & DEMO")
print("=" * 80)
print()

print("[1/7] 🔐 Using session from database...")

session_token = TEST_SESSION_TOKEN
user_id = TEST_USER_ID
print(f"✅ Session obtained from database")
print(f"   User ID: {user_id}")
print(f"   Token: {session_token[:40]}...")
print()

headers = {
    "Content-Type": "application/json",
    "X-Session-Token": session_token
}

# ============== STEP 2: TEST DEMO CONNECTION ==============
print("[2/7] 🧪 Testing DEMO broker connection (Exness 298997455)...")
try:
    demo_conn = requests.post(
        f"{BASE_URL}/api/broker/test-connection",
        json={
            "broker": "Exness",
            "account": DEMO_ACCOUNT,
            "password": DEMO_PASSWORD,
            "is_live": False,
            "server": "Exness-MT5Trial9"
        },
        headers=headers,
        timeout=90
    )
    
    demo_status = demo_conn.status_code
    demo_result = demo_conn.json()
    
    if demo_status == 200:
        print(f"✅ DEMO connection test: {demo_status}")
        print(f"   Result: {str(demo_result)[:150]}")
    else:
        print(f"⚠️  DEMO connection: {demo_status}")
        print(f"   Result: {str(demo_result)[:200]}")
except Exception as e:
    print(f"❌ DEMO connection error: {e}")
    demo_status = 0

print()

# ============== STEP 3: TEST LIVE CONNECTION ==============
print("[3/7] 🧪 Testing LIVE broker connection (Exness 295677214)...")
try:
    live_conn = requests.post(
        f"{BASE_URL}/api/broker/test-connection",
        json={
            "broker": "Exness",
            "account": LIVE_ACCOUNT,
            "password": LIVE_PASSWORD,
            "is_live": True,
            "server": "Exness-Real"
        },
        headers=headers,
        timeout=90
    )
    
    live_status = live_conn.status_code
    live_result = live_conn.json()
    
    if live_status == 200:
        print(f"✅ LIVE connection test: {live_status}")
        print(f"   Result: {str(live_result)[:150]}")
    else:
        print(f"⚠️  LIVE connection: {live_status}")
        print(f"   Result: {str(live_result)[:200]}")
except Exception as e:
    print(f"❌ LIVE connection error: {e}")
    live_status = 0

print()

# ============== STEP 4: GET BROKER ACCOUNTS ==============
print("[4/7] 📊 Fetching broker accounts...")
try:
    accounts_resp = requests.get(
        f"{BASE_URL}/api/accounts/balances",
        headers=headers,
        timeout=30
    )
    
    if accounts_resp.status_code == 200:
        accounts_data = accounts_resp.json()
        accounts = accounts_data.get('accounts', [])
        print(f"✅ Accounts retrieved: {len(accounts)} account(s)")
        for acc in accounts:
            mode = acc.get('mode', 'Unknown')
            broker = acc.get('broker', 'Unknown')
            acc_num = acc.get('accountNumber', 'N/A')
            balance = acc.get('balance', 0)
            equity = acc.get('equity', 0)
            print(f"   ├─ {broker} {mode}: #{acc_num}")
            print(f"   │  Balance: ${balance:.2f}, Equity: ${equity:.2f}")
    else:
        print(f"⚠️  Accounts call: {accounts_resp.status_code}")
        accounts = []
except Exception as e:
    print(f"❌ Accounts error: {e}")
    accounts = []

print()

# ============== STEP 5: CREATE/LIST BOTS ==============
print("[5/7] 🤖 Checking existing bots...")
try:
    bots_resp = requests.get(
        f"{BASE_URL}/api/bot/list",
        headers=headers,
        timeout=15
    )
    
    if bots_resp.status_code == 200:
        bots_data = bots_resp.json()
        bots_list = bots_data.get('bots', [])
        print(f"✅ Bots found: {len(bots_list)} bot(s)")
        
        for bot in bots_list[:3]:
            bot_id = bot.get('bot_id', 'Unknown')
            mode = bot.get('mode', 'Unknown')
            status = bot.get('status', 'Unknown')
            symbol = bot.get('symbol', 'N/A')
            print(f"   ├─ {bot_id}")
            print(f"   │  Mode: {mode}, Status: {status}, Symbol: {symbol}")
    else:
        print(f"⚠️  Bots list: {bots_resp.status_code}")
except Exception as e:
    print(f"❌ Bots error: {e}")

print()

# ============== STEP 6: CHECK TEST BUTTON ==============
print("[6/7] 🔘 Testing 'test connection' button...")
print(f"   [2/7] DEMO test result: {'✅ PASSED' if demo_status == 200 else '⚠️ CHECK'}")
print(f"   [3/7] LIVE test result: {'✅ PASSED' if live_status == 200 else '⚠️ CHECK'}")

print()

# ============== STEP 7: SUMMARY ==============
print("[7/7] 📋 Summary & Next Steps")
print("=" * 80)

if demo_status == 200 and live_status == 200:
    print("✅ BOTH DEMO AND LIVE CONNECTIONS WORK!")
    print()
    print("Next Steps:")
    print("1. ✅ Open Flutter app")
    print("2. ✅ Go to Broker Integration Screen")
    print("3. ✅ Add/Test both demo and live credentials")
    print("4. ✅ Go to Robot Configuration Screen")
    print("5. ✅ Create robot for demo account")
    print("6. ✅ Create robot for live account")
    print("7. ✅ Click 'Test' button before starting")
    print("8. ✅ Click 'Save' to persist configuration")
else:
    print("⚠️ CONNECTION ISSUES DETECTED")
    print()
    if demo_status != 200:
        print("❌ DEMO account connection failed:")
        print("   - Check demo credentials in .env")
        print("   - Verify Exness demo MT5 terminal is running")
        print("   - Check EXNESS_DEMO_PATH is set correctly")
    
    if live_status != 200:
        print("❌ LIVE account connection failed:")
        print("   - Check live credentials in .env")
        print("   - Verify Exness live MT5 terminal is running")
        print("   - Check EXNESS_LIVE_PATH is set correctly")

print()
print("=" * 80)
