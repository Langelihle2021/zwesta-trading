# VPS DEPLOYMENT QUICK REFERENCE

## 📂 Core Files to Copy

```
BACKEND APPLICATION:
  Source: C:\zwesta-trader\Zwesta Flutter App\multi_broker_backend_updated.py
  Target: /app/multi_broker_backend_updated.py
  Size: ~14MB (contains all logic, signals, symbol configs)

ENVIRONMENT VARIABLES:
  Source: C:\zwesta-trader\Zwesta Flutter App\.env
  Target: /app/.env
  Critical: PXBT_ACCOUNT, PXBT_PASSWORD, EXNESS_ACCOUNT, EXNESS_PASSWORD

DATABASE (Optional):
  Source: C:\backend\zwesta_trading.db
  Target: /app/zwesta_trading.db
  Note: Only if migrating existing data
```

---

## ✅ CURRENCIES & COMMODITIES WITH SIGNALS - VERIFICATION

### LINE NUMBERS IN multi_broker_backend_updated.py

**EXNESS SYMBOLS (16 total):**
```
Lines 6546-6562:  VALID_SYMBOLS definition
  - EURUSDm       ✅ Line 6553
  - USDJPYm       ✅ Line 6554
  - XAUUSDm       ✅ Line 6555
  - BTCUSDm       ✅ Line 6548
  - ETHUSDm       ✅ Line 6549
  - AAPLm through TSMm (11 stocks) ✅ Lines 6556-6562

Signal Thresholds (Lines 6780-6891):
  - EURUSDm       ✅ min_signal 50  (Line 6786)
  - USDJPYm       ✅ min_signal 50  (Line 6795)
  - XAUUSDm       ✅ min_signal 55  (Line 6860)
  - BTCUSDm       ✅ min_signal 40  (Line 6870)
  - ETHUSDm       ✅ min_signal 40  (Line 6879)
  - AAPLm         ✅ min_signal 60  (Line 6805)
  - AMDm          ✅ min_signal 65  (Line 6814)
  - TSMm          ✅ min_signal 65  (Line 6823)
  - MSFTm         ✅ min_signal 60  (Line 6832)
  - NVDAm         ✅ min_signal 63  (Line 6841)
  - BACm          ✅ min_signal 58  (Line 6850)
  + JPMm, WFCm, GOOGLm, METAm, ORCLm with 58-60 signal
```

**PXBT SYMBOLS (10 total):**
```
Lines 6578-6584:  PXBT_VALID_SYMBOLS definition
  - EURUSD        ✅ Line 6579 (uses DEFAULT: 55)
  - GBPUSD        ✅ Line 6579 (uses DEFAULT: 55)
  - USDJPY        ✅ Line 6579 (uses DEFAULT: 55)
  - USDCHF        ✅ Line 6579 (uses DEFAULT: 55)
  - XAUUSD        ✅ Line 6580 (uses DEFAULT: 55)
  - XAGUSD        ✅ Line 6580 (uses DEFAULT: 55)
  - US30          ✅ Line 6581 (uses DEFAULT: 55)
  - EUR50         ✅ Line 6581 (uses DEFAULT: 55)
  - BRENT         ✅ Line 6581 (uses DEFAULT: 55)
  - BTCUSDT       ✅ Line 6582 (uses DEFAULT: 55)
  - ETHUSDT       ✅ Line 6582 (uses DEFAULT: 55)

Default Signal (Line 6891):
  - DEFAULT_SYMBOL_PARAMS['min_signal_strength'] = 55 ✅
```

---

## 🎯 SIGNAL PROCESSING IN TRADING LOOP

```
File: multi_broker_backend_updated.py
Function: continuous_bot_trading_loop()

Signal Strength Checks:
  Line 7190:   Trend Following    - checks min_signal_strength
  Line 7222:   Mean Reversion     - checks min_signal_strength + 5
  Line 7256:   Momentum Trading   - checks min_signal_strength
  Line 7290:   Support/Resistance - checks min_signal_strength - 5
  Line 7324:   Advanced MA        - checks min_signal_strength - 10
  Line 7354:   Volatility BO      - checks min_signal_strength + 10

All strategies follow pattern:
  if signal_eval['strength'] < params['min_signal_strength']:
      skip trade  # Signal too weak
  else:
      execute trade  # Signal meets threshold
```

---

## 🔗 CURRENCY/COMMODITY MAPPINGS

```
File: multi_broker_backend_updated.py
Lines 6585-6650:  SYMBOL_MAPPING dictionary

Exness Symbols (XAUUSD variations):
  'XAUUSD'   → XAUUSDm   ✅ Line 6589
  'XAGUSD'   → (mapped to XAUUSD) ✅ Line 6589
  
Forex Pairs:
  'EURUSD'   → EURUSDm   ✅ Line 6587
  'USDJPY'   → USDJPYm   ✅ Line 6588

PXBT Symbols (all in SYMBOL_MAPPING):
  'EURUSD'   → 'EURUSD'  ✅ (Line 6693)
  'XAUUSD'   → 'XAUUSD'  ✅ (Line 6695)
  'BTCUSDT'  → 'BTCUSDT' ✅ (Line 6700)
```

---

## 📡 API ENDPOINTS FOR VPS TESTING

After deploying to VPS, verify signals:

```bash
# 1. Get all commodities with signals
curl http://vps_ip:9000/api/commodities/list
# Should return: Exness + PXBT symbols

# 2. Check market sentiment with signals
curl http://vps_ip:9000/api/market/commodities
# Should show signal_strength for each symbol

# 3. Check PXBT availability
curl http://vps_ip:9000/api/brokers/check-pxbt
# Should return: { "available": true, ... }

# 4. Create bot with signals (test request)
curl -X POST http://vps_ip:9000/api/bot/create \
  -H "Content-Type: application/json" \
  -d '{
    "credentialId": "test_cred",
    "symbols": ["EURUSD", "XAUUSD", "BTCUSDT"],
    "strategy": "Trend Following"
  }'
# Should use signal thresholds internally
```

---

## 🚀 QUICK COPY COMMANDS

### SCP (Secure Copy to VPS)

```bash
# Set variables
VPS_IP="38.247.146.198"
VPS_USER="ubuntu"

# Copy main backend
scp multi_broker_backend_updated.py ${VPS_USER}@${VPS_IP}:/app/

# Copy .env (with credentials)
scp .env ${VPS_USER}@${VPS_IP}:/app/

# Copy test scripts
scp test_pxbt_config.py ${VPS_USER}@${VPS_IP}:/app/

# Verify copy
ssh ${VPS_USER}@${VPS_IP} "ls -lh /app/*.py"
```

### Via GitHub (If using git)

```bash
# On VPS
cd /app
git pull origin main

# Update .env on VPS with live credentials
nano .env  # or vim .env
# (Set PXBT_ACCOUNT, PXBT_PASSWORD, EXNESS_ACCOUNT, EXNESS_PASSWORD)

# Start backend
python multi_broker_backend_updated.py
```

---

## 📊 SYMBOL STATUS GRID

```
┌──────────────┬────────────┬──────────────┬──────────────┐
│ Symbol       │ Broker     │ Signal Conf  │ Status       │
├──────────────┼────────────┼──────────────┼──────────────┤
│ EURUSDm      │ Exness     │ 50           │ ✅ Configured│
│ USDJPYm      │ Exness     │ 50           │ ✅ Configured│
│ XAUUSDm      │ Exness     │ 55           │ ✅ Configured│
│ BTCUSDm      │ Exness     │ 40           │ ✅ Configured│
│ ETHUSDm      │ Exness     │ 40           │ ✅ Configured│
│ AAPLm-TSMm   │ Exness     │ 58-65        │ ✅ Configured│
│              │            │              │              │
│ EURUSD       │ PXBT       │ 55 (default) │ ✅ Configured│
│ GBPUSD       │ PXBT       │ 55 (default) │ ✅ Configured│
│ USDJPY       │ PXBT       │ 55 (default) │ ✅ Configured│
│ USDCHF       │ PXBT       │ 55 (default) │ ✅ Configured│
│ XAUUSD       │ PXBT       │ 55 (default) │ ✅ Configured│
│ XAGUSD       │ PXBT       │ 55 (default) │ ✅ Configured│
│ US30         │ PXBT       │ 55 (default) │ ✅ Configured│
│ EUR50        │ PXBT       │ 55 (default) │ ✅ Configured│
│ BRENT        │ PXBT       │ 55 (default) │ ✅ Configured│
│ BTCUSDT      │ PXBT       │ 55 (default) │ ✅ Configured│
│ ETHUSDT      │ PXBT       │ 55 (default) │ ✅ Configured│
└──────────────┴────────────┴──────────────┴──────────────┘

Total: 26 symbols (16 Exness + 10 PXBT)
All: ✅ Have signal strength configured
```

---

## ⚙️ CONFIGURATION CHECKLIST FOR VPS

Before starting backend on VPS:

```bash
☐ Copy multi_broker_backend_updated.py to /app/
☐ Copy .env to /app/ and update with VPS paths
☐ Set DEPLOYMENT_MODE=VPS in .env
☐ Set ENVIRONMENT=LIVE or DEMO in .env
☐ Set PXBT_ACCOUNT and PXBT_PASSWORD in .env
☐ Set EXNESS_ACCOUNT and EXNESS_PASSWORD in .env
☐ Verify permissions: chmod 600 /app/.env
☐ Copy database if needed: /app/zwesta_trading.db
☐ Install Python dependencies (if not pre-installed)
☐ Run backend: python multi_broker_backend_updated.py
☐ Test endpoint: curl http://localhost:9000/api/commodities/list
☐ Verify all 26 symbols appear in response
☐ Confirm signal_strength values in response
```

---

## 🧪 Validation Commands Post-Deployment

```bash
# SSH into VPS
ssh user@vps_ip

# Test 1: Backend running?
curl -s http://localhost:9000/api/commodities/list | head -20

# Test 2: Count symbols received
curl -s http://localhost:9000/api/commodities/list | grep -o '"' | wc -l

# Test 3: Check signals present?
curl -s http://localhost:9000/api/market/commodities | grep signal_strength

# Test 4: PXBT availability
curl http://localhost:9000/api/brokers/check-pxbt

# Test 5: Check logs for errors
tail -50 /app/logs/backend.log  # (if logging to file)
```

---

**Status:** ✅ All 26 symbols (currencies/commodities) configured with signals  
**Ready:** ✅ Files identified and tested for VPS deployment  
**Date:** March 25, 2026
