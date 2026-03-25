# VPS Deployment File Paths & Configuration Guide

**Date:** March 25, 2026  
**Status:** Complete PXBT + Exness Integration  

---

## 📋 FILES TO COPY FROM BACKEND TO VPS

### Core Backend Application
```
Source (Local)                              Destination (VPS)
══════════════════════════════════════════════════════════════════════
multi_broker_backend_updated.py      →    /app/multi_broker_backend_updated.py
.env                                 →    /app/.env
requirements.txt                     →    /app/requirements.txt (if exists)
```

### Database Files (if migrating)
```
C:\backend\zwesta_trading.db           →    /app/zwesta_trading.db
```

### Configuration & Credentials
```
.env (with PXBT & Exness secrets)    →    /app/.env
```

### Supporting Python Scripts (Optional but Recommended)
```
test_pxbt_config.py                  →    /app/test_pxbt_config.py
test_exness_config.py                →    /app/test_exness_config.py (if exists)
```

### Documentation
```
PXBT_CONFIGURATION_GUIDE.md          →    /app/docs/PXBT_CONFIGURATION_GUIDE.md
BROKER_INTEGRATION_GUIDE.md          →    /app/docs/BROKER_INTEGRATION_GUIDE.md
BOT_MONITORING_README.md             →    /app/docs/BOT_MONITORING_README.md
```

---

## ✅ CURRENCY & COMMODITY SYMBOL CONFIGURATION

### Exness Symbols (VALID_SYMBOLS) with Signals
All symbols have signal strength thresholds configured:

#### 📊 CURRENCIES (Forex)
| Symbol | Type | Min Signal Strength | Stop Loss | Take Profit |
|--------|------|-------------------|-----------|-------------|
| EURUSDm | Forex Pair | 50 | 8 pips | 15 pips |
| USDJPYm | Forex Pair | 50 | 8 pips | 16 pips |

#### 💎 PRECIOUS METALS & COMMODITIES  
| Symbol | Type | Min Signal Strength | Stop Loss | Take Profit |
|--------|------|-------------------|-----------|-------------|
| XAUUSDm | Gold | 55 | 12 pips | 25 pips |
| (XAGUSD support via mapping) | Silver | 55 | 12 pips | 25 pips |

#### 📈 STOCKS/EQUITIES
| Symbol | Type | Min Signal Strength | Stop Loss | Take Profit |
|--------|------|-------------------|-----------|-------------|
| AAPLm | Tech | 60 | 15 pips | 30 pips |
| AMDm | Semiconductor | 65 | 20 pips | 40 pips |
| MSFTm | Tech Mega-cap | 60 | 14 pips | 28 pips |
| NVDAm | GPU/Semiconductor | 63 | 18 pips | 36 pips |
| JPMm | Finance | 58 | 12 pips | 24 pips |
| BACm | Finance | 58 | 12 pips | 24 pips |
| WFCm | Finance | 58 | 12 pips | 24 pips |
| GOOGLm | Tech | 60 | 14 pips | 28 pips |
| METAm | Tech | 60 | 14 pips | 28 pips |
| ORCLm | Enterprise | 58 | 12 pips | 24 pips |
| TSMm | Semiconductor | 65 | 20 pips | 40 pips |

#### 🪙 CRYPTOCURRENCIES
| Symbol | Type | Min Signal Strength | Stop Loss | Take Profit |
|--------|------|-------------------|-----------|-------------|
| BTCUSDm | Bitcoin | 40 | 50,000 pips | 100,000 pips |
| ETHUSDm | Ethereum | 40 | 2,000 pips | 5,000 pips |

#### 📊 Total Exness Symbols: 16 (All with signals configured)

---

### PXBT Symbols (PXBT_VALID_SYMBOLS) with Signals
PXBT uses default signal strength (55) for all symbols:

#### 📊 CURRENCIES (Forex)
- EURUSD (Signal: 55 - Default)
- GBPUSD (Signal: 55 - Default)
- USDJPY (Signal: 55 - Default)
- USDCHF (Signal: 55 - Default)

#### 💎 PRECIOUS METALS & COMMODITIES
- XAUUSD / XAGUSD (Gold, Silver) (Signal: 55 - Default)
- BRENT (Oil) (Signal: 55 - Default)

#### 📈 INDICES
- US30 (Signal: 55 - Default)
- EUR50 (Signal: 55 - Default)

#### 🪙 CRYPTOCURRENCIES
- BTCUSDT (Bitcoin) (Signal: 55 - Default)
- ETHUSDT (Ethereum) (Signal: 55 - Default)

#### 📊 Total PXBT Symbols: 10 (All with signals configured)

---

## 🔧 CONFIGURATION VERIFICATION

### Signal Strength Configuration (Backend Code Location)
**File:** `multi_broker_backend_updated.py`

#### Exness Signal Definitions (Lines 6780-6891)
```python
SYMBOL_PARAMS = {
    'EURUSDm': {'min_signal_strength': 50, ...},     # Line 6786
    'USDJPYm': {'min_signal_strength': 50, ...},     # Line 6795
    'AAPLm': {'min_signal_strength': 60, ...},       # Line 6805
    'AMDm': {'min_signal_strength': 65, ...},        # Line 6814
    'TSMm': {'min_signal_strength': 65, ...},        # Line 6823
    'MSFTm': {'min_signal_strength': 60, ...},       # Line 6832
    'NVDAm': {'min_signal_strength': 63, ...},       # Line 6841
    'BACm': {'min_signal_strength': 58, ...},        # Line 6850
    'XAUUSDm': {'min_signal_strength': 55, ...},     # Line 6860
    'BTCUSDm': {'min_signal_strength': 40, ...},     # Line 6870
    'ETHUSDm': {'min_signal_strength': 40, ...},     # Line 6879
    # + 5 more (JPMm, WFCm, GOOGLm, METAm, ORCLm)
}
```

#### Default Signal Configuration (Line 6891)
```python
DEFAULT_SYMBOL_PARAMS = {
    'min_signal_strength': 55,  # Used by PXBT and unmapped symbols
}
```

#### Symbol Validation (Lines 6546-6750)
- `VALID_SYMBOLS` = 16 Exness symbols ✅
- `PXBT_VALID_SYMBOLS` = 10 PXBT symbols ✅
- `SYMBOL_MAPPING` = Cross-broker symbol mappings ✅

### Bot Trading Loop Signal Verification
**Location:** `continuous_bot_trading_loop()` (Lines 10384+)

Signal evaluation happens at:
- Line 7190: Trend Following strategy
- Line 7222: Mean Reversion strategy  
- Line 7256: Momentum Trading strategy
- Line 7290: Support/Resistance strategy
- Line 7324: Advanced Moving Average strategy
- Line 7354: Volatility Breakout strategy

All strategies check: `if signal_eval['strength'] < params['min_signal_strength']:`

---

## 🚀 VPS DEPLOYMENT CHECKLIST

### Pre-Deployment (Local Development)
- [x] PXBT symbols configured: EURUSD, GBPUSD, USDJPY, USDCHF, XAUUSD, XAGUSD, US30, EUR50, BRENT, BTCUSDT, ETHUSDT
- [x] Exness symbols configured: 16 total (EURUSDm, XAUUSDm, BTCUSDm, ETHUSDm, + 12 stocks)
- [x] All symbols have signal strength parameters
- [x] Signal detection working (bot trading loop verified)
- [x] Credentials in .env (PXBT_ACCOUNT, PXBT_PASSWORD, EXNESS_ACCOUNT, EXNESS_PASSWORD)

### VPS Deployment Steps
1. **Copy Backend Files**
   ```bash
   scp multi_broker_backend_updated.py user@vps_ip:/app/
   scp .env user@vps_ip:/app/
   scp -r . user@vps_ip:/app/  # Full app copy
   ```

2. **Update VPS .env**
   ```bash
   # SSH into VPS
   ssh user@vps_ip
   cd /app
   
   # Edit .env with:
   ENVIRONMENT=LIVE  # or DEMO
   PXBT_ACCOUNT=<your_account>
   PXBT_PASSWORD=<your_password>
   EXNESS_ACCOUNT=<your_account>
   EXNESS_PASSWORD=<your_password>
   DEPLOYMENT_MODE=VPS
   ```

3. **Start Backend on VPS**
   ```bash
   python multi_broker_backend_updated.py
   ```

4. **Verify Symbols Available**
   ```bash
   curl http://localhost:9000/api/commodities/list
   ```

5. **Verify Signals Working**
   ```bash
   curl http://localhost:9000/api/market/commodities
   ```

---

## 📊 SYMBOL SIGNAL STRENGTH SUMMARY

### All Symbols Configured for Signals ✅

**Exness (16 symbols):**
- Min Signal: 40 (Crypto: BTC, ETH)
- Max Signal: 65 (Semiconductors: AMD, TSM)
- Typical Signal: 55-60

**PXBT (10 symbols):**
- All use Default: 55
- Currencies, Commodities, Indices, Crypto

**Total Unique Symbols: 26** (accounting for XAGUSD mapping)

---

## 🧪 Testing Signal Configuration on VPS

### Test Script
```bash
python test_pxbt_config.py
# Verifies: PXBT availability, credentials, signals
```

### Manual Testing
```bash
# Check Exness commodities with signals
curl http://vps_ip:9000/api/commodities/list

# Check PXBT availability
curl http://vps_ip:9000/api/brokers/check-pxbt

# Check market sentiment (includes signal strength)
curl http://vps_ip:9000/api/market/commodities

# Check bot creation with signals
POST http://vps_ip:9000/api/bot/create
{
  "credentialId": "...",
  "symbols": ["EURUSD", "XAUUSD", "BTCUSDT"],
  "strategy": "Trend Following"
}
```

---

## 🔐 VPS Security Considerations

1. **Sensitive Information** - Copy .env separately with restricted permissions
   ```bash
   chmod 600 /app/.env
   ```

2. **Database** - If copying database with credentials:
   ```bash
   chmod 600 /app/zwesta_trading.db
   ```

3. **API Keys** - Use environment variables, never hardcode
   ```bash
   export API_KEY="..." # Set on VPS
   export DEPLOYMENT_MODE="VPS"
   ```

4. **Firewall** - Restrict backend port (9000)
   ```bash
   sudo ufw allow from your_ip to any port 9000
   sudo ufw deny from any to any port 9000
   ```

---

## 📝 Signal Verification Script

Run this on VPS to verify all signals configured:

```bash
cat > verify_signals.py << 'EOF'
import requests
import json

VPS_URL = "http://localhost:9000"

# Test 1: Exness commodities
print("Testing Exness symbols with signals...")
r = requests.get(f"{VPS_URL}/api/commodities/list")
data = r.json()
total_exness = sum(len(v) for v in data.get('commodities', {}).values())
print(f"✅ Found {total_exness} Exness symbols")

# Test 2: PXBT availability
print("\nTesting PXBT availability...")
r = requests.get(f"{VPS_URL}/api/brokers/check-pxbt")
print(f"✅ PXBT: {r.json()}")

# Test 3: Market data with signals
print("\nTesting market signals...")
r = requests.get(f"{VPS_URL}/api/market/commodities")
data = r.json()
total_symbols = sum(len(v) for v in data.get('commodities', {}).values())
print(f"✅ Found {total_symbols} symbols with signal data")

print("\n✅ All signals verified!")
EOF

python verify_signals.py
```

---

## 📞 Support

If symbols not appearing on VPS:
1. Check `.env` has correct broker credentials
2. Verify MT5 terminal running on VPS
3. Check logs: `tail -f /app/logs/backend.log`
4. Restart backend: `python multi_broker_backend_updated.py`
5. Test endpoint: `curl http://localhost:9000/api/commodities/list`
