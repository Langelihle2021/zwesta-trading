# 🔐 Multi-User Credential Management Guide

## Overview

Your Zwesta Trading System supports **unlimited users** with their own isolated credentials and trading bots. Each user:
- Has their own username/password
- Can add multiple broker credentials (Exness, Binance, etc.)
- Can create multiple trading bots
- Cannot see others' data (complete isolation)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ZWESTA DATABASE                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  User 1 (You)                                            │
│  ├─ Credentials: Exness #298997455 (Demo + Live)        │
│  ├─ Bots: demo_btc_test_001, eth_trader_001             │
│  └─ Trades: All isolated, user can see all              │
│                                                           │
│  User 2 (Customer A)                                     │
│  ├─ Credentials: Their Exness account #12345            │
│  ├─ Bots: Their own bots only                           │
│  └─ Trades: Their own trades only (CANNOT see User 1)   │
│                                                           │
│  User 3 (Customer B)                                     │
│  ├─ Credentials: Their Binance keys                     │
│  ├─ Bots: Their own bots                                │
│  └─ Trades: Their own trades (CANNOT see others)        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Step 1: Add New User (Customer)

### **Method A: Via Flutter App (Recommended)**
1. Open the app → Sign Up
2. Customer creates own account with email + password
3. Their credentials stored securely in database
4. They log in and add their broker credentials

### **Method B: Programmatically (Admin)**

Create `add_customer.py`:

```python
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = r"C:\backend\zwesta_trading.db"

def add_customer(email, first_name, last_name, password):
    """Add a new customer"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Generate secure password hash
    password_hash = generate_password_hash(password)
    
    # User ID based on email
    user_id = f"user_{email.split('@')[0]}_{int(time.time())}"
    
    cursor.execute('''
        INSERT INTO users (user_id, email, first_name, last_name, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, email, first_name, last_name, password_hash, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created user: {email}")
    return user_id
```

---

## Step 2: Customer Adds Their Broker Credentials

### **API Endpoint**: `POST /api/broker/credentials`

```javascript
// Flutter/App Usage
const response = await fetch('http://localhost:9000/api/broker/credentials', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Session-Token': sessionToken, // Their auth token
  },
  body: JSON.stringify({
    broker: 'Exness',
    account_number: '12345678',
    password: 'their_trading_password',
    server: 'Exness-Real', // or 'Exness-MT5Trial9' for demo
    is_live: true, // false for demo
  })
});
```

**Response**:
```json
{
  "success": true,
  "credential_id": "cred_user_exness_live_001",
  "message": "Credentials added successfully"
}
```

---

## Step 3: Customer Creates Their Trading Bot

### **API Endpoint**: `POST /api/bot/create`

```javascript
const response = await fetch('http://localhost:9000/api/bot/create', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Session-Token': sessionToken,
  },
  body: JSON.stringify({
    bot_name: 'My BTC Trader',
    broker_credential_id: 'cred_user_exness_live_001',
    symbols: ['BTCUSDm', 'ETHUSDm'],
    strategy: 'signal-based',
    risk_per_trade: 2.0, // 2% of balance per trade
    take_profit: 100,
    stop_loss: 50,
  })
});
```

---

## Current Demo Setup

### **Your Demo Bot (Already Created)**

```
User: user_demo_1 (Demo User)
Email: demo@test.com

Credentials:
├─ ID: cred_demo_exness_btc
├─ Broker: Exness
├─ Account: 298997455
├─ Server: Exness-MT5Trial9 (Demo)
└─ Is Live: NO

Bot:
├─ ID: demo_btc_test_001
├─ Name: Demo BTC Test
├─ Symbol: BTCUSDm
├─ Status: Ready to start
└─ Takes profit at $100, stops at $50 loss
```

---

## Step 4: Moving to Real Money

### **For You (Demo → Live)**

1. **Create Live Credentials** in your Exness account
   ```
   Account: Your Live Account #XXXXX
   Password: Your trading password
   Server: Exness-Real (NOT Trial)
   ```

2. **Add to Backend** via Flutter app or API:
   ```json
   {
     "broker": "Exness",
     "account_number": "YOUR_LIVE_ACCOUNT",
     "password": "YOUR_PASSWORD",
     "server": "Exness-Real",
     "is_live": true
   }
   ```

3. **Create Live Bot** using that credential
   - Start small (0.01 lots = ~$50 per trade)
   - Monitor for 24 hours before scaling up

### **For Your Customers**

1. You send them a **sign-up link**
2. They create account in your Flutter app
3. They add their own broker credentials
4. They create bots with their money
5. **You take commission** (if implemented)

---

## Data Isolation & Security

### ✅ What Each User Can See

- ✅ Their own credentials
- ✅ Their own bots
- ✅ Their own trades
- ✅ Their own account balance
- ✅ Their own performance stats

### ❌ What Users CANNOT See

- ❌ Other users' credentials
- ❌ Other users' bots
- ❌ Other users' trades
- ❌ Other users' balances
- ❌ Other users' profits/losses

**Enforcement**: Backend checks `user_id` on EVERY API call. If user_id doesn't match, request is rejected.

---

## API Routes for User Management

| Endpoint | Method | Purpose | Auth? |
|----------|--------|---------|-------|
| `/api/auth/register` | POST | Create new user account | ❌ No |
| `/api/auth/login` | POST | User login | ❌ No |
| `/api/broker/credentials` | POST | Add broker credentials | ✅ Yes |
| `/api/broker/credentials/list` | GET | List user's credentials | ✅ Yes |
| `/api/bot/create` | POST | Create new bot | ✅ Yes |
| `/api/bot/list` | GET | List user's bots | ✅ Yes |
| `/api/trades` | GET | Get user's trades | ✅ Yes |
| `/api/account/info` | GET | Get user's account info | ✅ Yes |

---

## Next Steps

1. ✅ **Demo bot created** - You can test now
2. 🔄 **Add real money** - Create live Exness account with R100
3. 📱 **Flutter app** - Download and test with demo first
4. 👥 **Add customers** - They sign up and link their accounts
5. 💰 **Scale up** - Monitor live trading and increase bot activity

---

## Testing Checklist

- [ ] Backend running on http://localhost:9000
- [ ] Database has demo bot (demo_btc_test_001)
- [ ] Flutter app can display live positions
- [ ] Flutter app can connect to backend
- [ ] Demo bot can trade (watch logs)
- [ ] P&L updates in real-time
- [ ] Multiple users can coexist (no data leakage)

---

## Security Notes

1. **Passwords**: Never hardcode them. Use environment variables or secure input.
2. **Sessions**: Each user gets a session token (JWT/custom). Token expires after 24 hours.
3. **Audit Logs**: Every trade is logged with user_id + timestamp
4. **Isolation**: Database enforces user_id on every query

---

## Example: Adding Customer "Alice"

```python
# Backend adds Alice
add_customer('alice@example.com', 'Alice', 'Smith', 'alice_password_123')
# → Creates user_id: user_alice_1234567890

# Alice logs in (via Flutter app)
# → Gets session token

# Alice adds her Exness account
POST /api/broker/credentials
{
  "broker": "Exness",
  "account_number": "555666777",
  "password": "alice_trading_pwd",
  "server": "Exness-Real",
  "is_live": true
}

# Alice creates a bot
POST /api/bot/create
{
  "bot_name": "Alice's BTC Bot",
  "broker_credential_id": "cred_user_alice_exness_001",
  "symbols": ["BTCUSDm"],
  "risk_per_trade": 1.0
}

# Alice's bot starts trading with HER money
# Alice sees HER trades, HER balance, HER profits
# You see Alice's account in admin dashboard
# Alice CANNOT see other users' data
```

---

**Ready to test? Follow the checklist and let me know when you're ready to add customers!** 🚀
