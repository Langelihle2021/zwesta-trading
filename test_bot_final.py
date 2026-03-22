import requests
import json

credential_id = 'bdcdc580-bb7c-405e-84d5-3d75d03f8556'
token = 'b0e9501facce951ab7c8ae189b0fad43faedc2ea4621d75d407873f996cfcaf8'

payload = {
    'credentialId': credential_id,
    'symbols': ['EURUSDm'],
    'strategy': 'Trend Following',
    'name': 'ETHBotTest',
    'investmentAmount': 500
}

headers = {
    'Content-Type': 'application/json',
    'X-Session-Token': token
}

print("🤖 Creating Ethereum bot with existing backend credentials...")
print(f"Credential: {credential_id[:20]}...")
print(f"Token: {token[:40]}...")
print()

try:
    resp = requests.post('http://localhost:9000/api/bot/create', json=payload, headers=headers, timeout=10)
    print(f'Status: {resp.status_code}')
    body = resp.json()
    print(json.dumps(body, indent=2))
    
    if resp.status_code in [200, 201] and body.get('success'):
        print(f'\n✅ BOT CREATED!')
        print(f'Bot ID: {body.get("bot_id")}')
except Exception as e:
    print(f'❌ Error: {e}')
