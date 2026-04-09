import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/account.dart';
import '../models/financial_statement.dart';
import '../models/trade.dart';

class FinancialService extends ChangeNotifier {
  FinancialService() {
    // Initialize lazily when needed, not in constructor
  }
  List<FinancialStatement> _financialStatements = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<FinancialStatement> get financialStatements => _financialStatements;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> _loadFinancialStatementsFromStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final statementsJson = prefs.getStringList('financial_statements') ?? [];
      _financialStatements = statementsJson
          .map((json) => FinancialStatement.fromJson(jsonDecode(json)))
          .toList();
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to load financial statements: $e';
      notifyListeners();
    }
  }

  /// Generate comprehensive financial statement with capital, revenue, costs, and cash flows
  Future<FinancialStatement> generateFinancialStatement(
    Account account,
    List<Trade> trades,
    DateTime startDate,
    DateTime endDate, {
    double? initialCapital,
    double? commissionRate = 0.001, // 0.1% default commission
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // Filter trades by date range
      final tradesInPeriod = trades
          .where((t) =>
              t.closedAt != null &&
              t.closedAt!.isAfter(startDate) &&
              t.closedAt!.isBefore(endDate.add(const Duration(days: 1))))
          .toList();

      // ==================== CAPITAL & INVESTMENT ====================
      final capitalInvested = initialCapital ?? account.balance;
      const additionalInvestments = 0.0; // Would come from deposit history
      final totalCapital = capitalInvested + additionalInvestments;

      // ==================== REVENUE ====================
      final closedTrades =
          tradesInPeriod.where((t) => t.status == TradeStatus.closed).toList();
      final winningTrades =
          closedTrades.where((t) => t.profit != null && t.profit! > 0).toList();
      final losingTrades = closedTrades
          .where((t) => t.profit == null || t.profit! <= 0)
          .toList();

      final tradingProfit = winningTrades.fold<double>(
        0.0,
        (sum, t) => sum + (t.profit ?? 0),
      );
      const dividends = 0.0; // Would come from dividend records
      const interest = 0.0; // Would come from interest records
      const otherIncome = 0.0;
      final totalRevenue = tradingProfit + dividends + interest + otherIncome;

      // ==================== OPERATING COSTS ====================
      // Calculate commissions from trades
      var commissions = 0.0;
      for (final trade in tradesInPeriod) {
        final tradeValue = trade.quantity * trade.entryPrice;
        commissions += tradeValue *
            (commissionRate ?? 0.001); // Commission on entry and exit
        commissions += tradeValue * (commissionRate ?? 0.001);
      }

      var spreads = 0.0; // Average spread cost per trade
      if (tradesInPeriod.isNotEmpty) {
        spreads = tradesInPeriod.length *
            2.0; // Approximate spread cost (varies by instrument)
      }

      const platformFees = 0.0; // Monthly platform fees
      const withdrawalFees = 0.0; // Withdrawal transaction fees
      const otherCosts = 0.0;

      final totalCosts =
          commissions + spreads + platformFees + withdrawalFees + otherCosts;

      // ==================== NET PROFIT/LOSS ====================
      final grossProfit = tradingProfit;
      final operatingProfit = grossProfit - (commissions + spreads);
      final netProfit = totalRevenue - totalCosts;
      final profitMargin =
          totalRevenue > 0 ? ((netProfit / totalRevenue) * 100) : 0.0;
      final roi = totalCapital > 0 ? ((netProfit / totalCapital) * 100) : 0.0;

      // ==================== CASH FLOW ====================
      final cashFlowIn = <CashFlowEntry>[];
      final cashFlowOut = <CashFlowEntry>[];

      // Add trade profits as cash flow
      for (final trade in winningTrades) {
        cashFlowIn.add(
          CashFlowEntry(
            id: 'cf_in_${trade.id}',
            description: 'Trading Profit - ${trade.symbol}',
            amount: trade.profit ?? 0.0,
            date: trade.closedAt ?? DateTime.now(),
            category: 'trading_profit',
            reference: trade.id,
          ),
        );
      }

      // Add trade losses as cash flow out
      for (final trade in losingTrades) {
        cashFlowOut.add(
          CashFlowEntry(
            id: 'cf_out_${trade.id}',
            description: 'Trading Loss - ${trade.symbol}',
            amount: (trade.profit ?? 0.0).abs(),
            date: trade.closedAt ?? DateTime.now(),
            category: 'trading_loss',
            reference: trade.id,
          ),
        );
      }

      // Add commissions as cash flow out
      if (commissions > 0) {
        cashFlowOut.add(
          CashFlowEntry(
            id: 'cf_out_commissions',
            description: 'Trading Commissions',
            amount: commissions,
            date: endDate,
            category: 'commission',
          ),
        );
      }

      // Add spreads as cash flow out
      if (spreads > 0) {
        cashFlowOut.add(
          CashFlowEntry(
            id: 'cf_out_spreads',
            description: 'Bid-Ask Spreads',
            amount: spreads,
            date: endDate,
            category: 'spread',
          ),
        );
      }

      // Add platform fees as cash flow out
      if (platformFees > 0) {
        cashFlowOut.add(
          CashFlowEntry(
            id: 'cf_out_platform_fees',
            description: 'Platform Fees',
            amount: platformFees,
            date: endDate,
            category: 'platform_fee',
          ),
        );
      }

      final totalCashIn = cashFlowIn.fold<double>(
        0.0,
        (sum, e) => sum + e.amount,
      );
      final totalCashOut = cashFlowOut.fold<double>(
        0.0,
        (sum, e) => sum + e.amount,
      );
      final netCashFlow = totalCashIn - totalCashOut;

      // ==================== ACCOUNT BALANCE ====================
      final openingBalance =
          account.balance - netProfit; // Reconstruct opening balance
      final closingBalance = account.balance;
      final balanceChange = closingBalance - openingBalance;

      // Create financial statement
      final statement = FinancialStatement(
        id: 'fin_stmt_${DateTime.now().millisecondsSinceEpoch}',
        accountId: account.id,
        currency: account.currency,
        startDate: startDate,
        endDate: endDate,
        capitalInvested: capitalInvested,
        additionalInvestments: additionalInvestments,
        totalCapital: totalCapital,
        tradingProfit: tradingProfit,
        dividends: dividends,
        interest: interest,
        otherIncome: otherIncome,
        totalRevenue: totalRevenue,
        commissions: commissions,
        spreads: spreads,
        platformFees: platformFees,
        withdrawalFees: withdrawalFees,
        otherCosts: otherCosts,
        totalCosts: totalCosts,
        grossProfit: grossProfit,
        operatingProfit: operatingProfit,
        netProfit: netProfit,
        profitMargin: profitMargin,
        ROI: roi,
        cashFlowIn: cashFlowIn,
        cashFlowOut: cashFlowOut,
        totalCashIn: totalCashIn,
        totalCashOut: totalCashOut,
        netCashFlow: netCashFlow,
        openingBalance: openingBalance,
        closingBalance: closingBalance,
        balanceChange: balanceChange,
        generatedAt: DateTime.now(),
      );

      // Save to storage
      _financialStatements.add(statement);
      await _saveFinancialStatementsToStorage();

      _isLoading = false;
      notifyListeners();
      return statement;
    } catch (e) {
      _errorMessage = 'Failed to generate financial statement: $e';
      _isLoading = false;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> _saveFinancialStatementsToStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final statementsJson = _financialStatements
          .map((stmt) => jsonEncode(stmt.toJson()))
          .toList();
      await prefs.setStringList('financial_statements', statementsJson);
    } catch (e) {
      _errorMessage = 'Failed to save financial statements: $e';
      notifyListeners();
    }
  }

  Future<void> deleteFinancialStatement(String statementId) async {
    try {
      _financialStatements.removeWhere((stmt) => stmt.id == statementId);
      await _saveFinancialStatementsToStorage();
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to delete financial statement: $e';
      notifyListeners();
    }
  }

  void clearErrorMessage() {
    _errorMessage = null;
    notifyListeners();
  }
}
