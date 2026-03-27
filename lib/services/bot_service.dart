import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import '../models/bot_model.dart';
import '../utils/environment_config.dart';

class BotService extends ChangeNotifier {
  Bot? _bot;
  BotStats? _stats;
  BotBilling? _billing;
  bool _isLoading = false;
  bool _isConnected = false;
  String? _errorMessage;
  String? _apiUrl;
  List<Map<String, dynamic>> _activeBots = [];

  Bot? get bot => _bot;
  BotStats? get stats => _stats;
  BotBilling? get billing => _billing;
  bool get isLoading => _isLoading;
  bool get isConnected => _isConnected;
  String? get errorMessage => _errorMessage;
  List<Map<String, dynamic>> get activeBots => _activeBots;

  // Fallback list for Exness / MT5 symbols when backend data is not yet loaded.
  final List<String> availableTradingSymbols = [
    'BTCUSDm',   // Bitcoin / USD
    'ETHUSDm',   // Ethereum / USD
    'EURUSDm',   // Euro / USD
    'USDJPYm',   // USD / Japanese Yen
    'XAUUSDm',   // Gold / USD
    'AAPLm',
    'AMDm',
    'MSFTm',
    'NVDAm',
    'JPMm',
    'BACm',
    'WFCm',
    'GOOGLm',
    'METAm',
    'ORCLm',
    'TSMm',
  ];

  final List<String> availableStrategies = [
    'Scalping',
    'Momentum Trading',
    'Trend Following',
    'Mean Reversion',
    'Range Trading',
    'Breakout Trading'
  ];

  BotService() {
    _apiUrl = EnvironmentConfig.apiUrl;
    // Initialize lazily when needed, not in constructor
    print('🔧 BotService initialized');
    print('🌐 API URL: $_apiUrl');
    print('📱 Environment: ${EnvironmentConfig.currentEnvironment}');
    _checkBackendConnection();
  }

  /// Check if backend is available
  Future<void> _checkBackendConnection() async {
    try {
      print('🔄 Checking backend connection to: $_apiUrl/api/health');
      final response = await http.get(
        Uri.parse('$_apiUrl/api/health'),
      ).timeout(const Duration(seconds: 5));
      
      _isConnected = response.statusCode == 200;
      if (_isConnected) {
        print('✅ Backend connected successfully');
        print('📊 Response: ${response.body}');
      } else {
        _errorMessage = 'Backend connection failed: HTTP ${response.statusCode}';
        print('❌ Backend health check failed: ${response.statusCode}');
        print('📄 Response: ${response.body}');
      }
      notifyListeners();
    } catch (e) {
      _isConnected = false;
      _errorMessage = 'Cannot connect to backend: $e';
      print('❌ Backend connection error: $e');
      notifyListeners();
    }
  }

  /// Fetch active bots from backend
  Future<void> fetchActiveBots({String? tradingMode}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (!_isConnected) {
        await _checkBackendConnection();
      }

      // Get user_id from SharedPreferences
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('user_id');
      final sessionToken = prefs.getString('auth_token');
      final mode = tradingMode ?? prefs.getString('trading_mode') ?? 'DEMO';

      String url = '$_apiUrl/api/bot/status?mode=$mode';
      if (userId != null && userId.isNotEmpty) {
        url += '&user_id=$userId';
      }

      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Content-Type': 'application/json',
          if (sessionToken != null && sessionToken.isNotEmpty)
            'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _activeBots = List<Map<String, dynamic>>.from(data['bots'] ?? []);
          _errorMessage = null;
          print('Fetched ${_activeBots.length} active bots from backend');
        } else {
          _errorMessage = data['error'] ?? 'Failed to fetch bots';
          _activeBots = [];
        }
      } else {
        _errorMessage = 'Backend returned status ${response.statusCode}';
        // Don't wipe _activeBots - preserve previous data on error
      }
    } catch (e) {
      _errorMessage = 'Error fetching bots: $e';
      // Don't wipe _activeBots - preserve previous data on error
      print('Bot fetch error: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Create new bot on backend
  Future<bool> createBotOnBackend({
    required String botId,
    required String accountId,
    required List<String> symbols,
    required String strategy,
    required double riskPerTrade,
    required double maxDailyLoss,
    required bool enabled,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // Get session token and user_id from SharedPreferences
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      print('🔐 DEBUG: CreateBot - Checking session...');
      print('  All keys in SharedPreferences: ${prefs.getKeys()}');
      print('  auth_token value: $sessionToken');
      print('  auth_token is null: ${sessionToken == null}');
      print('  auth_token isEmpty: ${sessionToken?.isEmpty ?? 'null object'}');
      print('  user_id: $userId');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage = 'Session expired. Please login again. Token was null or empty.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      print('✅ Token found, creating request headers...');
      final headers = {
        'Content-Type': 'application/json',
        'X-Session-Token': sessionToken,
      };
      print('📤 Headers being sent:');
      print('  Content-Type: ${headers['Content-Type']}');
      print('  X-Session-Token: ${headers['X-Session-Token']?.substring(0, 20)}...');

      final requestBody = {
        'botId': botId,
        'user_id': userId,
        'credentialId': accountId,
        'symbols': symbols,
        'strategy': strategy,
        'riskPerTrade': riskPerTrade,
        'maxDailyLoss': maxDailyLoss,
        'enabled': enabled,
        'autoSwitch': true,
        'dynamicSizing': true,
        'basePositionSize': 1.0,
      };

      print('📤 Sending bot creation request to $_apiUrl/api/bot/create');
      print('  Body: $requestBody');

      final response = await http.post(
        Uri.parse('$_apiUrl/api/bot/create'),
        headers: headers,
        body: jsonEncode(requestBody),
      ).timeout(const Duration(seconds: 10));

      print('📥 Response: ${response.statusCode}');
      print('  Body: ${response.body}');
      
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final responseData = jsonDecode(response.body);
        if (responseData['success'] == true) {
          await fetchActiveBots();
          return true;
        }
        _errorMessage = responseData['error'] ?? 'Failed to create bot';
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired or invalid token. Please login again.';
        print('❌ BOT CREATION 401 ERROR:');
        print('  Status: ${response.statusCode}');
        print('  Response: ${response.body}');
        print('  Token was: ${sessionToken?.substring(0, 20)}...');
      } else {
        final responseData = jsonDecode(response.body);
        _errorMessage = responseData['error'] ?? 'Failed to create bot';
        print('❌ BOT CREATION ERROR (${response.statusCode}):');
        print('  Error: ${_errorMessage}');
        print('  Full response: ${response.body}');
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error creating bot: $e';
      print('Bot creation error: $e');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Start bot trading on backend
  Future<bool> startBotTrading(String botId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage = 'Session expired. Please login again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      final response = await http.post(
        Uri.parse('$_apiUrl/api/bot/start'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({'botId': botId}),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          print('Bot started: $botId');
          await fetchActiveBots();
          return true;
        }
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired. Please login again.';
      } else {
        _errorMessage = jsonDecode(response.body)['error'] ?? 'Failed to start bot';
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error starting bot: $e';
      print('Bot start error: $e');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Stop bot trading
  Future<bool> stopBotTrading(String botId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage = 'Session expired. Please login again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      final response = await http.post(
        Uri.parse('$_apiUrl/api/bot/stop/$botId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          print('Bot stopped: $botId');
          await fetchActiveBots();
          return true;
        }
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired. Please login again.';
      } else {
        _errorMessage = jsonDecode(response.body)['error'] ?? 'Failed to stop bot';
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error stopping bot: $e';
      print('Bot stop error: $e');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> _initializeBot() async {
    _isLoading = true;
    notifyListeners();

    try {
      // First try to fetch from backend
      await fetchActiveBots();
      if (_activeBots.isNotEmpty) {
        // Use first bot from backend
        final botData = _activeBots[0];
        _updateBotFromData(botData);
      } else {
        // Fallback: Load from local storage
        final prefs = await SharedPreferences.getInstance();
        final botJson = prefs.getString('bot_config');
        // Note: Fallback provider notification would be done from UI layer
        if (botJson != null) {
          _bot = Bot.fromJson(jsonDecode(botJson));
          _loadBotStats();
          _loadBotBilling();
        } else {
          // Create default bot
          _bot = Bot(
            id: 'bot_${DateTime.now().millisecondsSinceEpoch}',
            isActive: false,
            riskPerTrade: 100.0,
            riskType: 'fixed',
            maxDailyLoss: 500.0,
            tradingPairs: ['EURUSD', 'BTCUSD'],
            strategies: ['Scalping'],
            createdAt: DateTime.now(),
          );
          await saveBot(_bot!);
        }
      }
    } catch (e) {
      print('Error initializing bot: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Update bot from backend data
  void _updateBotFromData(Map<String, dynamic> botData) {
    try {
      _bot = Bot(
        id: botData['botId'] ?? 'unknown',
        isActive: botData['enabled'] ?? false,
        riskPerTrade: (botData['riskPerTrade'] ?? 100.0).toDouble(),
        riskType: botData['riskType'] ?? 'fixed',
        maxDailyLoss: (botData['maxDailyLoss'] ?? 500.0).toDouble(),
        tradingPairs: List<String>.from(botData['symbols'] ?? []),
        strategies: [botData['strategy'] ?? 'Trend Following'],
        createdAt: DateTime.parse(botData['createdAt'] ?? DateTime.now().toIso8601String()),
      );

      // Update stats from backend
      final status = botData['status'] ?? {};
      _stats = BotStats(
        totalTrades: status['totalTrades'] ?? 0,
        winningTrades: status['winningTrades'] ?? 0,
        losingTrades: (status['totalTrades'] ?? 0) - (status['winningTrades'] ?? 0),
        winRate: (status['winRate'] ?? 0) / 100,
        grossProfit: (status['totalProfit'] ?? 0.0).toDouble(),
        commission: 0,
        netProfit: (status['totalProfit'] ?? 0.0).toDouble(),
        dailyPnL: status['dailyProfit'] ?? 0.0,
      );

      _loadBotBilling();
    } catch (e) {
      print('Error updating bot from data: $e');
    }
  }

  Future<void> saveBot(Bot bot) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('bot_config', jsonEncode(bot.toJson()));
      _bot = bot;
      notifyListeners();
    } catch (e) {
      print('Error saving bot: $e');
    }
  }

  Future<void> toggleBot(bool isActive) async {
    if (_bot != null) {
      final updatedBot = Bot(
        id: _bot!.id,
        isActive: isActive,
        riskPerTrade: _bot!.riskPerTrade,
        riskType: _bot!.riskType,
        maxDailyLoss: _bot!.maxDailyLoss,
        tradingPairs: _bot!.tradingPairs,
        strategies: _bot!.strategies,
        createdAt: _bot!.createdAt,
        startedAt: isActive ? DateTime.now() : _bot!.startedAt,
      );
      await saveBot(updatedBot);
      
      // Also start/stop on backend if connected
      if (isActive) {
        await startBotTrading(_bot!.id);
      } else {
        await stopBotTrading(_bot!.id);
      }
    }
  }

  Future<void> updateRiskSettings({
    required double riskPerTrade,
    required String riskType,
    required double maxDailyLoss,
  }) async {
    if (_bot != null) {
      final updatedBot = Bot(
        id: _bot!.id,
        isActive: _bot!.isActive,
        riskPerTrade: riskPerTrade,
        riskType: riskType,
        maxDailyLoss: maxDailyLoss,
        tradingPairs: _bot!.tradingPairs,
        strategies: _bot!.strategies,
        createdAt: _bot!.createdAt,
        startedAt: _bot!.startedAt,
      );
      await saveBot(updatedBot);
    }
  }

  Future<void> updateTradingPairs(List<String> pairs) async {
    if (_bot != null) {
      final updatedBot = Bot(
        id: _bot!.id,
        isActive: _bot!.isActive,
        riskPerTrade: _bot!.riskPerTrade,
        riskType: _bot!.riskType,
        maxDailyLoss: _bot!.maxDailyLoss,
        tradingPairs: pairs,
        strategies: _bot!.strategies,
        createdAt: _bot!.createdAt,
        startedAt: _bot!.startedAt,
      );
      await saveBot(updatedBot);
    }
  }

  Future<void> updateStrategies(List<String> strategies) async {
    if (_bot != null) {
      final updatedBot = Bot(
        id: _bot!.id,
        isActive: _bot!.isActive,
        riskPerTrade: _bot!.riskPerTrade,
        riskType: _bot!.riskType,
        maxDailyLoss: _bot!.maxDailyLoss,
        tradingPairs: _bot!.tradingPairs,
        strategies: strategies,
        createdAt: _bot!.createdAt,
        startedAt: _bot!.startedAt,
      );
      await saveBot(updatedBot);
    }
  }

  void _loadBotStats() {
    // Initialize with empty stats; real data comes from backend via _updateBotFromData
    if (_stats == null) {
      _stats = BotStats(
        totalTrades: 0,
        winningTrades: 0,
        losingTrades: 0,
        winRate: 0,
        grossProfit: 0,
        commission: 0,
        netProfit: 0,
        dailyPnL: 0,
      );
    }
    notifyListeners();
  }

  void _loadBotBilling() {
    _billing = BotBilling(
      monthlyFee: 1000.00,
      commissionRate: 0.15,
      totalEarnings: _stats?.netProfit ?? 0,
      totalBilled: 1000.00 + ((_stats?.netProfit ?? 0) * 0.15),
      billingCycle: DateTime.now(),
    );
    notifyListeners();
  }

  /// Remove a bot from the active bots list locally
  void removeBotLocally(String botId) {
    _activeBots.removeWhere((bot) => (bot['botId'] ?? bot['id']) == botId);
    notifyListeners();
  }
}

