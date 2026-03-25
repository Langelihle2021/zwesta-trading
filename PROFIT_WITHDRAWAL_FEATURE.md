# Profit Withdrawal System - Complete Guide

## 🎯 Overview

Your trading bots now support **two intelligent profit withdrawal modes**:

### 1. **FIXED MODE** - User Controls When to Withdraw
Bot automatically withdraws profits when it reaches a **user-predetermined amount**

### 2. **INTELLIGENT MODE** - Robot Decides When to Withdraw
Bot intelligently decides to withdraw based on **market conditions & performance metrics**

---

## 📚 MODE COMPARISON

| Feature | Fixed Mode | Intelligent Mode |
|---------|-----------|------------------|
| **Trigger Type** | Profit target reached | Multiple conditions met |
| **User Config** | Single: target_profit | 6 parameters |
| **Best For** | Conservative traders | Aggressive, optimized traders |
| **Example** | "Withdraw $500 profit" | "Withdraw when win rate >60% & trend strong" |
| **Risk Level** | Low (you control it) | Medium (robot analyzes conditions) |

---

## 🔧 FIXED MODE - Setup & Usage

### Configuration (API)
```json
POST /api/bot/<bot_id>/auto-withdrawal
{
  "user_id": "your_user_id",
  "withdrawal_mode": "fixed",
  "target_profit": 500  // Withdraw when profit reaches $500
}
```

### Parameters
- `target_profit` - Target profit amount ($10 - $50,000)
- That's it! Simple and straightforward

### How It Works
1. Bot runs and accumulates profit
2. When profit reaches $500 → Automatic withdrawal triggered
3. Fee deducted (2%)
4. Profits reset to $0
5. Bot continues trading

### Example Flow
- Bot starts: $0 profit
- After trades: +$200 profit  → No action
- After more trades: +$500 profit → ✅ WITHDRAWAL TRIGGERED
- Net withdrawal: $500 - (2% fee) = $490
- Bot profit reset to: $0
- Cycle repeats

---

## 🤖 INTELLIGENT MODE - Setup & Usage

### Configuration (API)
```json
POST /api/bot/<bot_id>/intelligent-withdrawal
{
  "user_id": "your_user_id",
  "min_profit": 50,                          // Don't withdraw below $50
  "max_profit": 1000,                        // Don't exceed $1000 per withdrawal
  "volatility_threshold": 0.02,              // Don't withdraw if volatility > 2%
  "win_rate_min": 60,                        // Only withdraw if win rate > 60%
  "trend_strength_min": 0.5,                 // Trend must be at least 50% strong
  "time_between_withdrawals_hours": 24       // Max 1 withdrawal per 24 hours
}
```

### Parameters Explained

**min_profit** (Default: $50)
- Minimum profit before robot considers withdrawal
- Must be ≥ $10
- Example: If set to $100, robot won't withdraw unless profit > $100

**max_profit** (Default: $1,000)
- Maximum amount per single withdrawal
- Limits withdrawal size to protect capital
- Example: If set to $500, won't withdraw more than $500 at once

**volatility_threshold** (Default: 0.02 = 2%)
- Max market volatility allowed for withdrawal
- Range: 0 to 0.1 (0% to 10%)
- Protects against withdrawing during volatile markets
- Lower = safer but less frequent withdrawals

**win_rate_min** (Default: 60%)
- Minimum win rate required before withdrawal
- Range: 40% to 100%
- Won't withdraw if bot's win rate is below this
- Example: If set to 70%, only withdraws when bot wins 70% of trades

**trend_strength_min** (Default: 0.5)
- Confirms the bot has winning momentum
- Range: 0 (none) to 1 (perfect streak)
- Calculated from consecutive wins
- 0.5 = at least 5 consecutive wins

**time_between_withdrawals_hours** (Default: 24)
- Minimum hours between automatic withdrawals
- Range: 1 hour to 720 hours (30 days)
- Prevents excessive withdrawals
- Example: If set to 12, won't withdraw more than twice per day

### How Intelligent Withdrawal Works

Bot checks every 30 seconds:

```
IF profit >= min_profit:
  ✓ Check 1: Is win_rate > 60%?
  ✓ Check 2: Is market volatility < 2%?
  ✓ Check 3: Is trend_strength >= 0.5?
  ✓ Check 4: Has 24+ hours passed since last withdrawal?
  
  IF ALL Checks Pass:
    → 🎯 WITHDRAWAL TRIGGERED
    → Withdraw: min(profit × withdrawal_ratio, max_profit)
    → withdrawal_ratio = 50% + (trend_strength × 40%) = 50-90%
```

### Example Scenarios

**Scenario 1: Conservative Settings**
```json
{
  "min_profit": 100,
  "max_profit": 300,
  "volatility_threshold": 0.01,  // Very strict (1%)
  "win_rate_min": 70,             // High threshold
  "trend_strength_min": 0.7,      // Strong momentum required
  "time_between_withdrawals_hours": 48  // Every 2 days max
}
```
✓ Safe, predictable, fewer withdrawals
✗ Robot waits for perfect conditions

**Scenario 2: Aggressive Settings**
```json
{
  "min_profit": 20,
  "max_profit": 2000,
  "volatility_threshold": 0.05,  // More lenient (5%)
  "win_rate_min": 50,            // Just break-even
  "trend_strength_min": 0.3,     // Weak momentum ok
  "time_between_withdrawals_hours": 12  // Multiple times per day
}
```
✓ More frequent withdrawals
✗ Higher risk of withdrawing in bad conditions

**Scenario 3: Balanced (Recommended)**
```json
{
  "min_profit": 75,
  "max_profit": 500,
  "volatility_threshold": 0.02,  // 2% (industry standard)
  "win_rate_min": 60,            // Good threshold
  "trend_strength_min": 0.5,     // Reasonable momentum
  "time_between_withdrawals_hours": 24  // Once per day
}
```
✓ Good balance of safety and frequency

---

## 📊 Checking Withdrawal Status

### API Endpoint
```
GET /api/bot/<bot_id>/auto-withdrawal-status
```

### Response
```json
{
  "success": true,
  "bot_id": "ZWE1",
  "current_setting": {
    "setting_id": "abc123...",
    "target_profit": 500,
    "is_active": true,
    "created_at": "2026-03-11T01:52:00Z"
  },
  "history": [
    {
      "withdrawal_id": "xyz789...",
      "triggered_profit": 502.50,
      "withdrawal_amount": 502.50,
      "net_amount": 492.45,  // After 2% fee
      "status": "completed",
      "created_at": "2026-03-11T01:30:00Z",
      "completed_at": "2026-03-11T01:30:05Z"
    }
  ],
  "total_auto_withdrawals": 5,
  "total_amount_withdrawn": 2450.75
}
```

---

## ⚙️ Disabling Withdrawal

### API
```
POST /api/bot/<bot_id>/disable-auto-withdrawal
{
  "user_id": "your_user_id"
}
```

This stops automatic withdrawals but keeps history

---

## 📈 Real-World Examples

### Single Mom Trader (Conservative)
```javascript
{
  "withdrawal_mode": "fixed",
  "target_profit": 100  // Simple: $100 = withdraw
}
```
✓ Easy to understand
✓ Predictable withdrawals
✓ Set it and forget it

### Day Trader (Aggressive)
```javascript
{
  "withdrawal_mode": "intelligent",
  "min_profit": 25,
  "max_profit": 500,
  "volatility_threshold": 0.03,
  "win_rate_min": 55,
  "trend_strength_min": 0.3,
  "time_between_withdrawals_hours": 6
}
```
✓ Multiple withdrawals per day
✓ Captures strong trends
✗ Needs monitoring

### Passive Investor (Balanced)
```javascript
{
  "withdrawal_mode": "intelligent",
  "min_profit": 200,
  "max_profit": 1000,
  "volatility_threshold": 0.02,
  "win_rate_min": 65,
  "trend_strength_min": 0.6,
  "time_between_withdrawals_hours": 48
}
```
✓ Quality withdrawals only
✓ Protects capital
✓ Works with full-time job

---

## 🚨 Important Notes

### Fees
- 2% fee on every automatic withdrawal
- Applied automatically
- Example: $100 withdrawal → $98 net

### Withdrawal Reset
- After withdrawal, bot's `totalProfit` resets to $0
- Bot continues trading normally
- Previous withdrawal history preserved

### Database Migration
- Existing bots get default settings automatically
- No data loss from old system
- Can switch modes anytime

### Intelligent Mode Accuracy
- Bot needs **at least 5 trades** to make intelligent decisions
- Win rate calculated from all completed trades
- Volatility estimated from recent price movements
- Trend strength from consecutive wins

### Time Intervals
- Each withdrawal cycles independently
- 24-hour interval = 1 withdrawal per day MAX
- Multiple withdrawals allowed if interval passed
- Prevents withdrawal spam

---

## 🔍 Troubleshooting

### Withdrawals Not Triggering (Fixed Mode)
- Check profit is actually reaching target
- Verify withdrawal is enabled (is_active = true)
- Check bot is actively trading

### Withdrawals Not Triggering (Intelligent Mode)
- Win rate might be too low (check current_setting)
- Volatility might be too high
- Trend strength might be weak
- Check time interval hasn't passed

### Want to Switch Modes?
Simply call the appropriate endpoint:
- For Fixed: `POST /api/bot/<bot_id>/auto-withdrawal`
- For Intelligent: `POST /api/bot/<bot_id>/intelligent-withdrawal`

It will replace the previous settings.

---

## 📝 Git Commit

**Commit Hash:** `2ce6a51`
**Changes:**
- Enhanced database schema with intelligent parameters
- Dual-mode withdrawal system in monitor function
- New API endpoint for intelligent configuration
- Updated fixed-mode endpoint with mode parameter
- Intelligent decision logic with 6 validation checks

---

## 🎯 Next Steps

1. **For Fixed Mode Users:** Just specify target_profit
2. **For Intelligent Mode Users:** Fine-tune the 6 parameters
3. **Monitor:** Check withdrawal status regularly
4. **Adjust:** Tweak parameters based on bot performance

Good luck! 🚀
