import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

class BotConfig {
  final String accountId;
  bool isEnabled;
  String riskType; // 'fixed' or 'percentage'
  double riskAmount; // $ amount or % percentage
  double maxDailyLossLimit; // $ amount
  List<String> tradingPairs; // ['EURUSD', 'GBPUSD', 'BTCUSD', etc]
  bool enableScalping;
  bool enableEconomicEventTrading;
  double leverage;

  BotConfig({
    required this.accountId,
    this.isEnabled = false,
    this.riskType = 'fixed',
    this.riskAmount = 10.0,
    this.maxDailyLossLimit = 100.0,
    this.tradingPairs = const ['EURUSD', 'GBPUSD'],
    this.enableScalping = true,
    this.enableEconomicEventTrading = true,
    this.leverage = 1.0,
  });

  Map<String, dynamic> toJson() => {
    'accountId': accountId,
    'isEnabled': isEnabled,
    'riskType': riskType,
    'riskAmount': riskAmount,
    'maxDailyLossLimit': maxDailyLossLimit,
    'tradingPairs': tradingPairs,
    'enableScalping': enableScalping,
    'enableEconomicEventTrading': enableEconomicEventTrading,
    'leverage': leverage,
  };

  BotConfig.fromJson(Map<String, dynamic> json)
    : accountId = json['accountId'],
      isEnabled = json['isEnabled'] ?? false,
      riskType = json['riskType'] ?? 'fixed',
      riskAmount = (json['riskAmount'] ?? 10.0).toDouble(),
      maxDailyLossLimit = (json['maxDailyLossLimit'] ?? 100.0).toDouble(),
      tradingPairs = List<String>.from(json['tradingPairs'] ?? ['EURUSD', 'GBPUSD']),
      enableScalping = json['enableScalping'] ?? true,
      enableEconomicEventTrading = json['enableEconomicEventTrading'] ?? true,
      leverage = (json['leverage'] ?? 1.0).toDouble();
}

class BotService extends ChangeNotifier {
  Map<String, BotConfig> _botConfigs = {};
  Map<String, BotStats> _botStats = {};

  BotService() {
    _loadConfigs();
  }

  Future<void> _loadConfigs() async {
    final prefs = await SharedPreferences.getInstance();
    final botConfigsJson = prefs.getString('bot_configs');
    final botStatsJson = prefs.getString('bot_stats');

    if (botConfigsJson != null) {
      final decoded = jsonDecode(botConfigsJson) as Map<String, dynamic>;
      _botConfigs = decoded.map((key, value) =>
        MapEntry(key, BotConfig.fromJson(value)));
    }

    if (botStatsJson != null) {
      final decoded = jsonDecode(botStatsJson) as Map<String, dynamic>;
      _botStats = decoded.map((key, value) =>
        MapEntry(key, BotStats.fromJson(value)));
    }

    notifyListeners();
  }

  Future<void> _saveConfigs() async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(_botConfigs.map((key, value) =>
      MapEntry(key, value.toJson())));
    await prefs.setString('bot_configs', encoded);
  }

  Future<void> _saveStats() async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(_botStats.map((key, value) =>
      MapEntry(key, value.toJson())));
    await prefs.setString('bot_stats', encoded);
  }

  BotConfig? getConfig(String accountId) {
    return _botConfigs[accountId];
  }

  BotStats? getStats(String accountId) {
    return _botStats[accountId] ?? BotStats(accountId: accountId);
  }

  void createConfig(String accountId) {
    if (!_botConfigs.containsKey(accountId)) {
      _botConfigs[accountId] = BotConfig(accountId: accountId);
      _botStats[accountId] = BotStats(accountId: accountId);
      _saveConfigs();
      _saveStats();
      notifyListeners();
    }
  }

  Future<void> toggleBot(String accountId, bool enabled) async {
    final config = _botConfigs[accountId];
    if (config != null) {
      config.isEnabled = enabled;
      await _saveConfigs();
      notifyListeners();
    }
  }

  Future<void> updateRiskSettings(
    String accountId,
    String riskType,
    double riskAmount,
    double maxDailyLoss,
  ) async {
    final config = _botConfigs[accountId];
    if (config != null) {
      config.riskType = riskType;
      config.riskAmount = riskAmount;
      config.maxDailyLossLimit = maxDailyLoss;
      await _saveConfigs();
      notifyListeners();
    }
  }

  Future<void> updateTradingPairs(String accountId, List<String> pairs) async {
    final config = _botConfigs[accountId];
    if (config != null) {
      config.tradingPairs = pairs;
      await _saveConfigs();
      notifyListeners();
    }
  }

  Future<void> updateBotStrategies(
    String accountId,
    bool scalping,
    bool economicEvents,
  ) async {
    final config = _botConfigs[accountId];
    if (config != null) {
      config.enableScalping = scalping;
      config.enableEconomicEventTrading = economicEvents;
      await _saveConfigs();
      notifyListeners();
    }
  }

  Future<void> recordTrade(
    String accountId,
    double profitLoss,
    bool isWin,
  ) async {
    final stats = _botStats[accountId] ?? BotStats(accountId: accountId);
    stats.totalTrades++;
    stats.totalProfitLoss += profitLoss;
    stats.dailyProfitLoss += profitLoss;

    if (isWin) {
      stats.winningTrades++;
    } else {
      stats.losingTrades++;
    }

    _botStats[accountId] = stats;
    await _saveStats();
    notifyListeners();
  }

  double getWinRate(String accountId) {
    final stats = _botStats[accountId];
    if (stats == null || stats.totalTrades == 0) return 0.0;
    return (stats.winningTrades / stats.totalTrades) * 100;
  }
}

class BotStats {
  final String accountId;
  int totalTrades = 0;
  int winningTrades = 0;
  int losingTrades = 0;
  double totalProfitLoss = 0.0;
  double dailyProfitLoss = 0.0;
  DateTime lastTradeTime = DateTime.now();

  BotStats({required this.accountId});

  Map<String, dynamic> toJson() => {
    'accountId': accountId,
    'totalTrades': totalTrades,
    'winningTrades': winningTrades,
    'losingTrades': losingTrades,
    'totalProfitLoss': totalProfitLoss,
    'dailyProfitLoss': dailyProfitLoss,
  };

  BotStats.fromJson(Map<String, dynamic> json)
    : accountId = json['accountId'],
      totalTrades = json['totalTrades'] ?? 0,
      winningTrades = json['winningTrades'] ?? 0,
      losingTrades = json['losingTrades'] ?? 0,
      totalProfitLoss = (json['totalProfitLoss'] ?? 0.0).toDouble(),
      dailyProfitLoss = (json['dailyProfitLoss'] ?? 0.0).toDouble();
}
