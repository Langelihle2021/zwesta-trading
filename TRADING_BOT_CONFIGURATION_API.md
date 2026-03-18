# Trading Bot Configuration API Reference

## Overview
Complete API reference for configuring and managing trading bots with dual-mode support (interval-based and signal-driven).

---

## API Endpoints

### 1. Configure Trading Mode
**Endpoint:** `POST /api/bot/{bot_id}/configure-trading-mode`
**Authentication:** Required (Bearer token)
**Purpose:** Switch bot between signal-driven and interval modes

**Request Body:**
```json
{
  "tradingMode": "signal-driven",  // or "interval"
  "signalThreshold": 70,            // 0-100 (only for signal-driven)
  "pollInterval": 15,               // seconds (only for signal-driven)
  "tradingInterval": 600            // seconds (applies to both modes)
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Trading mode configured successfully",
  "botId": "bot123",
  "configuration": {
    "tradingMode": "signal-driven",
    "signalThreshold": 70,
    "pollInterval": 15,
    "tradingInterval": 600
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Invalid signal threshold. Must be between 0 and 100"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9000/api/bot/bot123/configure-trading-mode \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tradingMode": "signal-driven",
    "signalThreshold": 70,
    "pollInterval": 15,
    "tradingInterval": 600
  }'
```

---

### 2. Get Trading Mode Configuration
**Endpoint:** `GET /api/bot/{bot_id}/trading-mode`
**Authentication:** Required (Bearer token)
**Purpose:** Retrieve current trading mode configuration

**Response:**
```json
{
  "success": true,
  "botId": "bot123",
  "botName": "My Signal Bot",
  "configuration": {
    "tradingMode": "signal-driven",
    "signalThreshold": 70,
    "pollInterval": 15,
    "tradingInterval": 600
  },
  "stats": {
    "signalsChecked": 1245,
    "signalsExecuted": 89,
    "averageSignalStrength": 62.5,
    "lastCheckTime": "2024-03-18T10:35:42Z"
  }
}
```

**Example cURL:**
```bash
curl -X GET http://localhost:9000/api/bot/bot123/trading-mode \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 3. Get Bot Performance
**Endpoint:** `GET /api/bot/{bot_id}/performance`
**Authentication:** Required (Bearer token)
**Purpose:** Get detailed performance metrics

**Response:**
```json
{
  "success": true,
  "botId": "bot123",
  "botName": "My Trading Bot",
  "brokerType": "MT5",
  "currentBalance": 5234.56,
  "initialBalance": 5000.00,
  "trades": {
    "total": 45,
    "winning": 31,
    "losing": 14,
    "winRate": 68.9
  },
  "profitLoss": {
    "totalProfit": 325.40,
    "totalLoss": 91.16,
    "netProfit": 234.24,
    "roi": 4.68,
    "profitFactor": 3.57
  },
  "drawdown": {
    "maxDrawdown": 127.50,
    "peakProfit": 450.75,
    "currentDrawdown": 216.35
  },
  "tradingMode": "signal-driven",
  "symbol": "EURUSDm",
  "status": "Running"
}
```

---

### 4. Get Detailed Trade History
**Endpoint:** `GET /api/bot/{bot_id}/trades-detailed`
**Authentication:** Required (Bearer token)
**Query Parameters:**
- `limit` (default: 50) - Max trades to return
- `offset` (default: 0) - Pagination offset
- `symbol` (optional) - Filter by symbol
- `status` (default: all) - 'open', 'closed', 'all'

**Example:**
```bash
curl -X GET "http://localhost:9000/api/bot/bot123/trades-detailed?limit=50&offset=0&status=closed" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "botId": "bot123",
  "trades": [
    {
      "id": "trade_456",
      "symbol": "EURUSDm",
      "type": "BUY",
      "volume": 0.5,
      "entry_price": 1.0850,
      "exit_price": 1.0875,
      "profit": 12.50,
      "profit_pct": 2.3,
      "status": "closed",
      "created_at": "2024-03-18T10:05:30Z",
      "closed_at": "2024-03-18T10:08:45Z"
    }
  ],
  "pagination": {
    "total": 145,
    "offset": 0,
    "limit": 50,
    "hasMore": true
  }
}
```

---

### 5. Get Commission Data
**Endpoint:** `GET /api/bot/{bot_id}/commissions`
**Authentication:** Required (Bearer token)
**Purpose:** Get commission earnings and withdrawal history

**Response:**
```json
{
  "success": true,
  "botId": "bot123",
  "totalCommissions": 485.50,
  "commissionHistory": [
    {
      "date": "2024-03-18",
      "daily_commission": 45.50,
      "trades": 12
    },
    {
      "date": "2024-03-17",
      "daily_commission": 38.75,
      "trades": 10
    }
  ],
  "withdrawals": [
    {
      "id": "wd_001",
      "amount": 100.00,
      "status": "completed",
      "bank_account": "****1234",
      "createdAt": "2024-03-17T14:30:00Z"
    },
    {
      "id": "wd_002",
      "amount": 50.00,
      "status": "pending",
      "bank_account": "****5678",
      "createdAt": "2024-03-18T09:15:00Z"
    }
  ],
  "pendingWithdrawal": 50.00,
  "completedWithdrawal": 250.00
}
```

---

### 6. Get Dashboard Summary (All Bots)
**Endpoint:** `GET /api/dashboard/bots-summary`
**Authentication:** Required (Bearer token)
**Purpose:** Get summary of all bots for dashboard

**Response:**
```json
{
  "success": true,
  "botsCount": 3,
  "botsRunning": 2,
  "totalBalance": 15234.50,
  "totalProfit": 1234.75,
  "bots": [
    {
      "botId": "bot123",
      "botName": "Aggressive Bot",
      "broker": {
        "type": "MT5",
        "accountNumber": "123456"
      },
      "balance": 5234.56,
      "profit": 234.56,
      "trades": 45,
      "winRate": 68.9,
      "status": "Running",
      "tradingMode": "signal-driven",
      "createdAt": "2024-03-15T10:30:00Z"
    },
    {
      "botId": "bot124",
      "botName": "Conservative Bot",
      "broker": {
        "type": "MT5",
        "accountNumber": "234567"
      },
      "balance": 10000.00,
      "profit": 1000.19,
      "trades": 120,
      "winRate": 71.5,
      "status": "Running",
      "tradingMode": "interval",
      "createdAt": "2024-03-10T15:45:00Z"
    }
  ],
  "timestamp": "2024-03-18T10:35:42Z"
}
```

---

## Configuration Examples

### Example 1: Ultra-Conservative Signal Trading
```json
POST /api/bot/bot123/configure-trading-mode

{
  "tradingMode": "signal-driven",
  "signalThreshold": 85,      // Only excellent signals
  "pollInterval": 30,         // Check every 30 seconds
  "tradingInterval": 1800     // Max 30 minutes between trades
}
```

**Expected:** 2-4 trades/day, high accuracy, low frequency

---

### Example 2: Balanced Signal Trading
```json
{
  "tradingMode": "signal-driven",
  "signalThreshold": 70,      // Strong signals
  "pollInterval": 15,         // Check every 15 seconds
  "tradingInterval": 900      // Max 15 minutes between trades
}
```

**Expected:** 10-15 trades/day, balanced risk/reward

---

### Example 3: Aggressive Signal Trading
```json
{
  "tradingMode": "signal-driven",
  "signalThreshold": 60,      // Medium-strong signals
  "pollInterval": 10,         // Check every 10 seconds
  "tradingInterval": 300      // Max 5 minutes between trades
}
```

**Expected:** 20-30+ trades/day, higher volatility

---

### Example 4: Traditional Interval Trading
```json
{
  "tradingMode": "interval",
  "tradingInterval": 300      // Trade every 5 minutes
}
```

**Expected:** Fixed schedule, 288 trades/day (24hrs * 3600s / 300s)

---

## Signal Strength Calculation

### How Signal Strength is Calculated

**Final Score Formula:**
```
signal_strength = (base_indicator_score × win_rate_weight) ± volatility_adjustment

Where:
- base_indicator_score: 85 (Strong Buy) to 20 (Strong Sell)
- win_rate_weight: Historical win rate as confidence factor (0.5 to 1.5)
- volatility_adjustment: +10% to -10% based on current market volatility
```

### Indicator Scoring
```
Strong Buy:    85 points
Buy:           65 points
Hold:          40 points
Sell:          30 points
Strong Sell:   20 points
```

### Volatility Impact
```
High Volatility (>2%):      +10 points
Normal Volatility (0.5-2%):  0 points
Low Volatility (<0.5%):     -10 points
```

### Sample Calculations

**Example 1: Strong Buy + Normal Volatility + 70% Win Rate**
```
Signal = (85 × 1.2) ± 0
       = 102 (capped at 100)
       = 100 points → EXECUTE (above 70 threshold)
```

**Example 2: Hold + High Volatility + 50% Win Rate**
```
Signal = (40 × 1.0) + 10
       = 50 points → SKIP (below 70 threshold)
```

**Example 3: Buy + Low Volatility + 75% Win Rate**
```
Signal = (65 × 1.25) - 10
       = 81.25 - 10
       = 71.25 points → EXECUTE (above 70 threshold)
```

---

## Status Codes & Errors

| Code | Error | Cause | Fix |
|------|-------|-------|-----|
| 200 | Success | Operation completed | N/A |
| 400 | Invalid threshold | Threshold not 0-100 | Use value between 0-100 |
| 400 | Invalid poll interval | Poll interval < 5 | Use interval ≥ 5 seconds |
| 401 | Unauthorized | No valid token | Provide valid Bearer token |
| 404 | Bot not found | Bot ID doesn't exist | Check bot ID is correct |
| 500 | Server error | Backend failure | Retry or contact support |

---

## Python Client Example

```python
import requests
import json

class TradingBotClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {'Authorization': f'Bearer {token}'}
    
    def configure_trading_mode(self, bot_id, config):
        """Configure trading mode for a bot"""
        response = requests.post(
            f'{self.base_url}/api/bot/{bot_id}/configure-trading-mode',
            headers=self.headers,
            json=config
        )
        return response.json()
    
    def get_performance(self, bot_id):
        """Get bot performance metrics"""
        response = requests.get(
            f'{self.base_url}/api/bot/{bot_id}/performance',
            headers=self.headers
        )
        return response.json()
    
    def get_dashboard_summary(self):
        """Get all bots summary"""
        response = requests.get(
            f'{self.base_url}/api/dashboard/bots-summary',
            headers=self.headers
        )
        return response.json()

# Usage
client = TradingBotClient('http://localhost:9000', 'YOUR_TOKEN')

# Configure bot to signal-driven
config = {
    'tradingMode': 'signal-driven',
    'signalThreshold': 70,
    'pollInterval': 15,
    'tradingInterval': 600
}
result = client.configure_trading_mode('bot123', config)
print(result)

# Get performance
perf = client.get_performance('bot123')
print(f"Current Balance: ${perf['currentBalance']}")
print(f"Win Rate: {perf['trades']['winRate']}%")

# Get all bots
dashboard = client.get_dashboard_summary()
print(f"Total Balance: ${dashboard['totalBalance']}")
```

---

## JavaScript/Node.js Client Example

```javascript
class TradingBotAPI {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  async configureTradingMode(botId, config) {
    const response = await fetch(
      `${this.baseUrl}/api/bot/${botId}/configure-trading-mode`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
      }
    );
    return response.json();
  }

  async getPerformance(botId) {
    const response = await fetch(
      `${this.baseUrl}/api/bot/${botId}/performance`,
      {
        headers: { 'Authorization': `Bearer ${this.token}` }
      }
    );
    return response.json();
  }

  async getDashboardSummary() {
    const response = await fetch(
      `${this.baseUrl}/api/dashboard/bots-summary`,
      {
        headers: { 'Authorization': `Bearer ${this.token}` }
      }
    );
    return response.json();
  }
}

// Usage
const api = new TradingBotAPI('http://localhost:9000', 'YOUR_TOKEN');

// Switch to signal-driven
await api.configureTradingMode('bot123', {
  tradingMode: 'signal-driven',
  signalThreshold: 70,
  pollInterval: 15,
  tradingInterval: 600
});

// Get dashboard
const dashboard = await api.getDashboardSummary();
console.log(`Total Balance: $${dashboard.totalBalance}`);
```

---

## Rate Limiting

- Dashboard calls: **100 requests/minute**
- Individual bot calls: **50 requests/minute**
- Performance queries: **200 requests/minute**

---

## Best Practices

## ✅ DO
1. Cache dashboard data (refresh every 30 seconds)
2. Use pagination for trade history (limit 50)
3. Check bot status before configuration
4. Validate thresholds before sending
5. Handle network timeouts gracefully

## ❌ DON'T
1. Poll performance every second (too much load)
2. Change config while bot is trading
3. Use invalid token formats
4. Send unvalidated threshold values
5. Ignore error responses

---

## Troubleshooting

### "Invalid signal threshold"
**Cause:** Threshold outside 0-100 range
**Fix:** Ensure signalThreshold is between 0 and 100

### "Bot not found"
**Cause:** Bot ID doesn't exist or isn't running
**Fix:** Verify bot exists via `/api/dashboard/bots-summary`

### "Unauthorized"
**Cause:** Invalid or expired token
**Fix:** Get fresh token and retry

### "Connection timeout"
**Cause:** Server unreachable
**Fix:** Check server is running: `http://localhost:9000/health`
