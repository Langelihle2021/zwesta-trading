#!/usr/bin/env python3
"""
Check MT5 connection status and why positions aren't syncing
"""

import requests
import json

BACKEND_URL = "http://localhost:9000"

def check_mt5_connection():
    """Check if backend has active MT5 connections"""
    print("=" * 70)
    print("🔍 CHECKING MT5 CONNECTION STATUS")
    print("=" * 70)
    
    endpoints = [
        ("/api/broker/status", "Broker connection status"),
        ("/api/mt5/account", "MT5 account info"),
        ("/api/account/balance", "Account balance"),
    ]
    
    for endpoint, desc in endpoints:
        print(f"\n📡 {desc}")
        print(f"   Endpoint: {endpoint}")
        print("-" * 70)
        try:
            resp = requests.get(f"{BACKEND_URL}{endpoint}", timeout=5)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print("Response:")
                print(json.dumps(data, indent=2))
            else:
                print(f"Response: {resp.text[:300]}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    # Check logs
    print("\n\n📋 Recent Backend Logs (last 30 lines)")
    print("=" * 70)
    try:
        with open(r"C:\zwesta-trader\Zwesta Flutter App\backend.log", "r") as f:
            lines = f.readlines()
            relevant = [l for l in lines[-100:] if any(x in l for x in ['MT5', 'position', 'connect', 'ERROR', 'PositionGet'])]
            for line in relevant[-30:]:
                print(line.rstrip())
    except Exception as e:
        print(f"Could not read logs: {e}")

if __name__ == '__main__':
    check_mt5_connection()
