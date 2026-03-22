# MT5 Lock Contention - Troubleshooting Guide

## 🔴 The Problem You're Seeing

```
⚠️ TIMEOUT: Could not acquire MT5 lock after 0.1 seconds - system is busy
Skipping this trade cycle - will retry in 300 seconds
```

This means:
- ❌ Multiple bots trying to trade simultaneously
- ❌ They're all waiting for ONE shared MT5 connection lock
- ❌ Timeout was too short (0.1s) - bots gave up immediately
- ❌ Balance cache wasn't being used as fallback

---

## ✅ Fixes Applied

### Fix #1: Changed Lock Type
```python
# BEFORE (Basic Lock - not reentrant)
mt5_connection_lock = threading.Lock()

# AFTER (Reentrant Lock - better for nested operations)
mt5_connection_lock = threading.RLock()
```
**Impact**: Reduces deadlocks when bots have nested MT5 calls

### Fix #2: Increased Balance Check Timeout
```python
# BEFORE (Too short - failed immediately)
lock_timeout = 0.1  # 100ms

# AFTER (Reasonable queue wait)
lock_timeout = 3.0  # 3 seconds
```
**Impact**: Balance fetches now wait properly instead of timing out constantly

### Fix #3: Increased Default Lock Timeout
```python
# BEFORE (Limited time for bot trades)
lock_timeout = self.credentials.get('lock_timeout', 10)  # 10 seconds

# AFTER (Better for queued operations)
lock_timeout = self.credentials.get('lock_timeout', 20)  # 20 seconds
```
**Impact**: Bot trading loops get more time to acquire lock before giving up

---

## 📊 How It Works Now

### Before Fixes
```
Bot1 tries to trade → Waits 0.1s → TIMEOUT → Skips 5 minutes
Bot2 tries to trade → Waits 0.1s → TIMEOUT → Skips 5 minutes
Bot3 tries to trade → Waits 0.1s → TIMEOUT → Skips 5 minutes
Result: No trades happening!
```

### After Fixes
```
Bot1 tries to trade → Waits in queue (up to 20s) → Gets lock → Trades ✅
Bot2 tries to trade → Waits in queue (up to 20s) → Gets lock → Trades ✅
Bot3 tries to trade → Waits in queue (up to 20s) → Gets lock → Trades ✅
Result: All bots eventually trade!
```

---

## 🧪 Testing the Fixes

### Option 1: Run Diagnostic Script (Recommended)
```bash
python monitor_mt5_locks.py
```

This will:
- ✅ Check bot status every 5 seconds
- ✅ Test balance fetches (low-risk lock test)
- ✅ Show lock timeout patterns
- ✅ Provide recommendations

### Option 2: Watch Backend Logs
```bash
# In a new terminal while backend is running
tail -f /path/to/backend/logs.txt | grep -E "TIMEOUT|Acquired|MT5 lock"
```

Look for:
- ✅ `✅ Acquired MT5 connection lock` - Bot successfully traded
- ❌ `⚠️ TIMEOUT: Could not acquire` - Still having issues
- ✅ `Balance check: Waiting for MT5 lock` - Balance fetch working

---

## 📈 Expected Behavior After Fixes

### Good Signs ✅
```
🔄 Bot1: Trade cycle #1 starting
⏳ Waiting for MT5 connection lock (max 20s)...
✅ Acquired MT5 connection lock - proceeding with connection
📍 Bot1: Placing BUY order on EURUSD
✅ Trade placed successfully
```

### Still Bad Signs ❌
```
⚠️ TIMEOUT: Could not acquire MT5 lock after 20 seconds
ERROR: Bot: MT5 connection failed - will retry next cycle
```

If you still see 20-second timeouts:
1. **Too many bots**: Stop some bots that aren't performing
2. **MT5 terminal stuck**: Restart Exness MT5 terminal
3. **System overload**: Check CPU/memory usage

---

## 🚨 If Issues Persist

### Step 1: Check How Many Bots Running
```bash
curl -H "X-Session-Token: YOUR_TOKEN" \
  http://localhost:9000/api/bot/status?user_id=YOUR_USER_ID
```

Look for the count of bots with `"status": "ACTIVE"`

### Step 2: Stop Non-Essential Bots
```bash
# Stop individual bots if too many
curl -X POST \
  -H "X-Session-Token: YOUR_TOKEN" \
  http://localhost:9000/api/bot/{botId}/stop
```

### Step 3: Restart MT5 Terminal
1. Kill Exness MT5 terminal
2. Backend will auto-detect and reconnect
3. Bots will resume trading

### Step 4: Check Balance Cache
```bash
curl -H "X-Session-Token: YOUR_TOKEN" \
  http://localhost:9000/api/accounts/balances
```

Should return cached balances even during lock busy periods

---

## 🎯 Optimal Configuration

### For 1-2 Bots
- Works fine with default settings
- Lock timeouts rarely needed

### For 3-5 Bots
- Current fix should work well
- 20-second timeout is sufficient
- RLock prevents deadlocks

### For 6+ Bots
- **Recommended**: Run bots on separate accounts/terminals
- OR: Implement connection pooling (future enhancement)
- OR: Stagger bot start times (reduce simultaneous lock requests)

---

## 📝 Configuration Tuning

If you want to adjust timeouts, edit `multi_broker_backend_updated.py`:

### To increase timeout further:
```python
# Line ~1770
lock_timeout = self.credentials.get('lock_timeout', 30)  # 30 seconds instead of 20
```

### To make balance checks wait longer:
```python
# Line ~1776
lock_timeout = 5.0  # 5 seconds instead of 3
```

### To use connection pooling (advanced):
Consider implementing in future versions:
- Multiple MT5 connections (one per bot)
- Connection pool manager
- Load balancing across connections

---

## 🔍 Monitoring Checklist

Daily checks:
- [ ] Bots are placing trades (check totalTrades increasing)
- [ ] No repeated TIMEOUT messages in logs
- [ ] Balance cache is being populated
- [ ] MT5 terminal responds to connection attempts
- [ ] CPU usage < 50% on backend
- [ ] Memory usage stable (not growing)

---

## 💡 Pro Tips

1. **Stagger Bot Start Times**
   - Don't create all bots at once
   - Space out by 30-60 seconds
   - Reduces lock contention during initialization

2. **Use Balance Cache**
   - Frontend should prefer cached balances
   - Only refresh every 30+ seconds
   - Reduces lock pressure

3. **Monitor Long Locks**
   - If MT5 connection takes >10 seconds consistently
   - Terminal may be unresponsive
   - Restart fixes most issues

4. **Log Rotation**
   - Enable log rotation to prevent disk fill
   - Keep 3-5 backup logs
   - Makes troubleshooting easier

---

## 🆘 Emergency Troubleshooting

If bots completely stop trading:

```bash
# 1. Check backend is running
curl http://localhost:9000/health

# 2. Check MT5 terminal is responding
# (Windows) Open Exness MT5 terminal manually

# 3. Restart backend
# Stop the running python process
# Restart: python multi_broker_backend_updated.py

# 4. Check logs for errors
grep ERROR backend_logs.txt | tail -20

# 5. Clear lock state (if backend won't start)
# Delete any .lock files in project directory
rm -f *.lock
```

---

## Questions?

Check these files for more details:
- `multi_broker_backend_updated.py` - Line 67 (lock config)
- `multi_broker_backend_updated.py` - Line 1762 (lock acquisition)
- `monitor_mt5_locks.py` - Diagnostic script

Good luck! 🚀
