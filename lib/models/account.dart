class Account {
  final String id;
  final String accountNumber;
  final double balance;
  final double usedMargin;
  final double availableMargin;
  final double profit;
  final String currency;
  final String status;
  final DateTime createdAt;
  final String leverage;
  final String? broker;
  final String? server;

  Account({
    required this.id,
    required this.accountNumber,
    required this.balance,
    required this.usedMargin,
    required this.availableMargin,
    required this.profit,
    required this.currency,
    required this.status,
    required this.createdAt,
    required this.leverage,
    this.broker,
    this.server,
  });

  factory Account.fromJson(Map<String, dynamic> json) {
    return Account(
      id: json['id'] ?? '',
      accountNumber: json['accountNumber'] ?? '',
      balance: (json['balance'] ?? 0).toDouble(),
      usedMargin: (json['usedMargin'] ?? 0).toDouble(),
      availableMargin: (json['availableMargin'] ?? 0).toDouble(),
      profit: (json['profit'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'USD',
      status: json['status'] ?? 'active',
      createdAt: DateTime.parse(json['createdAt'] ?? DateTime.now().toString()),
      leverage: json['leverage'] ?? '1:100',
      broker: json['broker'],
      server: json['server'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'accountNumber': accountNumber,
      'balance': balance,
      'usedMargin': usedMargin,
      'availableMargin': availableMargin,
      'currency': currency,
      'status': status,
      'createdAt': createdAt.toIso8601String(),
      'leverage': leverage,
      'broker': broker,
      'server': server,
    };
  }

  double get marginUsagePercentage {
    if (balance == 0) return 0;
    return (usedMargin / balance) * 100;
  }

  bool get isActive => status.toLowerCase() == 'active';
}
