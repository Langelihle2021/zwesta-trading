import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';

class BrokerCredential {

  BrokerCredential({
    required this.credentialId,
    required this.broker,
    required this.accountNumber,
    required this.server,
    required this.accountCurrency,
    required this.isLive,
    required this.isActive,
    required this.createdAt,
    required this.cachedBalance,
    required this.hasCachedBalance,
    this.apiKey,
  });

  factory BrokerCredential.fromJson(Map<String, dynamic> json) => BrokerCredential(
      credentialId: json['credential_id'] ?? '',
      broker: json['broker'] ?? '',
      accountNumber: json['account_number'] ?? '',
      server: json['server'] ?? '',
      accountCurrency: (json['account_currency'] ?? 'USD').toString().toUpperCase(),
      isLive: json['is_live'] ?? false,
      isActive: json['is_active'] ?? true,
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toString()),
      cachedBalance: (json['cached_balance'] ?? 0).toDouble(),
      hasCachedBalance: json['has_cached_balance'] ?? ((json['cached_balance'] ?? 0).toDouble() > 0),
      apiKey: json['api_key'],
    );
  final String credentialId;
  final String broker;
  final String accountNumber;
  final String server;
  final String accountCurrency;
  final bool isLive;
  final bool isActive;
  final DateTime createdAt;
  final double cachedBalance;
  final bool hasCachedBalance;
  final String? apiKey;

  bool get isHealthy => hasCachedBalance || cachedBalance > 0;

  Map<String, dynamic> toJson() => {
    'credential_id': credentialId,
    'broker': broker,
    'account_number': accountNumber,
    'server': server,
    'account_currency': accountCurrency,
    'is_live': isLive,
    'is_active': isActive,
    'created_at': createdAt.toIso8601String(),
    'cached_balance': cachedBalance,
    'has_cached_balance': hasCachedBalance,
  };
}

class BrokerCredentialsService extends ChangeNotifier {

  BrokerCredentialsService() {
    _apiUrl = EnvironmentConfig.apiUrl;
    _loadSavedCredentials();
  }
  List<BrokerCredential> _credentials = [];
  BrokerCredential? _activeCredential;
  bool _isLoading = false;
  String? _errorMessage;
  String? _apiUrl;

  List<BrokerCredential> get credentials => _credentials;
  BrokerCredential? get activeCredential => _activeCredential;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  static const List<String> _brokerPriority = ['exness', 'binance', 'oanda'];

  List<BrokerCredential> _rankCredentials(Iterable<BrokerCredential> credentials) {
    final ranked = credentials.toList();
    ranked.sort((a, b) {
      final healthCompare = (b.isHealthy ? 1 : 0).compareTo(a.isHealthy ? 1 : 0);
      if (healthCompare != 0) {
        return healthCompare;
      }

      final activeCompare = (b.isActive ? 1 : 0).compareTo(a.isActive ? 1 : 0);
      if (activeCompare != 0) {
        return activeCompare;
      }

      final brokerIndexA = _brokerPriority.indexOf(a.broker.toLowerCase().trim());
      final brokerIndexB = _brokerPriority.indexOf(b.broker.toLowerCase().trim());
      final normalizedBrokerIndexA = brokerIndexA == -1 ? _brokerPriority.length : brokerIndexA;
      final normalizedBrokerIndexB = brokerIndexB == -1 ? _brokerPriority.length : brokerIndexB;
      final brokerCompare = normalizedBrokerIndexA.compareTo(normalizedBrokerIndexB);
      if (brokerCompare != 0) {
        return brokerCompare;
      }

      return b.createdAt.compareTo(a.createdAt);
    });
    return ranked;
  }

  BrokerCredential? _preferredCredential(
    Iterable<BrokerCredential> credentials, {
    String? preferredTradingMode,
    String? preferredCredentialId,
  }) {
    final list = _rankCredentials(credentials);
    if (list.isEmpty) {
      return null;
    }

    if (preferredCredentialId != null && preferredCredentialId.isNotEmpty) {
      for (final credential in list) {
        if (credential.credentialId == preferredCredentialId) {
          return credential;
        }
      }
    }

    final normalizedMode = preferredTradingMode?.trim().toUpperCase();
    final modeMatched = normalizedMode == null
        ? list
        : list.where((credential) => normalizedMode == 'LIVE' ? credential.isLive : !credential.isLive).toList();
    final rankedPool = _rankCredentials(modeMatched.isNotEmpty ? modeMatched : list);

    for (final brokerName in _brokerPriority) {
      for (final credential in rankedPool) {
        if (credential.broker.toLowerCase().trim() == brokerName) {
          return credential;
        }
      }
    }

    return rankedPool.first;
  }

  /// Load credentials from backend
  Future<void> fetchCredentials() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');
      final preferredTradingMode = prefs.getString('trading_mode');
      final persistedActiveCredentialId = prefs.getString('active_credential_id');
      final currentActiveCredentialId = _activeCredential?.credentialId;

      if (sessionToken == null || userId == null) {
        _errorMessage = 'Not authenticated. Please login again.';
        _isLoading = false;
        notifyListeners();
        return;
      }

      print('🔐 Fetching broker credentials for user: $userId');

      final response = await http.get(
        Uri.parse('$_apiUrl/api/broker/credentials'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final credentialsList = (data['credentials'] as List)
            .map((c) => BrokerCredential.fromJson(c))
            .toList();

        // Deduplicate: keep only latest credential for each broker+account combo
        final deduped = <String, BrokerCredential>{};
        for (final cred in credentialsList) {
          final key = '${cred.broker}_${cred.accountNumber}';
          // Compare by createdAt - keep the more recent one
          if (!deduped.containsKey(key) || 
              cred.createdAt.isAfter(deduped[key]!.createdAt)) {
            deduped[key] = cred;
          }
        }
        
        _credentials = _rankCredentials(deduped.values);
        
        // Set active credential if available
        if (_credentials.isNotEmpty) {
          final activeCredentials = _credentials.where((c) => c.isActive);
          _activeCredential = _preferredCredential(
            activeCredentials.isNotEmpty ? activeCredentials : _credentials,
            preferredTradingMode: preferredTradingMode,
            preferredCredentialId: currentActiveCredentialId ?? persistedActiveCredentialId,
          );
        }

        print('✅ Loaded ${_credentials.length} broker credentials');
        _saveCredentialsLocal();
      } else {
        _errorMessage = 'Failed to load credentials: ${response.statusCode}';
        print('❌ Error loading credentials: ${response.statusCode}');
      }
    } catch (e) {
      _errorMessage = 'Error loading credentials: $e';
      print('❌ Error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Save broker credentials
  Future<bool> saveCredential({
    required String broker,
    required String accountNumber,
    required String password,
    required String server,
    required bool isLive,
    String? apiKey,
    String? apiSecret,
    String? username,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        _errorMessage = 'Not authenticated. Please login again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      print('🔐 Saving broker credential for: $broker | Account: $accountNumber');

      final body = <String, dynamic>{
        'broker': broker,
        'account_number': accountNumber,
        'password': password,
        'server': server,
        'is_live': isLive,
      };
      if (apiKey != null) body['api_key'] = apiKey;
      if (apiSecret != null) body['api_secret'] = apiSecret;
      if (username != null) body['username'] = username;

      final response = await http.post(
        Uri.parse('$_apiUrl/api/broker/credentials'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        final newCredential = BrokerCredential.fromJson(data['credential']);
        
        _credentials.add(newCredential);
        _activeCredential = newCredential;

        print('✅ Credential saved! ID: ${newCredential.credentialId}');
        _saveCredentialsLocal();
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        final errorData = jsonDecode(response.body);
        _errorMessage = errorData['error'] ?? 'Failed to save credential';
        print('❌ Error: ${response.statusCode} - $_errorMessage');
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Error saving credential: $e';
      print('❌ Error: $e');
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Test broker connection
  Future<bool> testConnection({
    required String broker,
    required String accountNumber,
    required String password,
    required String server,
    required bool isLive,
  }) async {
    try {
      print('🔌 Testing connection to: $broker | Account: $accountNumber');

      final response = await http.post(
        Uri.parse('$_apiUrl/api/broker/test-connection'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'broker': broker,
          'account_number': accountNumber,
          'password': password,
          'server': server,
          'is_live': isLive,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        print('✅ Connection test successful: ${data['message']}');
        return true;
      } else {
        final data = jsonDecode(response.body);
        _errorMessage = data['error'] ?? 'Connection test failed';
        print('❌ Connection failed: $_errorMessage');
        return false;
      }
    } catch (e) {
      _errorMessage = 'Connection test error: $e';
      print('❌ Error: $e');
      return false;
    }
  }

  /// Set active credential for bot creation
  void setActiveCredential(BrokerCredential credential) {
    _activeCredential = credential;
    _saveCredentialsLocal();
    notifyListeners();
  }

  /// Delete credential
  Future<bool> deleteCredential(String credentialId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        _errorMessage = 'Not authenticated';
        _isLoading = false;
        notifyListeners();
        return false;
      }

      final response = await http.delete(
        Uri.parse('$_apiUrl/api/broker/credentials/$credentialId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        _credentials.removeWhere((c) => c.credentialId == credentialId);
        if (_activeCredential?.credentialId == credentialId) {
          _activeCredential = _preferredCredential(_credentials);
        }
        _saveCredentialsLocal();
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = 'Failed to delete credential';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Error deleting credential: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Save credentials to local storage for offline access
  Future<void> _saveCredentialsLocal() async {
    final prefs = await SharedPreferences.getInstance();
    final credentialsJson = jsonEncode(
      _credentials.map((c) => c.toJson()).toList(),
    );
    await prefs.setString('broker_credentials', credentialsJson);
    if (_activeCredential != null) {
      await prefs.setString('active_credential_id', _activeCredential!.credentialId);
    }
  }

  /// Load credentials from local storage
  Future<void> _loadSavedCredentials() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final credentialsJson = prefs.getString('broker_credentials');
      
      if (credentialsJson != null) {
        final credentialsList = (jsonDecode(credentialsJson) as List)
            .map((c) => BrokerCredential.fromJson(c))
            .toList();
        _credentials = _rankCredentials(credentialsList);

        final activeId = prefs.getString('active_credential_id');
        if (activeId != null) {
          final matchedCredential = _credentials.where(
            (c) => c.credentialId == activeId,
          );
          _activeCredential = matchedCredential.isNotEmpty
              ? matchedCredential.first
              : _preferredCredential(_credentials, preferredCredentialId: activeId);
        } else {
          _activeCredential = _preferredCredential(_credentials);
        }
      }
    } catch (e) {
      print('⚠️ Error loading saved credentials: $e');
    }
  }

  /// Has any valid credentials
  bool get hasCredentials => _credentials.isNotEmpty && _activeCredential != null;
}
