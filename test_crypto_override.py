import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, r'C:\zwesta-trader')

# Import the backend to test the function
from multi_broker_backend_updated import is_market_open_for_symbol

print("=" * 60)
print("Testing Crypto 24/7 Override - " + datetime.now().strftime("%H:%M:%S on %A"))
print("=" * 60)

# Test symbols
test_cases = [
    ("ETHUSDm", "Crypto - Ethereum"),
    ("BTCUSDm", "Crypto - Bitcoin"),
    ("XRPUsdt", "Crypto - Ripple"),
    ("EURUSDm", "Forex - Should be blocked on weekends"),
    ("GCz26", "Commodity - Gold"),
]

for symbol, description in test_cases:
    try:
        is_open, message = is_market_open_for_symbol(symbol)
        status = "✅ OPEN" if is_open else "❌ CLOSED"
        print(f"\n{status} | {symbol:12} | {description:40} | {message}")
    except Exception as e:
        print(f"❌ ERROR | {symbol:12} | {str(e)}")

print("\n" + "=" * 60)
print("Test completed")
print("=" * 60)
