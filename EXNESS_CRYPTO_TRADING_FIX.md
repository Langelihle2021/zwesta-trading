# Exness BTC/ETH Trade Execution - Diagnostic & Fix Guide

## Quick Diagnosis

Your bot trades for BTC and Ethereum aren't executing because the **MT5 connection to Exness fails** with error:
```
Terminal: Authorization failed (-6)
```

This prevents the bot trading loop from even connecting to place orders.

## ✓ Quick Checklist - Try These First

### 1. Check Exness MT5 Terminal Login Status
- [ ] Open your Exness MT5 terminal manually  
- [ ] If you see LOGIN SCREEN:
  - Account: `298997455` (demo) or `295619855` (live)
  - Password: Check in `C:\zwesta-trader\Zwesta Flutter App\.env` file
  - Server: Should be `Exness-MT5Trial9` (demo) or `Exness-Real` (live)
- [ ] After login, check status bar at bottom says "Ready"
- [ ] Don't close the terminal

### 2. Verify Crypto Symbols Are Enabled
With terminal logged in:
- [ ] Market Watch panel (right side)
- [ ] Right-click → Symbols
- [ ] Search for "BTCUSDm" - **must appear in list**
- [ ] Search for "ETHUSDm" - **must appear in list**
- [ ] If missing: Go to Exness website → Account Settings → Enable Crypto Trading

### 3. Restart Backend with Fresh Connection
```bash
python multi_broker_backend_updated.py
```
This will now automatically connect to the logged-in MT5 terminal.

### 4. Test Bot Trade Execution
```bash
# From another terminal:
python test_exness_crypto_simple.py
```
If it succeeds:
- ✅ Connection works
- ✅ BTC/ETH orders can be placed
- ✅ Your bots should now execute

---

## If Symbols Still Don't Appear

### Issue: "BTCUSDm" and "ETHUSDm" not in Exness symbol list

**Root Cause**: Crypto trading disabled on your Exness account

**Solution**:
1. Go to your Exness account: https://client.exness.com
2. Settings → Trading → Instruments
3. Find "Cryptocurrencies" section
4. Enable or upgrade subscription for BTC/ETH
5. Close and reopen MT5 terminal
6. Symbols should now appear

### Alternative: Use Forex Instead
If crypto is restricted, test with forex:
- Change `symbols: ['BTCUSDm', 'ETHUSDm']` 
- To: `symbols: ['EURUSDm']` (always available)
- Test bots work with EURUSD first, then add crypto after enabling it

---

## If Login Still Fails

**Error: "Terminal: Authorization failed"**

### Check 1: Verify Credentials
```bash
python -c "
import sqlite3
conn = sqlite3.connect('C:/backend/zwesta_trading.db')
cursor = conn.cursor()
cursor.execute('SELECT account_number, password, server FROM broker_credentials WHERE broker_name LIKE \"%Exness%\" LIMIT 1')
for row in cursor.fetchall():
    print(f'Account: {row[0]}, Password: {row[1]}, Server: {row[2]}')
conn.close()
"
```

Verify these match your actual Exness account.

### Check 2: Try Manual Restart
```bash
# Kill all MT5 terminals
taskkill /F /IM terminal64.exe

# Wait 3 seconds
timeout 3

# Restart terminal
C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe

# Then login manually
```

### Check 3: Check .env File
File: `C:\zwesta-trader\Zwesta Flutter App\.env`

Ensure:
```
ENVIRONMENT=DEMO
EXNESS_ACCOUNT=298997455
EXNESS_PASSWORD=Password123!  # Your actual password
EXNESS_SERVER=Exness-MT5Trial9
```

If changed, restart backend: `python multi_broker_backend_updated.py`

---

## Testing Trade Execution After Fix

### Quick Test Script
```bash
cd "c:\zwesta-trader\Zwesta Flutter App"
python test_exness_crypto_simple.py
```

### Expected Output
```
===============================================================
[4] Checking BTC/ETH symbol availability...
   BTCUSDm: AVAILABLE (bid=43520.50)
   ETHUSDm: AVAILABLE (bid=2280.45)

[5] Testing BTC trade placement...
   Result: {'success': True, 'symbol': 'BTCUSDm', ...}
OK: BTC order placed successfully

[6] Testing ETH trade placement...
   Result: {'success': True, 'symbol': 'ETHUSDm', ...}
OK: ETH order placed successfully
```

If you see "AVAILABLE" for both symbols and "OK" for both trades, then:
✅ **Your BTC/ETH trades will now execute!**

---

## Verify Bot Trades Work

After fix, create a test bot:
1. Open Flutter app
2. Create bot with:
   - Broker: Exness
   - Symbols: BTC, ETH (or both)
   - Risk: Low
   - Duration: 1 cycle
3. Start bot
4. Check backend logs (scroll to see bot trading loop)
5. Verify it places orders for BTC/ETH

---

## Questions?

- Log file: `C:\backend\test_exness_simple.log`
- Backend logs: `C:\backend\backend_live.log`
- Full logs included in startup output
