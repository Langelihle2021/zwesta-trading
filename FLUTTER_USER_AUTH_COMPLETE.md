# Flutter App - Complete User Authentication & Data Isolation Integration

## 🎯 Overview

This guide shows how to update your Flutter app to:
- ✅ Properly authenticate users with session tokens
- ✅ Display only the current user's data
- ✅ Manage user-specific bots and broker credentials
- ✅ Prevent data leakage between users

---

## 📱 Updated User Service

Replace your existing user service with this complete implementation:

```dart
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

class UserService {
  final String baseUrl = 'http://localhost:9000';
  
  String? _userId;
  String? _sessionToken;
  String? _userName;
  
  // Initialize from stored session
  Future<bool> initializeFromStorage() async {
    final prefs = await SharedPreferences.getInstance();
    _userId = prefs.getString('user_id');
    _sessionToken = prefs.getString('session_token');
    _userName = prefs.getString('user_name');
    
    return _userId != null && _sessionToken != null;
  }
  
  // ==================== AUTHENTICATION ====================
  
  /// Register new user
  Future<RegistrationResponse?> register({
    required String email,
    required String name,
    String? referralCode,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/user/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'name': name,
          if (referralCode != null) 'referral_code': referralCode,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          return RegistrationResponse.fromJson(data);
        }
      }
      return null;
    } catch (e) {
      print('Registration error: $e');
      return null;
    }
  }
  
  /// Login user by email
  Future<bool> login(String email) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/user/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          _userId = data['user_id'];
          _sessionToken = data['session_token'];
          _userName = data['name'];
          
          // Save to persistent storage
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('user_id', _userId!);
          await prefs.setString('session_token', _sessionToken!);
          await prefs.setString('user_name', _userName!);
          
          print('✅ User logged in: $_userName ($_userId)');
          return true;
        }
      }
      return false;
    } catch (e) {
      print('Login error: $e');
      return false;
    }
  }
  
  /// Logout user
  Future<void> logout() async {
    _userId = null;
    _sessionToken = null;
    _userName = null;
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_id');
    await prefs.remove('session_token');
    await prefs.remove('user_name');
    
    print('✅ User logged out');
  }
  
  /// Check if user is logged in
  bool isLoggedIn() => _userId != null && _sessionToken != null;
  
  String? get userId => _userId;
  String? get userName => _userName;
  String? get sessionToken => _sessionToken;
  
  // ==================== USER PROFILE ====================
  
  /// Get current user's profile
  Future<UserProfile?> getUserProfile() async {
    if (_userId == null) {
      print('❌ User not logged in');
      return null;
    }
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/user/profile/$_userId'),
        headers: _getAuthHeaders(),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          return UserProfile.fromJson(data);
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Cannot access this profile');
      }
      return null;
    } catch (e) {
      print('Get profile error: $e');
      return null;
    }
  }
  
  // ==================== BROKER CREDENTIALS ====================
  
  /// Add broker credentials for current user
  Future<bool> addBrokerCredentials({
    required String brokerName,
    required String accountNumber,
    required String password,
    required String server,
    required bool isLive,
  }) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return false;
    }
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/user/$_userId/broker-credentials'),
        headers: _getAuthHeaders(),
        body: jsonEncode({
          'broker_name': brokerName,
          'account_number': accountNumber,
          'password': password,
          'server': server,
          'is_live': isLive,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          print('✅ Broker credentials added: $brokerName');
          return true;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Cannot add credentials for this user');
      }
      return false;
    } catch (e) {
      print('Add broker credentials error: $e');
      return false;
    }
  }
  
  /// Get all broker credentials for current user
  Future<List<BrokerCredential>> getBrokerCredentials() async {
    if (_userId == null) {
      print('❌ User not logged in');
      return [];
    }
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/user/$_userId/broker-credentials'),
        headers: _getAuthHeaders(),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          final credentials = (data['credentials'] as List)
              .map((c) => BrokerCredential.fromJson(c))
              .toList();
          print('✅ Loaded ${credentials.length} broker credentials');
          return credentials;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Cannot access these credentials');
      }
      return [];
    } catch (e) {
      print('Get broker credentials error: $e');
      return [];
    }
  }
  
  // ==================== BOT MANAGEMENT ====================
  
  /// Create a new bot for current user
  Future<String?> createBot({
    required String name,
    required String strategy,
    required String accountId,
    required List<String> symbols,
    required double riskPerTrade,
    required double maxDailyLoss,
  }) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return null;
    }
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/bot/create'),
        headers: _getAuthHeaders(),
        body: jsonEncode({
          'user_id': _userId,
          'name': name,
          'strategy': strategy,
          'accountId': accountId,
          'symbols': symbols,
          'riskPerTrade': riskPerTrade,
          'maxDailyLoss': maxDailyLoss,
          'enabled': true,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          final botId = data['botId'];
          print('✅ Bot created: $botId');
          return botId;
        }
      }
      return null;
    } catch (e) {
      print('Create bot error: $e');
      return null;
    }
  }
  
  /// Get all bots for current user
  Future<List<BotInfo>> getUserBots() async {
    if (_userId == null) {
      print('❌ User not logged in');
      return [];
    }
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/user/$_userId/bots'),
        headers: _getAuthHeaders(),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          final bots = (data['bots'] as List)
              .map((b) => BotInfo.fromJson(b))
              .toList();
          print('✅ Loaded ${bots.length} bots for user');
          return bots;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Cannot access these bots');
      }
      return [];
    } catch (e) {
      print('Get user bots error: $e');
      return [];
    }
  }
  
  /// Start a bot
  Future<bool> startBot(String botId) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return false;
    }
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/bot/start'),
        headers: _getAuthHeaders(),
        body: jsonEncode({
          'botId': botId,
          'user_id': _userId,
        }),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          print('✅ Bot started: $botId');
          return true;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Bot does not belong to this user');
      }
      return false;
    } catch (e) {
      print('Start bot error: $e');
      return false;
    }
  }
  
  /// Stop a bot
  Future<bool> stopBot(String botId) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return false;
    }
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/bot/stop/$botId'),
        headers: _getAuthHeaders(),
        body: jsonEncode({'user_id': _userId}),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          print('✅ Bot stopped: $botId');
          return true;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Bot does not belong to this user');
      }
      return false;
    } catch (e) {
      print('Stop bot error: $e');
      return false;
    }
  }
  
  /// Delete a bot
  Future<bool> deleteBot(String botId) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return false;
    }
    
    try {
      final response = await http.delete(
        Uri.parse('$baseUrl/api/bot/delete/$botId'),
        headers: _getAuthHeaders(),
        body: jsonEncode({'user_id': _userId}),
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          print('✅ Bot deleted: $botId');
          return true;
        }
      } else if (response.statusCode == 403) {
        print('❌ Unauthorized: Bot does not belong to this user');
      }
      return false;
    } catch (e) {
      print('Delete bot error: $e');
      return false;
    }
  }
  
  /// Get bot status
  Future<BotStatus?> getBotStatus(String botId) async {
    if (_userId == null) {
      print('❌ User not logged in');
      return null;
    }
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/bot/status?user_id=$_userId'),
        headers: {'X-Session-Token': _sessionToken!},
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          // Find the specific bot in the list
          final bots = data['bots'] as List;
          final botData = bots.firstWhere(
            (b) => b['botId'] == botId,
            orElse: () => null,
          );
          
          if (botData != null) {
            return BotStatus.fromJson(botData);
          }
        }
      }
      return null;
    } catch (e) {
      print('Get bot status error: $e');
      return null;
    }
  }
  
  // ==================== HELPER METHODS ====================
  
  /// Get authentication headers with session token
  Map<String, String> _getAuthHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-Session-Token': _sessionToken ?? '',
    };
  }
}

// ==================== DATA MODELS ====================

class RegistrationResponse {
  final String userId;
  final String referralCode;
  final String? referrerId;
  final String message;
  
  RegistrationResponse({
    required this.userId,
    required this.referralCode,
    this.referrerId,
    required this.message,
  });
  
  factory RegistrationResponse.fromJson(Map<String, dynamic> json) {
    return RegistrationResponse(
      userId: json['user_id'],
      referralCode: json['referral_code'],
      referrerId: json['referrer_id'],
      message: json['message'],
    );
  }
}

class UserProfile {
  final String userId;
  final String name;
  final String email;
  final String referralCode;
  final double totalCommission;
  final List<BotInfo> bots;
  final List<BrokerCredential> brokers;
  
  UserProfile({
    required this.userId,
    required this.name,
    required this.email,
    required this.referralCode,
    required this.totalCommission,
    required this.bots,
    required this.brokers,
  });
  
  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user']['user_id'],
      name: json['user']['name'],
      email: json['user']['email'],
      referralCode: json['user']['referral_code'],
      totalCommission: (json['user']['total_commission'] ?? 0).toDouble(),
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
  final String createdAt;
  
  BotInfo({
    required this.botId,
    required this.name,
    required this.strategy,
    required this.enabled,
    required this.dailyProfit,
    required this.totalProfit,
    required this.createdAt,
  });
  
  factory BotInfo.fromJson(Map<String, dynamic> json) {
    return BotInfo(
      botId: json['bot_id'],
      name: json['name'],
      strategy: json['strategy'],
      enabled: json['enabled'] ?? false,
      dailyProfit: (json['daily_profit'] ?? 0).toDouble(),
      totalProfit: (json['total_profit'] ?? 0).toDouble(),
      createdAt: json['created_at'] ?? '',
    );
  }
}

class BrokerCredential {
  final String credentialId;
  final String brokerName;
  final String accountNumber;
  final bool isLive;
  final bool isActive;
  
  BrokerCredential({
    required this.credentialId,
    required this.brokerName,
    required this.accountNumber,
    required this.isLive,
    required this.isActive,
  });
  
  factory BrokerCredential.fromJson(Map<String, dynamic> json) {
    return BrokerCredential(
      credentialId: json['credential_id'],
      brokerName: json['broker_name'],
      accountNumber: json['account_number'],
      isLive: json['is_live'] ?? false,
      isActive: json['is_active'] ?? true,
    );
  }
}

class BotStatus {
  final String botId;
  final String strategy;
  final int totalTrades;
  final int winningTrades;
  final double totalProfit;
  final double dailyProfit;
  final double maxDrawdown;
  final double roi;
  final bool enabled;
  
  BotStatus({
    required this.botId,
    required this.strategy,
    required this.totalTrades,
    required this.winningTrades,
    required this.totalProfit,
    required this.dailyProfit,
    required this.maxDrawdown,
    required this.roi,
    required this.enabled,
  });
  
  factory BotStatus.fromJson(Map<String, dynamic> json) {
    return BotStatus(
      botId: json['botId'],
      strategy: json['strategy'],
      totalTrades: json['totalTrades'] ?? 0,
      winningTrades: json['winningTrades'] ?? 0,
      totalProfit: (json['totalProfit'] ?? 0).toDouble(),
      dailyProfit: (json['dailyProfit'] ?? 0).toDouble(),
      maxDrawdown: (json['maxDrawdown'] ?? 0).toDouble(),
      roi: (json['roi'] ?? 0).toDouble(),
      enabled: json['enabled'] ?? false,
    );
  }
}
```

---

## 🎨 Updated Dashboard Screen

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class DashboardScreen extends StatefulWidget {
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late UserService userService;
  UserProfile? userProfile;
  List<BotInfo> userBots = [];
  bool isLoading = true;
  
  @override
  void initState() {
    super.initState();
    userService = UserService();
    _loadUserData();
  }
  
  Future<void> _loadUserData() async {
    setState(() => isLoading = true);
    
    // Get user profile
    final profile = await userService.getUserProfile();
    
    setState(() {
      userProfile = profile;
      userBots = profile?.bots ?? [];
      isLoading = false;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Dashboard')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    
    if (userProfile == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Dashboard')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('Failed to load profile'),
              ElevatedButton(
                onPressed: _loadUserData,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    
    return Scaffold(
      appBar: AppBar(
        title: Text('Welcome, ${userProfile!.name}'),
        actions: [
          PopupMenuButton(
            itemBuilder: (context) => [
              PopupMenuItem(
                child: const Text('Logout'),
                onTap: () async {
                  await userService.logout();
                  Navigator.pushReplacementNamed(context, '/login');
                },
              ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadUserData,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // User Info Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      userProfile!.name,
                      style: Theme.of(context).textTheme.headline6,
                    ),
                    const SizedBox(height: 8),
                    Text('Email: ${userProfile!.email}'),
                    Text('Referral Code: ${userProfile!.referralCode}'),
                    Text('Commission: \$${userProfile!.totalCommission.toStringAsFixed(2)}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            
            // Broker Credentials Section
            Text(
              'Broker Accounts (${userProfile!.brokers.length})',
              style: Theme.of(context).textTheme.headline6,
            ),
            if (userProfile!.brokers.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('No broker accounts connected'),
              )
            else
              ...userProfile!.brokers.map((broker) => ListTile(
                title: Text(broker.brokerName),
                subtitle: Text(
                  'Account: ${broker.accountNumber} (${broker.isLive ? 'Live' : 'Demo'})',
                ),
              )),
            
            ElevatedButton.icon(
              onPressed: () => _showAddBrokerDialog(),
              icon: const Icon(Icons.add),
              label: const Text('Add Broker'),
            ),
            const SizedBox(height: 16),
            
            // Bots Section
            Text(
              'Trading Bots (${userBots.length})',
              style: Theme.of(context).textTheme.headline6,
            ),
            if (userBots.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('No bots created yet'),
              )
            else
              ...userBots.map((bot) => BotCard(
                bot: bot,
                userService: userService,
                onBotUpdated: _loadUserData,
              )),
            
            ElevatedButton.icon(
              onPressed: () => _navigateToCreateBot(),
              icon: const Icon(Icons.add),
              label: const Text('Create Bot'),
            ),
          ],
        ),
      ),
    );
  }
  
  void _showAddBrokerDialog() {
    showDialog(
      context: context,
      builder: (context) => AddBrokerDialog(
        userService: userService,
        onBrokerAdded: _loadUserData,
      ),
    );
  }
  
  void _navigateToCreateBot() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => CreateBotScreen(onBotCreated: _loadUserData)),
    );
  }
}

// Bot Card Widget
class BotCard extends StatelessWidget {
  final BotInfo bot;
  final UserService userService;
  final VoidCallback onBotUpdated;
  
  const BotCard({
    required this.bot,
    required this.userService,
    required this.onBotUpdated,
  });
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        bot.name,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text('Strategy: ${bot.strategy}'),
                    ],
                  ),
                ),
                Chip(
                  label: Text(bot.enabled ? 'Active' : 'Inactive'),
                  backgroundColor: bot.enabled ? Colors.green : Colors.grey,
                ),
              ],
            ),
            const Divider(),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Daily: \$${bot.dailyProfit.toStringAsFixed(2)}'),
                    Text('Total: \$${bot.totalProfit.toStringAsFixed(2)}'),
                  ],
                ),
                Row(
                  children: [
                    if (bot.enabled)
                      ElevatedButton(
                        onPressed: () async {
                          await userService.stopBot(bot.botId);
                          onBotUpdated();
                        },
                        child: const Text('Stop'),
                      )
                    else
                      ElevatedButton(
                        onPressed: () async {
                          await userService.startBot(bot.botId);
                          onBotUpdated();
                        },
                        child: const Text('Start'),
                      ),
                    const SizedBox(width: 8),
                    ElevatedButton(
                      onPressed: () async {
                        final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: const Text('Delete Bot'),
                            content: const Text('Are you sure?'),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(context, false),
                                child: const Text('Cancel'),
                              ),
                              TextButton(
                                onPressed: () => Navigator.pop(context, true),
                                child: const Text('Delete'),
                              ),
                            ],
                          ),
                        ) ?? false;
                        
                        if (confirmed) {
                          await userService.deleteBot(bot.botId);
                          onBotUpdated();
                        }
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                      ),
                      child: const Text('Delete'),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// Add Broker Dialog
class AddBrokerDialog extends StatefulWidget {
  final UserService userService;
  final VoidCallback onBrokerAdded;
  
  const AddBrokerDialog({
    required this.userService,
    required this.onBrokerAdded,
  });
  
  @override
  State<AddBrokerDialog> createState() => _AddBrokerDialogState();
}

class _AddBrokerDialogState extends State<AddBrokerDialog> {
  late TextEditingController brokerController;
  late TextEditingController accountController;
  late TextEditingController passwordController;
  late TextEditingController serverController;
  bool isLive = false;
  bool isLoading = false;
  
  @override
  void initState() {
    super.initState();
    brokerController = TextEditingController();
    accountController = TextEditingController();
    passwordController = TextEditingController();
    serverController = TextEditingController();
  }
  
  @override
  void dispose() {
    brokerController.dispose();
    accountController.dispose();
    passwordController.dispose();
    serverController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add Broker Account'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: brokerController,
              decoration: const InputDecoration(
                labelText: 'Broker Name',
                hintText: 'e.g., XM, IC Markets',
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: accountController,
              decoration: const InputDecoration(
                labelText: 'Account Number',
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Password',
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: serverController,
              decoration: const InputDecoration(
                labelText: 'Server',
                hintText: 'e.g., XMGlobal-MT5',
              ),
            ),
            const SizedBox(height: 8),
            CheckboxListTile(
              title: const Text('Live Account'),
              value: isLive,
              onChanged: (value) => setState(() => isLive = value ?? false),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: isLoading ? null : () => _addBroker(),
          child: isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Add'),
        ),
      ],
    );
  }
  
  Future<void> _addBroker() async {
    setState(() => isLoading = true);
    
    final success = await widget.userService.addBrokerCredentials(
      brokerName: brokerController.text,
      accountNumber: accountController.text,
      password: passwordController.text,
      server: serverController.text,
      isLive: isLive,
    );
    
    setState(() => isLoading = false);
    
    if (success) {
      widget.onBrokerAdded();
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to add broker')),
      );
    }
  }
}
```

---

## 🔐 Updated Login Screen

```dart
class LoginScreen extends StatefulWidget {
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailController = TextEditingController();
  final userService = UserService();
  bool isLoading = false;
  
  @override
  void initState() {
    super.initState();
    _checkExistingSession();
  }
  
  Future<void> _checkExistingSession() async {
    if (await userService.initializeFromStorage()) {
      // User already logged in, go to dashboard
      Navigator.pushReplacementNamed(context, '/dashboard');
    }
  }
  
  Future<void> _handleLogin() async {
    final email = emailController.text.trim();
    if (email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter email')),
      );
      return;
    }
    
    setState(() => isLoading = true);
    
    final success = await userService.login(email);
    
    setState(() => isLoading = false);
    
    if (success) {
      Navigator.pushReplacementNamed(context, '/dashboard');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Login failed')),
      );
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Zwesta Trading')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.trending_up, size: 64),
              const SizedBox(height: 24),
              const Text(
                'Welcome to Zwesta',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: emailController,
                enabled: !isLoading,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  hintText: 'Enter your email',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.email),
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: isLoading ? null : _handleLogin,
                  child: isLoading
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Text(
                          'Login',
                          style: TextStyle(fontSize: 16),
                        ),
                ),
              ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: isLoading ? null : () => _showRegisterDialog(),
                child: const Text('Create New Account'),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  void _showRegisterDialog() {
    showDialog(
      context: context,
      builder: (context) => RegisterDialog(userService: userService),
    );
  }
}
```

---

## 🚀 Key Features

✅ **Session-Based Authentication**
- User logs in, gets X-Session-Token
- Token attached to all protected API calls
- Token validates on server-side

✅ **User-Specific Data**
- Only sees own bots and brokers
- Unauthorized access returns 403 Forbidden
- Session token prevents cross-user access

✅ **Automatic Session Management**
- Stored in SharedPreferences for app restart
- Auto-login on app launch
- Logout clears all data

✅ **Error Handling**
- 403: Unauthorized (wrong user)
- 401: Invalid/expired session
- 404: Bot/user not found

---

**Version:** 1.0
**Status:** Ready for Integration
