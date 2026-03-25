# PXBT Configuration Guide

**Last Updated:** March 25, 2026

## Overview
Prime XBT (PXBT) is now fully integrated with the Zwesta Trading system. This guide explains how to configure and use PXBT for automated trading.

## Quick Start

### 1. Get PXBT Account
- Visit: https://www.primexbt.com/
- Sign up for demo or live trading account
- Download MT5 Terminal

### 2. Configure .env File
Set your PXBT credentials in `.env`:

```env
# For DEMO trading (no real money)
ENVIRONMENT=DEMO
PXBT_ACCOUNT=<your_demo_account_id>
PXBT_PASSWORD=<your_demo_password>
PXBT_SERVER=PXBT-Demo

# For LIVE trading (real money)
ENVIRONMENT=LIVE
PXBT_ACCOUNT=<your_live_account_id>
PXBT_PASSWORD=<your_live_password>
PXBT_SERVER=PXBT-Real
```

### 3. Start Backend
```bash
python multi_broker_backend_updated.py
```

### 4. Integrate Broker Account
```bash
# Create PXBT credential in system
curl -X POST http://localhost:9000/api/broker/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "brokerName": "PXBT",
    "accountNumber": "<account_id>",
    "password": "<password>",
    "server": "PXBT-Demo",
    "isLive": false
  }'
```

### 5. Create Trading Bot
```bash
curl -X POST http://localhost:9000/api/bot/create \
  -H "Content-Type: application/json" \
  -d '{
    "credentialId": "<credential_id_from_step_4>",
    "symbols": ["EURUSD", "XAUUSD"],
    "strategy": "Trend Following",
    "riskPerTrade": 20,
    "maxDailyLoss": 100
  }'
```

### 6. Start Trading
Bot will automatically execute trades based on configured strategy.

## Configuration Details

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `PXBT_ACCOUNT` | Numeric account ID | `123456` |
| `PXBT_PASSWORD` | MT5 password | `YourPassword123` |
| `PXBT_SERVER` | Trading server | `PXBT-Demo` or `PXBT-Real` |
| `PXBT_PATH` | MT5 terminal path | `C:\Program Files\PXBT...` |
| `ENVIRONMENT` | Mode | `DEMO` or `LIVE` |

### Broker Server Names

- **DEMO:** `PXBT-Demo` (practice account, no real money)
- **LIVE:** `PXBT-Real` (real money trading)

### Supported Symbols

PXBT supports these symbol categories:

**Forex:**
- EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF

**Commodities:**
- XAUUSD (Gold)
- XAGUSD (Silver)
- CRUDE (Crude Oil)
- BRENT (Brent Oil)

**Indices:**
- US500 (S&P 500)
- US100 (Nasdaq 100)
- GER30 (DAX Germany)
- EU50 (Euro Stoxx 50)

**Crypto (if available):**
- BTCUSD (Bitcoin)
- ETHUSD (Ethereum)

## API Endpoints

### Check PXBT Availability
```http
GET /api/brokers/check-pxbt
```
Verifies PXBT MT5 terminal is available.

**Response:**
```json
{
  "available": true,
  "path": "C:\\Program Files\\PXBT Trading MT5 Terminal\\terminal64.exe",
  "status": "ready"
}
```

### Integrate Broker Credentials
```http
POST /api/broker/credentials
```
Register PXBT account for trading.

**Request:**
```json
{
  "brokerName": "PXBT",
  "accountNumber": "123456",
  "password": "yourpassword",
  "server": "PXBT-Demo",
  "isLive": false
}
```

### Create Trading Bot
```http
POST /api/bot/create
```
Create a new trading bot using PXBT credentials.

**Request:**
```json
{
  "credentialId": "uuid-from-broker-integration",
  "botId": "PXBT_Bot_1",
  "symbols": ["EURUSD", "XAUUSD", "GBPUSD"],
  "strategy": "Trend Following",
  "riskPerTrade": 20,
  "maxDailyLoss": 100,
  "enabled": true
}
```

## Backend Integration

### File Changes Made

1. **.env**
   - Added PXBT credential placeholders
   - Server name configuration
   - Path auto-detection option

2. **multi_broker_backend_updated.py**
   - Lines 225-251: PXBT configuration detection
   - Lines 4536-4548: `/api/brokers/check-pxbt` endpoint
   - Line 10521: Bot trading loop includes PXBT in MT5 detection
   - Automatic path detection for PXBT terminal

3. **lib/screens/broker_integration_screen.dart**
   - PXBT added to broker list (line 64)
   - PXBT server mapping (line 84-85)
   - PXBT availability check (lines 246-271)
   - Connection testing (line 345)

## Troubleshooting

### Error: "PXBT MT5 not found"
**Solution:** 
1. Install PXBT MT5 Terminal from https://www.primexbt.com/
2. Set `PXBT_PATH` in .env if installed in custom location
3. Ensure terminal is running before starting backend

### Error: "Unknown symbol" in trading
**Solution:**
1. Verify symbol exists on PXBT MT5
2. Check symbol naming: PXBT uses standard MT5 symbols (EURUSD, not EUR/USD)
3. Quote your strategy symbol configuration

### Error: "Account not found"
**Solution:**
1. Verify account number matches MT5 terminal
2. Check password is correct
3. Ensure account is active on PXBT server

### MT5 Connection Timeout
**Solution:**
1. Start PXBT MT5 Terminal manually
2. Login to account (symbol quotes will load)
3. Wait 5-10 seconds for terminal to fully initialize
4. Restart backend: `python multi_broker_backend_updated.py`

## Testing

### Run Configuration Test
```bash
python test_pxbt_config.py
```

This checks:
- ✅ Environment variables set
- ✅ PXBT MT5 terminal installed
- ✅ Backend endpoint available
- ✅ PXBT configured correctly
- ✅ Bot creation support

### Manual Testing Flow
1. Start backend: `python multi_broker_backend_updated.py`
2. Get PXBT availability: `curl http://localhost:9000/api/brokers/check-pxbt`
3. Integrate credentials: POST `/api/broker/credentials`
4. Create bot: POST `/api/bot/create`
5. Monitor logs: Check trading activity in logs

## Performance Notes

- **First trade cycle:** Waits up to 30 seconds for MT5 readiness
- **Connection caching:** Bot reuses MT5 connection (improves speed)
- **Symbol support:** Validated against PXBT broker on bot creation
- **Order execution:** Uses MT5 SDK for reliable order placement

## Security

- Credentials stored in database (encrypted)
- Server names normalized (no user input trusting)
- API key required for endpoints
- Account number validated against credential entry
- Private broker servers not exposed to UI

## Next Steps

1. ✅ Configure PXBT credentials in .env
2. ✅ Start backend service
3. ✅ Verify PXBT MT5 Terminal is installed and running
4. ✅ Integrate PXBT broker account via API
5. ✅ Create trading bot with PXBT credential
6. ✅ Monitor first trades in MT5 terminal
7. ✅ Adjust risk parameters if needed

## Support

For issues with PXBT trading:
- Check backend logs: `multi_broker_backend_updated.py`
- Verify MT5 terminal is running and logged in
- Test connectivity: `test_pxbt_config.py`
- Review demo before using live account

---

**Status:** ✅ PXBT integration complete and tested
**Last verified:** March 25, 2026
