# Bot Monitoring & Auto-Withdrawal System Guide

## Overview

The Zwesta Trading Platform now includes a comprehensive bot monitoring and automatic profit withdrawal system. This guide explains how to use these features.

## Features

### 1. **Real-Time Bot Monitoring**
- Health status tracking
- Performance metrics
- Error tracking and logging
- Uptime monitoring
- Auto-restart capabilities

### 2. **Automatic Profit Withdrawal**
- Set profit targets (min: $10, max: $50,000)
- Automatic withdrawal when target is reached
- Fee calculation (2% deducted)
- Withdrawal history tracking
- One withdrawal per 24-hour period

## API Endpoints

### 1. Get Bot Health Status

**Endpoint:** `GET /api/bot/<bot_id>/health`

**Authentication:** Required (API Key)

**Response:**
```json
{
  "success": true,
  "health": {
    "bot_id": "bot_123",
    "is_running": true,
    "strategy": "scalping",
    "daily_profit": 150.25,
    "total_profit": 1250.75,
    "status": "active",
    "last_heartbeat": "2024-01-15T14:32:00",
    "uptime_seconds": 86400,
    "health_checks": 2880,
    "error_count": 0,
    "last_error": null,
    "auto_restarts": 0
  }
}
```

**Example cURL:**
```bash
curl -X GET http://localhost:9000/api/bot/bot_123/health \
  -H "X-API-Key: your_api_key_here"
```

---

### 2. Set Auto-Withdrawal Target

**Endpoint:** `POST /api/bot/<bot_id>/auto-withdrawal`

**Authentication:** Required (API Key)

**Request Body:**
```json
{
  "user_id": "user_456",
  "target_profit": 500.00
}
```

**Constraints:**
- Minimum target: $10
- Maximum target: $50,000
- User must be the bot owner

**Response:**
```json
{
  "success": true,
  "setting_id": "setting_789",
  "bot_id": "bot_123",
  "target_profit": 500.00,
  "message": "Auto-withdrawal will trigger when bot reaches $500 profit"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9000/api/bot/bot_123/auto-withdrawal \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_456",
    "target_profit": 500.00
  }'
```

---

### 3. Get Auto-Withdrawal Status

**Endpoint:** `GET /api/bot/<bot_id>/auto-withdrawal-status`

**Authentication:** Required (API Key)

**Response:**
```json
{
  "success": true,
  "bot_id": "bot_123",
  "current_setting": {
    "setting_id": "setting_789",
    "target_profit": 500.00,
    "is_active": 1,
    "created_at": "2024-01-15T10:00:00"
  },
  "history": [
    {
      "withdrawal_id": "wd_001",
      "triggered_profit": 500.25,
      "withdrawal_amount": 500.25,
      "net_amount": 490.25,
      "status": "completed",
      "created_at": "2024-01-15T14:00:00",
      "completed_at": "2024-01-15T14:05:00"
    }
  ],
  "total_auto_withdrawals": 1,
  "total_amount_withdrawn": 490.25
}
```

**Example cURL:**
```bash
curl -X GET http://localhost:9000/api/bot/bot_123/auto-withdrawal-status \
  -H "X-API-Key: your_api_key_here"
```

---

### 4. Disable Auto-Withdrawal

**Endpoint:** `POST /api/bot/<bot_id>/disable-auto-withdrawal`

**Authentication:** Required (API Key)

**Response:**
```json
{
  "success": true,
  "message": "Auto-withdrawal disabled for bot bot_123"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9000/api/bot/bot_123/disable-auto-withdrawal \
  -H "X-API-Key: your_api_key_here"
```

---

## Development & Integration

### Setting Up in Your Application

#### Flutter/Mobile Integration

```dart
import 'package:http/http.dart' as http;

class BotMonitoringService {
  final String apiKey;
  final String baseUrl;

  BotMonitoringService({
    required this.apiKey,
    required this.baseUrl,
  });

  Future<BotHealth> getBotHealth(String botId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/bot/$botId/health'),
      headers: {'X-API-Key': apiKey},
    );

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return BotHealth.fromJson(json['health']);
    }
    throw Exception('Failed to get bot health');
  }

  Future<void> setAutoWithdrawal({
    required String botId,
    required String userId,
    required double targetProfit,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/bot/$botId/auto-withdrawal'),
      headers: {
        'X-API-Key': apiKey,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'user_id': userId,
        'target_profit': targetProfit,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to set auto-withdrawal');
    }
  }

  Future<AutoWithdrawalStatus> getWithdrawalStatus(String botId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/bot/$botId/auto-withdrawal-status'),
      headers: {'X-API-Key': apiKey},
    );

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body);
      return AutoWithdrawalStatus.fromJson(json);
    }
    throw Exception('Failed to get withdrawal status');
  }
}
```

#### Python Client

```python
import requests
import json

class BotMonitoringClient:
    def __init__(self, api_key, base_url='http://localhost:9000'):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {'X-API-Key': api_key}

    def get_bot_health(self, bot_id):
        """Get bot health status"""
        response = requests.get(
            f'{self.base_url}/api/bot/{bot_id}/health',
            headers=self.headers
        )
        return response.json()

    def set_auto_withdrawal(self, bot_id, user_id, target_profit):
        """Set auto-withdrawal target"""
        response = requests.post(
            f'{self.base_url}/api/bot/{bot_id}/auto-withdrawal',
            headers={**self.headers, 'Content-Type': 'application/json'},
            json={
                'user_id': user_id,
                'target_profit': target_profit
            }
        )
        return response.json()

    def get_withdrawal_status(self, bot_id):
        """Get withdrawal status and history"""
        response = requests.get(
            f'{self.base_url}/api/bot/{bot_id}/auto-withdrawal-status',
            headers=self.headers
        )
        return response.json()

    def disable_auto_withdrawal(self, bot_id):
        """Disable auto-withdrawal"""
        response = requests.post(
            f'{self.base_url}/api/bot/{bot_id}/disable-auto-withdrawal',
            headers=self.headers
        )
        return response.json()

# Usage
client = BotMonitoringClient(api_key='your_api_key_here')

# Get bot health
health = client.get_bot_health('bot_123')
print(f"Bot Status: {health['health']['status']}")

# Set auto-withdrawal for $500 profit
result = client.set_auto_withdrawal('bot_123', 'user_456', 500.00)
print(f"Auto-withdrawal set: {result['message']}")

# Check withdrawal status
status = client.get_withdrawal_status('bot_123')
print(f"Total withdrawn: ${status['total_amount_withdrawn']}")
```

---

## Database Schema

### bot_monitoring Table
```sql
CREATE TABLE bot_monitoring (
    monitoring_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    last_heartbeat TEXT,
    uptime_seconds INTEGER DEFAULT 0,
    health_check_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_time TEXT,
    auto_restart_count INTEGER DEFAULT 0,
    created_at TEXT
)
```

### auto_withdrawal_settings Table
```sql
CREATE TABLE auto_withdrawal_settings (
    setting_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    target_profit REAL NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    withdrawal_method TEXT DEFAULT 'auto',
    created_at TEXT,
    updated_at TEXT
)
```

### auto_withdrawal_history Table
```sql
CREATE TABLE auto_withdrawal_history (
    withdrawal_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    triggered_profit REAL NOT NULL,
    withdrawal_amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    net_amount REAL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    completed_at TEXT
)
```

---

## Monitoring System

### Background Monitoring Thread

The system runs a background thread that:
1. **Checks every 30 seconds** for bots reaching profit targets
2. **Verifies withdrawal conditions:**
   - Auto-withdrawal setting is active
   - Bot profit >= target profit
   - No withdrawal in last 24 hours
3. **Executes withdrawal:**
   - Creates withdrawal record
   - Calculates 2% fee
   - Resets bot profit counters
   - Updates completion timestamp

### Thread Safety

- Uses SQLite's built-in thread safety
- Daemon thread (stops when app stops)
- Thread-safe global variables
- Error handling and logging

---

## Configuration

### Environment Variables

```bash
# API Security
API_KEY=your_generated_api_key_here

# Trading Environment
TRADING_ENV=DEMO  # or LIVE

# MT5 Configuration
MT5_ACCOUNT=104017418
MT5_PASSWORD=*6RjhRvH
MT5_SERVER=MetaQuotes-Demo
MT5_PATH=C:\Program Files\XM Global MT5
```

---

## Performance & Monitoring

### Withdrawal Frequency Limits
- **Maximum:** 1 withdrawal per 24 hours per bot
- **Purpose:** Prevent excessive fee accumulation
- **Override:** Contact support for emergency withdrawal

### Monitoring Intervals
- **Health check:** Every 30 seconds
- **Database logs:** Continuous
- **Error tracking:** Real-time

### Resource Usage
- **CPU:** Minimal (checks only when needed)
- **Memory:** ~5MB per monitored bot
- **Database:** ~1KB per transaction

---

## Error Handling

### Common Errors

**Error 404: Bot not found**
```json
{
  "success": false,
  "error": "Bot bot_123 not found"
}
```
**Solution:** Verify bot_id is correct

**Error 400: Invalid target profit**
```json
{
  "success": false,
  "error": "Minimum profit target is $10"
}
```
**Solution:** Set target between $10 and $50,000

**Error 500: Server error**
```json
{
  "success": false,
  "error": "Database connection failed"
}
```
**Solution:** Check server logs for details

---

## Best Practices

### 1. **Set Realistic Profit Targets**
- Based on bot's historical performance
- Account for market conditions
- Consider withdrawal fees (2%)

### 2. **Monitor Regularly**
- Check bot health daily
- Review withdrawal history weekly
- Monitor error logs

### 3. **manage Multiple Bots**
- Set different targets per strategy
- Track performance separately
- Adjust targets based on results

### 4. **Security**
- Keep API key confidential
- Use HTTPS in production
- Rotate API keys monthly
- Monitor API usage logs

---

## Troubleshooting

### Bot Not Reaching Target
1. Check bot is enabled: `GET /api/bot/<bot_id>/health`
2. Verify strategy parameters
3. Check market conditions
4. Review bot error logs

### Auto-Withdrawal Not Triggering
1. Verify setting is active
2. Check target profit amount
3. Ensure bot profit > target (not equal)
4. Review monitoring thread logs

### High Error Rate
1. Check database connection
2. Verify API key is valid
3. Check server resources (CPU, memory)
4. Review error logs

---

## Testing

### Test Auto-Withdrawal Manually

```bash
# 1. Get bot health
curl http://localhost:9000/api/bot/bot_123/health \
  -H "X-API-Key: test_key"

# 2. Set low profit target for testing
curl -X POST http://localhost:9000/api/bot/bot_123/auto-withdrawal \
  -H "X-API-Key: test_key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_456", "target_profit": 1.00}'

# 3. Simulate profit (in code/database)
# UPDATE active_bots SET totalProfit = 2.00 WHERE botId = 'bot_123'

# 4. Wait 30 seconds for monitoring to trigger

# 5. Check withdrawal status
curl http://localhost:9000/api/bot/bot_123/auto-withdrawal-status \
  -H "X-API-Key: test_key"
```

---

## Support & Updates

For issues, suggestions, or updates:
- Check logs: `multi_broker_backend.log`
- Review error messages in response
- Contact development team

---

**Last Updated:** January 2024
**Version:** 1.0
