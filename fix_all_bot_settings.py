#!/usr/bin/env python3
"""
Fix All Bot Settings Script
Restarts all bots for a user to apply corrected SYMBOL_PARAMETERS and runtime state fixes.
"""

import requests
import json
import sys
import os

# Configuration
VPS_URL = "http://38.247.146.198:9000"  # Update if different
USER_ID = "23386f67-aeb4-4de2-98a7-33c1fced2755"  # Your user ID
SESSION_TOKEN = "your_session_token_here"  # Get from browser dev tools or backend logs

def get_user_bots():
    """Get all bots for the user"""
    url = f"{VPS_URL}/api/user/{USER_ID}/bots"
    headers = {
        'Authorization': f'Bearer {SESSION_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('bots', [])
            else:
                print(f"Error getting bots: {data.get('error')}")
                return []
        else:
            print(f"HTTP {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting bots: {e}")
        return []

def start_bot(bot_id):
    """Start a specific bot"""
    url = f"{VPS_URL}/api/bot/start"
    headers = {
        'Authorization': f'Bearer {SESSION_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        'botId': bot_id,
        'user_id': USER_ID,
        'activation_pin': '000000'  # Use test PIN for now
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print(f"✅ Successfully restarted bot {bot_id}")
                return True
            else:
                print(f"❌ Failed to restart bot {bot_id}: {result.get('error')}")
                return False
        else:
            print(f"❌ HTTP {response.status_code} restarting bot {bot_id}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error restarting bot {bot_id}: {e}")
        return False

def main():
    print("🔧 Fixing all bot settings by restarting bots...")
    print(f"User ID: {USER_ID}")
    print(f"VPS URL: {VPS_URL}")
    print(f"Session Token: {SESSION_TOKEN[:20]}..." if SESSION_TOKEN != "your_session_token_here" else "NOT SET")

    if SESSION_TOKEN == "your_session_token_here":
        print("\n❌ ERROR: Session token not set!")
        print("\nTo get your session token:")
        print("1. Open your Flutter web app in browser")
        print("2. Log in to your account")
        print("3. Open Developer Tools (F12)")
        print("4. Go to Application/Storage > Local Storage")
        print("5. Look for 'session_token' or similar key")
        print("6. Copy the token value and paste it here")
        print("\nAlternatively, check backend logs on VPS for session creation.")
        return

    # Get all bots
    bots = get_user_bots()
    if not bots:
        print("No bots found or error retrieving bots")
        return

    print(f"Found {len(bots)} bots to restart")

    # Restart each bot
    restarted = 0
    for bot in bots:
        bot_id = bot.get('botId') or bot.get('bot_id')
        if bot_id:
            print(f"Restarting bot: {bot_id} ({bot.get('name', 'Unknown')})")
            if start_bot(bot_id):
                restarted += 1
        else:
            print(f"Skipping bot with missing ID: {bot}")

    print(f"\n✅ Successfully restarted {restarted}/{len(bots)} bots")
    print("All bots should now use the corrected SYMBOL_PARAMETERS for crypto trading")
    print("Analytics should populate with real data after trades execute")

if __name__ == "__main__":
    main()