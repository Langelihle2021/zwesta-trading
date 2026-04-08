import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../utils/environment_config.dart';

class BrokerConfig {

  BrokerConfig({
    required this.id,
    required this.name,
    required this.displayName,
    required this.logo,
    required this.accountTypes,
    required this.isActive,
    this.description,
  });

  factory BrokerConfig.fromJson(Map<String, dynamic> json) => BrokerConfig(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      displayName: json['display_name'] ?? json['name'] ?? '',
      logo: json['logo'] ?? '',
      accountTypes: List<String>.from(json['account_types'] ?? ['DEMO', 'LIVE']),
      isActive: json['is_active'] ?? true,
      description: json['description'],
    );
  final String id;
  final String name;
  final String displayName;
  final String logo;
  final List<String> accountTypes; // ['DEMO', 'LIVE']
  final bool isActive;
  final String? description;

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'display_name': displayName,
    'logo': logo,
    'account_types': accountTypes,
    'is_active': isActive,
    'description': description,
  };
}

class BrokerRegistryService extends ChangeNotifier {

  BrokerRegistryService() {
    _apiUrl = EnvironmentConfig.apiUrl;
    _initializeDefaultBrokers();
    fetchBrokersFromBackend();
  }
  List<BrokerConfig> _brokers = [];
  bool _isLoading = false;
  String? _errorMessage;
  String? _apiUrl;

  List<BrokerConfig> get brokers => _brokers;
  List<BrokerConfig> get activeBrokers => _brokers.where((b) => b.isActive).toList();
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  /// Initialize with default brokers (fallback if backend is down)
  void _initializeDefaultBrokers() {
    _brokers = [
      BrokerConfig(
        id: 'exness',
        name: 'Exness',
        displayName: 'Exness',
        logo: '⚡',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Primary MT5 broker for forex, metals, and crypto pairs',
      ),
      BrokerConfig(
        id: 'binance',
        name: 'Binance',
        displayName: 'Binance',
        logo: '₿',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Primary crypto exchange for spot and futures trading',
      ),
      BrokerConfig(
        id: 'pepperstone',
        name: 'Pepperstone',
        displayName: 'Pepperstone Global',
        logo: '🐘',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Low-cost forex and CFD trading',
      ),
      BrokerConfig(
        id: 'fxopen',
        name: 'FxOpen',
        displayName: 'FxOpen',
        logo: '📊',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Forex, metals, and energies broker',
      ),
      BrokerConfig(
        id: 'darwinex',
        name: 'Darwinex',
        displayName: 'Darwinex',
        logo: '🦎',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Social forex trading platform',
      ),
      BrokerConfig(
        id: 'ic-markets',
        name: 'IC Markets',
        displayName: 'IC Markets',
        logo: '📈',
        accountTypes: ['DEMO', 'LIVE'],
        isActive: true,
        description: 'Australian regulated MT5 broker',
      ),
    ];
  }

  /// Fetch broker list from backend (dynamic configuration)
  Future<void> fetchBrokersFromBackend() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      print('🔄 Fetching broker registry from backend...');

      final response = await http.get(
        Uri.parse('$_apiUrl/api/brokers'),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final brokersList = (data['brokers'] as List)
            .map((b) => BrokerConfig.fromJson(b))
            .toList();

        _brokers = brokersList;
        print('✅ Loaded ${_brokers.length} brokers from backend');
      } else if (response.statusCode == 404) {
        // Backend doesn't have broker endpoint yet, use defaults
        print('ℹ️ Broker endpoint not available, using default brokers');
      } else {
        print('⚠️ Failed to fetch brokers: ${response.statusCode}');
      }
    } catch (e) {
      print('⚠️ Error fetching brokers: $e');
      // Use default brokers on error
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Get broker by ID (case-insensitive)
  BrokerConfig? getBrokerById(String id) {
    try {
      return _brokers.firstWhere(
        (b) => b.id.toLowerCase() == id.toLowerCase(),
      );
    } catch (e) {
      return null;
    }
  }

  /// Get broker by name
  BrokerConfig? getBrokerByName(String name) {
    try {
      return _brokers.firstWhere(
        (b) => b.name.toLowerCase() == name.toLowerCase(),
      );
    } catch (e) {
      return null;
    }
  }

  /// Check if broker is available
  bool isBrokerActive(String brokerId) {
    final broker = getBrokerById(brokerId);
    return broker?.isActive ?? false;
  }

  /// Get supported account types for a broker
  List<String> getAccountTypes(String brokerId) {
    final broker = getBrokerById(brokerId);
    return broker?.accountTypes ?? ['DEMO'];
  }

  /// Add new broker dynamically (admin function)
  void addBroker(BrokerConfig broker) {
    if (!_brokers.any((b) => b.id == broker.id)) {
      _brokers.add(broker);
      notifyListeners();
    }
  }

  /// Toggle broker active status (admin function)
  void toggleBrokerStatus(String brokerId) {
    final index = _brokers.indexWhere((b) => b.id == brokerId);
    if (index >= 0) {
      final broker = _brokers[index];
      _brokers[index] = BrokerConfig(
        id: broker.id,
        name: broker.name,
        displayName: broker.displayName,
        logo: broker.logo,
        accountTypes: broker.accountTypes,
        isActive: !broker.isActive,
        description: broker.description,
      );
      notifyListeners();
    }
  }

  /// Get localized broker name
  String getDisplayName(String brokerId) {
    final broker = getBrokerById(brokerId);
    return broker?.displayName ?? brokerId;
  }
}
