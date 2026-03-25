import requests
import json

endpoints = [
    ('account', 'GET'),
    ('positions', 'GET'),
    ('trades', 'GET'),
    ('statistics', 'GET'),
    ('status', 'GET'),
]

for endpoint, method in endpoints:
    url = f'http://127.0.0.1:5000/api/{endpoint}'
    resp = requests.get(url, headers={'Authorization': 'Bearer dummy'})
    print(f"\n=== /api/{endpoint} ===")
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:800])  # First 800 chars
    except Exception as e:
        print(f"Error: {e}")
        print(f"Body: {resp.text[:200]}")
