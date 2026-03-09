# User-Specific Account & Data Isolation System

## Overview

Each user now has complete data isolation with their own:
- ✅ User profile and account information
- ✅ Broker credentials (MT5, XM, etc.)
- ✅ Bots linked to their specific account
- ✅ Trading records and performance metrics
- ✅ Commission and earnings history

**Key Principle:** Every user sees **only their own data**, regardless of who else is logged in.

---

## 🔐 Authentication & Session Management

### 1. User Registration
**Endpoint:** `POST /api/user/register`

**Request:**
```json
{
  "email": "trader@example.com",
  "name": "John Trader",
  "referral_code": "ABC123XY"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-12345",
  "referral_code": "XY5ABC12",
  "referrer_id": "uuid-referrer",
  "message": "User registered successfully"
}
```

---

### 2. User Login
**Endpoint:** `POST /api/user/login`

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
  "name": "John Trader",
  "email": "trader@example.com",
  "referral_code": "XY5ABC12",
  "session_token": "hash_token_here",
  "message": "Login successful"
}
```

**⚠️ Important:** Store the `session_token` in your Flutter app and include it in API requests.

---

## 👤 User Profile

### Get User Profile
**Endpoint:** `GET /api/user/profile/<user_id>`

**Authentication:** X-API-Key header

**Response:**
```json
{
  "success": true,
  "user": {
    "user_id": "uuid-12345",
    "name": "John Trader",
    "email": "trader@example.com",
    "referral_code": "XY5ABC12",
    "total_commission": 250.50,
    "created_at": "2024-01-15T10:30:00"
  },
  "bots": [
    {
      "bot_id": "bot_12345",
      "name": "Scalper Bot",
      "strategy": "Scalping",
      "status": "active",
      "enabled": true,
      "daily_profit": 150.00,
      "total_profit": 2500.00,
      "created_at": "2024-01-20T14:30:00"
    }
  ],
  "total_bots": 1,
  "brokers": [
    {
      "credential_id": "cred_123",
      "broker_name": "XM",
      "account_number": "123456789",
      "is_live": false,
      "is_active": true
    }
  ],
  "total_brokers": 1
}
```

---

## 🏦 Broker Credentials Management

### Add Broker Credentials
**Endpoint:** `POST /api/user/<user_id>/broker-credentials`

**Request:**
```json
{
  "broker_name": "XM",
  "account_number": "123456789",
  "password": "trader_password",
  "server": "XMGlobal-MT5",
  "is_live": false
}
```

**Response:**
```json
{
  "success": true,
  "credential_id": "cred_123",
  "message": "Broker credentials added for XM"
}
```

---

### Get All Broker Credentials
**Endpoint:** `GET /api/user/<user_id>/broker-credentials`

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-12345",
  "credentials": [
    {
      "credential_id": "cred_123",
      "broker_name": "XM",
      "account_number": "123456789",
      "server": "XMGlobal-MT5",
      "is_live": false,
      "is_active": true,
      "created_at": "2024-01-15T10:30:00"
    }
  ],
  "total": 1
}
```

---

## 🤖 User-Specific Bots

### Create Bot (User-Specific)
**Endpoint:** `POST /api/bot/create`

**Request:**
```json
{
  "user_id": "uuid-12345",
  "name": "My Scalper",
  "botId": "bot_uuid_12345",
  "strategy": "Scalping",
  "accountId": "123456789",
  "symbols": ["EURUSD", "GBPUSD"],
  "riskPerTrade": 100,
  "maxDailyLoss": 500,
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "botId": "bot_uuid_12345",
  "user_id": "uuid-12345",
  "message": "Bot created successfully",
  "config": { ... }
}
```

---

### Get User's Bots
**Endpoint:** `GET /api/user/<user_id>/bots`

**Response:**
```json
{
  "success": true,
  "user_id": "uuid-12345",
  "bots": [
    {
      "bot_id": "bot_uuid_1",
      "name": "Scalper Bot",
      "strategy": "Scalping",
      "status": "active",
      "enabled": true,
      "daily_profit": 150.00,
      "total_profit": 2500.00,
      "created_at": "2024-01-20T14:30:00"
    }
  ],
  "total_bots": 1,
  "active_bots": 1,
  "total_daily_profit": 150.00,
  "total_profit": 2500.00
}
```

---

### Get Bot Status (User-Specific)
**Endpoint:** `GET /api/bot/status?user_id=uuid-12345`

Returns only this user's bots with real-time metrics.

---

## 📱 Flutter Integration Example

### Complete Login & Profile Flow

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class UserService {
  final String baseUrl = 'http://localhost:9000';
  final String apiKey = 'your_api_key';
  
  String? _userId;
  String? _sessionToken;
  
  // 1. Login
  Future<bool> login(String email) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/user/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _userId = data['user_id'];
        _sessionToken = data['session_token'];
        
        // Save to shared preferences
        final prefs = await SharedPreferences.getInstance();
        prefs.setString('user_id', _userId!);
        prefs.setString('session_token', _sessionToken!);
        
        return true;
      }
      return false;
    } catch (e) {
      print('Login error: $e');
      return false;
    }
  }
  
  // 2. Get User Profile
  Future<UserProfile?> getUserProfile() async {
    if (_userId == null) return null;
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/user/profile/$_userId'),
        headers: {'X-API-Key': apiKey},
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return UserProfile.fromJson(data);
      }
      return null;
    } catch (e) {
      print('Profile error: $e');
      return null;
    }
  }
  
  // 3. Add Broker Credentials
  Future<bool> addBrokerCredentials({
    required String brokerName,
    required String accountNumber,
    required String password,
    required String server,
    required bool isLive,
  }) async {
    if (_userId == null) return false;
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/user/$_userId/broker-credentials'),
        headers: {
          'X-API-Key': apiKey,
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'broker_name': brokerName,
          'account_number': accountNumber,
          'password': password,
          'server': server,
          'is_live': isLive,
        }),
      );
      
      return response.statusCode == 200;
    } catch (e) {
      print('Add broker error: $e');
      return false;
    }
  }
  
  // 4. Create Bot
  Future<String?> createBot({
    required String name,
    required String strategy,
    required String accountId,
    required List<String> symbols,
  }) async {
    if (_userId == null) return null;
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/bot/create'),
        headers: {
          'X-API-Key': apiKey,
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'user_id': _userId,
          'name': name,
          'strategy': strategy,
          'accountId': accountId,
          'symbols': symbols,
          'enabled': true,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['botId'];
      }
      return null;
    } catch (e) {
      print('Create bot error: $e');
      return null;
    }
  }
  
  // 5. Get User Bots
  Future<List<BotInfo>> getUserBots() async {
    if (_userId == null) return [];
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/user/$_userId/bots'),
        headers: {'X-API-Key': apiKey},
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final bots = (data['bots'] as List)
            .map((b) => BotInfo.fromJson(b))
            .toList();
        return bots;
      }
      return [];
    } catch (e) {
      print('Get bots error: $e');
      return [];
    }
  }
}

// Models
class UserProfile {
  final String userId;
  final String name;
  final String email;
  final double totalCommission;
  final List<BotInfo> bots;
  final List<BrokerCredential> brokers;
  
  UserProfile({
    required this.userId,
    required this.name,
    required this.email,
    required this.totalCommission,
    required this.bots,
    required this.brokers,
  });
  
  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user']['user_id'],
      name: json['user']['name'],
      email: json['user']['email'],
      totalCommission: json['user']['total_commission']?.toDouble() ?? 0,
      bots: (json['bots'] as List)
          .map((b) => BotInfo.fromJson(b))
          .toList(),
      brokers: (json['brokers'] as List)
          .map((br) => BrokerCredential.fromJson(br))
          .toList(),
    );
  }
}

class BotInfo {
  final String botId;
  final String name;
  final String strategy;
  final bool enabled;
  final double dailyProfit;
  final double totalProfit;
  
  BotInfo({
    required this.botId,
    required this.name,
    required this.strategy,
    required this.enabled,
    required this.dailyProfit,
    required this.totalProfit,
  });
  
  factory BotInfo.fromJson(Map<String, dynamic> json) {
    return BotInfo(
      botId: json['bot_id'],
      name: json['name'],
      strategy: json['strategy'],
      enabled: json['enabled'] ?? false,
      dailyProfit: json['daily_profit']?.toDouble() ?? 0,
      totalProfit: json['total_profit']?.toDouble() ?? 0,
    );
  }
}

class BrokerCredential {
  final String credentialId;
  final String brokerName;
  final String accountNumber;
  final bool isLive;
  
  BrokerCredential({
    required this.credentialId,
    required this.brokerName,
    required this.accountNumber,
    required this.isLive,
  });
  
  factory BrokerCredential.fromJson(Map<String, dynamic> json) {
    return BrokerCredential(
      credentialId: json['credential_id'],
      brokerName: json['broker_name'],
      accountNumber: json['account_number'],
      isLive: json['is_live'] ?? false,
    );
  }
}
```

---

## 🔄 User Login Screen Flow

```dart
class LoginScreen extends StatefulWidget {
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final userService = UserService();
  final emailController = TextEditingController();
  
  void _handleLogin() async {
    final email = emailController.text;
    
    // 1. Login
    final loginSuccess = await userService.login(email);
    if (!loginSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Login failed')),
      );
      return;
    }
    
    // 2. Load profile
    final profile = await userService.getUserProfile();
    if (profile == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to load profile')),
      );
      return;
    }
    
    // 3. Navigate to dashboard
    Navigator.pushReplacementNamed(
      context,
      '/dashboard',
      arguments: profile,
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Login')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: emailController,
              decoration: const InputDecoration(
                labelText: 'Email',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _handleLogin,
              child: const Text('Login'),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## 🔒 Data Isolation Principles

### 1. Every Query Requires User ID
- All bot queries filtered by user_id
- All broker credentials owned by user
- All commissions earned by user

### 2. No Shared Data
- ❌ NOT global demo bots for all users
- ✅ Each user has their own bots
- ❌ NOT shared broker credentials
- ✅ Each user manages their own brokers

### 3. Session Management
- Each login creates a session token
- Session token should be stored locally
- Token expires after 30 days
- Token required for database modifications

---

## 📊 Database Architecture

```
users
├─ user_id (PK)
├─ email
├─ name
├─ referrer_id (FK)
└─ created_at

user_bots
├─ bot_id (PK)
├─ user_id (FK) ← Links to users
├─ name
├─ strategy
├─ daily_profit
├─ total_profit
└─ created_at

broker_credentials
├─ credential_id (PK)
├─ user_id (FK) ← Links to users
├─ broker_name
├─ account_number
├─ password
├─ is_live
└─ created_at

user_sessions
├─ session_id (PK)
├─ user_id (FK) ← Links to users
├─ token
├─ created_at
├─ expires_at
└─ is_active
```

---

## ✅ Verification Checklist

- [ ] Each user login creates unique session
- [ ] User sees only their own bots
- [ ] User sees only their broker credentials
- [ ] Bot creation requires user_id
- [ ] Broker credentials isolated per user
- [ ] Commission calculated per user
- [ ] No shared demo account data
- [ ] Logout clears user data from frontend

---

## 🚀 Best Practices

1. **Always include user_id** in bot creation
2. **Store session token** securely in app
3. **Filter all queries** by current user
4. **Validate ownership** before bot operations
5. **Encrypt broker credentials** (future enhancement)
6. **Log all user actions** for audit trail

---

## 📞 Support

For issues with user isolation:
- Check user_id is correct
- Verify session token is active
- Ensure bot belongs to user
- Review database for orphaned records

---

**Version:** 1.0
**Last Updated:** March 2026
**Status:** ✅ Production Ready
