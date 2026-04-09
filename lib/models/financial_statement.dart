import 'package:intl/intl.dart';

/// Represents a complete financial statement with capital, revenue, costs, and cash flows
class FinancialStatement {
  final String id;
  final String accountId;
  final String currency;
  final DateTime startDate;
  final DateTime endDate;
  
  // Capital & Investment
  final double capitalInvested;
  final double additionalInvestments;
  final double totalCapital;
  
  // Revenue
  final double tradingProfit;
  final double dividends;
  final double interest;
  final double otherIncome;
  final double totalRevenue;
  
  // Operating Costs
  final double commissions;
  final double spreads;
  final double platformFees;
  final double withdrawalFees;
  final double otherCosts;
  final double totalCosts;
  
  // Net Profit/Loss
  final double grossProfit;
  final double operatingProfit;
  final double netProfit;
  final double profitMargin; // Net Profit / Total Revenue
  final double ROI; // (Net Profit / Total Capital) * 100
  
  // Cash Flow
  final List<CashFlowEntry> cashFlowIn;
  final List<CashFlowEntry> cashFlowOut;
  final double totalCashIn;
  final double totalCashOut;
  final double netCashFlow;
  
  // Account Balance
  final double openingBalance;
  final double closingBalance;
  final double balanceChange;
  
  final DateTime generatedAt;

  FinancialStatement({
    required this.id,
    required this.accountId,
    required this.currency,
    required this.startDate,
    required this.endDate,
    required this.capitalInvested,
    required this.additionalInvestments,
    required this.totalCapital,
    required this.tradingProfit,
    required this.dividends,
    required this.interest,
    required this.otherIncome,
    required this.totalRevenue,
    required this.commissions,
    required this.spreads,
    required this.platformFees,
    required this.withdrawalFees,
    required this.otherCosts,
    required this.totalCosts,
    required this.grossProfit,
    required this.operatingProfit,
    required this.netProfit,
    required this.profitMargin,
    required this.ROI,
    required this.cashFlowIn,
    required this.cashFlowOut,
    required this.totalCashIn,
    required this.totalCashOut,
    required this.netCashFlow,
    required this.openingBalance,
    required this.closingBalance,
    required this.balanceChange,
    required this.generatedAt,
  });

  factory FinancialStatement.fromJson(Map<String, dynamic> json) {
    return FinancialStatement(
      id: json['id'] ?? '',
      accountId: json['accountId'] ?? '',
      currency: json['currency'] ?? 'USD',
      startDate: DateTime.parse(json['startDate'] ?? DateTime.now().toString()),
      endDate: DateTime.parse(json['endDate'] ?? DateTime.now().toString()),
      capitalInvested: (json['capitalInvested'] ?? 0).toDouble(),
      additionalInvestments: (json['additionalInvestments'] ?? 0).toDouble(),
      totalCapital: (json['totalCapital'] ?? 0).toDouble(),
      tradingProfit: (json['tradingProfit'] ?? 0).toDouble(),
      dividends: (json['dividends'] ?? 0).toDouble(),
      interest: (json['interest'] ?? 0).toDouble(),
      otherIncome: (json['otherIncome'] ?? 0).toDouble(),
      totalRevenue: (json['totalRevenue'] ?? 0).toDouble(),
      commissions: (json['commissions'] ?? 0).toDouble(),
      spreads: (json['spreads'] ?? 0).toDouble(),
      platformFees: (json['platformFees'] ?? 0).toDouble(),
      withdrawalFees: (json['withdrawalFees'] ?? 0).toDouble(),
      otherCosts: (json['otherCosts'] ?? 0).toDouble(),
      totalCosts: (json['totalCosts'] ?? 0).toDouble(),
      grossProfit: (json['grossProfit'] ?? 0).toDouble(),
      operatingProfit: (json['operatingProfit'] ?? 0).toDouble(),
      netProfit: (json['netProfit'] ?? 0).toDouble(),
      profitMargin: (json['profitMargin'] ?? 0).toDouble(),
      ROI: (json['ROI'] ?? 0).toDouble(),
      cashFlowIn: (json['cashFlowIn'] as List?)
          ?.map((e) => CashFlowEntry.fromJson(e))
          .toList() ?? [],
      cashFlowOut: (json['cashFlowOut'] as List?)
          ?.map((e) => CashFlowEntry.fromJson(e))
          .toList() ?? [],
      totalCashIn: (json['totalCashIn'] ?? 0).toDouble(),
      totalCashOut: (json['totalCashOut'] ?? 0).toDouble(),
      netCashFlow: (json['netCashFlow'] ?? 0).toDouble(),
      openingBalance: (json['openingBalance'] ?? 0).toDouble(),
      closingBalance: (json['closingBalance'] ?? 0).toDouble(),
      balanceChange: (json['balanceChange'] ?? 0).toDouble(),
      generatedAt: DateTime.parse(json['generatedAt'] ?? DateTime.now().toString()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'accountId': accountId,
      'currency': currency,
      'startDate': startDate.toIso8601String(),
      'endDate': endDate.toIso8601String(),
      'capitalInvested': capitalInvested,
      'additionalInvestments': additionalInvestments,
      'totalCapital': totalCapital,
      'tradingProfit': tradingProfit,
      'dividends': dividends,
      'interest': interest,
      'otherIncome': otherIncome,
      'totalRevenue': totalRevenue,
      'commissions': commissions,
      'spreads': spreads,
      'platformFees': platformFees,
      'withdrawalFees': withdrawalFees,
      'otherCosts': otherCosts,
      'totalCosts': totalCosts,
      'grossProfit': grossProfit,
      'operatingProfit': operatingProfit,
      'netProfit': netProfit,
      'profitMargin': profitMargin,
      'ROI': ROI,
      'cashFlowIn': cashFlowIn.map((e) => e.toJson()).toList(),
      'cashFlowOut': cashFlowOut.map((e) => e.toJson()).toList(),
      'totalCashIn': totalCashIn,
      'totalCashOut': totalCashOut,
      'netCashFlow': netCashFlow,
      'openingBalance': openingBalance,
      'closingBalance': closingBalance,
      'balanceChange': balanceChange,
      'generatedAt': generatedAt.toIso8601String(),
    };
  }
}

/// Represents a single cash flow transaction
class CashFlowEntry {
  final String id;
  final String description;
  final double amount;
  final DateTime date;
  final String category; // 'deposit', 'withdrawal', 'dividend', 'interest', 'fee', etc.
  final String? reference; // Trade ID, Transaction ID, etc.

  CashFlowEntry({
    required this.id,
    required this.description,
    required this.amount,
    required this.date,
    required this.category,
    this.reference,
  });

  factory CashFlowEntry.fromJson(Map<String, dynamic> json) {
    return CashFlowEntry(
      id: json['id'] ?? '',
      description: json['description'] ?? '',
      amount: (json['amount'] ?? 0).toDouble(),
      date: DateTime.parse(json['date'] ?? DateTime.now().toString()),
      category: json['category'] ?? '',
      reference: json['reference'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'description': description,
      'amount': amount,
      'date': date.toIso8601String(),
      'category': category,
      'reference': reference,
    };
  }
}

/// Helper class for financial calculations
class FinancialMetrics {
  static String formatCurrency(double amount, [String currency = 'USD']) {
    const symbols = {
      'USD': r'$',
      'ZAR': 'R',
      'GBP': '£',
      'EUR': '€',
    };
    final normalizedCurrency = currency.trim().toUpperCase();
    final formatter = NumberFormat.currency(
      symbol: symbols[normalizedCurrency] ?? '$normalizedCurrency ',
      decimalDigits: 2,
    );
    return formatter.format(amount);
  }

  static String formatPercentage(double percentage) {
    return '${percentage.toStringAsFixed(2)}%';
  }

  static double calculateROI(double netProfit, double capitalInvested) {
    if (capitalInvested <= 0) return 0.0;
    return ((netProfit / capitalInvested) * 100);
  }

  static double calculateProfitMargin(double netProfit, double totalRevenue) {
    if (totalRevenue <= 0) return 0.0;
    return ((netProfit / totalRevenue) * 100);
  }

  static String getCashFlowStatus(double netCashFlow) {
    if (netCashFlow > 0) {
      return 'Positive Cash Flow';
    } else if (netCashFlow < 0) {
      return 'Negative Cash Flow';
    } else {
      return 'Neutral Cash Flow';
    }
  }

  static String getProfitStatus(double netProfit) {
    if (netProfit > 0) {
      return 'Profitable';
    } else if (netProfit < 0) {
      return 'Loss-Making';
    } else {
      return 'Break-Even';
    }
  }
}
