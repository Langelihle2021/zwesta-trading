# Trading Bot Dashboard - Quick Start Setup

## What's New ✨

Your trading system now features:

✅ **Advanced Trading Bot Dashboard** - Real-time monitoring of all bots
✅ **Dual Trading Modes** - Signal-driven (immediate) or Interval-based (scheduled)
✅ **Performance Metrics** - Balance, profit, trades, and win rate per bot
✅ **Commission Tracking** - Earnings breakdown by bot and date
✅ **Withdrawal Management** - Pending and completed withdrawals
✅ **API Endpoints** - Complete REST API for programmatic control

---

## 5-Minute Setup

### Step 1: Navigate to Dashboard
In Flutter app, go to:
```
Main Menu → Trading Bots Dashboard
```

### Step 2: View Bot Summary
You'll see:
- **Total balance** across all brokers
- **Total profit** from all bots
- **Bots running** count
- **Active trades** counter

### Step 3: Click Any Bot to Expand
See:
- Current balance per bot
- Profit/loss
- Trade count
- Win rate percentage
- Trading mode (Signal-Driven or Interval)

### Step 4: Click Action Buttons
- **Details** → Full bot configuration
- **Trades** → Trade history
- **Commission** → Earnings breakdown

---

## Switching Bot to Signal-Driven Mode

### Via Dashboard (Coming Soon)
1. Click bot → Expand
2. Click "Settings"
3. Toggle "Signal-Driven Mode"
4. Set threshold (default: 70)
5. Save

### Via API (Immediate)
```bash
curl -X POST http://localhost:9000/api/bot/{bot_id}/configure-trading-mode \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "tradingMode": "signal-driven",
    "signalThreshold": 70,
    "pollInterval": 15,
    "tradingInterval": 600
  }'
```

### Via Python
```python
import requests

url = "http://localhost:9000/api/bot/bot123/configure-trading-mode"
headers = {"Authorization": f"Bearer {token}"}
data = {
    "tradingMode": "signal-driven",
    "signalThreshold": 70,
    "pollInterval": 15,
    "tradingInterval": 600
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

---

## Mode Comparison

| Feature | Signal-Driven | Interval |
|---------|---------------|----------|
| **Trigger** | Market signal strength | Fixed schedule |
| **Trades/Day** | Variable (5-20) | Fixed (288 at 5min) |
| **Best For** | Profit optimization | Consistency |
| **Configuration** | Threshold-based | Time-based |
| **Latency** | Immediate (15s polled) | Scheduled |
| **CPU Usage** | Low | Very Low |

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  Trading Bots Dashboard                    [Refresh] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┬──────────────┐                   │
│  │Total Balance │ Total Profit │                   │
│  │$ 25,234.50  │  $ 1,250.75  │                   │
│  └──────────────┴──────────────┘                   │
│  ┌──────────────┬──────────────┐                   │
│  │ Bots Running │ Active Trades│                   │
│  │    3 / 5     │      47      │                   │
│  └──────────────┴──────────────┘                   │
│                                                     │
│  Trading Bots (5)                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🟢 Aggressive Bot          [signal-driven]  │   │
│  │ XM | Signal-Driven                          │   │
│  │ Balance: $5,234.56 | Profit: $234.56        │   │
│  │ Trades: 45 (W: 68.9%)                       │   │
│  │                                              │   │
│  │ [Details] [Trades] [Commission]             │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🟢 Balanced Bot            [interval]       │   │
│  │ MT5 | Interval Mode                         │   │
│  │ Balance: $10,000.00 | Profit: $1,000.19     │   │
│  │ Trades: 120 (W: 71.5%)                      │   │
│  │                                              │   │
│  │ [Details] [Trades] [Commission]             │   │
│  └─────────────────────────────────────────────┘   │
│  ...                                                │
└─────────────────────────────────────────────────────┘
```

---

## Key Metrics Explained

### Balance
**Real-time account balance** from your broker
- Updated every 3 seconds
- Includes all trades + commissions
- Per bot, per broker

### Profit
**Total profit/loss** from this bot since creation
- Profit = Entry Price - Exit Price × Volume
- Includes all closed trades
- Real-time calculation

### Trades
**Total number of trades** executed by bot
- Counts both wins and losses
- Cumulative (all-time)
- Updated after each trade

### Win Rate
**Percentage of profitable trades**
- Formula: (Winning Trades / Total Trades) × 100
- 50% = neutral trading
- 60%+ = good strategy

### Trading Mode
**How bot decides when to trade**
- **Signal-Driven:** On profit signals (reactive)
- **Interval:** Every X seconds (predictable)

---

## Trading Signal Strength Scale

```
Score    │ Action              │ Risk Level
─────────┼─────────────────────┼──────────
0-30     │ ❌ Skip - Too Weak  │ Too High
30-60    │ ⏳ Hold - Weak      │ High
60-70    │ ⚠️ Mild - Moderate  │ Medium
70-85    │ ✅ BUY - Strong     │ Low
85-100   │ 🔥 BUY - Excellent  │ Very Low
```

Signal strength factors:
1. **Technical indicator** (Buy/Sell signal)
2. **Market volatility** (trending up/down)
3. **Historical win rate** (confidence)
4. **Profitability** (is it worth trading?)

---

## Common Configurations

### Configuration 1: Conservative
```json
{
  "tradingMode": "signal-driven",
  "signalThreshold": 85,    // Only best signals
  "pollInterval": 30,       // Check less often
  "tradingInterval": 1800   // 30 min cap
}
```
**Result:** 2-3 trades/day, keep majority

---

### Configuration 2: Balanced
```json
{
  "tradingMode": "signal-driven",
  "signalThreshold": 70,    // Strong signals
  "pollInterval": 15,       // Check often
  "tradingInterval": 900    // 15 min cap
}
```
**Result:** 10-15 trades/day, good balance

---

### Configuration 3: Aggressive
```json
{
  "tradingMode": "signal-driven",
  "signalThreshold": 60,    // More signals
  "pollInterval": 10,       // Very frequent
  "tradingInterval": 300    // 5 min cap
}
```
**Result:** 20-30 trades/day, high volume

---

### Configuration 4: Fixed Schedule
```json
{
  "tradingMode": "interval",
  "tradingInterval": 300    // Every 5 minutes
}
```
**Result:** Predictable, always at X:00, X:05, X:10...

---

## API Endpoints Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/dashboard/bots-summary` | GET | All bots at a glance |
| `/bot/{id}/performance` | GET | Detailed metrics |
| `/bot/{id}/trades-detailed` | GET | Trade history |
| `/bot/{id}/commissions` | GET | Earnings & withdrawals |
| `/bot/{id}/configure-trading-mode` | POST | Change mode |
| `/bot/{id}/trading-mode` | GET | Current mode |

---

## Monitoring Checklist

### Daily
- [ ] Check total balance (should grow)
- [ ] Review trade count
- [ ] Monitor win rate (should be >60%)
- [ ] Check profit trend

### Weekly
- [ ] Analyze profit by bot
- [ ] Review commissions earned
- [ ] Check for any errors/stops
- [ ] Adjust settings if needed

### Monthly
- [ ] Compare ROI to benchmark
- [ ] Plan withdrawals
- [ ] Review strategy performance
- [ ] Adjust bot allocation

---

## Troubleshooting

### Bot shows "Stopped" but was running
**Check:**
1. Server still running? (`nc localhost 9000`)
2. Bot crashed? (Check logs)
3. Account disconnected? (Reconnect)

### Balance not updating
**Check:**
1. Broker connection active
2. Account credentials valid
3. Server has internet access

### Too few trades executing
**Fix:**
- Lower signal threshold (currently at 70?)
- Reduce pollInterval (check more often)
- Check bot logs for signal warnings

### Too many losing trades
**Fix:**
- Raise signal threshold (65 → 75)
- Increase trading interval (more selective)
- Review strategy for market fit

---

## File Locations

| File | Purpose |
|------|---------|
| `lib/screens/trading_bots_dashboard_screen.dart` | Dashboard UI |
| `TRADING_BOTS_DASHBOARD_GUIDE.md` | Complete guide |
| `TRADING_BOT_CONFIGURATION_API.md` | API reference |
| `multi_broker_backend_updated.py` | Backend APIs |

---

## Getting Help

### Check Logs
```bash
# Backend logs
tail -f backend.log

# Frontend logs
flutter run -v
```

### Test Connection
```bash
curl http://localhost:9000/health
```

### Test Bot Activity
```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:9000/api/dashboard/bots-summary
```

---

## What's Next?

1. **Start using signal-driven mode** - Configure first bot with threshold 70
2. **Monitor for 24 hours** - See how it performs
3. **Adjust settings** - Fine-tune based on results
4. **Scale up** - Add more bots as you gain confidence
5. **Withdraw profits** - Use commission endpoints to pull earnings

You're all set! 🚀
