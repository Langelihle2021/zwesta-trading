# Quick Testing Guide - Terminal Commands

**Use these commands to test the fixes immediately after restarting the backend.**

---

## Step 1: Get Your Session Token

First, log in to get a token:

```bash
curl -X POST http://localhost:5000/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'
```

**Expected Response** (save the `session_token` value):
```json
{
  "success": true,
  "session_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
  "user_id": "user-uuid-here",
  "name": "Test User"
}
```

---

## Step 2: Test 401 Header Logging (Authorization Fix)

### Test 2A: WITH session token (should work)

```bash
curl -X GET http://localhost:5000/api/broker/exness/account \
  -H "X-Session-Token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" \
  -H "Content-Type: application/json"
```

**Expected Response** (varies based on whether you have Exness credentials):
```json
{
  "success": true,
  "accountId": 298997455,
  "balance": 5000.00,
  "equity": 5000.00,
  "currency": "USD"
}
```

**Or if no credentials**:
```json
{
  "success": false,
  "error": "No Exness credentials found. Please connect your Exness account first."
}
```

**Check backend logs - you should see**:
```
[SESSION OK] User user-uuid-here authenticated for exness_account_info
✅ Exness account retrieved successfully
```

### Test 2B: WITHOUT session token (will show missing header message)

```bash
curl -X GET http://localhost:5000/api/broker/exness/account \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "success": false,
  "error": "Missing session token in X-Session-Token header"
}
```

**Check backend logs - you should see** (this is the new debugging feature):
```
🚨 [CRITICAL] MISSING X-Session-Token for GET /api/broker/exness/account
📋 Headers received: {'Host': 'localhost:5000', 'User-Agent': 'curl/7.68.0', ...}
🌐 Client IP: 127.0.0.1
```

**This output tells us the client is NOT sending the header** → Flutter bug to fix

---

## Step 3: Start a Bot and Monitor Signal Logging

### Get a bot ID first:

```bash
curl -X GET http://localhost:5000/api/bots \
  -H "X-Session-Token: your_token_here" \
  -H "Content-Type: application/json" | grep -i '"bot_id"'
```

### Start a bot:

```bash
curl -X POST http://localhost:5000/api/bot/start \
  -H "X-Session-Token: your_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "bot_1234567890",
    "user_id": "your_user_uuid"
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "botId": "bot_1234567890",
  "message": "Bot started successfully"
}
```

### Monitor logs in real-time (open new terminal):

```bash
# On Windows, tail the logs (if you have tail installed)
tail -f backend.log | grep -E "Cycle|Signal check|Trades placed|Order"

# Or on Windows PowerShell:
Get-Content backend.log -Wait | Select-String "Cycle|Signal"
```

**Expected log sequence** (this is the SIGNAL LOGGING FIX):
```
🔄 Bot bot_1234567890: Trade cycle #1 starting at 2024-12-19T15:30:45.123456
📊 Bot bot_1234567890 Cycle #1: Signal check: EURUSDm:72 | GBPUSDm:38 | XAUUSDm:55 (threshold: 65/100)
🎯 Bot bot_1234567890: BUY signal on EURUSDm
   Signal Strength: 72/100 | Reason: Trend strength confirmed
⏭️ Bot bot_1234567890: Skipping GBPUSDm - signal strength insufficient
⏭️ Bot bot_1234567890: Skipping XAUUSDm - signal strength insufficient
📍 Bot bot_1234567890: Placing BUY order on EURUSDm via Exness | Cycle: 1
✅ Bot bot_1234567890: Order placed successfully on EURUSDm
✅ Bot bot_1234567890: Trade executed | EURUSDm BUY | P&L: $0.00
✅ Bot bot_1234567890: Cycle #1 complete | Trades placed: 1 | Total P&L: $0.00
⏳ Bot bot_1234567890: Waiting 300 seconds until next cycle...

[After 5 minutes, cycle 2 starts]
🔄 Bot bot_1234567890: Trade cycle #2 starting at 2024-12-19T15:35:45.123456
📊 Bot bot_1234567890 Cycle #2: Signal check: EURUSDm:65 | GBPUSDm:42 | XAUUSDm:48 (threshold: 65/100)
✨ Bot bot_1234567890: New MT5 connection created and cached     # FIRST TIME
🎯 Bot bot_1234567890: BUY signal on EURUSDm
   Signal Strength: 65/100 | Reason: Momentum increasing
...

[After 5 more minutes, cycle 3 starts]
🔄 Bot bot_1234567890: Trade cycle #3 starting at 2024-12-19T15:40:45.123456
📊 Bot bot_1234567890 Cycle #3: Signal check: EURUSDm:58 | GBPUSDm:71 | XAUUSDm:43 (threshold: 65/100)
♻️ Bot bot_1234567890: Using cached MT5 connection (savings: 3-5s)   # CACHE WORKING!
⏭️ Bot bot_1234567890: Skipping EURUSDm - signal strength insufficient
🎯 Bot bot_1234567890: BUY signal on GBPUSDm
   Signal Strength: 71/100 | Reason: Breakout pattern detected
...
```

**What to look for**:
- ✅ Signal check line appears (shows all 3 symbols)
- ✅ Clear explanation for each trade decision
- ✅ Cache logs show `✨` then `♻️` symbols
- ✅ NO 401 errors in logs

---

## Step 4: Monitor Performance Improvements (Cycle Times)

### Start bot and time the cycles:

```bash
# Terminal 1: Start bot and note exact time
curl -X POST http://localhost:5000/api/bot/start \
  -H "X-Session-Token: token" \
  -H "Content-Type: application/json" \
  -d '{"bot_id":"bot_123","user_id":"user-uuid"}'

# Terminal 2: Get real-time cycle times
tail -f backend.log | grep -E "Trade cycle|waiting"
```

**Expected output**:
```
🔄 Bot bot_123: Trade cycle #1 starting at 2024-12-19T15:30:45.100000  [START]
First trade cycle - waiting for MT5 readiness (up to 30s)...
✅ Bot bot_123: Cycle #1 complete at 2024-12-19T15:31:15.230000        [30s passed]
⏳ Bot bot_123: Waiting 300 seconds until next cycle...

🔄 Bot bot_123: Trade cycle #2 starting at 2024-12-19T15:35:45.200000  [+5m]
♻️ Bot bot_123: Using cached MT5 connection (savings: 3-5s)
✅ Bot bot_123: Cycle #2 complete at 2024-12-19T15:35:50.900000        [5s passed]  ← FASTER!
⏳ Bot bot_123: Waiting 300 seconds until next cycle...
```

**Metrics to measure**:
- Cycle 1 duration: 30-45 seconds (was 120+)
- Cycle 2+ duration: 5-8 seconds (was 10-12)
- Cache hits: Should see `♻️` starting cycle 2

---

## Step 5: Test Cache Cleanup (Bot Stop)

```bash
# Stop the bot
curl -X POST http://localhost:5000/api/bot/stop/bot_123 \
  -H "X-Session-Token: your_token" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"your_user_uuid"}'
```

**Expected Response**:
```json
{
  "success": true,
  "message": "Bot bot_123 stopped"
}
```

**Check logs for cache cleanup**:
```
🛑 Bot bot_123: Stopping background trading thread...
✅ Bot bot_123: Background thread stopped
♻️ Bot bot_123: Cached connection cleaned up (0 remaining)
⏸️ Bot bot_123 stopped (still in system, can be restarted)
```

---

## Interpreting Results

### ✅ ALL FIXES WORKING
```
✅ 401 error shows [SESSION OK] with token
✅ 401 error shows 🚨 MISSING when no token
✅ Cycle logs show signal evaluation for all symbols
✅ Cycle 1 takes 30-45s, cycles 2+ take 5-8s
✅ See ♻️ cache hits on cycles 2+
✅ See cache cleanup on bot stop
```

### ⚠️ 401 STILL SHOWING MISSING HEADER
**Problem**: Flutter app not sending X-Session-Token header  
**Action**: Check Flutter's HTTP client setup:
1. Find where API requests are made (usually `api_client.dart` or `services/api_service.dart`)
2. Verify X-Session-Token header is added to ALL requests
3. Verify token is stored correctly after login

### ⚠️ SAME CYCLE TIMES (No improvement)
**Problem**: Cache not working  
**Action**: 
1. Check you see `✨ New MT5 connection created` message (cache initialized)
2. Verify you see `♻️ Using cached MT5 connection` on cycle 2+
3. If not, cache code may not have applied - verify file changes took effect
4. Restart backend after file modification

### ⚠️ Trade Status Still "Trades placed: 0"
**Check the signal line**:
- `EURUSDm:35 | GBPUSDm:42 | XAUUSDm:28` → All weak, no trade (NORMAL)
- `EURUSDm:75 | GBPUSDm:42 | XAUUSDm:28` → Should trade but didn't (CHECK LOGS FOR ERROR)

---

## Quick Reference: Key Log Patterns

| Log Pattern | Means |
|-------------|-------|
| `🚨 [CRITICAL] MISSING X-Session-Token` | Client not sending header (Flutter bug) |
| `[SESSION OK] User ... authenticated` | Session validation passed (✅) |
| `📊 Signal check: EURUSDm:72...` | Signal evaluation working (✅) |
| `✨ New MT5 connection created and cached` | Cache initialized (✅) |
| `♻️ Using cached MT5 connection` | Cache hit, saved 3-5s (✅) |
| `First trade cycle - waiting for MT5 readiness` | Should say "30s" not "120s" |
| `Trades placed: 0` | Check signal scores - all weak? Or error logs? |
| `Error connecting to Exness MT5` | Check credentials in database |
| `Symbol EURUSDm not found` | Symbol doesn't exist on this broker/server |

---

## Need Help?

1. **Run tests above** ✓
2. **Collect the relevant log snippets** from the output
3. **Check which tests pass**: Authorization? Signal logging? Performance?
4. **Share findings** along with log patterns

Then we can pinpoint the exact issue and implement targeted fixes.

---

**All tests should complete in 30 minutes. Good luck!** 🚀
