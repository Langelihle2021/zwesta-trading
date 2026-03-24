"""Quick MT5 login test - verifies credentials work before starting backend"""
import MetaTrader5 as mt5
import time

MT5_PATH = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
ACCOUNT = 298997455
PASSWORD = "Zwesta@1985"
SERVER = "Exness-MT5Trial9"

print(f"MT5 SDK version: {mt5.__version__}")
print(f"Initializing MT5 at: {MT5_PATH}")

# Initialize
if not mt5.initialize(path=MT5_PATH):
    err = mt5.last_error()
    print(f"INIT FAILED: {err}")
    # Try again after waiting
    print("Waiting 5s and retrying...")
    time.sleep(5)
    if not mt5.initialize(path=MT5_PATH):
        print(f"INIT FAILED AGAIN: {mt5.last_error()}")
        exit(1)

print("MT5 initialized OK")

# Login
print(f"Logging in: Account={ACCOUNT}, Server={SERVER}")
login_ok = mt5.login(ACCOUNT, password=PASSWORD, server=SERVER)
if not login_ok:
    err = mt5.last_error()
    print(f"LOGIN FAILED: {err}")
    mt5.shutdown()
    exit(1)

print("LOGIN SUCCESS!")

# Get account info
info = mt5.account_info()
if info:
    print(f"  Balance: ${info.balance:.2f}")
    print(f"  Equity: ${info.equity:.2f}")
    print(f"  Leverage: 1:{info.leverage}")
    print(f"  Server: {info.server}")
    print(f"  Name: {info.name}")

# Test getting ETHUSDm symbol
sym = mt5.symbol_info("ETHUSDm")
if sym:
    print(f"\nETHUSDm found:")
    print(f"  Bid: {sym.bid}")
    print(f"  Ask: {sym.ask}")
    print(f"  Spread: {sym.spread}")
    print(f"  Volume min: {sym.volume_min}")
else:
    print(f"\nETHUSDm NOT FOUND - trying ETHUSD...")
    sym = mt5.symbol_info("ETHUSD")
    if sym:
        print(f"  ETHUSD found: Bid={sym.bid}, Ask={sym.ask}")

# List some available symbols with 'm' suffix
print("\nAvailable symbols with 'm' suffix:")
symbols = mt5.symbols_get()
if symbols:
    m_symbols = [s.name for s in symbols if s.name.endswith('m')][:20]
    for s in m_symbols:
        print(f"  {s}")

mt5.shutdown()
print("\nDONE - MT5 credentials and symbols verified!")
