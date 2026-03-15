import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/environment_config.dart';

enum IGConnectionState {
  disconnected,
  connecting,
  connected,
  error,
  reconnecting,
}

class IGConnectionInfo {
  final String accountId;
  final String accountName;
  final double balance;
  final double profitLoss;
  final String currency;
  final bool isLive;
  final DateTime connectedAt;

  IGConnectionInfo({
    required this.accountId,
    required this.accountName,
    required this.balance,
    required this.profitLoss,
    required this.currency,
    required this.isLive,
    required this.connectedAt,
  });

  factory IGConnectionInfo.fromJson(Map<String, dynamic> json) {
    return IGConnectionInfo(
      accountId: json['account_id'] ?? '',
      accountName: json['account_name'] ?? 'IG Account',
      balance: (json['balance'] ?? 0).toDouble(),
      profitLoss: (json['profit_loss'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'USD',
      isLive: json['is_live'] ?? false,
      connectedAt: DateTime.now(),
    );
  }
}

class IGAutoConnectService extends ChangeNotifier {
  IGConnectionState _state = IGConnectionState.disconnected;
  IGConnectionInfo? _connectionInfo;
  String? _errorMessage;
  int _retryCount = 0;
  Timer? _healthCheckTimer;
  Timer? _reconnectTimer;

  static const int maxRetries = 3;
  static const Duration healthCheckInterval = Duration(seconds: 30);
  static const Duration reconnectDelay = Duration(seconds: 5);

  // Keys for secure storage
  static const String _keyIGSaved = 'ig_credentials_saved';
  static const String _keyIGApiKey = 'ig_api_key';
  static const String _keyIGUsername = 'ig_username';
  static const String _keyIGPassword = 'ig_password';
  static const String _keyIGIsLive = 'ig_is_live';
  static const String _keyIGAutoConnect = 'ig_auto_connect';

  IGConnectionState get state => _state;
  IGConnectionInfo? get connectionInfo => _connectionInfo;
  String? get errorMessage => _errorMessage;
  bool get isConnected => _state == IGConnectionState.connected;
  bool get isConnecting => _state == IGConnectionState.connecting || _state == IGConnectionState.reconnecting;

  /// Check if saved IG credentials exist
  Future<bool> hasSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyIGSaved) == true;
  }

  /// Check if auto-connect is enabled
  Future<bool> isAutoConnectEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyIGAutoConnect) == true;
  }

  /// Save IG credentials for auto-connect
  Future<void> saveCredentials({
    required String apiKey,
    required String username,
    required String password,
    required bool isLive,
    bool autoConnect = true,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyIGSaved, true);
    await prefs.setString(_keyIGApiKey, apiKey);
    await prefs.setString(_keyIGUsername, username);
    await prefs.setString(_keyIGPassword, password);
    await prefs.setBool(_keyIGIsLive, isLive);
    await prefs.setBool(_keyIGAutoConnect, autoConnect);
    notifyListeners();
  }

  /// Clear saved credentials
  Future<void> clearCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyIGSaved);
    await prefs.remove(_keyIGApiKey);
    await prefs.remove(_keyIGUsername);
    await prefs.remove(_keyIGPassword);
    await prefs.remove(_keyIGIsLive);
    await prefs.remove(_keyIGAutoConnect);
    _state = IGConnectionState.disconnected;
    _connectionInfo = null;
    _healthCheckTimer?.cancel();
    notifyListeners();
  }

  /// Auto-connect using saved credentials (called on app startup)
  Future<void> autoConnect() async {
    final prefs = await SharedPreferences.getInstance();
    final hasCreds = prefs.getBool(_keyIGSaved) == true;
    final autoEnabled = prefs.getBool(_keyIGAutoConnect) == true;

    if (!hasCreds || !autoEnabled) return;

    final apiKey = prefs.getString(_keyIGApiKey) ?? '';
    final username = prefs.getString(_keyIGUsername) ?? '';
    final password = prefs.getString(_keyIGPassword) ?? '';
    final isLive = prefs.getBool(_keyIGIsLive) ?? false;

    if (apiKey.isEmpty || username.isEmpty || password.isEmpty) return;

    await connect(apiKey: apiKey, username: username, password: password, isLive: isLive);
  }

  /// Connect to IG API through the backend
  Future<bool> connect({
    required String apiKey,
    required String username,
    required String password,
    required bool isLive,
  }) async {
    _state = IGConnectionState.connecting;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null || sessionToken.isEmpty) {
        _state = IGConnectionState.error;
        _errorMessage = 'Session expired. Please login again.';
        notifyListeners();
        return false;
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/test-connection'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({
          'broker': 'IG',
          'account_number': username,
          'password': password,
          'server': isLive ? 'IG-Live' : 'IG-Demo',
          'is_live': isLive,
          'api_key': apiKey,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _connectionInfo = IGConnectionInfo(
            accountId: data['credential_id'] ?? data['account_number'] ?? username,
            accountName: 'IG ${isLive ? "Live" : "Demo"}',
            balance: (data['balance'] ?? 0).toDouble(),
            profitLoss: 0,
            currency: 'USD',
            isLive: isLive,
            connectedAt: DateTime.now(),
          );
          _state = IGConnectionState.connected;
          _retryCount = 0;
          _startHealthCheck();
          notifyListeners();
          return true;
        } else {
          _state = IGConnectionState.error;
          _errorMessage = data['error'] ?? 'Connection failed';
          notifyListeners();
          return false;
        }
      } else if (response.statusCode == 401) {
        _state = IGConnectionState.error;
        _errorMessage = 'Authentication failed. Check your IG credentials.';
        notifyListeners();
        return false;
      } else {
        _state = IGConnectionState.error;
        _errorMessage = 'Server error (${response.statusCode})';
        notifyListeners();
        return false;
      }
    } catch (e) {
      _state = IGConnectionState.error;
      _errorMessage = 'Connection timeout. Please try again.';
      notifyListeners();
      _scheduleReconnect();
      return false;
    }
  }

  /// Disconnect from IG
  void disconnect() {
    _healthCheckTimer?.cancel();
    _reconnectTimer?.cancel();
    _state = IGConnectionState.disconnected;
    _connectionInfo = null;
    _retryCount = 0;
    notifyListeners();
  }

  void _startHealthCheck() {
    _healthCheckTimer?.cancel();
    _healthCheckTimer = Timer.periodic(healthCheckInterval, (_) => _performHealthCheck());
  }

  Future<void> _performHealthCheck() async {
    if (_state != IGConnectionState.connected) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      if (sessionToken == null) return;

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/health'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode != 200) {
        _scheduleReconnect();
      }
    } catch (e) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_retryCount >= maxRetries) {
      _state = IGConnectionState.error;
      _errorMessage = 'Connection lost. Max retries reached.';
      notifyListeners();
      return;
    }

    _retryCount++;
    _state = IGConnectionState.reconnecting;
    notifyListeners();

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(reconnectDelay * _retryCount, () async {
      final hasCreds = await hasSavedCredentials();
      if (hasCreds) await autoConnect();
    });
  }

  @override
  void dispose() {
    _healthCheckTimer?.cancel();
    _reconnectTimer?.cancel();
    super.dispose();
  }
}
