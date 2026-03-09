# Data Isolation Implementation Checklist

## 🎯 Problem Statement
All users were seeing the same demo account data and bots regardless of which account they logged into. Root cause: global `active_bots` dictionary with no user_id filtering.

## ✅ Phase 1: Database Schema (COMPLETED)

### New Tables Created
- [x] `user_bots` - Maps bots to specific users
- [x] `broker_credentials` - Stores each user's broker login info
- [x] `user_sessions` - Tracks authenticated sessions with tokens

### Schema Details
```sql
-- User-Specific Bots
CREATE TABLE user_bots (
    bot_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL FOREIGN KEY REFERENCES users(user_id),
    name TEXT NOT NULL,
    strategy TEXT,
    status TEXT,
    enabled BOOLEAN,
    daily_profit REAL,
    total_profit REAL,
    created_at DATETIME,
    updated_at DATETIME
);

-- Broker Credentials Per User
CREATE TABLE broker_credentials (
    credential_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL FOREIGN KEY REFERENCES users(user_id),
    broker_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    password TEXT NOT NULL,
    server TEXT,
    is_live BOOLEAN,
    is_active BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME
);

-- User Session Tokens
CREATE TABLE user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL FOREIGN KEY REFERENCES users(user_id),
    token TEXT NOT NULL UNIQUE,
    created_at DATETIME,
    expires_at DATETIME,
    ip_address TEXT,
    user_agent TEXT,
    is_active BOOLEAN
);
```

---

## ✅ Phase 2: Authentication Endpoints (COMPLETED)

### POST /api/user/login
**Purpose:** Authenticate user and create session token
**Status:** ✅ IMPLEMENTED
**Code Location:** multi_broker_backend_updated.py, line ~2463

**Flow:**
1. Accept email in request
2. Query users table for matching email
3. Generate session token (SHA256 hash)
4. Insert into user_sessions table
5. Return user data + session token

**Request:**
```json
{
  "email": "trader@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-12345",
  "session_token": "hash_token_here"
}
```

---

### GET /api/user/profile/<user_id>
**Purpose:** Return user profile with their bots and brokers
**Status:** ✅ IMPLEMENTED
**Code Location:** multi_broker_backend_updated.py, line ~2520

**Flow:**
1. Validate user_id exists in users table
2. Query user_bots WHERE user_id = ?
3. Query broker_credentials WHERE user_id = ?
4. Return aggregated user data

**Response:**
```json
{
  "success": true,
  "user": {...},
  "bots": [...],
  "brokers": [...]
}
```

---

### POST /api/user/<user_id>/broker-credentials
**Purpose:** Add broker credentials for user
**Status:** ✅ IMPLEMENTED
**Code Location:** multi_broker_backend_updated.py, line ~2620

**Flow:**
1. Validate user_id exists
2. Generate credential_id
3. Insert into broker_credentials table with user_id
4. Return credential_id

**Request:**
```json
{
  "broker_name": "XM",
  "account_number": "123456789",
  "password": "password",
  "server": "XMGlobal-MT5",
  "is_live": false
}
```

---

### GET /api/user/<user_id>/broker-credentials
**Purpose:** Return all broker credentials for user
**Status:** ✅ IMPLEMENTED
**Code Location:** multi_broker_backend_updated.py, line ~2680

**Flow:**
1. Validate user_id exists
2. Query broker_credentials WHERE user_id = ?
3. Return list of credentials

---

### GET /api/user/<user_id>/bots
**Purpose:** Return all bots for user
**Status:** ✅ IMPLEMENTED
**Code Location:** multi_broker_backend_updated.py, line ~2720

**Flow:**
1. Validate user_id exists
2. Query user_bots WHERE user_id = ?
3. Calculate aggregated stats
4. Return list of user's bots

---

## ✅ Phase 3: Bot Endpoint Modifications (COMPLETED)

### POST /api/bot/create
**Purpose:** Create bot linked to user
**Status:** ✅ MODIFIED
**Code Location:** multi_broker_backend_updated.py, line ~1957

**Changes Made:**
- Added `user_id` as required parameter
- Generate bot_id with user_id included: `bot_{user_id}_{timestamp}`
- Insert into `user_bots` table instead of global dictionary only
- Include `user_id` in active_bots memory cache
- Return bot with user_id confirmation

**Before:**
```python
botId = f"bot_{int(datetime.now().timestamp())}"
active_bots[botId] = {...}
```

**After:**
```python
user_id = data.get('user_id')  # Required parameter
bot_id = f"bot_{user_id}_{int(datetime.now().timestamp())}"
cursor.execute('''INSERT INTO user_bots VALUES (...)''', 
               (bot_id, user_id, name, strategy, ...))
active_bots[bot_id] = {..., 'user_id': user_id, ...}
```

---

### GET /api/bot/status
**Purpose:** Return bot status filtered by user
**Status:** ✅ MODIFIED
**Code Location:** multi_broker_backend_updated.py, line ~2199

**Changes Made:**
- Added `user_id` query parameter support
- Filter active_bots by user_id
- Only return bots belonging to querying user
- Query database for historical data if needed

**Before:**
```python
bots = active_bots.values()  # All bots returned
```

**After:**
```python
user_id = request.args.get('user_id')
bots = [bot for bot in active_bots.values() 
        if not user_id or bot.get('user_id') == user_id]
```

---

## ⏳ Phase 4: Remaining Bot Endpoints (PENDING)

### POST /api/bot/start
**Status:** 🟠 NEEDS UPDATE
**Current Issue:** No user_id verification; can start other user's bots
**Required Changes:**
1. Accept `user_id` parameter
2. Query user_bots table: `SELECT * FROM user_bots WHERE bot_id = ? AND user_id = ?`
3. Return 403 Forbidden if bot doesn't belong to user
4. Only start bot if ownership verified

**Code Location:** multi_broker_backend_updated.py (~line 1850)

---

### POST /api/bot/stop
**Status:** 🟠 NEEDS UPDATE
**Current Issue:** No user_id verification
**Required Changes:** Same as /api/bot/start with stop logic

**Code Location:** multi_broker_backend_updated.py (~line 1895)

---

### DELETE /api/bot/delete
**Status:** 🟠 NEEDS UPDATE
**Current Issue:** No user_id verification
**Required Changes:**
1. Accept `user_id` parameter
2. Verify bot belongs to user
3. Delete from user_bots table
4. Remove from active_bots memory cache

**Code Location:** multi_broker_backend_updated.py (~line 1920)

---

### GET /api/bot/config
**Status:** 🟠 NEEDS UPDATE
**Current Issue:** Returns all bot configs
**Required Changes:**
1. Accept `user_id` parameter
2. Filter by user_id

---

### POST /api/bot/update-config
**Status:** 🟠 NEEDS UPDATE
**Current Issue:** No user_id verification
**Required Changes:** Verify ownership before updating

---

## ⏳ Phase 5: Session Middleware (PENDING)

### Create @require_session Decorator
**Purpose:** Validate session token on protected endpoints
**Status:** 🟠 NOT STARTED
**Location:** New function in multi_broker_backend_updated.py

**Implementation:**
```python
def require_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return {'success': False, 'error': 'Missing session token'}, 401
        
        # Query user_sessions table
        cursor.execute(
            'SELECT user_id, expires_at FROM user_sessions WHERE token = ? AND is_active = 1',
            (session_token,)
        )
        session = cursor.fetchone()
        
        if not session:
            return {'success': False, 'error': 'Invalid session'}, 401
        
        # Check expiration
        expires_at = datetime.fromisoformat(session[1])
        if expires_at < datetime.now():
            return {'success': False, 'error': 'Session expired'}, 401
        
        request.user_id = session[0]  # Attach to request
        return f(*args, **kwargs)
    return decorated_function
```

---

### Apply to All Protected Endpoints
**Status:** 🟠 NOT STARTED
**Endpoints Needing Update:**
- GET /api/user/profile/<user_id>
- POST /api/user/<user_id>/broker-credentials
- GET /api/user/<user_id>/broker-credentials
- GET /api/user/<user_id>/bots
- POST /api/bot/create
- GET /api/bot/status
- POST /api/bot/start
- POST /api/bot/stop
- DELETE /api/bot/delete
- And all other user-specific endpoints

---

## ⏳ Phase 6: Frontend Integration (PENDING)

### Update Flutter App
**Status:** 🟠 NOT STARTED

**Required Changes:**
1. Store session token on login
2. Send `user_id` with all API calls
3. Store `user_id` in app state
4. Display only current user's bots
5. Filter broker list by user
6. Verify ownership before operations

**Example Implementation:**
```dart
// main.dart
final userService = UserService();

// On login
await userService.login(email);
final profile = await userService.getUserProfile();

// Store in provider/state
final userProvider = Provider.of<UserProvider>(context);
userProvider.setUser(profile.userId, profile.name);

// All subsequent API calls automatically include user_id
await userService.getUserBots(); // Calls /api/user/{userId}/bots
```

---

## ⏳ Phase 7: Broker Account Integration (PENDING)

### MT5 Connection Per User
**Status:** 🟠 NOT STARTED
**Current Issue:** All users connect to demo MT5_CONFIG

**Required Changes:**
1. Query broker_credentials for user
2. Use user's account_number and password
3. Connect to user's specified server
4. Store account connection status
5. Fall back to demo if credentials invalid

**Implementation:**
```python
def get_user_broker_config(user_id):
    cursor.execute(
        '''SELECT account_number, password, server, is_live 
           FROM broker_credentials 
           WHERE user_id = ? AND is_active = 1 
           LIMIT 1''',
        (user_id,)
    )
    config = cursor.fetchone()
    
    if config:
        return {
            'account': config[0],
            'password': config[1],
            'server': config[2],
            'is_live': config[3]
        }
    else:
        return MT5_CONFIG  # Demo fallback
```

---

## 📋 Testing Checklist

### Unit Tests
- [ ] Register 2 different users
- [ ] Login each user separately
- [ ] Verify each user gets different session token
- [ ] Create bot for user 1
- [ ] Verify user 1 sees the bot
- [ ] Verify user 2 does NOT see the bot
- [ ] Add broker credentials for user 1
- [ ] Verify user 2 cannot see user 1's brokers
- [ ] Delete bot as user 1
- [ ] Verify bot deleted from user 1's list

### Integration Tests
- [ ] Multi-user simultaneous login
- [ ] One user creating bot while another accesses profile
- [ ] Bot operations with wrong user_id (should fail)
- [ ] Session expiration handling
- [ ] Database consistency after operations

### End-to-End Tests
- [ ] Complete user registration flow
- [ ] Complete login -> broker setup -> bot creation flow
- [ ] Verify Flutter app shows correct data for each user
- [ ] Verify bot operations work correctly
- [ ] Verify no data leakage between users

---

## 🐛 Debugging Guide

### User Seeing Other User's Bots
1. Check user_bots table: `SELECT * FROM user_bots WHERE bot_id = ?`
2. Verify bot has correct user_id
3. Check /api/bot/status endpoint is filtering by user_id
4. Check frontend is sending correct user_id

### Bot Operations Failing
1. Verify user_id is correct
2. Check bot_id is in user_bots table for that user
3. Verify session token is active
4. Check user_sessions table for active session

### Login Not Working
1. Check users table has the email
2. Verify email field exactly matches
3. Check user_sessions table has token entry
4. Verify token not expired

---

## 📊 SQL Verification Queries

```sql
-- Check all users and their bot count
SELECT u.user_id, u.email, COUNT(b.bot_id) as bot_count
FROM users u
LEFT JOIN user_bots b ON u.user_id = b.user_id
GROUP BY u.user_id;

-- Check all active sessions
SELECT s.session_id, u.email, s.expires_at, s.is_active
FROM user_sessions s
JOIN users u ON s.user_id = u.user_id
WHERE s.is_active = 1;

-- Check broker credentials per user
SELECT u.email, COUNT(bc.credential_id) as broker_count
FROM users u
LEFT JOIN broker_credentials bc ON u.user_id = bc.user_id
WHERE bc.is_active = 1
GROUP BY u.user_id;

-- Find orphaned bots (no user)
SELECT * FROM user_bots WHERE user_id NOT IN (SELECT user_id FROM users);

-- Check for duplicate session tokens (shouldn't happen)
SELECT token, COUNT(*) as count FROM user_sessions GROUP BY token HAVING count > 1;
```

---

## 🚀 Deployment Checklist

Before deploying to production:
- [ ] All Phase 4 endpoints updated with user_id verification
- [ ] Phase 5 session middleware implemented
- [ ] Phase 6 frontend integration complete
- [ ] All tests passing
- [ ] Database backups created
- [ ] SQL migration tested in staging
- [ ] No console errors in Flutter app
- [ ] Session tokens properly encrypted
- [ ] Broker passwords encrypted in database
- [ ] API rate limiting implemented per user

---

## 📞 Common Issues & Solutions

### "User sees anoth user's bots"
**Solution:** Check /api/user/<user_id>/bots endpoint is filtering by user_id

### "Bot stays in active state after deletion"
**Solution:** Remove from both user_bots table AND active_bots dictionary

### "Session token not working"
**Solution:** Verify token is being sent in X-Session-Token header and not expired

### "Broker credentials not visible"
**Solution:** Check is_active = 1 in broker_credentials table

---

**Version:** 1.0
**Last Updated:** March 2026
**Overall Progress:** 60% Complete (Phases 1-3 done, Phases 4-7 pending)
