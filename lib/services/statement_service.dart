import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/account.dart';
import '../models/statement.dart';
import '../models/trade.dart';

class StatementService extends ChangeNotifier {
  StatementService() {
    // Initialize lazily when needed, not in constructor
  }
  List<Statement> _statements = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<Statement> get statements => _statements;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> _loadStatementsFromStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final statementsJson = prefs.getStringList('statements') ?? [];
      _statements = statementsJson
          .map((json) => Statement.fromJson(jsonDecode(json)))
          .toList();
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to load statements: $e';
      notifyListeners();
    }
  }

  Future<Statement> generateStatement(
    Account account,
    List<Trade> trades,
    DateTime startDate,
    DateTime endDate,
  ) async {
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

      // Calculate statistics
      final closedTrades =
          tradesInPeriod.where((t) => t.status == TradeStatus.closed).toList();
      final winningTrades =
          closedTrades.where((t) => t.profit != null && t.profit! > 0).toList();
      final losingTrades = closedTrades
          .where((t) => t.profit == null || t.profit! <= 0)
          .toList();

      final totalProfit = winningTrades.fold<double>(
        0.0,
        (sum, t) => sum + (t.profit ?? 0),
      );
      final totalLoss = losingTrades.fold<double>(
        0.0,
        (sum, t) => sum + (t.profit ?? 0),
      );

      final largestWin = winningTrades.isEmpty
          ? 0.0
          : winningTrades
              .map((t) => t.profit ?? 0)
              .reduce((a, b) => a > b ? a : b);
      final largestLoss = losingTrades.isEmpty
          ? 0.0
          : losingTrades
              .map((t) => t.profit ?? 0)
              .reduce((a, b) => a < b ? a : b);

      final averageWin =
          winningTrades.isEmpty ? 0.0 : totalProfit / winningTrades.length;
      final averageLoss =
          losingTrades.isEmpty ? 0.0 : totalLoss / losingTrades.length;

      final winRate = closedTrades.isEmpty
          ? 0.0
          : (winningTrades.length / closedTrades.length) * 100;

      // Convert trades to statement trades
      final statementTrades = tradesInPeriod
          .map((trade) => StatementTrade(
                id: trade.id,
                symbol: trade.symbol,
                type: trade.type == TradeType.buy ? 'BUY' : 'SELL',
                quantity: trade.quantity,
                entryPrice: trade.entryPrice,
                exitPrice: trade.currentPrice ?? trade.entryPrice,
                openDate: trade.openedAt,
                closeDate: trade.closedAt ?? DateTime.now(),
                profit: trade.profit ?? 0,
                profitPercentage: trade.profitPercentage ?? 0,
                status: trade.status.toString().split('.').last,
              ))
          .toList();

      // Create statement
      final statement = Statement(
        id: 'stmt_${DateTime.now().millisecondsSinceEpoch}',
        accountId: account.id,
        accountNumber: account.accountNumber,
        startDate: startDate,
        endDate: endDate,
        openingBalance: account.balance - (totalProfit + totalLoss),
        closingBalance: account.balance,
        totalDeposits: 0, // Would need transaction history
        totalWithdrawals: 0, // Would need transaction history
        totalProfit: totalProfit,
        totalLoss: totalLoss,
        totalTrades: closedTrades.length,
        winningTrades: winningTrades.length,
        losingTrades: losingTrades.length,
        winRate: winRate,
        largestWin: largestWin,
        largestLoss: largestLoss,
        averageWin: averageWin,
        averageLoss: averageLoss,
        trades: statementTrades,
        generatedAt: DateTime.now(),
      );

      // Save to storage
      _statements.add(statement);
      await _saveStatementsToStorage();

      _isLoading = false;
      notifyListeners();
      return statement;
    } catch (e) {
      _errorMessage = 'Failed to generate statement: $e';
      _isLoading = false;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> _saveStatementsToStorage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final statementsJson =
          _statements.map((stmt) => jsonEncode(stmt.toJson())).toList();
      await prefs.setStringList('statements', statementsJson);
    } catch (e) {
      _errorMessage = 'Failed to save statements: $e';
      notifyListeners();
    }
  }

  Future<void> deleteStatement(String statementId) async {
    try {
      _statements.removeWhere((stmt) => stmt.id == statementId);
      await _saveStatementsToStorage();
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to delete statement: $e';
      notifyListeners();
    }
  }

  void clearErrorMessage() {
    _errorMessage = null;
    notifyListeners();
  }
}
