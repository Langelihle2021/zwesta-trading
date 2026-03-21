# 🔄 DEMO vs LIVE Trading Mode Guide

## Current Status
✅ Backend configured for **BOTH DEMO and LIVE modes**  
✅ Easily switch modes via `.env` file  
✅ Trade verification instructions included

---

## 🟢 DEMO MODE (Default - Safe for Testing)

### Current Config
- **Account:** 298997455
- **Server:** Exness-MT5Trial9
- **Broker:** Exness Demo
- **Status:** Safe for testing, no real money

### How to Verify DEMO Trades
1. **Open Exness MT5 Demo Terminal**
2. **Go to: Terminal → Trade History tab**
3. **Look for trades** matching your bot execution times
4. **Trades appear within 1-2 seconds** of bot cycle starting

### What You'll See
```
Trade History in Exness MT5 Demo:
├─ Ticket: 1234567
├─ Symbol: EURUSDm
├─ Type: Buy
├─ Volume: 0.01
├─ Open Time: 13:45:30
└─ Status: Closed/Open
```

---

## 🔴 LIVE MODE (Real Money Trading)

### How to Enable LIVE Mode

#### Step 1: Edit `.env` File
Open `.env` in text editor and find the ENVIRONMENT section:

```env
# BEFORE (DEMO):
ENVIRONMENT=DEMO

# AFTER (LIVE):
ENVIRONMENT=LIVE
```

#### Step 2: Add Your Exness Live Credentials
In the same `.env` file, update:

```env
# YOUR LIVE Exness Account Number
EXNESS_ACCOUNT=295619855

# YOUR LIVE Exness Password
EXNESS_PASSWORD=Zwesta@1985

# LIVE Trading Server
EXNESS_SERVER=Exness-Real
```

**Replace 295619855 and Zwesta@1985 with your actual credentials!**

#### Step 3: Save `.env` File
Make sure to save the file!

#### Step 4: Restart Backend
```powershell
# Close current backend (Ctrl+C)
# Then restart:
python multi_broker_backend_updated.py
```

#### Step 5: Verify in Logs
Look for these messages in the backend logs:

```
======================================================================
[ENVIRONMENT] Current Mode: LIVE
======================================================================

======================================================================
[LIVE MODE ACTIVATED] 🔴 REAL MONEY TRADING
======================================================================
Account:  295619855
Server:   Exness-Real
Broker:   Exness
======================================================================

[LIVE] ⚠️  USING LIVE EXNESS CREDENTIALS - Account: 295619855
```

### How to Verify LIVE Trades

#### Option 1: Exness Portal
1. **Go to:** https://my.exness.com/account
2. **Click:** Account → Trade History
3. **Look for trades** matching bot execution times
4. **Trades appear 1-2 seconds** after bot cycle

#### Option 2: Exness MT5 Live Terminal
1. **Open Exness MT5 Live Terminal**
2. **Go to: Terminal → Trade History tab**
3. **Look for trades** matching bot execution times
4. **Verify:**
   - Account dropdown shows correct account number
   - Trades show your symbols (EURUSDm, GBPUSDm, etc.)
   - Profit/Loss updates in real-time

### What You'll See
```
Trade History in Exness Portal:
├─ Account: 295619855
├─ Ticket: 7654321
├─ Symbol: EURUSDm
├─ Type: Buy
├─ Volume: 0.01
├─ Open Time: 13:45:30
├─ Closed Time: 13:46:15
└─ Profit: $2.50 USD
```

---

## 🔍 Quick Environment Check

### Option 1: Run Python Script
```powershell
cd C:\zwesta-trader\Zwesta Flutter App
python check_environment.py
```

Output will show:
```
🔴 LIVE MODE - REAL MONEY TRADING ACTIVE
Account:   295619855
Server:    Exness-Real
Password:  ✓ SET
```

or

```
🟢 DEMO MODE - SAFE FOR TESTING
Account:   298997455
Server:    Exness-MT5Trial9
Password:  ✓ SET (Demo)
```

### Option 2: Check via API
```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/environment"
```

Response:
```json
{
  "success": true,
  "environment": "LIVE",
  "account": 295619855,
  "server": "Exness-Real",
  "isLive": true,
  "warning": "🔴 LIVE MODE - REAL MONEY TRADING"
}
```

---

## ⚠️ Important Safety Notes

### Before Trading LIVE
- ✅ Test in DEMO mode first
- ✅ Verify your credentials are correct
- ✅ Confirm account number matches in MT5 terminal dropdown
- ✅ Check that AutoTrading is **ENABLED** in MT5 (Toolbar → AutoTrading button)
- ✅ Ensure account has sufficient balance
- ✅ Monitor first few trades manually

### AutoTrading Check (Critical!)
If trades don't appear on LIVE:
1. **Open Exness MT5 Terminal**
2. **Look at top toolbar**
3. **Find AutoTrading button** (should be highlighted/green)
4. **If disabled:** Click it to enable
5. **If error:** Check backend logs for error code 10027

### Troubleshooting

#### Problem: Trades not appearing in DEMO
```
Checklist:
❌ Is Exness MT5 Demo terminal open?
   → Open it from Start menu
❌ Is account logged in?
   → Check Account dropdown in MT5
❌ Is ENVIRONMENT set to DEMO?
   → Run: python check_environment.py
❌ Is backend running?
   → Check terminal for: python multi_broker_backend_updated.py
```

#### Problem: Trades not appearing in LIVE
```
Checklist:
❌ Is ENVIRONMENT set to LIVE?
   → Run: python check_environment.py
❌ Are credentials correct in .env?
   → Verify EXNESS_ACCOUNT and EXNESS_PASSWORD
❌ Is Exness MT5 terminal connected?
   → Check Account dropdown matches EXNESS_ACCOUNT
❌ Is AutoTrading enabled?
   → Look for green AutoTrading button in toolbar
❌ Has backend been restarted after .env change?
   → Kill backend and restart
```

### Checking Backend Logs
```
When bot starts trading, you should see:

[DEMO] Bot bot_1234: Placing BUY order on EURUSDm
✅ Bot bot_1234: Order placed successfully on EURUSDm
✅ Bot bot_1234: Trade executed | EURUSDm BUY | P&L: $0.00

or (if error):

❌ Bot bot_1234: Order failed on EURUSDm: Symbol not found
⚠️ MT5 order_send returned None - terminal may have disconnected
```

---

## 📋 Environment Variables Reference

### .env File Location
```
C:\zwesta-trader\Zwesta Flutter App\.env
```

### All Settings
```env
# Mode: DEMO or LIVE
ENVIRONMENT=DEMO

# Live credentials (only used when ENVIRONMENT=LIVE)
EXNESS_ACCOUNT=295619855
EXNESS_PASSWORD=Zwesta@1985
EXNESS_SERVER=Exness-Real
EXNESS_PATH=

# Demo credentials (hardcoded as defaults)
# Account: 298997455
# Server: Exness-MT5Trial9
# Password: Zwesta@1985
```

---

## 🚀 Quick Start

### For DEMO Testing
```powershell
# 1. Verify .env has ENVIRONMENT=DEMO
# 2. Restart backend (it's already in DEMO by default)
python multi_broker_backend_updated.py

# 3. Open Exness MT5 Demo Terminal
# 4. Create and start a bot in Flutter app
# 5. Check Trade History in MT5 Demo Terminal
```

### For LIVE Trading
```powershell
# 1. Edit .env and set ENVIRONMENT=LIVE
# 2. Add your Exness live credentials to .env
# 3. Restart backend
python multi_broker_backend_updated.py

# 4. See "[LIVE] USING LIVE EXNESS CREDENTIALS" in logs
# 5. Create and start a bot in Flutter app
# 6. Check Trade History in Exness portal / MT5 Live Terminal
```

---

## 📞 Support

If trades don't appear:
1. Check backend logs for errors
2. Verify `.env` settings with `python check_environment.py`
3. Confirm MT5 terminal is connected
4. Enable AutoTrading in MT5 terminal
5. Check Exness account has sufficient balance

**Created:** March 20, 2026  
**Last Updated:** March 20, 2026  
**Status:** Ready for DEMO/LIVE Trading with Full Verification
