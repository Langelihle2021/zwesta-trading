import requests
import json

# Test /api/user/accounts endpoint
resp = requests.get('http://127.0.0.1:5000/api/user/accounts', 
    headers={'Authorization': 'Bearer test_token'})

print(f"Status: {resp.status_code}")
print(f"Headers: {dict(resp.headers)}")
print(f"Response text:\n{resp.text}")

try:
    data = resp.json()
    print(f"\nParsed JSON:\n{json.dumps(data, indent=2)}")
except Exception as e:
    print(f"JSON parse error: {e}")
