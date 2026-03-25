import 'package:flutter/material.dart';
import 'package:zwesta_trading/models/trade_model.dart';
import 'package:zwesta_trading/models/position_model.dart';
import 'package:zwesta_trading/services/api_service.dart';

class TradingProvider extends ChangeNotifier {
  final _apiService = ApiService();

  List<TradeModel> _trades = [];
  List<PositionModel> _positions = [];
  double _totalPnL = 0;
  double _winRate = 0;
  bool _isLoading = false;
  String? _error;

  // Getters
  List<TradeModel> get trades => _trades;
  List<PositionModel> get positions => _positions;
  double get totalPnL => _totalPnL;
  double get winRate => _winRate;
  bool get isLoading => _isLoading;
  String? get error => _error;

  int get totalTrades => _trades.length;
  int get openPositions => _positions.length;

  Future<void> fetchTrades() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _apiService.getTrades();
      _trades = (data['trades'] as List)
          .map((t) => TradeModel.fromJson(t))
          .toList();

      _calculateStatistics();
      _error = null;
    } catch (e) {
      _error = 'Failed to fetch trades: $e';
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> fetchPositions() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _apiService.getPositions();
      _positions = (data['positions'] as List)
          .map((p) => PositionModel.fromJson(p))
          .toList();
      _error = null;
    } catch (e) {
      _error = 'Failed to fetch positions: $e';
    }

    _isLoading = false;
    notifyListeners();
  }

  void _calculateStatistics() {
    if (_trades.isEmpty) {
      _totalPnL = 0;
      _winRate = 0;
      return;
    }

    _totalPnL = _trades.fold(0, (sum, trade) => sum + trade.pnl);

    int winningTrades =
        _trades.where((trade) => trade.pnl > 0).length;
    _winRate = (winningTrades / _trades.length) * 100;
  }

  Future<bool> closeTrade(String tradeId) async {
    try {
      await _apiService.closeTrade(tradeId);
      _trades.removeWhere((t) => t.id == tradeId);
      _calculateStatistics();
      notifyListeners();
      return true;
    } catch (e) {
      _error = 'Failed to close trade: $e';
      notifyListeners();
      return false;
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  Future<void> refreshData() async {
    await Future.wait([fetchTrades(), fetchPositions()]);
  }
}
