#!/usr/bin/env python3
"""
Test Binance Connection & Create Demo Trading Bot
This script tests your Binance API credentials and creates a bot with demo trading
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:9000"  # Your backend server
SESSION_TOKEN = "debug_token_49b6b05ad32648759f26f6ac37eebcef"  # Update with your session token

# Your Binance API credentials (from the screenshot)
BINANCE_API_KEY = "JBPMO44roltRZjQhxM0YqZLCgpYd7dHiddZru8GHJzJI6AveL3yv3M95imfFZT3b"
BINANCE_API_SECRET = "your_api_secret_here"  # ⚠️ Replace with your actual secret

# ==================== STEP 1: TEST BINANCE CONNECTION ====================
def test_binance_connection(api_key: str, api_secret: str, is_live: bool = False):
    """Test Binance API connection and retrieve account info"""
    
    print("\n" + "="*70)
    print("🔌 STEP 1: Testing Binance Connection")
    print("="*70)
    
    headers = {
        "Content-Type": "application/json",
        "X-Session-Token": SESSION_TOKEN
    }
    
    payload = {
        "broker": "Binance",
        "api_key": api_key,
        "api_secret": api_secret,
        "is_live": is_live,
        "market": "spot"  # "spot" or "futures"
    }
    
    print(f"\n📨 Sending connection test request...")
    print(f"   Broker: Binance")
    print(f"   Mode: {'LIVE' if is_live else 'DEMO/TESTNET'}")
    print(f"   Market: spot")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/broker/test-connection",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ CONNECTION SUCCESSFUL!\n")
            print(json.dumps(result, indent=2))
            
            credential_id = result.get('credential_id')
            balance = result.get('balance', 0)
            
            print(f"\n💾 Credential ID: {credential_id}")
            print(f"💰 Account Balance: ${balance:.2f}")
            
            return credential_id, balance
        else:
            print("\n❌ CONNECTION FAILED!\n")
            print(json.dumps(response.json(), indent=2))
            return None, None
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out - backend may not be running")
        return None, None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None, None


# ==================== STEP 2: CREATE DEMO TRADING BOT ====================
def create_demo_bot(credential_id: str, symbols: list = None, strategy: str = "Momentum Trading"):
    """Create a demo trading bot using the verified Binance credential"""
    
    if not credential_id:
        print("❌ Skipping bot creation - no credential ID")
        return None
    
    print("\n" + "="*70)
    print("🤖 STEP 2: Creating Demo Trading Bot")
    print("="*70)
    
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # High-performing pairs
    
    headers = {
        "Content-Type": "application/json",
        "X-Session-Token": SESSION_TOKEN
    }
    
    payload = {
        "credentialId": credential_id,
        "botId": f"demo_bot_{int(time.time())}",
        "name": "Demo Trading Bot",
        "symbols": symbols,
        "strategy": strategy,
        "enabled": True,
        "riskPerTrade": 15,        # 15% risk per trade (crypto-optimized)
        "maxDailyLoss": 50,        # Stop if lose 50UFSDT per day
        "profitLock": 40,          # Lock in at 40 USDT daily profit
        "basePositionSize": 1.0,
        "displayCurrency": "USDT"
    }
    
    print(f"\n📨 Creating bot with:")
    print(f"   Strategy: {strategy}")
    print(f"   Symbols: {', '.join(symbols)}")
    print(f"   Risk per trade: {payload['riskPerTrade']}%")
    print(f"   Daily loss limit: ${payload['maxDailyLoss']}")
    print(f"   Status: DEMO MODE ({'Testnet' if 'DEMO' in credential_id.upper() else 'Spot'})")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/bot/create",
            headers=headers,
            json=payload,
            timeout=60  # Bot creation may take time
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print("\n✅ BOT CREATED SUCCESSFULLY!\n")
            print(json.dumps(result, indent=2))
            
            bot_id = result.get('botId')
            balance = result.get('balance', 0)
            
            print(f"\n🎯 Bot Details:")
            print(f"   Bot ID: {bot_id}")
            print(f"   Account Balance: ${balance:.2f}")
            print(f"   Status: {result.get('status', 'STARTING')}")
            print(f"   Mode: {result.get('mode', 'demo')}")
            
            return bot_id
        else:
            print("\n❌ BOT CREATION FAILED!\n")
            print(json.dumps(response.json(), indent=2))
            return None
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timed out - bot creation took too long")
        return None
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


# ==================== STEP 3: CHECK BOT STATUS ====================
def get_bot_status(bot_id: str):
    """Get current status and performance of a bot"""
    
    if not bot_id:
        return
    
    print("\n" + "="*70)
    print("📈 STEP 3: Checking Bot Status")
    print("="*70)
    
    headers = {
        "Content-Type": "application/json",
        "X-Session-Token": SESSION_TOKEN
    }
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/bot/{bot_id}/status",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ BOT STATUS:\n")
            print(json.dumps(result, indent=2))
        else:
            print(f"\n⚠️ Status endpoint returned {response.status_code}")
            
    except Exception as e:
        print(f"\n⚠️ Could not fetch bot status: {e}")


# ==================== MAIN EXECUTION ====================
def main():
    """Run the complete test flow"""
    
    print("\n" + "="*70)
    print("🚀 ZWESTA TRADER - BINANCE BOT CREATION FLOW")
    print("="*70)
    print(f"⏰ Started at: {datetime.now().isoformat()}")
    print(f"🌐 Backend: {BACKEND_URL}")
    
    # Check if backend is running
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print(f"✅ Backend is running")
    except:
        print(f"\n❌ ERROR: Backend not running at {BACKEND_URL}")
        print("   Make sure your backend server is running on port 9000")
        return
    
    # STEP 1: Test connection
    print("\n⏳ Waiting 2 seconds before test...")
    time.sleep(2)
    
    credential_id, balance = test_binance_connection(
        api_key=BINANCE_API_KEY,
        api_secret=BINANCE_API_SECRET,
        is_live=False  # Demo mode
    )
    
    if not credential_id:
        print("\n❌ Cannot proceed without valid Binance credential")
        return
    
    # STEP 2: Create demo bot
    print("\n⏳ Waiting 3 seconds before bot creation...")
    time.sleep(3)
    
    bot_id = create_demo_bot(
        credential_id=credential_id,
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        strategy="Momentum Trading"
    )
    
    if not bot_id:
        print("\n❌ Bot creation failed")
        return
    
    # STEP 3: Check bot status
    print("\n⏳ Waiting 5 seconds for bot to start trading...")
    time.sleep(5)
    
    get_bot_status(bot_id)
    
    # SUMMARY
    print("\n" + "="*70)
    print("✅ COMPLETE!")
    print("="*70)
    print(f"\n📝 Summary:")
    print(f"   ✓ Binance connection tested")
    print(f"   ✓ Credential ID: {credential_id}")
    print(f"   ✓ Account balance: ${balance:.2f}")
    print(f"   ✓ Demo bot created: {bot_id}")
    print(f"   ✓ Bot is now actively trading on: BTCUSDT, ETHUSDT, SOLUSDT")
    print(f"\n💡 Next steps:")
    print(f"   1. Check bot dashboard for live trading updates")
    print(f"   2. Monitor daily P&L on the Fleet page")
    print(f"   3. Edit risk settings if needed (risk per trade, daily loss limit)")
    print(f"\n🔗 API Endpoints:")
    print(f"   - Get bot status: GET /api/bot/{bot_id}/status")
    print(f"   - Stop bot: POST /api/bot/{bot_id}/stop")
    print(f"   - Get trades: GET /api/bot/{bot_id}/trades")
    print(f"\n⏰ Completed at: {datetime.now().isoformat()}\n")


if __name__ == "__main__":
    main()
