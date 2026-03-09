# Zwesta Trading - Referral & Commission System

## Overview
A complete multi-level referral system with commission tracking and earnings dashboard. No upfront payment required from clients - Zwesta takes 30% commission from bot profits and distributes 5% to referrers.

---

## 🎯 Commission Structure

### Revenue Breakdown (Per Client Profit)
```
Client Bot Profit: $100
├─ 5% → Referrer (who recruited): $5
├─ 25% → Zwesta (company): $25
└─ 70% → Client keeps: $70
```

### Multi-Level Example
```
You (Level 1)
├─ Recruit: Alice → You earn 5% of Alice's bot profits
│  └─ Alice recruits Bob → Alice earns 5% of Bob's profits (separate from your 5%)
├─ Recruit: Charlie → You earn 5% of Charlie's bot profits
└─ Recruit: Diana → You earn 5% of Diana's bot profits
```

---

## 📲 Flutter Integration

### Two New Screens

#### 1. **Join with Referral Screen** (`join_with_referral_screen.dart`)
- New user registration with optional referral code
- Benefits highlight: Free to start, 5% earnings
- Validates referral codes in real-time
- Shows referrer name when code is valid

**Navigation:**
```dart
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const JoinWithReferralScreen()),
);
```

#### 2. **Referral Dashboard Screen** (`referral_dashboard_screen.dart`)
- Display unique referral code
- Share referral code via clipboard
- Show all recruited members
- Earnings summary:
  - Total earned from referrals
  - Active client count
  - Transaction count
  - Recent earnings history

**Navigation:**
```dart
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => ReferralDashboardScreen(userId: currentUserId),
  ),
);
```

---

## 🔌 Backend API Endpoints

### 1. Register User with Referral
**POST** `/api/user/register`

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "referral_code": "ABC123XY"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-string",
  "referral_code": "XY1A2B3C",
  "referrer_id": "uuid-string-of-referrer",
  "message": "User registered successfully"
}
```

### 2. Get User Recruits
**GET** `/api/user/{user_id}/recruits`

**Response:**
```json
{
  "success": true,
  "recruits": [
    {
      "user_id": "uuid",
      "email": "recruit@example.com",
      "name": "Alice",
      "created_at": "2026-03-09T...",
      "total_commission": 45.50
    }
  ],
  "total_recruits": 3
}
```

### 3. Get Earnings Summary
**GET** `/api/user/{user_id}/earnings`

**Response:**
```json
{
  "success": true,
  "referral_code": "ABC123XY",
  "total_commission": 250.75,
  "total_clients": 5,
  "total_earned": 250.75,
  "total_transactions": 18,
  "recent_earnings": [
    {
      "commission_amount": 15.50,
      "created_at": "2026-03-09T...",
      "name": "Alice"
    }
  ]
}
```

### 4. Validate Referral Code
**GET** `/api/referral/validate/{code}`

**Response (Valid):**
```json
{
  "success": true,
  "valid": true,
  "referrer_name": "John Doe",
  "referrer_email": "john@example.com"
}
```

**Response (Invalid):**
```json
{
  "success": true,
  "valid": false,
  "message": "Referral code not found"
}
```

---

## 💾 Database Schema

### Users Table
```sql
CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  referrer_id TEXT,
  referral_code TEXT UNIQUE,
  created_at TEXT,
  total_commission REAL DEFAULT 0,
  FOREIGN KEY (referrer_id) REFERENCES users(user_id)
)
```

### Commissions Table
```sql
CREATE TABLE commissions (
  commission_id TEXT PRIMARY KEY,
  earner_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  bot_id TEXT,
  profit_amount REAL,
  commission_rate REAL DEFAULT 0.05,
  commission_amount REAL,
  created_at TEXT,
  FOREIGN KEY (earner_id) REFERENCES users(user_id),
  FOREIGN KEY (client_id) REFERENCES users(user_id)
)
```

### Referrals Table
```sql
CREATE TABLE referrals (
  referral_id TEXT PRIMARY KEY,
  referrer_id TEXT NOT NULL,
  referred_user_id TEXT NOT NULL,
  created_at TEXT,
  status TEXT DEFAULT 'active',
  FOREIGN KEY (referrer_id) REFERENCES users(user_id),
  FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
)
```

---

## 🤝 How to Use

### For Recruiters (You)
1. **Get Your Code**: View your unique 8-character referral code in Referral Dashboard
2. **Share Everywhere**: Copy code, share in WhatsApp, social media, email
3. **Track Recruits**: See all people you've recruited and their earnings
4. **Earn Money**: Get 5% commission whenever your recruits make bot profits
5. **Passive Income**: Build your network, earn from multiple levels

### For New Users
1. **Join with Code**: Use referrer's code during registration
2. **Start Free**: No payment required to begin
3. **Trade Immediately**: Create bots and start trading right away
4. **Both Earn**: You earn, referrer earns 5% of your profits

---

## 🚀 Example Workflow

```
Day 1: You signup
   └─ Your referral code: "ABC123XY"

Day 2: You share code with friend Alice
   └─ Alice joins using "ABC123XY"
   └─ System creates referral link: You → Alice

Day 3: Alice creates a bot and trades
   └─ Bot profit: $100
   └─ Commission calculation:
      - Alice gets: $70 (70% of profit)
      - You get: $5 (5% referral commission)
      - Zwesta gets: $25 (25% platform fee)

Day 5: Alice recruits her friend Bob
   └─ Bob joins using Alice's code
   └─ System creates referral link: Alice → Bob

Day 10: Bob trades and makes $200 profit
   └─ Bob gets: $140
   └─ Alice gets: $10 (5% commission from Bob)
   └─ You get: $0 (You're not directly referred Bob)
   └─ Zwesta gets: $50

Total Earned by You: $5 (from Alice)
Total Earned by Alice: $10 (from Bob) + 70 (her own profit) = $80
```

---

## 🔐 Security Features

- **Unique Codes**: Each user gets 8-character unique referral code
- **Email Validation**: Ensures no duplicate accounts
- **Referral Verification**: Server validates codes before accepting referrals
- **Commission Recording**: All transactions logged in database
- **Audit Trail**: Created_at timestamps on all records

---

## 📊 Future Enhancements

- [ ] Withdrawal system for commission earnings
- [ ] Leaderboard (top recruiters by earnings)
- [ ] Tiered rewards (earn more at higher levels)
- [ ] Affiliate dashboard with charts/graphs
- [ ] Email notifications for new recruits
- [ ] Bonus rewards for recruiting milestones
- [ ] Custom referral links (shareable URLs)

---

## 🛠️ Implementation Details

### ReferralSystem Class
Located in `multi_broker_backend_updated.py` lines 55-280

**Key Methods:**
```python
ReferralSystem.generate_referral_code()
  └─ Creates unique 8-char code

ReferralSystem.register_user(email, name, referral_code)
  └─ Register new user, link to referrer if code valid

ReferralSystem.add_commission(earner_id, client_id, profit_amount, bot_id)
  └─ Calculate 5% commission, update earner total

ReferralSystem.get_recruits(user_id)
  └─ Get all users recruited by this user

ReferralSystem.get_earning_recap(user_id)
  └─ Summary: total earned, clients, transactions
```

---

## 📝 Database Location

SQLite database file: `zwesta_trading.db` (in same directory as Flask app)

Auto-created on first run with all necessary tables.

---

## ✅ Testing the System

### Test with curl:

**1. Register User A:**
```bash
curl -X POST http://localhost:9000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{"name":"User A","email":"a@test.com"}'
```
Returns: `user_id` and `referral_code` (e.g., "ABC123XY")

**2. Register User B (with referral):**
```bash
curl -X POST http://localhost:9000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{"name":"User B","email":"b@test.com","referral_code":"ABC123XY"}'
```

**3. Get User A's Recruits:**
```bash
curl http://localhost:9000/api/user/{user_a_id}/recruits
```
Returns: List with User B

**4. Get Earnings:**
```bash
curl http://localhost:9000/api/user/{user_a_id}/earnings
```

---

## 💡 Key Features

✅ **No Upfront Investment** - Completely free to start
✅ **Instant Earnings** - Get 5% commission immediately
✅ **Lifetime Commissions** - Earn from recruits indefinitely
✅ **Passive Income** - Money comes automatically
✅ **Scale Unlimited** - Recruit as many as you want
✅ **Easy Tracking** - Dashboard shows all recruits & earnings
✅ **Real-Time Updates** - Earnings calculated instantly

---

## 📞 Support

For issues or questions about the referral system, check:
- Backend logs: `multi_broker_backend.log`
- Database: `zwesta_trading.db`
- API responses for error messages

