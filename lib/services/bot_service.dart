import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/bot_model.dart';
import '../utils/environment_config.dart';

class BotService extends ChangeNotifier {
  BotService() {
    _apiUrl = EnvironmentConfig.apiUrl;
    // Initialize lazily when needed, not in constructor
    debugPrint('🔧 BotService initialized');
    debugPrint('🌐 API URL: $_apiUrl');
    debugPrint('📱 Environment: ${EnvironmentConfig.currentEnvironment}');
    _checkBackendConnection();
  }
  Bot? _bot;
  BotStats? _stats;
  BotBilling? _billing;
  bool _isLoading = false;
  bool _isConnected = false;
  String? _errorMessage;
  String? _apiUrl;
  List<Map<String, dynamic>> _activeBots = [];
  SharedPreferences? _prefs;
  Timer? _pollTimer;
  bool _authPollingDisabled = false;
  DateTime? _lastFetchAt;
  String? _lastTradingMode;
  Future<void>? _inFlightFetch;

  Bot? get bot => _bot;
  BotStats? get stats => _stats;
  BotBilling? get billing => _billing;
  bool get isLoading => _isLoading;
  bool get isConnected => _isConnected;
  String? get errorMessage => _errorMessage;
  List<Map<String, dynamic>> get activeBots => _activeBots;

  Future<SharedPreferences> _getPrefs() async {
    _prefs ??= await SharedPreferences.getInstance();
    return _prefs!;
  }

  void startPolling({String? tradingMode, Duration interval = const Duration(seconds: 15)}) {
    final mode = tradingMode ?? _lastTradingMode;
    _pollTimer?.cancel();
    if (mode == null || mode.isEmpty || _authPollingDisabled) {
      return;
    }
    _pollTimer = Timer.periodic(interval, (_) {
      fetchActiveBots(tradingMode: mode);
    });
  }

  void stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  // Fallback list for Exness / MT5 symbols when backend data is not yet loaded.
  final List<String> availableTradingSymbols = [
    'BTCUSD', // Bitcoin / USD
    'ETHUSD', // Ethereum / USD
    'EURUSD', // Euro / USD
    'USDJPY', // USD / Japanese Yen
    'XAUUSD', // Gold / USD
    'AAPL',
    'AMD',
    'MSFT',
    'NVDA',
    'JPM',
    'BAC',
    'WFC',
    'GOOGL',
    'META',
    'ORCL',
    'TSM',
  ];

  final List<String> availableStrategies = [
    'Scalping',
    'Momentum Trading',
    'Trend Following',
    'Mean Reversion',
    'Range Trading',
    'Breakout Trading'
  ];

  /// Check if backend is available
  Future<void> _checkBackendConnection() async {
    try {
      debugPrint('🔄 Checking backend connection to: $_apiUrl/api/health');
      final response = await http
          .get(
            Uri.parse('$_apiUrl/api/health'),
          )
          .timeout(const Duration(seconds: 5));

      _isConnected = response.statusCode == 200;
      if (_isConnected) {
        debugPrint('✅ Backend connected successfully');
        debugPrint('📊 Response: ${response.body}');
      } else {
        _errorMessage =
            'Backend connection failed: HTTP ${response.statusCode}';
        debugPrint('❌ Backend health check failed: ${response.statusCode}');
        debugPrint('📄 Response: ${response.body}');
      }
      notifyListeners();
    } catch (e) {
      _isConnected = false;
      _errorMessage = 'Cannot connect to backend: $e';
      debugPrint('❌ Backend connection error: $e');
      notifyListeners();
    }
  }

  /// Fetch active bots from backend
  Future<void> fetchActiveBots({String? tradingMode, bool force = false}) async {
    if (_inFlightFetch != null && !force) {
      return _inFlightFetch!;
    }

    final future = _fetchActiveBotsInternal(tradingMode: tradingMode, force: force);
    _inFlightFetch = future;
    try {
      await future;
    } finally {
      if (identical(_inFlightFetch, future)) {
        _inFlightFetch = null;
      }
    }
  }

  Future<void> _fetchActiveBotsInternal({String? tradingMode, bool force = false}) async {
    final prefs = await _getPrefs();
    final mode = tradingMode ?? prefs.getString('trading_mode') ?? 'DEMO';
    final now = DateTime.now();
    if (!force && _lastFetchAt != null && _lastTradingMode == mode && now.difference(_lastFetchAt!) < const Duration(seconds: 3)) {
      return;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (!_isConnected) {
        await _checkBackendConnection();
      }

      // Get user_id from SharedPreferences
      final userId = prefs.getString('user_id');
      final sessionToken = prefs.getString('auth_token');
      _lastTradingMode = mode;

      // Avoid hammering protected endpoints without auth header.
      if (sessionToken == null || sessionToken.isEmpty) {
        _authPollingDisabled = true;
        stopPolling();
        _isLoading = false;
        _errorMessage = 'Session token missing. Please login again.';
        notifyListeners();
        return;
      }

      var url = '$_apiUrl/api/bot/summary?mode=$mode';
      if (userId != null && userId.isNotEmpty) {
        url += '&user_id=$userId';
      }

      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        _authPollingDisabled = false;
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _activeBots = List<Map<String, dynamic>>.from(data['bots'] ?? []);
          _lastFetchAt = now;
          _errorMessage = null;
          debugPrint('Fetched ${_activeBots.length} active bots from backend');
        } else {
          _errorMessage = data['error'] ?? 'Failed to fetch bots';
          _activeBots = [];
        }
      } else {
        _errorMessage = 'Backend returned status ${response.statusCode}';
        if (response.statusCode == 401 || response.statusCode == 403) {
          _authPollingDisabled = true;
          stopPolling();
        }
        // Don't wipe _activeBots - preserve previous data on error
      }
    } catch (e) {
      _errorMessage = 'Error fetching bots: $e';
      // Don't wipe _activeBots - preserve previous data on error
      debugPrint('Bot fetch error: $e');
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
      final prefs = await _getPrefs();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      debugPrint('🔐 DEBUG: CreateBot - Checking session...');
      debugPrint('  All keys in SharedPreferences: ${prefs.getKeys()}');
      debugPrint('  auth_token value: $sessionToken');
      debugPrint('  auth_token is null: ${sessionToken == null}');
      debugPrint(
          "  auth_token isEmpty: ${sessionToken?.isEmpty ?? 'null object'}");
      debugPrint('  user_id: $userId');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage =
            'Session expired. Please login again. Token was null or empty.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      debugPrint('✅ Token found, creating request headers...');
      final headers = {
        'Content-Type': 'application/json',
        'X-Session-Token': sessionToken,
      };
      debugPrint('📤 Headers being sent:');
      debugPrint('  Content-Type: ${headers['Content-Type']}');
      debugPrint(
          "  X-Session-Token: ${headers['X-Session-Token']?.substring(0, 20)}...");

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

      debugPrint('📤 Sending bot creation request to $_apiUrl/api/bot/create');
      debugPrint('  Body: $requestBody');

      final response = await http
          .post(
            Uri.parse('$_apiUrl/api/bot/create'),
            headers: headers,
            body: jsonEncode(requestBody),
          )
          .timeout(const Duration(seconds: 10));

      debugPrint('📥 Response: ${response.statusCode}');
      debugPrint('  Body: ${response.body}');

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final responseData = jsonDecode(response.body);
        if (responseData['success'] == true) {
          await fetchActiveBots(force: true);
          return true;
        }
        _errorMessage = responseData['error'] ?? 'Failed to create bot';
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired or invalid token. Please login again.';
        debugPrint('❌ BOT CREATION 401 ERROR:');
        debugPrint('  Status: ${response.statusCode}');
        debugPrint('  Response: ${response.body}');
        debugPrint('  Token was: ${sessionToken.substring(0, 20)}...');
      } else {
        final responseData = jsonDecode(response.body);
        _errorMessage = responseData['error'] ?? 'Failed to create bot';
        debugPrint('❌ BOT CREATION ERROR (${response.statusCode}):');
        debugPrint('  Error: $_errorMessage');
        debugPrint('  Full response: ${response.body}');
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error creating bot: $e';
      debugPrint('Bot creation error: $e');
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
      final prefs = await _getPrefs();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage = 'Session expired. Please login again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      final response = await http
          .post(
            Uri.parse('$_apiUrl/api/bot/start'),
            headers: {
              'Content-Type': 'application/json',
              'X-Session-Token': sessionToken,
            },
            body: jsonEncode({'botId': botId}),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          debugPrint('Bot started: $botId');
          await fetchActiveBots(force: true);
          return true;
        }
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired. Please login again.';
      } else {
        _errorMessage =
            jsonDecode(response.body)['error'] ?? 'Failed to start bot';
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error starting bot: $e';
      debugPrint('Bot start error: $e');
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
      final prefs = await _getPrefs();
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
          debugPrint('Bot stopped: $botId');
          await fetchActiveBots(force: true);
          return true;
        }
      } else if (response.statusCode == 401) {
        _errorMessage = 'Session expired. Please login again.';
      } else {
        _errorMessage =
            jsonDecode(response.body)['error'] ?? 'Failed to stop bot';
      }
      return false;
    } catch (e) {
      _errorMessage = 'Error stopping bot: $e';
      debugPrint('Bot stop error: $e');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> saveBot(Bot bot) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('bot_config', jsonEncode(bot.toJson()));
      _bot = bot;
      notifyListeners();
    } catch (e) {
      debugPrint('Error saving bot: $e');
    }
  }

  Future<void> toggleBot({required bool isActive}) async {
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

  /// Remove a bot from the active bots list locally
  void removeBotLocally(String botId) {
    _activeBots.removeWhere((bot) => (bot['botId'] ?? bot['id']) == botId);
    notifyListeners();
  }

  Future<bool> deleteBot(String botId) async {
    try {
      final prefs = await _getPrefs();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      if (sessionToken == null || sessionToken.isEmpty) {
        _errorMessage = 'Session expired. Please login again.';
        notifyListeners();
        return false;
      }

      final response = await http.delete(
        Uri.parse('$_apiUrl/api/bot/delete/$botId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({
          if (userId != null && userId.isNotEmpty) 'user_id': userId,
        }),
      ).timeout(const Duration(seconds: 15));

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode == 200 && data['success'] == true) {
        removeBotLocally(botId);
        return true;
      }

      _errorMessage = data['error']?.toString() ?? 'Failed to delete bot';
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'Error deleting bot: $e';
      notifyListeners();
      return false;
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
