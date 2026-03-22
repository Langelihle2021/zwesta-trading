import requests
import json

credential_id = 'b7cc78a2-7096-4fc9-aa80-6d6eb2c06f88'
token = 'test-session-token-123'

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

print('🤖 Creating bot with test-session-token-123...')
try:
    resp = requests.post('http://localhost:9000/api/bot/create', json=payload, headers=headers, timeout=10)
    print(f'Status: {resp.status_code}')
    body = resp.json()
    print(json.dumps(body, indent=2))
    
    if resp.status_code == 201 and body.get('success'):
        print(f'\n✅ BOT CREATED!')
        print(f'Bot ID: {body.get("bot_id")}')
except Exception as e:
    print(f'Error: {e}')
