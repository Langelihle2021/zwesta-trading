# MT5 Connection Troubleshooting - Quick Reference

## Common Issues & Fixes

### Issue: "MT5 already connected" error

**Symptoms**:
```
Error: MT5 already connected
Connection failed: IPC already in use
Exness connection attempt failed on account 298997455
```

**Root Cause**:
- Previous connection not properly cleaned up
- Connection object still in `broker_manager.connections`
- MT5 module not shutdown

**Fix**:
1. **Immediate**: Restart backend
2. **Permanent**: Ensure all logouts remove connections
3. **Verify**:
   ```bash
   grep "Removed connection" multi_broker_backend.log
   # Should see this after every logout
   ```

**Code Check**:
```python
# Should see this sequence:
✅ Removed connection: Exness MT5        # From remove_connection()
💾 Cleared balance cache for Exness:... # From remove_connection()
✅ Global MT5 module shutdown           # From logout endpoint
```

---

### Issue: Wrong balance displayed ($10,000 instead of real balance)

**Symptoms**:
```json
{
  "balance": 10000.00,
  "status": "CONNECTED",
  "note": "This looks like default, not real balance"
}
```

**Root Causes** (in order):
1. Balance cache key mismatch (common)
2. MT5 connection timeout
3. Account number format mismatch

**Fixes**:

**Fix A: Check balance cache key format**
```
Expected format: "Exness:298997455"
Wrong format: "MetaTrader5:298997455" 
Wrong format: "Exness|298997455"

Check in logs:
✓ Good:  💾 [BOT CACHE] Key='Exness:298997455'
✗ Bad:   💾 [BOT CACHE] Key='MetaTrader5:298997455'
```

Add debug code:
```python
from multi_broker_backend_updated import get_balance_cache_key, balance_cache

# Check what key is being used
key = get_balance_cache_key('Exness', '298997455')
print(f"Cache key: {key}")  # Should be "Exness:298997455"

# Check if in cache
print(f"In cache: {key in balance_cache}")  # Should be True after login
```

**Fix B: Check MT5 connection lock**
```bash
# If seeing lock timeouts:
⚠️ Waiting for exclusive MT5 connection lock (max 30 seconds)
⚠️ Could not acquire MT5 lock for balance check

# Another operation is using MT5, will use cached balance
# This is OK if cache is populated
```

**Fix C: Verify account number consistency**
```python
# Account numbers should match exactly:
Account from DB:    "298997455"  ✓
Account from user:  "298997455"  ✓
Cache key:          "Exness:298997455" ✓

# Check for mismatches:
Account from DB:    "298997455"
Account from user:  "0298997455"  ✗ Extra leading zero
Account from user:  "298997455 "  ✗ Trailing space
```

---

### Issue: User can't reconnect after logout

**Symptoms**:
```
Logout successful
Next login attempt: Connection failed
No error message in logs
```

**Root Cause**:
- Connection still in `broker_manager.connections` but MT5 terminated
- Trying to reuse stale connection object

**Fix**:
Verify logout removed connection:
```bash
# In logs after logout:
grep "Removed connection" multi_broker_backend.log
# Should show: ✅ Removed connection: Exness MT5
```

If not appearing, manually cleanup:
```python
# Debug/admin endpoint
import multi_broker_backend_updated as backend

# Force cleanup
for key in list(backend.broker_manager.connections.keys()):
    if 'MT5' in key or 'Exness' in key:
        backend.broker_manager.remove_connection(key)
        print(f"Cleaned up: {key}")
```

---

### Issue: Memory leak - connection count keeps growing

**Symptoms**:
```
Backend running for days
Connection errors increase
Memory usage grows
```

**Root Cause**:
- Connections created but not removed
- No logout calls or incomplete logout
- Bots not stopping properly

**Diagnosis**:
```bash
# Count connections in logs
grep "✅ Removed connection" multi_broker_backend.log | wc -l
# Should equal number of logout calls

grep "Connection added:" multi_broker_backend.log | wc -l
# Should equal above count

# If counts differ: Memory leak detected
```

**Fix**:
1. **Ensure logout cleanup**:
   ```python
   # Verify in exness_logout():
   # Should call: broker_manager.remove_connection()
   # Check multiple connections are being removed
   ```

2. **Add bot cleanup on stop**:
   ```python
   # In stop_bot_runtime():
   # Already cleans broker_connection_cache
   # May also need to clean broker_manager.connections
   ```

3. **Periodic cleanup (advanced)**:
   ```python
   # Add to backend startup
   def cleanup_stale_connections():
       """Remove connections older than 1 hour"""
       # Implement with connection creation timestamps
   ```

---

### Issue: Multiple users connecting to same account conflict

**Symptoms**:
```
User A connects account 298997455
User B connects same account 298997455
Error: MT5 authorization failed
Both users unable to trade
```

**Root Cause**:
- Only one MT5 session per account at a time
- Connection lock prevents simultaneous access

**Expected Behavior**:
- User B's connection waits for User A's
- Then connects sequentially (lock ensures this)
- Both can operate via balance cache

**Fix**:
1. **Check lock is working**:
   ```bash
   # In logs should see:
   ⏳ Waiting for exclusive MT5 connection lock
   ✅ Acquired MT5 connection lock
   # For each user
   ```

2. **Optimize lock timeout**:
   ```python
   # In MT5Connection.connect():
   lock_timeout = 60  # Or adjust based on needs
   # Higher = longer wait but more reliable
   # Lower = faster fail but may drop connections
   ```

3. **Use balance cache**:
   - User B doesn't need fresh balance immediately
   - Use cached balance while waiting for lock
   - Cache updates after User A completes

---

### Issue: "IPC timeout" errors in logs

**Symptoms**:
```
⚠️ IPC CONNECTION TIMEOUT: ...
MT5 not responding
Connection failed after retries
```

**Root Causes**:
1. MT5 terminal not running (common)
2. Terminal crashed or unresponsive
3. Computer resources exhausted
4. Network/IPC pipe corrupted

**Fixes**:

**Fix A: Start MT5 terminal**
```bash
# Windows - Check if running:
tasklist | findstr "terminal64"
# Should show one terminal64.exe per Exness installation

# If not running, start it:
"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
```

**Fix B: Restart terminal if hung**
```bash
# Force kill
taskkill /F /IM terminal64.exe

# System will auto-start on next connection attempt
# Or manually restart as above
```

**Fix C: Reduce connection frequency**
```python
# If too many connections overwhelming terminal:
# Increase bot sleep time between trades
# Use connection caching (already implemented)
# Stagger bot startups (add delays)
```

**Fix D: Check system resources**
```bash
# Memory usage
tasklist | findstr "terminal64"  # Check memory column

# Disk space (MT5 needs working disk space)
dir C:\

# Network: Ping Exness server
ping trade.exness.com
```

---

### Issue: Bot stops randomly, never reconnects

**Symptoms**:
```
Bot running successfully
Suddenly stops trading
No explicit stop command
Logs show connection error
Next trade never attempted
```

**Root Cause**:
- Connection lost during trade
- Exception in reconnection logic
- Bot not properly handling disconnection

**Fix**:
1. **Check bot error handling**:
   ```python
   # In bot trading loop:
   # Should catch connection errors and retry
   try:
       # Place order
   except MTOrderError:
       logger.warning("Order failed, next trade will auto-reconnect")
   ```

2. **Verify bot stop flags**:
   ```python
   # Bot should check:
   if bot_stop_flags.get(bot_id):
       break  # Stop gracefully
   
   # Should NOT just stop on connection error
   ```

3. **Check log for errors**:
   ```bash
   grep bot_id multi_broker_backend.log
   # Look for last error before stop
   # See what triggered the stop
   ```

---

### Issue: Connection cleanup hangs/takes forever

**Symptoms**:
```
Logout API call never returns
Browser showing loading...
Timeout after 30+ seconds
```

**Root Cause**:
- Lock acquisition timeout waiting
- MT5.shutdown() hanging
- Database update slow

**Fix**:
1. **Check lock wait**:
   ```bash
   grep "Waiting for exclusive MT5 connection lock" multi_broker_backend.log
   # If many of these: Lock contention issue
   # Another operation holding lock too long
   ```

2. **Increase timeout (temporary)**:
   ```python
   # In exness_logout():
   # Current: Uses default connection lock timeout
   # May increase if needed:
   lock_timeout = 120  # seconds
   ```

3. **Skip cleanup if needed (emergency)**:
   ```python
   # Unsafe but fast:
   try:
       mt5.shutdown()
   except:
       pass  # Ignore errors, don't wait
   # Connection removed from broker_manager immediately
   ```

---

### Issue: Cache shows old balance after trade

**Symptoms**:
```
Before trade: balance = $1000
Execute trade (profit $100)
Check balance: still $1000
```

**Root Cause**:
- Balance cache not updated during trade
- Bot doesn't refresh cache per trade
- Cache update only on login/logout

**Expected Behavior**:
- Cache updated only at login/logout
- During trade: Each operation via MT5 connection gets real balance
- API calls use cached value (may be stale)

**Workaround**:
1. **Force cache refresh**:
   ```python
   # At bot start/stop:
   # Re-login to refresh balance cache
   ```

2. **Query fresh balance endpoint** (if exists):
   ```bash
   GET /api/broker/account-info
   # Should query MT5 directly, bypass cache
   ```

3. **Understand cache purpose**:
   - Cache is for API availability during MT5 downtime
   - Not real-time, OK to be slightly stale
   - Bots always get real balance via connection

---

## Quick Diagnostics

### Run these to diagnose issues:

```bash
# 1. Check recent connections
grep "✅ Connected to MT5" multi_broker_backend.log | tail -5

# 2. Check recent cleanups  
grep "✅ Removed connection" multi_broker_backend.log | tail -5

# 3. Check for errors
grep "❌\|Error\|Exception" multi_broker_backend.log | tail -10

# 4. Check lock contention
grep "Waiting for exclusive MT5 connection lock" multi_broker_backend.log | wc -l

# 5. Check balance cache activity
grep "[BOT CACHE]" multi_broker_backend.log | tail -10

# 6. Check MT5 terminal state
tasklist | findstr "terminal64"
```

### Python Debug Script

```python
#!/usr/bin/env python3
"""Debug script for connection state"""

import sys
sys.path.insert(0, '/path/to/backend')

from multi_broker_backend_updated import (
    broker_manager, balance_cache, 
    balance_cache_lock, logger
)

print("=== BROKER MANAGER STATE ===")
print(f"Connections: {len(broker_manager.connections)}")
for key, conn in broker_manager.connections.items():
    print(f"  {key}: connected={conn.connected}")

print("\n=== BALANCE CACHE STATE ===")
with balance_cache_lock:
    print(f"Cache entries: {len(balance_cache)}")
    for key, value in balance_cache.items():
        print(f"  {key}: balance=${value.get('balance', 'N/A')}")

print("\n=== RECOMMENDATIONS ===")
if len(broker_manager.connections) > 2:
    print("⚠️ Many connections in manager, check if cleanup working")
if len(balance_cache) == 0:
    print("⚠️ No balance cache, may return defaults")
print("✅ Otherwise looks good")
```

---

## Contact Points for Different Issues

| Issue | Check First | If Persists |
|-------|------------|------------|
| Connection fails | MT5 terminal running? | Restart backend |
| Wrong balance | Balance cache key format | Check DB account numbers |
| Can't reconnect | Logout logs show "Removed connection"? | Manual broker_manager cleanup |
| Memory leak | Connection count growing? | Add periodic cleanup |
| Timeout | Another operation using lock? | Increase timeout, check CPU |
| Multi-user conflict | Lock acquisition messages? | Sequential behavior OK |

---

## When to Restart Backend

**Do restart if:**
- ❌ Multiple "MT5 already connected" errors
- ❌ Memory constantly growing
- ❌ Lock timeouts increasing
- ❌ Bots can't reconnect after logout

**Don't restart if:**
- ⚠️ Single connection error (will retry)
- ⚠️ One user logout issue (won't affect others)
- ⚠️ Cache miss showing default balance (cache will populate)
- ⚠️ One bot stops (can restart bot only)

---

For detailed information, see:
- `MT5_CONNECTION_MANAGEMENT.md` - Architecture guide
- `MT5_CONNECTION_TESTING_GUIDE.md` - Testing procedures
- `multi_broker_backend_updated.py` - Source code
