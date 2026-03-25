# Profit Withdrawal API Reference

## Endpoints

### 1. Set Fixed Withdrawal Target
**Configure bot to withdraw at a specific profit level**

```
POST /api/bot/<bot_id>/auto-withdrawal
```

**Request Body:**
```json
{
  "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9",
  "withdrawal_mode": "fixed",
  "target_profit": 500
}
```

**Response (Success):**
```json
{
  "success": true,
  "setting_id": "550e8400-e29b-41d4-a716-446655440000",
  "bot_id": "ZWE1",
  "withdrawal_mode": "fixed",
  "message": "Fixed withdrawal set: Will withdraw when profit reaches $500"
}
```

**Parameters:**
- `user_id` (required) - Your user ID
- `withdrawal_mode` (required) - Must be "fixed"
- `target_profit` (required) - Target amount ($10-$50,000)

**Error Cases:**
- `target_profit < 10` → "Minimum profit target is $10"
- `target_profit > 50000` → "Maximum profit target is $50,000"

---

### 2. Configure Intelligent Withdrawal
**Let the robot intelligently decide when to withdraw**

```
POST /api/bot/<bot_id>/intelligent-withdrawal
```

**Request Body:**
```json
{
  "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9",
  "min_profit": 75,
  "max_profit": 500,
  "volatility_threshold": 0.02,
  "win_rate_min": 60,
  "trend_strength_min": 0.5,
  "time_between_withdrawals_hours": 24
}
```

**Response (Success):**
```json
{
  "success": true,
  "bot_id": "ZWE1",
  "mode": "intelligent",
  "parameters": {
    "min_profit": 75,
    "max_profit": 500,
    "volatility_threshold": "2.00%",
    "win_rate_min": "60%",
    "trend_strength_min": 0.5,
    "time_between_withdrawals": "24 hours"
  },
  "message": "Intelligent withdrawal activated. Robot will monitor conditions and withdraw when criteria met."
}
```

**Parameters (all optional, defaults shown):**
- `user_id` (required) - Your user ID
- `min_profit` (optional, default: 50) - Minimum profit threshold ($10+)
- `max_profit` (optional, default: 1000) - Maximum per withdrawal
- `volatility_threshold` (optional, default: 0.02) - Max market volatility (0-0.1)
- `win_rate_min` (optional, default: 60) - Minimum win rate % (40-100)
- `trend_strength_min` (optional, default: 0.5) - Min trend strength (0-1)
- `time_between_withdrawals_hours` (optional, default: 24) - Hours between withdrawals (1-720)

**Validation Rules:**
```
min_profit >= 10
max_profit >= min_profit
0 <= volatility_threshold <= 0.1
40 <= win_rate_min <= 100
0 <= trend_strength_min <= 1
1 <= time_between_withdrawals_hours <= 720
```

---

### 3. Get Withdrawal Status
**Check current settings and withdrawal history**

```
GET /api/bot/<bot_id>/auto-withdrawal-status
```

**Response:**
```json
{
  "success": true,
  "bot_id": "ZWE1",
  "current_setting": {
    "setting_id": "550e8400-e29b-41d4-a716-446655440000",
    "target_profit": 500,
    "is_active": true,
    "created_at": "2026-03-11T01:52:00Z"
  },
  "history": [
    {
      "withdrawal_id": "660e8401-e29b-41d4-a716-446655440001",
      "triggered_profit": 502.50,
      "withdrawal_amount": 502.50,
      "fee": 10.05,
      "net_amount": 492.45,
      "status": "completed",
      "created_at": "2026-03-11T01:30:00Z",
      "completed_at": "2026-03-11T01:30:05Z"
    },
    {
      "withdrawal_id": "770e8402-e29b-41d4-a716-446655440002",
      "triggered_profit": 475.80,
      "withdrawal_amount": 475.80,
      "fee": 9.52,
      "net_amount": 466.28,
      "status": "completed",
      "created_at": "2026-03-11T12:15:00Z",
      "completed_at": "2026-03-11T12:15:05Z"
    }
  ],
  "total_auto_withdrawals": 2,
  "total_amount_withdrawn": 958.73
}
```

**Response Fields:**
- `current_setting` - Active withdrawal configuration (null if none)
- `history` - Last 10 withdrawals
- `total_auto_withdrawals` - Total number of completed withdrawals
- `total_amount_withdrawn` - Total amount withdrawn (after fees)

---

### 4. Disable Automatic Withdrawal
**Stop automatic withdrawals for a bot**

```
POST /api/bot/<bot_id>/disable-auto-withdrawal
```

**Request Body:**
```json
{
  "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9"
}
```

**Response:**
```json
{
  "success": true,
  "bot_id": "ZWE1",
  "message": "Auto-withdrawal disabled for ZWE1"
}
```

**Note:** Withdrawal history is preserved. You can re-enable by posting to auto-withdrawal endpoint again.

---

## Important Details

### Fee Structure
- **Withdrawal Fee:** 2% (automatic)
- Applied to gross amount
- Example: $100 withdrawal → $98 net

### Intelligent Withdrawal Logic
```
Every 30 seconds, check:

IF profit >= min_profit AND 24hrs since last withdrawal:
  IF win_rate >= win_rate_min:
    IF volatility <= volatility_threshold:
      IF trend_strength >= trend_strength_min:
        → EXECUTE WITHDRAWAL
```

### Withdrawal Amount Calculation

**Fixed Mode:**
```
withdrawal_amount = total_profit
fee = withdrawal_amount × 0.02
net_amount = withdrawal_amount - fee
```

**Intelligent Mode:**
```
withdrawal_ratio = 0.5 + (trend_strength × 0.4)  // 50-90%
base_amount = profit × withdrawal_ratio
withdrawal_amount = MIN(base_amount, max_profit)
fee = withdrawal_amount × 0.02
net_amount = withdrawal_amount - fee
```

### After Withdrawal
- Bot's `totalProfit` resets to $0
- Bot's `dailyProfit` resets to $0
- Withdrawal history preserved
- Bot continues trading normally

---

## Example Workflows

### Workflow 1: Simple Fixed Withdrawal
```bash
# 1. Set profit target to $500
curl -X POST http://197.185.139.72:9000/api/bot/ZWE1/auto-withdrawal \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9",
    "withdrawal_mode": "fixed",
    "target_profit": 500
  }'

# 2. Check status whenever
curl http://197.185.139.72:9000/api/bot/ZWE1/auto-withdrawal-status

# 3. Disable when done
curl -X POST http://197.185.139.72:9000/api/bot/ZWE1/disable-auto-withdrawal \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9"
  }'
```

### Workflow 2: Intelligent Withdrawal Setup
```bash
# 1. Configure intelligent parameters
curl -X POST http://197.185.139.72:9000/api/bot/ZWE1/intelligent-withdrawal \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "81b273c1-9f62-43e8-8f97-5dce967bf0c9",
    "min_profit": 100,
    "max_profit": 750,
    "volatility_threshold": 0.02,
    "win_rate_min": 65,
    "trend_strength_min": 0.6,
    "time_between_withdrawals_hours": 24
  }'

# 2. Monitor bot (robot handles rest)
# Check status periodically
curl http://197.185.139.72:9000/api/bot/ZWE1/auto-withdrawal-status
```

---

## Common Questions

**Q: Can I switch between modes?**
A: Yes, just post to the other endpoint. New settings replace old ones.

**Q: What happens if both conditions are met?**
A: The most recently configured mode is active.

**Q: How often are withdrawals checked?**
A: Every 30 seconds in the background monitoring thread.

**Q: Can I have multiple withdrawal modes?**
A: No, one bot = one withdrawal configuration at a time.

**Q: What if bot is offline?**
A: Withdrawal logic continues in background. Bot profit tracked locally.

**Q: Can I manually trigger a withdrawal?**
A: Not with this API. Only automatic withdrawal is supported.

**Q: Why 2% fee?**
A: Platform overhead. Covers payment processing and maintenance.

---

## Integration Example (Flutter/Dart)

```dart
// Set fixed withdrawal
Future<void> setFixedWithdrawal(String botId, double targetProfit) async {
  final response = await http.post(
    Uri.parse('http://197.185.139.72:9000/api/bot/$botId/auto-withdrawal'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'user_id': userId,
      'withdrawal_mode': 'fixed',
      'target_profit': targetProfit,
    }),
  );
  
  if (response.statusCode == 200) {
    debugPrint('Fixed withdrawal set: \$$targetProfit');
  }
}

// Get status
Future<Map> getWithdrawalStatus(String botId) async {
  final response = await http.get(
    Uri.parse('http://197.185.139.72:9000/api/bot/$botId/auto-withdrawal-status'),
  );
  
  if (response.statusCode == 200) {
    return jsonDecode(response.body);
  }
  throw Exception('Failed to get withdrawal status');
}

// Set intelligent withdrawal
Future<void> setIntelligentWithdrawal(String botId) async {
  final response = await http.post(
    Uri.parse('http://197.185.139.72:9000/api/bot/$botId/intelligent-withdrawal'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'user_id': userId,
      'min_profit': 75,
      'max_profit': 500,
      'volatility_threshold': 0.02,
      'win_rate_min': 60,
      'trend_strength_min': 0.5,
      'time_between_withdrawals_hours': 24,
    }),
  );
  
  if (response.statusCode == 200) {
    debugPrint('Intelligent withdrawal configured');
  }
}
```

---

## Generated

**Commit:** `2ce6a51`
**Date:** March 11, 2026
**Feature:** Profit Withdrawal System v2.0
