# Multi-User, Multi-Broker Trading System Guide 🚀

## Complete System Architecture

This Flutter application now supports a **complete multi-tenant, multi-broker trading platform** where each user can:

1. ✅ Register with email and password
2. ✅ Add multiple broker credentials (MetaQuotes, FxOpen, etc.)
3. ✅ Create trading bots using ANY of their brokers
4. ✅ View personal trading dashboard with comprehensive statistics
5. ✅ Track earnings and commissions
6. ✅ Switch assets intelligently based on profitability
7. ✅ Earn referral commissions (15% on friends' trades)

---

## 🔐 User Authentication & Registration

### Getting Started

1. **Launch the app**
   - You'll see the login screen
   - Click "Don't have an account? Register here"

2. **Registration Form**
   ```
   Email: your@email.com
   Name: Your Full Name
   Password: Strong password (min 8 chars)
   
   Optional:
   Referrer Code: (Friend's referral code - to earn them commission)
   ```

3. **After Registration**
   - You'll receive a **unique Referral Code** (share with friends!)
   - Your **User ID** is stored in the system
   - Your account is isolated and secure

### Login
- Email and password for existing users
- Session token is stored locally (30-day validity)
- Each user sees ONLY their own data

---

## 💼 Multi-Broker Management

### Add Your First Broker

1. **From Dashboard → Menu → "Multi-Broker Management"**

2. **Fill in Broker Details:**
   ```
   Broker Name: MetaQuotes
   Account Number: 104254514
   Password: Your MT5 password
   Server: MetaQuotes-Demo (or MetaQuotes-Live)
   
   ☐ Live Account (check if REAL money trading)
   ```

3. **Click "Add Broker"**
   - Credential stored securely in database
   - Multiple brokers can be added
   - Each broker maintains separate trading activity

### Supported Brokers
- MetaQuotes (Demo & Live)
- FxOpen
- Saxo Bank
- Interactive Brokers
- Any MT5-compatible broker

### Managing Brokers
- View all your added brokers
- Delete a broker credential (removes from storage)
- Multiple brokers allow parallel trading
- Each bot uses a SPECIFIC broker

---

## 🤖 Creating Multi-Broker Bots

### Start a Trading Bot

1. **Dashboard → Bot Configuration**

2. **Bot Setup Form:**
   ```
   Bot Name: My Gold Trading Bot
   Strategy: Signal-based (6-tier EMO)
   
   📌 SELECT BROKER (NEW!)
      Choose one of your added brokers
      Bot will trade using THIS broker's account
   
   SELECT SYMBOLS:
      Gold (XAUUSD)
      Silver (XAGUSD)
      Or any of 27 available symbols
   
   Click: START BOT
   ```

3. **Bot Behavior:**
   - ✅ Uses REAL MT5 trading (no simulation)
   - ✅ Places live orders on selected broker
   - ✅ Tracks profits per broker
   - ✅ Records all trades in your personal database

---

## 📊 Trading Dashboard (Enhanced)

### View Your Statistics

**Menu → Trading Dashboard**

Shows your complete trading profile:

#### User Info Card
```
Name: Your Name
Email: your@email.com
Member Since: 2024-01-15
User ID: 42
```

#### Performance Stats (Grid)
```
┌─────────────┬─────────────┐
│ Active Bots │ Total Bots  │
│      2      │      5      │
├─────────────┼─────────────┤
│Total Profit │ Total Trades│
│  +$5,234.50 │     324     │
├─────────────┼─────────────┤
│  Win Rate   │  Brokers    │
│    68%      │      3      │
└─────────────┴─────────────┘
```

#### Performance Overview
- **Total Profit**: Sum of all trades across all bots
- **Commission Earned**: 15% from referrals + platform fees
- **Avg Profit/Trade**: Total Profit / Total Trades

#### Top Performing Bots
```
#1 Gold Trading Bot     +$2,145.75
#2 Forex Pair Bot       +$1,856.20
#3 Indices Bot          +$1,232.55
```

#### Commission Summary
```
Total Commissions: $1,450.00
This Month: $340.00

💡 Tip: Share your referral code to earn 15% 
        commission on friends' trades!
```

---

## 🌟 27 Available Trading Symbols

### Forex (9 symbols)
- EURUSD - Euro/US Dollar
- GBPUSD - British Pound/US Dollar
- USDJPY - US Dollar/Japanese Yen
- AUDUSD - Australian Dollar/US Dollar
- NZDUSD - New Zealand Dollar/US Dollar
- USDCAD - US Dollar/Canadian Dollar
- USDCHF - US Dollar/Swiss Franc
- EURJPY - Euro/Japanese Yen
- GBPJPY - British Pound/Japanese Yen

### Precious Metals (4 symbols)
- **XAUUSD** - Gold (most popular!)
- **XAGUSD** - Silver
- **XPDUSD** - Palladium
- **XPTUSD** - Platinum

### Energy (2 symbols)
- **NATGAS** - Natural Gas
- **CRUDE** - Crude Oil

### Indices (4 symbols)
- **US500** - S&P 500 (USA 500 companies)
- **US100** - NASDAQ 100 (Tech stocks)
- **US30** - Dow Jones 30
- **VIX** - Volatility Index

### Stocks (5 symbols)
- **AAPL** - Apple
- **MSFT** - Microsoft
- **GOOGL** - Google
- **AMZN** - Amazon
- **TSLA** - Tesla

---

## 🎯 Intelligent Asset Switching

### How It Works

The system automatically evaluates which symbols are most profitable and can update your bot's trading assets.

### Using Intelligent Switch

1. **From Mobile App:** Dashboard → Tap "Intelligent Switch" button
2. **Or via API:** `POST /api/trading/intelligent-switch`

3. **System Analyzes:**
   - Win rate for each symbol
   - Average profit per trade
   - Trading frequency
   - Recent performance (last 30 days)

4. **Results:**
   ```
   PREVIOUS SYMBOLS:
   EURUSD, GBPUSD, AUDUSD
   
   TOP 5 MOST PROFITABLE:
   1. XAUUSD (Gold) - 72% win rate
   2. US500 (S&P 500) - 68% win rate
   3. XAGUSD (Silver) - 65% win rate
   4. NATGAS - 62% win rate
   5. MSFT - 60% win rate
   
   ✅ SWITCHED: Bot now trades these 5 assets
   ```

---

## 💰 Commission & Referral System

### How You Earn Money

#### Method 1: Referral Commission (15% for life!)
```
You invite friend → Friend registers with YOUR referral code
↓
Friend trades and makes $1000 profit
↓
You earn 15% = $150 (automatically!)
↓
Can withdraw earned commissions to account
```

#### Method 2: Platform Fee
```
Your bots execute trades
↓
System charges 2% commission on profits
↓
Credited to your account (displayed in dashboard)
```

### Viewing Commissions

**Dashboard → Commission Summary**
```
Total Commissions: $2,450.00
This Month: $580.00
This Year: $5,234.00

Recent Commissions:
- Friend John: +$85.50 (3 days ago)
- Friend Mary: +$120.75 (1 week ago)
- Bot Profit Fee: +$45.00 (today)
```

### Share Your Referral Code

1. Go to: **Menu → My Referrals**
2. Your unique code: `USER_42_ABC123XYZ`
3. Share with friends via:
   - WhatsApp
   - Email
   - Social Media
4. They use code during registration
5. You earn 15% commission on their trades!

---

## 🔒 Data Isolation & Security

### Multi-Tenant Architecture

Each user's data is 100% isolated:

| User A | User B | User C |
|--------|--------|--------|
| 3 bots | 5 bots | 2 bots |
| 450 trades | 320 trades | 180 trades |
| $5,234 profit | $3,120 profit | $2,450 profit |
| **CANNOT SEE B,C** | **CANNOT SEE A,C** | **CANNOT SEE A,B** |

### Security Features
- ✅ Session token authentication
- ✅ Per-endpoint user verification
- ✅ Database user_id filtering
- ✅ Encrypted broker credentials
- ✅ No cross-user data leakage

---

## 🛠️ Technical Implementation

### API Endpoints for Multi-User Support

#### User Management
```
POST /api/user/register
  - Create new account
  - Generate referral code
  - Link to referrer (if code provided)

GET /api/user/dashboard
  - Personal stats and metrics
  - Top performing bots
  - Commission summary
```

#### Broker Management
```
GET /api/user/brokers
  - List all user's broker credentials
  
POST /api/user/brokers/add
  - Add new broker credential
  - Validate account details
  
DELETE /api/user/brokers/<credential_id>
  - Remove broker credential
```

#### Trading Features
```
GET /api/trades
  - Get YOUR bots' trades (user_id filtered)
  
GET /api/bot/status
  - Get YOUR bots only
  - Status: RUNNING, STOPPED, ERROR
  
POST /api/trading/intelligent-switch
  - Analyze profitability
  - Update bot symbols
  
GET /api/user/commission-summary
  - Earn tracking
```

### Database Schema

```sql
users:
  user_id (PRIMARY)
  email (UNIQUE)
  name
  referrer_id (FK users)
  referral_code (UNIQUE)
  total_commission

broker_credentials:
  credential_id (PRIMARY)
  user_id (FK users)
  broker_name
  account_number
  password (encrypted)
  is_live
  created_at

user_bots:
  bot_id (PRIMARY)
  user_id (FK users)
  credential_id (FK broker_credentials)
  name
  strategy
  symbols (JSON)
  status

trades:
  trade_id (PRIMARY)
  user_id (FK users)
  bot_id (FK user_bots)
  entry_price
  exit_price
  profit_loss
  timestamp

commissions:
  commission_id (PRIMARY)
  earner_id (FK users)
  client_id (FK users)
  amount
  type ('referral', 'platform_fee')
  timestamp
```

---

## 🎯 Quick Start Checklist

- [ ] **Register**: Sign up with email & password
- [ ] **Add Broker**: Menu → Multi-Broker Management → Add first broker
- [ ] **Create Bot**: Dashboard → Bot Configuration → Select broker & symbols
- [ ] **View Dashboard**: Menu → Trading Dashboard → See your stats
- [ ] **Share Referral**: Menu → My Referrals → Copy your code
- [ ] **Invite Friends**: Send them your referral code
- [ ] **Earn Money**: Watch referral commissions accumulate!

---

## ⚠️ Important Notes

1. **Real Trading Only**
   - System now enforces REAL MT5 trading
   - No simulation fallback
   - Returns HTTP 503 if MT5 unavailable
   - Always verify broker credentials are correct

2. **Password Security**
   - Never share your broker password
   - System encrypts passwords in database
   - Only use official app (no APKs from third parties)

3. **Broker accounts**
   - Verify you have account on selected broker
   - Use correct server name (MetaQuotes-Demo vs Live)
   - Check account is active and funded

4. **Profit Calculations**
   - Profits shown are after all fees
   - Commission calculated separately
   - Daily resets on some demo accounts

5. **API Updates**
   - Dashboard refreshes every 10 seconds
   - Trades record in real-time
   - Commissions updated hourly

---

## 🤝 Getting Help

### Common Issues

**Q: "CRITICAL: Failed to connect to MT5"**
A: Your broker password is wrong or MT5 server is offline. Check:
   - Correct account number
   - Correct password
   - Correct server name
   - Internet connection

**Q: Can't see my bot's trades?**
A: Wait 5-10 seconds for MT5 to process. Trades show with 1-2 second delay.

**Q: Broker credential not working?**
A: Verify account is:
   - Not locked due to failed login attempts
   - Has sufficient margin for trading
   - Active on the broker's platform

**Q: How do I get my referral code?**
A: Menu → My Referrals (top of dashboard)

**Q: When do I earn commission?**
A: 
   - Immediately when friend registers with YOUR code
   - Friend's trades trigger commissions
   - Paid daily, accumulated in account

---

## 📈 Advanced Features (Future)

- [ ] Auto-switching assets every 5-15 minutes
- [ ] Risk-based position sizing
- [ ] Profit threshold triggers
- [ ] Historical performance tracking
- [ ] Commission withdrawal requests
- [ ] Two-factor authentication
- [ ] Automated broker switching
- [ ] Advanced charting & analysis

---

## Support & Feedback

For issues or feature requests:
1. Check the logs in the app → Settings
2. Report via the app's feedback button
3. Contact: support@zwesta.com

---

**System Version**: 2.0 (Multi-Broker, Multi-User)  
**Last Updated**: 2024-01-15  
**Backend**: Python Flask + SQLite  
**Frontend**: Flutter (Cross-platform)

🚀 Ready to trade across multiple brokers with multiple users? Start now!
