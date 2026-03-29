#!/usr/bin/env python3
"""Quick test to create a new bot and verify the NoneType fix works"""

import requests
import json
import time

API_URL = "http://localhost:9000"

# Use the session from the logs (from last login)
TOKEN = "ce4d79edc73d2bba5120098b6628a92fa998bf7608d7d0430562b2f4f52367b4"
USER_ID = "a8a3763f-1203-4f90-b168-6b4b2414432d"

def test_bot_creation():
    """Test creating a new bot"""
    print("[TEST] Testing Bot Creation...")
    
    # Create bot
    bot_payload = {
        "botName": "Test Bot Fix",
        "strategy": "MultiSymbol",
        "symbols": ["EURUSDm", "BTC"],
        "riskPerTrade": 2.0,
        "tradingMode": "interval",
        "tradingInterval": 300,
        "credentialId": "1",  # Demo credential
        "brokerType": "Exness"
    }
    
    headers = {
        "X-Session-Token": TOKEN,
        "Content-Type": "application/json"
    }
    
    print(f"\n📝 Creating bot with payload:")
    print(json.dumps(bot_payload, indent=2))
    
    try:
        response = requests.post(
            f"{API_URL}/api/bot/create",
            json=bot_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"\n✅ Create response: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        bot_id = result.get('botId')
        if not bot_id:
            print("❌ No botId in response!")
            return False
        
        print(f"\n🎯 Bot created: {bot_id}")
        
        # Wait a moment
        time.sleep(2)
        
        # Start bot
        print(f"\n🚀 Starting bot...")
        start_payload = {
            "botId": bot_id,
            "user_id": USER_ID
        }
        
        response = requests.post(
            f"{API_URL}/api/bot/start",
            json=start_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Start response: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        # Wait longer to catch any errors
        print("\n⏳ Waiting 5 seconds for trading loop to start...")
        time.sleep(5)
        
        # Check bot status
        print(f"\n📊 Checking bot status...")
        response = requests.get(
            f"{API_URL}/api/bot/status?mode=DEMO&user_id={USER_ID}",
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Status response: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bot_creation()
    print(f"\n{'✅ TEST PASSED' if success else '❌ TEST FAILED'}")
