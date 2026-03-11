#!/usr/bin/env python3
import requests
import json
import sys

BASE_URL = "http://localhost:9000"

print("=" * 70)
print("BOT CREATION TEST - SYMBOLS COLUMN FIX")
print("=" * 70)

# Test login
print("\n[1] Logging in as zwexman@gmail.com...")
try:
    response = requests.post(f"{BASE_URL}/api/user/login", json={
        "email": "zwexman@gmail.com",
        "password": "Temppass123!"
    }, timeout=10)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        sys.exit(1)
    
    data = response.json()
    print(f"   Response: {data}")
    token = data.get('token') or data.get('auth_token') or data.get('session_token')
    if not token:
        print(f"❌ No token in response: {data.keys()}")
        sys.exit(1)
    print(f"✅ Login successful - Token: {token[:30]}...")
    
except Exception as e:
    print(f"❌ Login error: {e}")
    sys.exit(1)

# Test bot creation
print("\n[2] Creating bot with symbols column...")
try:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "bot_name": "TestBot_SymbolsFix",
        "symbol": "EURUSD",
        "symbols": ["EURUSD", "GBPUSD", "XPTUSD"],
        "strategy": "TREND_FOLLOW",
        "risk_level": "MEDIUM",
        "initial_capital": 100.00,
        "status": "ACTIVE"
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    bot_response = requests.post(f"{BASE_URL}/api/bot/create", json=payload, headers=headers, timeout=10)
    
    print(f"\nStatus: {bot_response.status_code}")
    print(f"Response: {bot_response.text[:500]}")
    
    if bot_response.status_code in [200, 201]:
        print("\n✅ BOT CREATION SUCCESSFUL!")
    else:
        print("\n❌ Bot creation failed")
        
except Exception as e:
    print(f"❌ Bot creation error: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
