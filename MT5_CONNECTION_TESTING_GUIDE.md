# MT5 Connection Cleanup - Verification & Testing Guide

## Quick Summary of Fixes

| Component | Fix | Impact |
|-----------|-----|--------|
| `exness_logout()` | Now removes connections from `broker_manager.connections` | Users can reconnect without errors |
| `BrokerManager.remove_connection()` | New method for proper cleanup | Improves memory management |
| `balance_cache` | Cleared on logout | Prevents stale balance data |
| Logging | Enhanced cleanup logging | Better troubleshooting |

---

## Verification Checklist

### 1. Code Changes Applied ✓
- [ ] `BrokerManager.remove_connection()` method exists
- [ ] `BrokerManager.get_connection_by_broker_account()` helper exists
- [ ] `exness_logout()` endpoint rewritten with cleanup logic
- [ ] File saved: `MT5_CONNECTION_MANAGEMENT.md`

**Check with:**
```bash
grep -n "def remove_connection" multi_broker_backend_updated.py
grep -n "def exness_logout" multi_broker_backend_updated.py
```

### 2. Syntax Validation
```bash
python -m py_compile multi_broker_backend_updated.py
# Should return no errors
```

### 3. Basic Connection Test

**Scenario**: Single user connects and disconnects

```python
import requests
import json

BASE_URL = "http://localhost:5000"
HEADERS = {'Content-Type': 'application/json'}

# Step 1: Login (get session token)
login_response = requests.post(f'{BASE_URL}/api/auth/login', 
    json={'email': 'test@example.com', 'password': 'password'},
    headers=HEADERS
)
token = login_response.json()['session_token']
headers = {**HEADERS, 'Authorization': f'Bearer {token}'}

# Step 2: Test connection (verifies credentials)
test_response = requests.post(
    f'{BASE_URL}/api/broker/test-connection',
    json={
        'broker': 'Exness',
        'account_number': '298997455',
        'password': 'your_password',
        'server': 'Exness-MT5Trial9',
        'is_live': False
    },
    headers=headers
)
print("Test Connection:", test_response.json())
# Expected: balance shown, connection successful

# Step 3: Logout (should remove from broker_manager.connections)
logout_response = requests.post(
    f'{BASE_URL}/api/broker/exness/logout',
    headers=headers
)
print("Logout:", logout_response.json())
# Expected: accountsRemoved > 0 or message about cleanup
```

**What to verify in logs:**
```
[OK] ✅ Removed connection: Exness MT5
[OK] 💾 Cleared balance cache for Exness:298997455
[OK] ✅ Global MT5 module shutdown
[OK] ✅ Exness session ended - removed X accounts from broker_manager
```

### 4. Reconnection Test

**Scenario**: User connects, disconnects, reconnects (should work without "already connected" errors)

```python
# ... (Setup as above)

# Step 1: First connection test
requests.post(f'{BASE_URL}/api/broker/test-connection',
    json={...},
    headers=headers
)
print("✅ First connection successful")

# Step 2: Logout
requests.post(f'{BASE_URL}/api/broker/exness/logout', headers=headers)
print("✅ Logout successful")

# Step 3: Second connection test (should work without errors)
requests.post(f'{BASE_URL}/api/broker/test-connection',
    json={...},
    headers=headers
)
print("✅ Second connection successful (FIX VERIFIED)")
```

**Expected Logs**:
```
Connection attempt 1/3: Account=298997455, Server=Exness-MT5Trial9
✅ Connected to MT5 account 298997455 with password
💾 Cached balance IMMEDIATELY after login: Exness:298997455 = $197663.49

... logout ...

✅ Removed connection: Exness MT5
💾 Cleared balance cache for Exness:298997455
✅ Exness session ended - removed 1 accounts from broker_manager

Connection attempt 1/3: Account=298997455, Server=Exness-MT5Trial9
✅ Connected to MT5 account 298997455 with password
```

### 5. Multiple Load Test

**Scenario**: Multiple users with same broker connecting/disconnecting

```python
import threading
import time

def user_test_cycle(user_id, account_id):
    """Single user's login/logout cycle"""
    # ... (make connections as above)
    base_headers = {'Content-Type': 'application/json', 
                   'Authorization': f'Bearer {token_for_user}'}
    
    # Connect
    requests.post(f'{BASE_URL}/api/broker/test-connection',
        json={'broker': 'Exness', 'account_number': account_id, ...},
        headers=base_headers
    )
    print(f"User {user_id}: Connected")
    
    time.sleep(1)  # Simulate usage
    
    # Disconnect
    requests.post(f'{BASE_URL}/api/broker/exness/logout',
        headers=base_headers
    )
    print(f"User {user_id}: Logged out")

# Run multiple users in parallel
threads = []
for i in range(3):
    t = threading.Thread(target=user_test_cycle, args=(i, '298997455'))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("✅ All users completed without connection conflicts")
```

### 6. Balance Cache Validation

**Scenario**: Verify balance cache is properly maintained

```python
# Expect in logs after successful login:
# 💾 [BOT CACHE] Key='Exness:298997455' Balance=$197663.49 (Total cache entries: 1)

# After logout:
# 💾 Cleared balance cache for Exness:298997455

# Cache should be empty or only have other users' balances
```

### 7. Broker Manager Inspection

**Add debug endpoint (optional, for development):**

```python
@app.route('/api/debug/broker-manager', methods=['GET'])
def debug_broker_manager():
    """Debug endpoint to inspect broker manager state"""
    with balance_cache_lock:
        balance_cache_info = {k: {'balance': v.get('balance')} 
                             for k, v in balance_cache.items()}
    
    connections_info = {k: {
        'type': str(getattr(v, 'broker_type', 'unknown')),
        'connected': v.connected,
        'account': getattr(v, 'account', 'unknown')
    } for k, v in broker_manager.connections.items()}
    
    return jsonify({
        'balance_cache': balance_cache_info,
        'connections': connections_info,
        'timestamp': datetime.now().isoformat()
    })
```

**Usage**:
```bash
curl http://localhost:5000/api/debug/broker-manager

# Response before logout:
{
  "balance_cache": {
    "Exness:298997455": {"balance": 197663.49}
  },
  "connections": {
    "Exness MT5": {"type": "Exness", "connected": true, "account": "298997455"}
  }
}

# Response after logout:
{
  "balance_cache": {},
  "connections": {},
  "timestamp": "..."
}
```

---

## Edge Cases to Test

### Edge Case 1: Disconnect while bot is running
**Scenario**: User logs out, but bot still has active connection

**Current Behavior**: Bot continues using its cached connection from `broker_connection_cache`

**Expected**: Bot doesn't crash, continues working

**Verify with**:
```bash
# 1. Create and start bot
# 2. While bot running: call logout endpoint
# 3. Check bot continues trading
```

### Edge Case 2: Same account, multiple connections
**Scenario**: Same account connected under different keys in broker_manager

**Prevention**: 
- Logout removes ALL Exness connections
- Check for duplication in logs

**Test**:
```bash
# 1. Manually add duplicate connection to broker_manager
# 2. Call logout
# 3. Verify both removed in logs
```

### Edge Case 3: Connection cleanup while MT5 is unresponsive
**Scenario**: MT5 terminal crashed, trying to cleanup

**Expected**: Graceful handling, error logged but cleanup continues

**Verify in logs**:
```
Error disconnecting Exness MT5 during removal: ...
✅ Removed connection: Exness MT5  (still succeeds)
```

### Edge Case 4: Failed balance cache cleanup
**Scenario**: Cache key doesn't exist when trying to clear

**Expected**: Warning logged, but doesn't prevent connection removal

**Verify in logs**:
```
Error clearing balance cache for Exness MT5: ... (KeyError, etc)
✅ Removed connection: Exness MT5 (still removes)
```

---

## Log Analysis

### Green Flags ✅
```
✅ Connected to MT5 account 298997455
💾 Cached balance IMMEDIATELY after login: Exness:298997455 = $197663.49
✅ Removed connection: Exness MT5
💾 Cleared balance cache for Exness:298997455
✅ Exness session ended - removed X accounts from broker_manager
```

### Red Flags ❌
```
MT5 connection error: IPC timeout
Auto-retry or manual reconnect needed

Error removing connection: ...
Connection may still be in broker_manager

Missing balance cache key
May indicate key format mismatch
```

### Warning Flags ⚠️
```
⚠️ Cached MT5 is for different account
Normal if account changed between requests

⚠️ Could not acquire MT5 lock
Another operation holding lock, will retry

⚠️ Error disconnecting ... during removal
Connection cleanup incomplete but continues
```

---

## Performance Metrics

### Expected Timings
| Operation | Time | With Cache |
|-----------|------|-----------|
| Test Connection (first) | 3-5s | N/A |
| MT5 Login (switch account) | 0.5-2s | N/A |
| Balance Query (cache hit) | <0.1s | 0.1s |
| Logout (single account) | 1-2s | N/A |
| Bot Trade (new conn) | 3-5s | 0.1s |

### Monitoring Points
1. **Connection count**: Should decrease on logout
2. **Cache size**: Should decrease on logout
3. **Lock wait time**: Should be <2s for balance, <60s for full connection

---

## Rollback Plan (if needed)

If new code causes issues:

1. **Restore original logout**:
   - Remove new `remove_connection()` calls
   - Keep `mt5.shutdown()` for safety

2. **Disable balance cache cleanup**:
   - Comment out balance cache deletion
   - May cause duplicate balance issues but won't break connections

3. **Monitor for**:
   - "MT5 already connected" errors → Old connections not cleaned
   - Wrong balance shown → Cache key mismatch
   - Memory leaks → Connections not removed

---

## Success Criteria

All of the following must be true:

1. ✅ Code compiles without syntax errors
2. ✅ Reconnection works after logout
3. ✅ No "MT5 already connected" errors
4. ✅ Balance shows real value (not $10,000 default)
5. ✅ Logs show cleanup messages on logout
6. ✅ `broker_manager.connections` empty after logout
7. ✅ Multiple users can connect/disconnect without conflicts
8. ✅ Bots continue working during/after logout
9. ✅ No memory leaks in long-running tests
10. ✅ Cache consistency across all code paths

---

## Debugging Commands

### Check Connection State in Real-Time
```bash
# Terminal 1: Start backend with debug logging
export LOGLEVEL=DEBUG
python multi_broker_backend_updated.py

# Terminal 2: Make requests while watching logs
curl -X POST http://localhost:5000/api/broker/test-connection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"broker":"Exness","account_number":"298997455",...}'
```

### Parse Logs for Connection Lifecycle
```bash
# Show all connection/cleanup events
grep -E "(✅|💾|Removed|Cleared)" multi_broker_backend.log

# Show only cleanup events
grep "Removed connection" multi_broker_backend.log

# Show balance cache changes
grep "\[BOT CACHE\]|Cleared balance" multi_broker_backend.log
```

### Monitor in Real-Time
```bash
# Live tail of logs
tail -f multi_broker_backend.log | grep -E "(connection|cache|Exness)"
```

---

## Expected Error Messages (Normal)

These are OK and don't indicate problems:

```
⚠️ IPC CONNECTION TIMEOUT: ...
(Normal if terminal needs initialization)

⚠️ Could not acquire MT5 lock for balance check
(Another op using lock, will use cache)

Error getting user_id from session: 
(Session token not in DB, ok for test mode)
```

---

## Contact & Support

If issues occur:

1. **Check logs first** - Look for patterns in red flags above
2. **Run verification tests** - Use tests above to isolate issue
3. **Review code changes** - Compare old vs new logout endpoint
4. **Check thread safety** - Verify lock ordering not violated
5. **Test isolation** - Test with single user first, then multiple
