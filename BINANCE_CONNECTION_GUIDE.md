# Binance Connection Test & Demo Bot Creation Guide

## Quick Summary
This guide helps you:
1. ✅ Test your Binance API connection
2. ✅ Create a demo trading bot
3. ✅ Start automated trading on Binance

---

## Prerequisites

### 1. Binance API Credentials
You need from your HMAC dashboard:
- **API Key**: `JBPMO44roltRZjQhxM0YqZLCgpYd7dHiddZru8GHJzJI6AveL3yv3M95imfFZT3b`
- **API Secret**: Get from your HMAC app (Settings → API Keys)

### 2. Backend Running
Make sure your Flask backend is running:
```bash
python multi_broker_backend_updated.py
# Should start on http://localhost:9000
```

### 3. Session Token
Get from your login response - defaults to: `debug_token_49b6b05ad32648759f26f6ac37eebcef`

---

## Method 1: Python Script (Recommended)

### Setup
```bash
# Navigate to your project
cd c:\zwesta-trader\Zwesta Flutter App

# Update credentials in the script
# Edit: test_binance_connection.py
# Line 22: Change BINANCE_API_SECRET to your actual secret
```

### Run Test
```bash
python test_binance_connection.py
```

### Expected Output
```
======================================================================
🚀 ZWESTA TRADER - BINANCE BOT CREATION FLOW
======================================================================

🔌 STEP 1: Testing Binance Connection
======================================================================

✅ CONNECTION SUCCESSFUL!

{
  "success": true,
  "message": "Successfully connected to Binance account spot",
  "credential_id": "550e8400-e29b-41d4-a716-446655440000",
  "broker": "Binance",
  "account_number": "spot",
  "balance": 1234.56,
  "currency": "USDT",
  "is_live": false,
  "status": "CONNECTED"
}

💾 Credential ID: 550e8400-e29b-41d4-a716-446655440000
💰 Account Balance: $1234.56

🤖 STEP 2: Creating Demo Trading Bot
======================================================================

✅ BOT CREATED SUCCESSFULLY!

{
  "success": true,
  "botId": "demo_bot_1234567890",
  "accountId": "Binance_spot",
  "broker": "Binance",
  "balance": 1234.56,
  "mode": "demo",
  "status": "STARTING"
}

🎯 Bot Details:
   Bot ID: demo_bot_1234567890
   Account Balance: $1234.56
   Status: STARTING
   Mode: demo
```

---

## Method 2: Curl Commands (For Testing)

### Step 1: Test Connection
```bash
curl -X POST http://localhost:9000/api/broker/test-connection \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef" \
  -d '{
    "broker": "Binance",
    "api_key": "JBPMO44roltRZjQhxM0YqZLCgpYd7dHiddZru8GHJzJI6AveL3yv3M95imfFZT3b",
    "api_secret": "your_api_secret_here",
    "is_live": false,
    "market": "spot"
  }'
```

### Step 2: Create Bot
Replace `CREDENTIAL_ID_HERE` with the `credential_id` from Step 1:

```bash
curl -X POST http://localhost:9000/api/bot/create \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef" \
  -d '{
    "credentialId": "CREDENTIAL_ID_HERE",
    "botId": "my_first_bot",
    "name": "Demo Trading Bot",
    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "strategy": "Momentum Trading",
    "enabled": true,
    "riskPerTrade": 15,
    "maxDailyLoss": 50,
    "profitLock": 40,
    "basePositionSize": 1.0,
    "displayCurrency": "USDT"
  }'
```

---

## Bot Configuration Explained

### Symbols
Top-performing Binance pairs (all-time best performers):
- **BTCUSDT** - Bitcoin (6.8% edge)
- **ETHUSDT** - Ethereum (6.2% edge)
- **SOLUSDT** - Solana (7.4% momentum)
- **BNBUSDT** - Binance Coin (5.3% edge)

### Strategies
- **Momentum Trading** ← Recommended for crypto (current selection)
- **Trend Following** - Good for longer holdings
- **Mean Reversion** - Scalping-focused

### Risk Settings
| Setting | Value | Meaning |
|---------|-------|---------|
| riskPerTrade | 15 | Risk 15% of account per trade |
| maxDailyLoss | 50 | Stop trading if lose $50 today |
| profitLock | 40 | Lock in once you profit $40 daily |
| basePositionSize | 1.0 | Standard position |

### Mode Options
- **DEMO** (`is_live: false`) - Uses testnet, no real money
- **LIVE** (`is_live: true`) - Real trading on live account

---

## Demo Mode vs Live Mode

### DEMO MODE (Recommended for Testing)
```json
{
  "is_live": false,
  "market": "spot"
}
```
- ✅ Uses Binance testnet
- ✅ No real money spent
- ✅ Perfect for testing strategy
- ✅ May have limited liquidity
- ✅ Execution may not be realistic

### LIVE MODE (Real Trading)
```json
{
  "is_live": true,
  "market": "spot"
}
```
- ⚠️ Uses real Binance account
- ⚠️ Real money will be spent
- ⚠️ Real market execution
- ✅ Realistic market conditions
- ❌ RISK OF LOSS

---

## Troubleshooting

### Error: "Failed to authenticate with Binance"
**Causes:**
- API Key is wrong
- API Secret is wrong
- API Key restrictions (IP whitelist)
- Account not enabled for API trading

**Fix:**
1. Go to Binance HMAC dashboard
2. Click your API application
3. Copy exact API Key and Secret
4. Check "Enable trading" checkbox
5. Remove IP restrictions or add your IP

### Error: "Broker credential not found"
**Cause:** Connection test wasn't run first

**Fix:** 
1. Run `/api/broker/test-connection` first
2. Copy the `credential_id` from response
3. Use that ID in bot creation

### Error: "X-Session-Token required"
**Cause:** Missing session token in headers

**Fix:**
1. Login to get session token: `POST /api/auth/login`
2. Add to headers: `"X-Session-Token": "<your_token>"`

### Bot created but not trading
**Causes:**
- Backend not running properly
- MT5 not initialized (for MT5 brokers)
- No market data available

**Fix:**
1. Check backend console logs
2. Verify database is running
3. Check bot status: `GET /api/bot/{botId}/status`

---

## Monitoring Your Bot

### Get Bot Status
```bash
curl -X GET http://localhost:9000/api/bot/demo_bot_1234567890/status \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef"
```

### Response includes:
```json
{
  "botId": "demo_bot_1234567890",
  "status": "ACTIVE",
  "totalTrades": 42,
  "winningTrades": 28,
  "totalProfit": 1234.50,
  "dailyProfit": 234.50,
  "balance": 11234.50
}
```

### Get Bot Trade History
```bash
curl -X GET http://localhost:9000/api/bot/demo_bot_1234567890/trades \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef"
```

---

## Common Operations

### Stop a Bot
```bash
curl -X POST http://localhost:9000/api/bot/demo_bot_1234567890/stop \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef"
```

### Pause a Bot (Stop trading but keep running)
```bash
curl -X POST http://localhost:9000/api/bot/demo_bot_1234567890/pause \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef"
```

### List All Bots
```bash
curl -X GET http://localhost:9000/api/bots \
  -H "X-Session-Token: debug_token_49b6b05ad32648759f26f6ac37eebcef"
```

---

## API Endpoints Reference

### Broker Management
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/broker/test-connection` | Test broker credentials |
| GET | `/api/broker/balance` | Get account balance |
| GET | `/api/commodities/list` | Get available trading symbols |

### Bot Management
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/bot/create` | Create new bot |
| POST | `/api/bot/quick-create` | Quick bot (Binance only) |
| GET | `/api/bot/{botId}/status` | Get bot status |
| GET | `/api/bot/{botId}/trades` | Get trade history |
| POST | `/api/bot/{botId}/stop` | Stop bot |
| POST | `/api/bot/{botId}/pause` | Pause trading |
| DELETE | `/api/bot/{botId}` | Delete bot |

---

## Next Steps

1. ✅ Test connection with your API credentials
2. ✅ Verify account balance displays correctly
3. ✅ Create your first demo trading bot
4. ✅ Monitor trading activity on the dashboard
5. ✅ Once confident, create a LIVE bot with real money

---

## Support

If you encounter issues:
1. Check backend logs: `multi_broker_backend_updated.py` console output
2. Verify database is running (SQLite should auto-create)
3. Check Binance API status at: https://www.binance.com/en/support/notices
4. Review error messages in API responses

Good luck with your trading! 🚀
