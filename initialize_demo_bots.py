#!/usr/bin/env python3
"""
Initialize Demo Trading Bots on Backend
Runs the backend API calls to create and start trading bots
"""

import requests
import json
import time
import sys

# Backend URL - Change this if your backend is on a different IP/port
BACKEND_URL = "http://38.247.146.198:9000"

def create_bot(bot_config):
    """Create a trading bot via API"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/bot/create",
            json=bot_config,
            timeout=5
        )
        if response.status_code == 200:
            bot_data = response.json()
            print(f"✅ Bot created: {bot_data.get('botId')}")
            return bot_data.get('botId')
        else:
            print(f"❌ Failed to create bot: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error creating bot: {e}")
        return None

def start_bot(bot_id):
    """Start a trading bot via API"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/bot/start",
            json={"botId": bot_id},
            timeout=5
        )
        if response.status_code == 200:
            bot_data = response.json()
            print(f"✅ Bot started: {bot_id}")
            print(f"   Trades placed: {bot_data.get('tradesPlaced')}")
            print(f"   Total trades: {bot_data['botStats'].get('totalTrades')}")
            return True
        else:
            print(f"❌ Failed to start bot: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        return False

def get_bot_status():
    """Get status of all bots"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/bot/status",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Bot Status:")
            print(f"   Active Bots: {data.get('activeBots')}")
            print(f"   Total Bots: {len(data.get('bots', []))}")
            for bot in data.get('bots', []):
                print(f"\n   Bot: {bot.get('botId')}")
                print(f"   Status: {bot.get('status')}")
                print(f"   Strategy: {bot.get('strategy')}")
                print(f"   Symbols: {bot.get('symbols')}")
                print(f"   Total Trades: {bot.get('totalTrades')}")
                print(f"   Total Profit: ${bot.get('totalProfit', 0):.2f}")
                print(f"   Win Rate: {bot.get('winningTrades', 0)}/{bot.get('totalTrades', 0)}")
            return True
        else:
            print(f"❌ Failed to get bot status: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error getting bot status: {e}")
        return False

def main():
    print("🤖 Zwesta Trading Bot Initializer")
    print(f"Backend URL: {BACKEND_URL}\n")
    
    # Check backend connectivity
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Backend not responding properly")
            sys.exit(1)
        print(f"✅ Backend is online\n")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print(f"Make sure backend is running: python multi_broker_backend_updated.py")
        sys.exit(1)
    
    # Define demo bot configurations
    demo_bots = [
        {
            "botId": "DemoBot_EURUSD_TrendFollow",
            "accountId": "Demo MT5 - XM Global",
            "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
            "strategy": "Trend Following",
            "riskPerTrade": 100,
            "maxDailyLoss": 500,
            "enabled": True,
            "autoSwitch": True,
            "dynamicSizing": True,
            "basePositionSize": 1.0
        },
        {
            "botId": "DemoBot_Commodities_MeanReversion",
            "accountId": "Demo MT5 - XM Global",
            "symbols": ["XAUUSD", "XAGUSD", "WTIUSD"],
            "strategy": "Mean Reversion",
            "riskPerTrade": 75,
            "maxDailyLoss": 400,
            "enabled": True,
            "autoSwitch": True,
            "dynamicSizing": True,
            "basePositionSize": 0.8
        },
        {
            "botId": "DemoBot_Indices_RangeTrading",
            "accountId": "Demo MT5 - XM Global",
            "symbols": ["SPX500", "UK100", "GER40"],
            "strategy": "Range Trading",
            "riskPerTrade": 125,
            "maxDailyLoss": 600,
            "enabled": True,
            "autoSwitch": True,
            "dynamicSizing": True,
            "basePositionSize": 1.2
        }
    ]
    
    print("Creating demo bots...\n")
    
    bot_ids = []
    for bot_config in demo_bots:
        bot_id = create_bot(bot_config)
        if bot_id:
            bot_ids.append(bot_id)
        time.sleep(0.5)
    
    if not bot_ids:
        print("\n❌ Failed to create any bots")
        sys.exit(1)
    
    print(f"\n✅ Created {len(bot_ids)} bots\n")
    print("Starting bots and placing trades...\n")
    
    # Start each bot and run it multiple times to generate more trades
    for i, bot_id in enumerate(bot_ids, 1):
        print(f"Starting bot {i}/{len(bot_ids)}: {bot_id}")
        for trade_cycle in range(3):  # Run 3 trading cycles per bot
            if not start_bot(bot_id):
                print(f"   Warning: Issue starting bot on cycle {trade_cycle + 1}")
            time.sleep(0.5)
    
    # Get final status
    print("\n" + "="*60)
    time.sleep(1)
    get_bot_status()
    
    print("\n" + "="*60)
    print("✅ Demo bots initialized successfully!")
    print(f"\nYour Flutter app should now see {len(bot_ids)} active trading bots")
    print("Check the app's 'Active Bots' dashboard to view the bots and their statistics\n")

if __name__ == "__main__":
    main()
