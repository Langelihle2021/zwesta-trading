import requests
import json

print("=== API DATA TEST ===\n")

endpoints = [
    ('Account', 'http://127.0.0.1:5000/api/account'),
    ('Trades', 'http://127.0.0.1:5000/api/trades'),
    ('Positions', 'http://127.0.0.1:5000/api/positions'),
]

for name, url in endpoints:
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"✓ {name}: {r.status_code}")
            if 'data' in data:
                if isinstance(data['data'], list):
                    print(f"  Records: {len(data['data'])}")
                    if data['data']:
                        print(f"  Sample: {json.dumps(data['data'][0], indent=2)[:200]}...")
                else:
                    print(f"  Data: {json.dumps(data['data'], indent=2)[:200]}...")
        else:
            print(f"✗ {name}: {r.status_code}")
    except Exception as e:
        print(f"✗ {name}: {str(e)}")
    print()
