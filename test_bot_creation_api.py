import requests
import json

# Create bot with valid session token
headers = {
    "Content-Type": "application/json",
    "X-Session-Token": "debug_token_49b6b05ad32648759f26f6ac37eebcef"
}

bot_data = {
    "credentialId": "cred_demo_test",
    "symbols": ["EURUSDm"],
    "strategy": "Trend Following",
    "name": "DebugTestBot",
    "enabled": True,
    "riskPerTrade": 20,
    "maxDailyLoss": 60
}

try:
    response = requests.post(
        "http://localhost:9000/api/bot/create",
        headers=headers,
        json=bot_data,
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
