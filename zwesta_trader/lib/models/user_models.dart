import 'dart:convert';

class User {
  final String userId;
  final String username;
  final String email;
  final List<TradingAccount> tradingAccounts;
  String currentAccount;
  final DateTime createdAt;
  final DateTime lastLogin;

  User({
    required this.userId,
    required this.username,
    required this.email,
    required this.tradingAccounts,
    required this.currentAccount,
    required this.createdAt,
    required this.lastLogin,
  });

  String toJson() {
    return jsonEncode({
      'userId': userId,
      'username': username,
      'email': email,
      'tradingAccounts': tradingAccounts.map((a) => jsonDecode(a.toJson())).toList(),
      'currentAccount': currentAccount,
      'createdAt': createdAt.toIso8601String(),
      'lastLogin': lastLogin.toIso8601String(),
    });
  }

  factory User.fromJson(String json) {
    final data = jsonDecode(json);
    return User(
      userId: data['userId'],
      username: data['username'],
      email: data['email'],
      tradingAccounts: (data['tradingAccounts'] as List)
          .map((a) => TradingAccount.fromJson(jsonEncode(a)))
          .toList(),
      currentAccount: data['currentAccount'],
      createdAt: DateTime.parse(data['createdAt']),
      lastLogin: DateTime.parse(data['lastLogin']),
    );
  }
}

class TradingAccount {
  final String accountId;
  final String brokerId;
  final String brokerName;
  final String accountNumber;
  final String apiKey;
  final String accountType;
  final double maxDailyLoss;
  final double maxSessionLoss;
  final int maxConsecutiveLosses;
  bool isDefault;
  bool isActive;

  TradingAccount({
    required this.accountId,
    required this.brokerId,
    required this.brokerName,
    required this.accountNumber,
    required this.apiKey,
    required this.accountType,
    required this.maxDailyLoss,
    required this.maxSessionLoss,
    required this.maxConsecutiveLosses,
    required this.isDefault,
    required this.isActive,
  });

  String toJson() {
    return jsonEncode({
      'accountId': accountId,
      'brokerId': brokerId,
      'brokerName': brokerName,
      'accountNumber': accountNumber,
      'apiKey': apiKey,
      'accountType': accountType,
      'maxDailyLoss': maxDailyLoss,
      'maxSessionLoss': maxSessionLoss,
      'maxConsecutiveLosses': maxConsecutiveLosses,
      'isDefault': isDefault,
      'isActive': isActive,
    });
  }

  factory TradingAccount.fromJson(String json) {
    final data = jsonDecode(json);
    return TradingAccount(
      accountId: data['accountId'],
      brokerId: data['brokerId'],
      brokerName: data['brokerName'],
      accountNumber: data['accountNumber'],
      apiKey: data['apiKey'],
      accountType: data['accountType'],
      maxDailyLoss: (data['maxDailyLoss'] as num).toDouble(),
      maxSessionLoss: (data['maxSessionLoss'] as num).toDouble(),
      maxConsecutiveLosses: data['maxConsecutiveLosses'],
      isDefault: data['isDefault'],
      isActive: data['isActive'],
    );
  }
}

class BrokerConfig {
  static const List<BrokerInfo> supportedBrokers = [
    BrokerInfo(
      id: 'xm_global',
      name: 'XM Global',
      apiUrl: 'https://api-mt5.xm.com',
      description: 'Global regulated broker',
    ),
    BrokerInfo(
      id: 'ic_markets',
      name: 'IC Markets',
      apiUrl: 'https://api.icmarkets.com/mt5',
      description: 'Trusted Australian broker',
    ),
    BrokerInfo(
      id: 'pepperstone',
      name: 'Pepperstone',
      apiUrl: 'https://api.pepperstone.com/mt5',
      description: 'Professional trading platform',
    ),
    BrokerInfo(
      id: 'fxcm',
      name: 'FXCM',
      apiUrl: 'https://api.fxcm.com/mt5',
      description: 'Leading forex broker',
    ),
  ];
}

class BrokerInfo {
  final String id;
  final String name;
  final String apiUrl;
  final String description;

  const BrokerInfo({
    required this.id,
    required this.name,
    required this.apiUrl,
    required this.description,
  });
}
