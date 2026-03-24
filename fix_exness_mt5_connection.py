#!/usr/bin/env python3
"""
Fix Exness MT5 connection authorization issues
"""

import subprocess
import time
import sys

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

print("=" * 70)
print("EXNESS MT5 CONNECTION FIX")
print("=" * 70)

print("\n[STEP 1] Checking Exness MT5 terminal status...")
terminal_path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

# Check if terminal is running
procs = run_cmd('tasklist /FI "IMAGENAME eq terminal64.exe" /FO LIST')
if "terminal64.exe" in procs:
    print("OK: Exness MT5 terminal is running")
    
    # Kill it to restart fresh
    print("\n[STEP 2] Restarting MT5 terminal (kill and restart)...")
    run_cmd('taskkill /F /IM terminal64.exe 2>nul')
    time.sleep(2)
    print("Killed existing terminal, waiting 3 seconds...")
    time.sleep(3)
else:
    print("INFO: Terminal not running, will start it")

print("\n[STEP 3] Launching Exness MT5 terminal...")
try:
    # Launch terminal without parameters - user must login manually first
    subprocess.Popen(terminal_path)
    print("Terminal launched. Waiting 15 seconds for startup...")
    time.sleep(15)
    print("OK: Terminal should now be running")
except Exception as e:
    print(f"ERROR: Could not launch terminal: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("NEXT STEPS:")
print("=" * 70)
print("""
1. Exness MT5 terminal is now running

2. IF YOU SEE LOGIN SCREEN:
   - Enter your account number: 298997455
   - Enter your password
   - Make sure it connects to: Exness-MT5Trial9
   - Wait until "Ready" appears at bottom

3. Once logged in, verify:
   - Click Symbols in Market Watch  
   - Search for "BTCUSDm" and "ETHUSDm"
   - Make sure both appear in the list
   - If not: they're disabled on your account

4. After manual login, restart the backend:
   - Exit this terminal
   - Restart: python multi_broker_backend_updated.py
   - This will now connect automatically and place trades

5. Common issues:
   - If login fails: Check account number and password in .env file
   - If symbols don't appear: Enable crypto on Exness website
   - If "Authorization failed" continues: Account may be restricted
""")

print("\nWaiting for you to login to terminal manually...")
print("Press ENTER here after you've logged in...")
input()

print("\nVerifying terminal logged in...")
sys.path.insert(0, r'C:\zwesta-trader\Zwesta Flutter App')

try:
    import MetaTrader5 as mt5
    
    # Check if terminal is initialized
    info = mt5.terminal_info()
    if info:
        print(f"OK: MT5 terminal initialized")
        print(f"    Path: {info.path}")
        print(f"    Version: {info.version}")
    else:
        print("WARN: MT5 not initialized yet")
    
    # Check for account
    acc = mt5.account_info()
    if acc:
        print(f"OK: Logged into Exness account")
        print(f"    Account: {acc.login}")
        print(f"    Balance: ${acc.balance:,.2f}")
        print(f"    Equity: ${acc.equity:,.2f}")
        
        # Check symbols
        print(f"\nChecking for BTC/ETH symbols...")
        for sym in ['BTCUSDm', 'ETHUSDm']:
            info = mt5.symbol_info(sym)
            if info:
                print(f"    OK: {sym} available")
            else:
                print(f"    FAIL: {sym} NOT available - enable on Exness website")
    else:
        print("FAIL: Not logged into any account - login in terminal window and retry")
        
except Exception as e:
    print(f"Could not check MT5 status: {e}")

print("\nYou can now:")
print("1. Restart the backend: py multi_broker_backend_updated.py")
print("2. Run your bots - they should now execute trades")
