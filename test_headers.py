#!/usr/bin/env python3
"""Quick test to verify headers are sent"""

import requests

BASE_URL = "http://localhost:9000"
SESSION_TOKEN = "test-session-token-123"

headers = {
    "Content-Type": "application/json",
    "X-Session-Token": SESSION_TOKEN
}

print(f"Headers being sent: {headers}")
print()

# Test 1: Check if headers are included in request
response = requests.post(
    f"{BASE_URL}/api/broker/test-connection",
    json={
        "broker": "Exness",
        "account": "298997455",
        "password": "Zwesta@1985",
        "is_live": False
    },
    headers=headers,
    timeout=30
)

print(f"Response Status: {response.status_code}")
print(f"Response: {response.json()}")
