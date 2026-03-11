#!/usr/bin/env python3
"""Test bot creation with symbols"""
import requests
import json

print("="*70)
print("🤖 BOT CREATION TEST")
print("="*70)

# Use the test user we created
test_user_id = '81b273c1-9f62-43e8-8f97-5dce967bf0c9'
session_id = '066db957-c8ca-49c3-ad75-34300484c343'
print(f"\n[0] Using test user: {test_user_id}")
print(f"    Session ID: {session_id}")

# Create a bot with the symbols column
print("\n[1] Creating bot with symbols...")
headers = {'X-Session-Token': session_id}
bot_payload = {
    'name': 'Test Bot with Symbols',
    'strategy': 'trend_follow',
    'symbols': ['EURUSD', 'GBPUSD', 'XPTUSD'],
    'parameters': {
        'risk_per_trade': 0.02,
        'take_profit': 0.05
    }
}

create_resp = requests.post(
    'http://localhost:9000/api/bot/create',
    json=bot_payload,
    headers=headers,
    timeout=5
)

print(f"    Status: {create_resp.status_code}")
response_data = create_resp.json()
print(f"    Response: {json.dumps(response_data, indent=2)}")

if create_resp.status_code == 200:
    print("\n    ✅ Bot created successfully!")
    bot_id = response_data.get('bot_id')
    print(f"    Bot ID: {bot_id}")
    bot_data = create_resp.json()
    print(f"    Bot ID: {bot_data.get('bot_id')}")
    print(f"    Symbols: {bot_data.get('symbols')}")
else:
    print(f"\n    ❌ Failed to create bot")
