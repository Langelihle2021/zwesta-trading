# Bot Monitoring & Auto-Withdrawal - Quick Reference

## Quick Start

### 1️⃣ Set Auto-Withdrawal Target
```bash
POST /api/bot/{bot_id}/auto-withdrawal
Body: {
  "user_id": "user_456",
  "target_profit": 500.00
}
```
✅ Bot will auto-withdraw when profit reaches $500

### 2️⃣ Check Bot Health
```bash
GET /api/bot/{bot_id}/health
```
Returns: Status, uptime, errors, profit, strategy

### 3️⃣ View Withdrawal History
```bash
GET /api/bot/{bot_id}/auto-withdrawal-status
```
Returns: Current settings, withdrawal history, total withdrawn

### 4️⃣ Disable Auto-Withdrawal
```bash
POST /api/bot/{bot_id}/disable-auto-withdrawal
```

## Limits & Rules

| Rule | Value |
|------|-------|
| Min Target | $10 |
| Max Target | $50,000 |
| Fee | 2% |
| Frequency | 1 per 24 hours |
| Check Interval | Every 30 seconds |

## Response Examples

### ✅ Success
```json
{
  "success": true,
  "health": {
    "status": "active",
    "daily_profit": 150.25,
    "total_profit": 1250.75,
    "uptime_seconds": 86400,
    "error_count": 0
  }
}
```

### ❌ Error
```json
{
  "success": false,
  "error": "Minimum profit target is $10"
}
```

## Common Use Cases

### Track Multiple Bots
```bash
# Bot 1: Scalping, $500 target
POST /api/bot/bot_1/auto-withdrawal
{"user_id": "u1", "target_profit": 500}

# Bot 2: Swing, $1000 target
POST /api/bot/bot_2/auto-withdrawal
{"user_id": "u2", "target_profit": 1000}

# Bot 3: Long-term, $2000 target
POST /api/bot/bot_3/auto-withdrawal
{"user_id": "u3", "target_profit": 2000}
```

### Monitor Bot Performance
```bash
# Daily health check
GET /api/bot/bot_123/health

# Weekly withdrawal review
GET /api/bot/bot_123/auto-withdrawal-status

# Monthly report
SELECT COUNT(*), SUM(net_amount) FROM auto_withdrawal_history
WHERE bot_id = 'bot_123' AND created_at > date_sub(now(), interval 30 day)
```

## Python Example
```python
import requests

def set_auto_withdrawal(bot_id, user_id, target):
    response = requests.post(
        f'http://localhost:9000/api/bot/{bot_id}/auto-withdrawal',
        headers={'X-API-Key': 'your_api_key'},
        json={'user_id': user_id, 'target_profit': target}
    )
    return response.json()

# Usage
set_auto_withdrawal('bot_123', 'user_456', 500)
```

## Dart/Flutter Example
```dart
Future<void> setAutoWithdrawal() async {
  final response = await http.post(
    Uri.parse('http://localhost:9000/api/bot/bot_123/auto-withdrawal'),
    headers: {'X-API-Key': 'your_api_key'},
    body: jsonEncode({
      'user_id': 'user_456',
      'target_profit': 500.0,
    }),
  );
  
  if (response.statusCode == 200) {
    print('✅ Auto-withdrawal set!');
  }
}
```

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | ✅ Success |
| 400 | ❌ Bad request (invalid data) |
| 404 | ❌ Bot not found |
| 500 | ❌ Server error |

## Fee Calculation

| Profit | Fee (2%) | Net Received |
|--------|----------|--------------|
| $100 | $2 | $98 |
| $500 | $10 | $490 |
| $1,000 | $20 | $980 |
| $5,000 | $100 | $4,900 |

## Monitoring Thread

The backend runs a monitoring thread that:
- ✅ Checks profit targets every 30 seconds
- ✅ Auto-executes withdrawals when target is reached
- ✅ Logs all actions to database
- ✅ Handles errors gracefully

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Bot not found | Verify bot_id is correct |
| Target too low | Minimum is $10 |
| Not triggering | Wait 30 seconds, margin may not be counted |
| High fee | Fee is 2%, plan accordingly |
| API error | Check API key in headers |

## Log Files

Location: `multi_broker_backend.log`

Look for:
- `Auto-withdrawal set for`
- `Profit target reached for`
- `Auto-withdrawal executed`
- Error messages

## Testing

```bash
# Quick test with minimum target
curl -X POST http://localhost:9000/api/bot/bot_test/auto-withdrawal \
  -H "X-API-Key: test" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "target_profit": 10.00}'

# Check status
curl http://localhost:9000/api/bot/bot_test/auto-withdrawal-status \
  -H "X-API-Key: test"
```

---
**Version:** 1.0 | **Updated:** January 2024
