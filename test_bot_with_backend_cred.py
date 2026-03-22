import requests
import json

credential_id = 'a4369511-e8ee-4f57-8276-025956b87b3b'
token = 'test-backend-token'

payload = {
    'credentialId': credential_id,
    'symbols': ['EURUSDm'],
    'strategy': 'Trend Following',
    'name': 'TestEthBot',
    'investmentAmount': 500
}

headers = {
    'Content-Type': 'application/json',
    'X-Session-Token': token
}

print(f"🤖 Creating bot with credential from C:\\backend\\zwesta_trading.db...")
print(f"Credential ID: {credential_id}")
print(f"Session token: {token}")
print()

try:
    resp = requests.post('http://localhost:9000/api/bot/create', json=payload, headers=headers, timeout=10)
    print(f'Status: {resp.status_code}')
    body = resp.json()
    print(json.dumps(body, indent=2))
    
    if resp.status_code in [200, 201] and body.get('success'):
        print(f'\n✅ BOT CREATED SUCCESSFULLY!')
        print(f'Bot ID: {body.get("bot_id")}')
    elif resp.status_code == 401:
        print(f'\n❌ Session validation failed')
    elif resp.status_code == 404:
        print(f'\n❌ Credential not found')
except Exception as e:
    print(f'Error: {e}')
