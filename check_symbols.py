#!/usr/bin/env python3
import requests
import json

r = requests.get('http://localhost:9000/api/commodities/list')
data = r.json()

print("Symbol categories available:")
total = 0
for category, symbols in data['commodities'].items():
    count = len(symbols)
    total += count
    print(f"  {category}: {count} symbols")
    if symbols:
        print(f"    - {symbols[0]['symbol']} ({symbols[0]['name'][:40]})")

print(f"\nTotal symbols: {total}")
