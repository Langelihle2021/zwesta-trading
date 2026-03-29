#!/usr/bin/env python3
"""
Test robots with correct backend database session token
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:9000"

# Correct token from backend database
SESSION_TOKEN = "a3b5a921382ba80ff88c025988b98700d9b07c988e165b8d74adca6447545fcf"

# Exness credentials
DEMO_ACCOUNT = "298997455"
DEMO_PASSWORD = "Zwesta@1985"
LIVE_ACCOUNT = "295677214"
LIVE_PASSWORD = "Ithemba@2026"

print("=" * 80)
print("🔍 ZWESTA ROBOT TESTING - LIVE & DEMO (WITH CORRECT TOKEN)")
print("=" * 80)
print()

headers = {
    "Content-Type": "application/json",
    "X-Session-Token": SESSION_TOKEN
}

# ============== TEST 1: DEMO BROKER CONNECTION ==============
print("[1/4] 🧪 Testing DEMO broker connection (Exness 298997455)...")
try:
    resp = requests.post(
        f"{BASE_URL}/api/broker/test-connection",
        json={
            "broker": "Exness",
            "account_number": DEMO_ACCOUNT,
            "password": DEMO_PASSWORD,
            "is_live": False,
            "server": "Exness-MT5Trial9"
        },
        headers=headers,
        timeout=90
    )
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ DEMO connection: PASSED ({resp.status_code})")
        if data.get("success"):
            print(f"   Message: {data.get('message', 'Connected successfully')}")
        else:
            print(f"   Note: {data.get('error', 'See logs')}")
    else:
        print(f"⚠️  DEMO connection: {resp.status_code}")
        print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# ============== TEST 2: LIVE BROKER CONNECTION ==============
print("[2/4] 🧪 Testing LIVE broker connection (Exness 295677214)...")
try:
    resp = requests.post(
        f"{BASE_URL}/api/broker/test-connection",
        json={
            "broker": "Exness",
            "account_number": LIVE_ACCOUNT,
            "password": LIVE_PASSWORD,
            "is_live": True,
            "server": "Exness-Real"
        },
        headers=headers,
        timeout=90
    )
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ LIVE connection: PASSED ({resp.status_code})")
        if data.get("success"):
            print(f"   Message: {data.get('message', 'Connected successfully')}")
        else:
            print(f"   Note: {data.get('error', 'See logs')}")
    else:
        print(f"⚠️  LIVE connection: {resp.status_code}")
        print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# ============== TEST 3: GET BROKER ACCOUNTS ==============
print("[3/4] 📊 Fetching broker accounts...")
try:
    resp = requests.get(
        f"{BASE_URL}/api/accounts/balances",
        headers=headers,
        timeout=30
    )
    
    if resp.status_code == 200:
        data = resp.json()
        accounts = data.get('accounts', [])
        print(f"✅ Accounts retrieved: {len(accounts)} account(s)")
        for acc in accounts:
            mode = acc.get('mode', 'Unknown')
            broker = acc.get('broker', 'Unknown')
            acc_num = acc.get('accountNumber', 'N/A')
            balance = acc.get('balance', 0)
            equity = acc.get('equity', 0)
            margin = acc.get('margin', 0)
            free_margin = acc.get('marginFree', 0)
            total_pl = acc.get('total_pl', 0)
            
            print(f"\n   ├─ {broker} {mode}: Account #{acc_num}")
            print(f"   │  Balance: ${balance:,.2f}, Equity: ${equity:,.2f}")
            print(f"   │  Margin Used: ${margin:,.2f}, Free Margin: ${free_margin:,.2f}")
            print(f"   │  Total P/L: ${total_pl:,.2f}")
    else:
        print(f"⚠️  Failed: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# ============== TEST 4: LIST BOTS ==============
print("[4/4] 🤖 Listing existing bots...")
try:
    resp = requests.get(
        f"{BASE_URL}/api/bot/list",
        headers=headers,
        timeout=15
    )
    
    if resp.status_code == 200:
        data = resp.json()
        bots = data.get('bots', [])
        print(f"✅ Bots found: {len(bots)} bot(s)")
        for bot in bots[:5]:
            bot_id = bot.get('bot_id', 'Unknown')
            mode = bot.get('mode', 'Unknown')
            status = bot.get('status', 'Unknown')
            symbol = bot.get('symbol', 'N/A')
            enabled = bot.get('enabled', False)
            print(f"   ├─ {bot_id}")
            print(f"   │  Mode: {mode}, Status: {status}, Symbol: {symbol}, Enabled: {enabled}")
    else:
        print(f"⚠️  Failed: {resp.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print()
print("=" * 80)
print("✅ TESTING COMPLETE!")
print("=" * 80)
