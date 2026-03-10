# Zwesta Trading System - Proper Broker Integration Flow

## Overview

The Zwesta Trading System now implements a **proper multi-tenant architecture** where:

1. **User registers** → Gets referral code
2. **User integrates broker** → Saves broker credentials securely
3. **User creates bot** → Bot linked to specific broker credential
4. **Bot trades** → Commissions tracked per bot
5. **Commissions earned** → Distributed to user and referrer

## Architecture Diagram

```
┌─────────────────┐
│  User Registers │ → Generates referral_code (e.g., "ABC12345")
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│ Broker Integration Screen   │
│ User selects:               │
│ - Broker (XM, Pepperstone)  │
│ - Account Type (DEMO/LIVE)  │
│ - Credentials               │
│ - Tests Connection          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ credential_id created & stored  │
│ in broker_credentials table     │
│ User can have MULTIPLE          │
│ credentials (multi-account)     │
└────────┬────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Bot Configuration Screen         │
│ User creates bot with:           │
│ - Symbol selection               │
│ - Strategy                       │
│ - Risk parameters                │
│ - Links to credential_id         │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Bot Created & Started            │
│ Linked to credential_id          │
│ Commission tracking enabled      │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Bot Executes Trades              │
│ Each trade generates:            │
│ - Profit/Loss                    │
│ - Commission (5% of profit)      │
│ - Referral commission (if exists)│
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ Commissions Distributed          │
│ - Primary: Bot owner             │
│ - Secondary: Referrer (if any)   │
│ Tracked in commissions table     │
└──────────────────────────────────┘
```

## Database Schema

### broker_credentials table
```sql
credential_id      TEXT PRIMARY KEY
user_id            TEXT FOREIGN KEY → users.user_id
broker_name        TEXT (e.g., "XM", "Pepperstone")
account_number     TEXT (MT5 account #)
password           TEXT (encrypted in production)
server             TEXT (MT5 server)
is_live            BOOLEAN (0=DEMO, 1=LIVE)
is_active          BOOLEAN
created_at         TEXT (ISO format)
updated_at         TEXT (ISO format)
```

### bot_credentials table (Links bots to credentials)
```sql
bot_id             TEXT FOREIGN KEY → user_bots.bot_id
credential_id      TEXT FOREIGN KEY → broker_credentials.credential_id
user_id            TEXT FOREIGN KEY → users.user_id
created_at         TEXT
PRIMARY KEY (bot_id, credential_id)
```

### commissions table (Tracks earnings)
```sql
commission_id      TEXT PRIMARY KEY
earner_id          TEXT FOREIGN KEY → users.user_id
client_id          TEXT FOREIGN KEY → users.user_id (who was referred)
bot_id             TEXT FOREIGN KEY → user_bots.bot_id
profit_amount      REAL (from trade)
commission_rate    REAL (0.05 = 5%)
commission_amount  REAL (calculated)
created_at         TEXT
```

### referrals table (Tracks referrer-referred relationships)
```sql
referral_id        TEXT PRIMARY KEY
referrer_id        TEXT FOREIGN KEY → users.user_id
referred_user_id   TEXT FOREIGN KEY → users.user_id
created_at         TEXT
status             TEXT ('active', 'inactive')
```

## API Endpoints

### Authentication ✅ (Existing)
- `POST /api/user/login` → Returns session_token
- `POST /api/user/register` → Returns referral_code

### Broker Credentials 🆕
- `GET /api/broker/credentials` → List all user's credentials
- `POST /api/broker/credentials` → Save new credential
- `DELETE /api/broker/credentials/{id}` → Delete credential
- `POST /api/broker/test-connection` → Test broker connection

### Bot Management ✅ (Updated)
- `POST /api/bot/create` → NOW REQUIRES credential_id
- `POST /api/bot/start` → Start bot trading
- `GET /api/bot/list` → List user's bots

### Commission Tracking 🆕
- `GET /api/user/commissions` → Get commission history, stats
- `GET /api/user/referral-commissions` → Get referral earnings
- `POST /api/user/commission-withdrawal` → Request withdrawal

## Flutter Services

### AuthService (Existing)
- Handles login/register
- Saves session_token to SharedPreferences
- Provides isLoggedIn state

### BrokerCredentialsService (New)
```dart
// Load credentials from backend
await brokerService.fetchCredentials();

// Save new credential
bool success = await brokerService.saveCredential(
  broker: 'XM',
  accountNumber: '104017418',
  password: '*****',
  server: 'MetaQuotes-Demo',
  isLive: false,
);

// Test connection
bool connected = await brokerService.testConnection(...);

// Set active credential
brokerService.setActiveCredential(credential);

// Access
List<BrokerCredential> credentials = brokerService.credentials;
BrokerCredential? active = brokerService.activeCredential;
bool hasCredentials = brokerService.hasCredentials;
```

### CommissionService (New)
```dart
// Load commission data
await commissionService.fetchCommissions();

// Get stats
CommissionStats? stats = commissionService.stats;
// stats.totalEarned
// stats.totalPending
// stats.tradeCommissions
// stats.referralCommissions

// Get history
List<Commission> commissions = commissionService.commissions;

// Get specific commissions
List<Commission> tradeComms = commissionService.getCommissionsBySource('trade');
List<Commission> botComms = commissionService.getCommissionsForBot(botId);

// Request withdrawal
bool success = await commissionService.requestWithdrawal(100.00);
```

### BotService (Updated)
```dart
// Now handles credential linking
final sessionToken = prefs.getString('auth_token');
final credentialId = brokerService.activeCredential?.credentialId;

// Bot creation includes credential_id
await http.post('/api/bot/create',
  body: jsonEncode({
    'botId': botId,
    'credentialId': credentialId,  // ✅ From broker integration
    'symbols': symbols,
    'strategy': strategy,
    'riskPerTrade': risk,
    'maxDailyLoss': max,
  }),
);
```

## User Flow - Step by Step

### 1. **User Registration**
```
User enters email, password, name
↓
Backend generates unique referral_code
↓
User can share referral_code with others
↓
When others register with code: user becomes re eferrer
```

**Database:**
- New row in `users` table with `referral_code`
- If referral_code provided: new row in `referrals` table

### 2. **Broker Integration**
```
User: "Connect my broker account"
↓
BrokerIntegrationScreen: User selects broker, account type
↓
User enters: Account Number, Password, Server
↓
App tests connection: POST /api/broker/test-connection
↓
If successful: POST /api/broker/credentials (saves credential)
↓
Backend: Creates broker_credentials record, returns credential_id
↓
App: credential_id → SharedPreferences (for next step)
```

**Database:**
- New row in `broker_credentials` table with credential_id
- User can repeat to add multiple accounts

### 3. **Bot Creation**
```
User: "Create bot with these settings"
↓
BotConfigurationScreen: Check hasCredentials
↓
If NO: Show dialog "Setup broker first" → Redirect to broker integration
↓
If YES: Show active credential info:
  Broker: XM
  Account: 104017418
  Mode: LIVE
↓
User selects symbols, strategy, risk parameters
↓
User clicks "Create & Start Bot"
↓
App: POST /api/bot/create with:
  - credentialId (from broker integration)
  - symbols, strategy, risk parameters
  - X-Session-Token header (authentication)
↓
Backend: 
  - Verify credentialId belongs to user
  - Create bot record in user_bots
  - Link bot→credential in bot_credentials
  - Add to active_bots for trading
↓
Success: Bot starts trading with verified credentials
```

**Database:**
- New row in `user_bots` table
- New row in `bot_credentials` linking bot→credential

### 4. **Trading & Commission Generation**
```
Bot executes trade:
- Entry: BUY 1 EURUSD at 1.0850
- Exit: SELL 1 EURUSD at 1.0890
- Profit: $40
↓
Commission calculation:
- Commission Rate: 5% of profit
- Commission: $40 × 0.05 = $2.00
↓
Check if user has referrer:
- If YES: Split commission (50% each)
  - User: $1.00
  - Referrer: $1.00
- If NO: User gets full $2.00
↓
Database: Insert two commission records (if referred):
  1. earner_id=user_id, client_id=user_id, amount=$1.00
  2. earner_id=referrer_id, client_id=user_id, amount=$1.00
```

**Database:**
- New rows in `commissions` table
- For each trade: commission_id, earner_id, bot_id, profit_amount, commission_amount

### 5. **Commission Withdrawal**
```
User: "Withdraw $100 commission"
↓
CommissionDashboard: Show total_earned, total_pending, total_withdrawn
↓
User: "Request Withdrawal" → $100
↓
App: POST /api/user/commission-withdrawal with amount
↓
Backend:
  - Check available balance
  - Create commission_withdrawals record with status='pending'
  - Email notification to admin
↓
Admin: Reviews and processes withdrawal (usually 3-5 business days)
↓
User: Receives funds
```

**Database:**
- New row in `commission_withdrawals` table
- Status: pending → completed

## Multi-Account Support

Users can have MULTIPLE broker credentials:

```dart
// BrokerCredentialsService
List<BrokerCredential> credentials = brokerService.credentials;
// [
//   { credential_id: "abc-123", broker: "XM", account: "1000", is_live: false },
//   { credential_id: "def-456", broker: "Pepperstone", account: "2000", is_live: true },
//   { credential_id: "ghi-789", broker: "FxOpen", account: "3000", is_live: false }
// ]

// Set which one to use for bot creation
brokerService.setActiveCredential(credentials[1]);  // Use Pepperstone

// Create bot with active credential
```

Each bot is linked to ONE credential via `bot_credentials` table.

## Security Considerations

✅ **Session-based authentication:**
- Every API call requires `X-Session-Token` header
- Token validated in `@require_session` decorator
- Session expires after 30 days

✅ **Credentials isolation:**
- User can only access their own credentials
- Backend verifies credential→user relationship
- Password never returned in API responses

✅ **Commission tracking:**
- Only authenticated users can request their commissions
- Commissions tagged with bot_id for audit trail
- Withdrawal history tracked with timestamps

❌ **Production TODO:**
- Encrypt passwords in broker_credentials table (use encryption library)
- Use environment variables for sensitive config
- Implement rate limiting on credential endpoints
- Add audit logging for all credential operations
- Implement IP whitelisting for MT5 connections

## Testing Checklist

- [ ] User registration creates referral_code ✅
- [ ] Register with referral_code creates referral record
- [ ] Broker integration saves credentials
- [ ] Test connection validates credentials
- [ ] Bot creation requires credential_id
- [ ] Bot shows broker info in success message
- [ ] Commission calculation works (5% of profit)
- [ ] Referral commission splits correctly (50/50)
- [ ] Commission withdrawal request works
- [ ] User can have multiple credentials
- [ ] User can delete old credentials
- [ ] Switching active credential works
- [ ] Bot trades use correct credential's account

## Next Steps

1. **Test the flow end-to-end:**
   - Register user with referral code
   - Integrate broker account
   - Create bot
   - Generate test trades
   - Verify commissions created

2. **Add referral commission distribution:**
   - When bot owned by referred_user trades
   - Calculate referrer commission
   - Insert into commissions table

3. **Create commission dashboard:**
   - Show total earned, pending, withdrawn
   - Show commission history
   - Allow withdrawal requests

4. **Production hardening:**
   - Encrypt credentials
   - Add rate limiting
   - Implement audit logging
   - Add IP whitelisting
