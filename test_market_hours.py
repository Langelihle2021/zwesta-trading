#!/usr/bin/env python3
import sys
from datetime import datetime

# Test the crypto override directly
def is_market_open_for_symbol(symbol):
    """Simplified test of crypto 24/7 override logic"""
    symbol_upper = symbol.upper()
    
    # CRYPTO 24/7 OVERRIDE
    if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'XRP', 'USDT']):
        return True, f"✅ CRYPTO 24/7: {symbol} allowed to trade on weekends/weekdays"
    
    # For non-crypto, check day of week
    import calendar
    from datetime import datetime
    weekday = calendar.weekday(datetime.now().date())  # Mon=0, Sun=6
    
    if weekday == 6:  # Sunday
        return False, f"❌ Market closed (Sunday - day {weekday} not in trading days)"
    elif weekday == 5:  # Saturday
        return False, f"❌ Market closed (Saturday - day {weekday} not in trading days)"
    
    return True, f"✅ Market open for {symbol}"

# Test cases
print("\n" + "="*70)
print(f"Testing Crypto 24/7 Override - {datetime.now().strftime('%A, %B %d, %Y %H:%M:%S')}")
print("="*70)

test_symbols = ['ETHUSDm', 'BTCUSDm', 'XRPUsdt', 'EURUSDm', 'GBPUSD', 'XAUUSD']

for sym in test_symbols:
    is_open, message = is_market_open_for_symbol(sym)
    print(f"{message}")

print("="*70 + "\n")

# NOW TEST: If today is SUNDAY (day 6), crypto should be OPEN, forex should be CLOSED
import calendar
today_day = calendar.weekday(datetime.now().date())
print(f"📅 Today is day {today_day} ({['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][today_day]})")

if today_day == 6:  # Sunday
    print("\n✅ SUNDAY TEST RESULTS:")
    print("  • ETHUSDm (crypto): Should be ✅ OPEN")
    eth_open, eth_msg = is_market_open_for_symbol('ETHUSDm')
    print(f"    Result: {eth_msg}")
    
    print("  • EURUSDm (forex): Should be ❌ CLOSED")
    eur_open, eur_msg = is_market_open_for_symbol('EURUSDm')
    print(f"    Result: {eur_msg}")
else:
    print(f"\n⚠️ WARNING: Today is {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][today_day]} (not Sunday)")
    print("   For full testing, run this script on Sunday when market hours matter")
