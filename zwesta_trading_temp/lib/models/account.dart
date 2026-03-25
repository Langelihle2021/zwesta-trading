class Account {
  final int id;
  final String accountName;
  final String accountNumber;
  final String accountType;
  final double initialBalance;
  final double currentBalance;
  final String currency;

  Account({
    required this.id,
    required this.accountName,
    required this.accountNumber,
    required this.accountType,
    required this.initialBalance,
    required this.currentBalance,
    required this.currency,
  });

  double get profitLoss => currentBalance - initialBalance;
  double get profitPercent => (profitLoss / initialBalance) * 100;

  factory Account.fromJson(Map<String, dynamic> json) {
    return Account(
      id: json['id'] ?? 0,
      accountName: json['accountName'] ?? json['account_name'] ?? '',
      accountNumber: json['accountNumber'] ?? json['account_number'] ?? '',
      accountType: json['accountType'] ?? json['account_type'] ?? 'Standard',
      initialBalance: (json['initialBalance'] ?? json['initial_balance'] ?? 0).toDouble(),
      currentBalance: (json['currentBalance'] ?? json['current_balance'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'USD',
    );
  }
}
