#!/usr/bin/env python3
"""
Test script to verify robots work on both LIVE and DEMO Exness accounts
Tests: Connection, Bot Creation, Configuration Save
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:9000"

# Test user credentials (must exist in database)
TEST_USER_EMAIL = "trader2@example.com"
TEST_USER_PASSWORD = "password"  # Will try without password first

# Exness credentials
DEMO_ACCOUNT = "298997455"
DEMO_PASSWORD = "Zwesta@1985"
LIVE_ACCOUNT = "295677214"
LIVE_PASSWORD = "Ithemba@2026"

print("=" * 80)
print("🔍 ZWESTA ROBOT TESTING - LIVE & DEMO")
print("=" * 80)
print()

# ============== STEP 1: LOGIN ==============
print("[1/8] 🔐 Logging in user...")
login_response = requests.post(
    f"{BASE_URL}/api/user/login",
    json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
)

if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.status_code}")
    print(login_response.json())
    exit(1)

login_data = login_response.json()
session_token = login_data.get("session_token")
user_id = login_data.get("user_id")

print(f"✅ Login successful")
print(f"   User ID: {user_id}")
print(f"   Token: {session_token[:20]}...")
print()

headers = {
    "Content-Type": "application/json",
    "X-Session-Token": session_token
}

# ============== STEP 2: TEST DEMO CONNECTION ==============
print("[2/8] 🧪 Testing DEMO broker connection (298997455)...")
demo_connection_response = requests.post(
    f"{BASE_URL}/api/broker/test-connection",
    json={
        "broker": "Exness",
        "account": DEMO_ACCOUNT,
        "password": DEMO_PASSWORD,
        "is_live": False,
        "server": "Exness-MT5Trial9"
    },
    headers=headers,
    timeout=60
)

demo_connection_status = demo_connection_response.status_code
demo_connection_data = demo_connection_response.json()

if demo_connection_status == 200 and demo_connection_data.get("success"):
    print(f"✅ DEMO connection test PASSED")
    print(f"   Response: {json.dumps(demo_connection_data, indent=6)[:300]}")
else:
    print(f"⚠️  DEMO connection test result: {demo_connection_status}")
    print(f"   Response: {json.dumps(demo_connection_data, indent=6)[:500]}")

print()

# ============== STEP 3: TEST LIVE CONNECTION ==============
print("[3/8] 🧪 Testing LIVE broker connection (295677214)...")
live_connection_response = requests.post(
    f"{BASE_URL}/api/broker/test-connection",
    json={
        "broker": "Exness",
        "account": LIVE_ACCOUNT,
        "password": LIVE_PASSWORD,
        "is_live": True,
        "server": "Exness-Real"
    },
    headers=headers,
    timeout=60
)

live_connection_status = live_connection_response.status_code
live_connection_data = live_connection_response.json()

if live_connection_status == 200 and live_connection_data.get("success"):
    print(f"✅ LIVE connection test PASSED")
    print(f"   Response: {json.dumps(live_connection_data, indent=6)[:300]}")
else:
    print(f"⚠️  LIVE connection test result: {live_connection_status}")
    print(f"   Response: {json.dumps(live_connection_data, indent=6)[:500]}")

print()

# ============== STEP 4: GET BROKER ACCOUNTS ==============
print("[4/8] 📊 Fetching broker accounts...")
accounts_response = requests.get(
    f"{BASE_URL}/api/accounts/balances",
    headers=headers,
    timeout=30
)

if accounts_response.status_code == 200:
    accounts_data = accounts_response.json()
    print(f"✅ Fetched broker accounts")
    print(f"   Total accounts: {len(accounts_data.get('accounts', []))}")
    for account in accounts_data.get('accounts', []):
        print(f"   - {account['broker']} {account['mode']}: Account {account['accountNumber']}")
        print(f"     Balance: ${account.get('balance', 0):.2f}, Equity: ${account.get('equity', 0):.2f}")
else:
    print(f"⚠️  Failed to fetch accounts: {accounts_response.status_code}")
    print(f"   Response: {accounts_response.json()}")

print()

# ============== STEP 5: CREATE DEMO BOT ==============
print("[5/8] 🤖 Creating DEMO robot...")
demo_bot_response = requests.post(
    f"{BASE_URL}/api/bot/create",
    json={
        "botId": f"test_demo_btc_{datetime.now().timestamp()}",
        "symbol": "BTCUSDm",
        "strategy": "Trend Following",
        "riskPerTrade": 2.0,
        "timeframe": "1H",
        "is_live": False,
        "volatility_filter_enabled": False,
        "broker": "Exness",
        "account": DEMO_ACCOUNT,
        "mode": "demo",
        "leverage": 1
    },
    headers=headers,
    timeout=30
)

demo_bot_status = demo_bot_response.status_code
demo_bot_data = demo_bot_response.json()

if demo_bot_status == 200 and demo_bot_data.get("success"):
    demo_bot_id = demo_bot_data.get("botId")
    print(f"✅ DEMO bot created successfully")
    print(f"   Bot ID: {demo_bot_id}")
    print(f"   Response: {json.dumps(demo_bot_data, indent=6)[:200]}")
else:
    print(f"⚠️  DEMO bot creation result: {demo_bot_status}")
    print(f"   Response: {json.dumps(demo_bot_data, indent=6)[:500]}")
    demo_bot_id = None

print()

# ============== STEP 6: CREATE LIVE BOT ==============
print("[6/8] 🤖 Creating LIVE robot...")
live_bot_response = requests.post(
    f"{BASE_URL}/api/bot/create",
    json={
        "botId": f"test_live_btc_{datetime.now().timestamp()}",
        "symbol": "BTCUSDm",
        "strategy": "Trend Following",
        "riskPerTrade": 2.0,
        "timeframe": "1H",
        "is_live": True,
        "volatility_filter_enabled": False,
        "broker": "Exness",
        "account": LIVE_ACCOUNT,
        "mode": "live",
        "leverage": 1
    },
    headers=headers,
    timeout=30
)

live_bot_status = live_bot_response.status_code
live_bot_data = live_bot_response.json()

if live_bot_status == 200 and live_bot_data.get("success"):
    live_bot_id = live_bot_data.get("botId")
    print(f"✅ LIVE bot created successfully")
    print(f"   Bot ID: {live_bot_id}")
    print(f"   Response: {json.dumps(live_bot_data, indent=6)[:200]}")
else:
    print(f"⚠️  LIVE bot creation result: {live_bot_status}")
    print(f"   Response: {json.dumps(live_bot_data, indent=6)[:500]}")
    live_bot_id = None

print()

# ============== STEP 7: TEST BOT CONFIGURATION SAVE ==============
if demo_bot_id:
    print("[7/8] 💾 Testing bot configuration save (DEMO)...")
    save_response = requests.post(
        f"{BASE_URL}/api/bot/update",
        json={
            "botId": demo_bot_id,
            "symbol": "ETHUSDm",
            "strategy": "Grid Trading",
            "riskPerTrade": 3.0,
            "timeframe": "4H",
            "volatility_filter_enabled": True
        },
        headers=headers,
        timeout=30
    )

    save_status = save_response.status_code
    save_data = save_response.json()

    if save_status == 200 and save_data.get("success"):
        print(f"✅ Demo bot configuration SAVED successfully")
        print(f"   Response: {json.dumps(save_data, indent=6)[:200]}")
    else:
        print(f"⚠️  Demo bot save result: {save_status}")
        print(f"   Response: {json.dumps(save_data, indent=6)[:300]}")
else:
    print("[7/8] ⏭️  Skipping demo bot save test (bot creation failed)")

print()

# ============== STEP 8: LIST ALL BOTS ==============
print("[8/8] 📋 Listing all bots...")
list_response = requests.get(
    f"{BASE_URL}/api/bot/list",
    headers=headers,
    timeout=30
)

if list_response.status_code == 200:
    list_data = list_response.json()
    bots = list_data.get("bots", [])
    print(f"✅ Bots retrieved successfully")
    print(f"   Total bots: {len(bots)}")
    for bot in bots[:5]:  # Show first 5
        print(f"\n   Bot: {bot.get('botId')}")
        print(f"   - Mode: {bot.get('mode')}/{bot.get('is_live')}")
        print(f"   - Symbol: {bot.get('symbol')}")
        print(f"   - Status: {bot.get('status')}")
        print(f"   - Strategy: {bot.get('strategy')}")
else:
    print(f"⚠️  Failed to list bots: {list_response.status_code}")
    print(f"   Response: {list_response.json()}")

print()
print("=" * 80)
print("📊 TEST SUMMARY")
print("=" * 80)
print(f"Demo Connection:     {'✅ PASSED' if demo_connection_status == 200 else '⚠️  CHECK LOGS'}")
print(f"Live Connection:     {'✅ PASSED' if live_connection_status == 200 else '⚠️  CHECK LOGS'}")
print(f"Demo Bot Creation:   {'✅ PASSED' if demo_bot_status == 200 else '⚠️  CHECK LOGS'}")
print(f"Live Bot Creation:   {'✅ PASSED' if live_bot_status == 200 else '⚠️  CHECK LOGS'}")
print()
print("💡 Next Steps:")
print("1. If connections failed: Verify credentials in .env file")
print("2. If connections passed: Broker integration is working")
print("3. Check Flutter app - should show both demo and live accounts")
print("4. Start bots from broker_integration_screen and bot_configuration_screen")
print()
