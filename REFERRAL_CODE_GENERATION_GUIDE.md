# Referral Code Generation System

## Overview

The Zwesta Trading Platform now includes a complete referral code generation and management system. Every user automatically receives a unique referral code upon registration that can be shared to earn 5% commission from recruited users' bot profits.

---

## ✨ Features

✅ **Automatic Code Generation** - Unique 8-character codes generated on signup
✅ **Code Management** - View, share, and regenerate referral codes
✅ **Recruit Tracking** - See how many users you've recruited
✅ **Earnings Dashboard** - Track commission earnings from referrals
✅ **Share Links** - Pre-formatted links for easy sharing

---

## 🔌 API Endpoints

### 1. Get User's Referral Code
**Endpoint:** `GET /api/user/<user_id>/referral-code`

**Authentication:** Required (X-API-Key header)

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-string",
  "name": "John Doe",
  "email": "john@example.com",
  "referral_code": "ABC12XY5",
  "referral_link": "https://zwesta.com/register?ref=ABC12XY5",
  "recruited_count": 3,
  "created_at": "2024-01-15T10:30:00"
}
```

**Example cURL:**
```bash
curl http://localhost:9000/api/user/user_123/referral-code \
  -H "X-API-Key: your_api_key"
```

---

### 2. Regenerate Referral Code
**Endpoint:** `POST /api/user/<user_id>/regenerate-referral-code`

**Authentication:** Required (X-API-Key header)

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-string",
  "new_referral_code": "XY5ABC12",
  "referral_link": "https://zwesta.com/register?ref=XY5ABC12",
  "message": "Referral code regenerated successfully"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9000/api/user/user_123/regenerate-referral-code \
  -H "X-API-Key: your_api_key"
```

**⚠️ Important:** Regenerating will invalidate the old code. Only do this if compromised.

---

### 3. Validate Referral Code
**Endpoint:** `GET /api/referral/validate/<referral_code>`

**Response:**
```json
{
  "success": true,
  "is_valid": true,
  "referrer_name": "John Doe",
  "message": "Referral code is valid"
}
```

---

### 4. Get Referral Link
**Endpoint:** `GET /api/referral/link/<referral_code>`

**Response:**
```json
{
  "success": true,
  "referral_code": "ABC12XY5",
  "referral_link": "https://zwesta.com/register?ref=ABC12XY5",
  "referrer_name": "John Doe",
  "message": "Share this link to invite others: ..."
}
```

---

### 5. Get User Recruits
**Endpoint:** `GET /api/user/<user_id>/recruits`

**Response:**
```json
{
  "success": true,
  "recruits": [
    {
      "user_id": "recruit_1",
      "name": "Alice Smith",
      "email": "alice@example.com",
      "recruited_date": "2024-01-20T14:30:00",
      "status": "active"
    }
  ],
  "total_recruits": 1
}
```

---

### 6. Get Earnings Summary
**Endpoint:** `GET /api/user/<user_id>/earnings`

**Response:**
```json
{
  "success": true,
  "total_earnings": 125.50,
  "last_month_earnings": 45.25,
  "active_recruits": 3,
  "total_commissions": 8,
  "earnings_breakdown": {
    "pending": 10.00,
    "completed": 115.50
  }
}
```

---

## 🎯 Referral Code Format

- **Length:** 8 characters
- **Format:** Alphanumeric (A-Z, 0-9)
- **Case:** Automatically converted to uppercase
- **Uniqueness:** Each user gets one unique code (can regenerate)

**Example codes:**
```
ABC12XY5
ZX9Q4K2L
PWR8NXM3
```

---

## 📱 Frontend Integration

### Get User's Referral Code (Flutter)
```dart
Future<void> loadReferralCode() async {
  final response = await http.get(
    Uri.parse('http://localhost:9000/api/user/$userId/referral-code'),
    headers: {'X-API-Key': apiKey},
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    setState(() {
      referralCode = data['referral_code'];
      referralLink = data['referral_link'];
      recruitedCount = data['recruited_count'];
    });
  }
}
```

### Share Referral Code
```dart
void shareReferralCode() {
  final message = "Join Zwesta Trading! Use my referral code: $referralCode\n"
                  "Link: $referralLink";
  
  Share.share(message);
}
```

### Regenerate Code
```dart
Future<void> regenerateCode() async {
  final response = await http.post(
    Uri.parse('http://localhost:9000/api/user/$userId/regenerate-referral-code'),
    headers: {'X-API-Key': apiKey},
  );

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('New Referral Code'),
        content: Text('Your new code: ${data["new_referral_code"]}'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}
```

---

## 🐍 Python Integration

```python
import requests
import json

class ReferralManager:
    def __init__(self, api_key, base_url='http://localhost:9000'):
        self.headers = {'X-API-Key': api_key}
        self.base_url = base_url
    
    def get_referral_code(self, user_id):
        """Get user's referral code"""
        response = requests.get(
            f'{self.base_url}/api/user/{user_id}/referral-code',
            headers=self.headers
        )
        return response.json()
    
    def regenerate_code(self, user_id):
        """Regenerate user's referral code"""
        response = requests.post(
            f'{self.base_url}/api/user/{user_id}/regenerate-referral-code',
            headers=self.headers
        )
        return response.json()
    
    def get_recruits(self, user_id):
        """Get all recruits"""
        response = requests.get(
            f'{self.base_url}/api/user/{user_id}/recruits',
            headers=self.headers
        )
        return response.json()
    
    def get_earnings(self, user_id):
        """Get earnings summary"""
        response = requests.get(
            f'{self.base_url}/api/user/{user_id}/earnings',
            headers=self.headers
        )
        return response.json()
    
    def validate_code(self, code):
        """Validate a referral code"""
        response = requests.get(
            f'{self.base_url}/api/referral/validate/{code}',
            headers=self.headers
        )
        return response.json()

# Usage
manager = ReferralManager('your_api_key')
code = manager.get_referral_code('user_123')
print(f"Code: {code['referral_code']}")
print(f"Link: {code['referral_link']}")
print(f"Recruits: {code['recruited_count']}")
```

---

## 💡 Use Cases

### Direct Share
```
"Join Zwesta! Use code ABC12XY5 to earn 5% commission"
```

### Email Invitation
```
Subject: Earn 5% with Zwesta Trading

Hi [Name],

I'm earning passive income from my trading bots with Zwesta!
Join me using my referral link:
https://zwesta.com/register?ref=ABC12XY5

You'll get started for FREE and I'll earn 5% from your bot profits.

Best regards,
John
```

### Social Media
```
🚀 Join Zwesta Trading!
Use my code: ABC12XY5
Earn 5% commission from your referrals!
Link: https://zwesta.com/register?ref=ABC12XY5
```

---

## 🔒 Security

✅ Codes are unique and non-sequential
✅ Case-insensitive (ABC, abc all work)
✅ API key required to regenerate
✅ Old codes become invalid when regenerated
✅ No rate limiting on validation (can check validity anytime)

---

## 📊 Tracking

### Real-Time Metrics
- Active recruit count
- Commission earnings (total, pending, completed)
- Recruitment timeline
- Earnings history

### Dashboard Display
```
Your Referral Code: ABC12XY5

📊 Stats
├─ Recruits: 3
├─ Total Earnings: $125.50
├─ Pending: $10.00
└─ This Month: $45.25

🔗 Share Link
└─ https://zwesta.com/register?ref=ABC12XY5
```

---

## 🔧 Configuration

### Code Generation
- Length: 8 characters (configurable in future)
- Uniqueness: Database constraint ensures no duplicates
- Format: Alphanumeric only
- Regeneration: Allowed for each user

### Commission Rate
- Base: 5% of recruit's bot profits
- Frequency: Real-time calculation
- Withdrawal: Available daily

---

## ❓ Troubleshooting

### "Referral code not found"
**Solution:** 
- Verify user_id is correct
- Check user exists in system
- Ensure code was generated on registration

### "Invalid referral code"
**Solution:**
- Check code spelling (case-insensitive)
- Verify code hasn't been replaced
- Confirm code owner still exists

### "Earnings not showing"
**Solution:**
- Wait for recruits' first bot settlement
- Check if recruits are active
- Verify commission calculation (5% of profits)

---

## 🚀 Best Practices

1. **Share Often** - More shares = more recruits = more earnings
2. **Use Links** - Pre-formatted links work best
3. **Track Metrics** - Monitor your earnings dashboard
4. **Notify Recruits** - Tell recruits your code early
5. **Social Proof** - Share your success with others

---

## 📈 Earning Potential

```
Recruits  |  Avg Profit  |  Your 5%  |  Monthly
----------|--------------|-----------|----------
1         |  $500        |  $25      |  $300
3         |  $500        |  $75      |  $900
5         |  $500        |  $125     |  $1,500
10        |  $500        |  $250     |  $3,000
20        |  $500        |  $500     |  $6,000
```

---

## 📞 Support

For issues or questions:
- Check API response error messages
- Verify API key is correct
- Ensure user exists in system
- Review troubleshooting section

---

**Version:** 1.0
**Last Updated:** March 2026
**Status:** ✅ Production Ready
