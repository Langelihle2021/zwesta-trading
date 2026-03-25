import requests
import json

# Test /api/accounts/{id}/dashboard endpoints
for account_id in [1, 2]:
    resp = requests.get(f'http://127.0.0.1:5000/api/accounts/{account_id}/dashboard', 
        headers={'Authorization': 'Bearer test_token'})
    
    print(f"\n=== /api/accounts/{account_id}/dashboard ===")
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:500])
    except Exception as e:
        print(f"Error: {e}")
        print(f"Body: {resp.text[:300]}")
