#!/usr/bin/env python3
"""
Check Current Trading Environment Mode
Displays whether backend is in DEMO or LIVE mode
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded .env from: {env_file}\n")
else:
    print(f"❌ No .env file found at: {env_file}\n")
    sys.exit(1)

# Get current environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'DEMO').upper()

print("="*70)
print("ZWESTA TRADING ENVIRONMENT STATUS".center(70))
print("="*70)
print()

if ENVIRONMENT == 'LIVE':
    print("🔴 LIVE MODE - REAL MONEY TRADING ACTIVE")
    print("-" * 70)
    
    account = os.getenv('EXNESS_ACCOUNT', 'NOT SET').strip()
    password = os.getenv('EXNESS_PASSWORD', 'NOT SET').strip()
    server = os.getenv('EXNESS_SERVER', 'Exness-Real').strip()
    
    print(f"Account:   {account}")
    print(f"Server:    {server}")
    print(f"Password:  {'✓ SET' if password and password != 'NOT SET' else '❌ NOT SET'}")
    print()
    
    if not account or account == 'NOT SET' or not password or password == 'NOT SET':
        print("⚠️  WARNING: Credentials incomplete. Cannot start bot in LIVE mode.")
        print()
        print("TO FIX: Update .env file with:")
        print("  EXNESS_ACCOUNT=your_account_number")
        print("  EXNESS_PASSWORD=your_password")
    else:
        print("✅ All credentials configured. Bot will trade on LIVE account.")
        print()
        print("📌 VERIFY TRADES:")
        print("   - Open Exness Portal: my.exness.com/account")
        print("   - Check Account → Trade History")
        print("   - Trades should appear 1-2 seconds after bot execution")

else:
    print("🟢 DEMO MODE - SAFE FOR TESTING")
    print("-" * 70)
    
    account = 298997455
    server = 'Exness-MT5Trial9'
    password = 'Zwesta@1985'
    
    print(f"Account:   {account}")
    print(f"Server:    {server}")
    print(f"Password:  ✓ SET (Demo)")
    print()
    print("✅ Demo account configured. Bot will trade on DEMO account.")
    print()
    print("📌 VERIFY TRADES:")
    print("   - Open Exness MT5 DEMO Terminal")
    print("   - Click: Terminal → Trade History tab")
    print("   - Trades should appear 1-2 seconds after bot execution")

print()
print("="*70)
print("HOW TO SWITCH MODES")
print("="*70)
print()
print("TO SWITCH TO LIVE MODE:")
print("  1. Edit .env file (open with text editor)")
print("  2. Change: ENVIRONMENT=DEMO  →  ENVIRONMENT=LIVE")
print("  3. Update: EXNESS_ACCOUNT=your_account_number")
print("  4. Update: EXNESS_PASSWORD=your_password")
print("  5. Save .env file")
print("  6. Restart backend: python multi_broker_backend_updated.py")
print("  7. Check logs for: [LIVE] USING LIVE EXNESS CREDENTIALS")
print()
print("TO SWITCH BACK TO DEMO MODE:")
print("  1. Edit .env file")
print("  2. Change: ENVIRONMENT=LIVE  →  ENVIRONMENT=DEMO")
print("  3. Save .env file")
print("  4. Restart backend")
print()
print("="*70)
print()

# Test API endpoint
print("Testing API endpoint...")
try:
    import requests
    response = requests.get('http://localhost:5000/api/environment', timeout=2)
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Backend Response:")
        print(f"   Environment: {data.get('environment')}")
        print(f"   Account: {data.get('account')}")
        print(f"   Server: {data.get('server')}")
        print(f"   Status: {data.get('warning')}")
    else:
        print(f"\n⚠️  Backend not responding (status {response.status_code})")
        print("Make sure backend is running: python multi_broker_backend_updated.py")
except Exception as e:
    print(f"\n⚠️  Could not reach backend: {e}")
    print("Make sure backend is running: python multi_broker_backend_updated.py")

print("\n" + "="*70 + "\n")
