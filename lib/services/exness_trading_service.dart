import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';

/// Represents an Exness trading account
class ExnessAccount {
  final String accountId;
  final String accountType; // DEMO or LIVE
  final double balance;
  final double equity;
  final double margin;
  final double freeMargin;
  final double marginLevel;
  final List<String> availableSymbols;
  final DateTime? fetchedAt;

  ExnessAccount({
    required this.accountId,
    required this.accountType,
    required this.balance,
    required this.equity,
    required this.margin,
    required this.freeMargin,
    required this.marginLevel,
    required this.availableSymbols,
    this.fetchedAt,
  });

  factory ExnessAccount.fromJson(Map<String, dynamic> json) {
    return ExnessAccount(
      accountId: json['accountId'] ?? '',
      accountType: json['accountType'] ?? 'DEMO',
      balance: (json['balance'] as num?)?.toDouble() ?? 0.0,
      equity: (json['equity'] as num?)?.toDouble() ?? 0.0,
      margin: (json['margin'] as num?)?.toDouble() ?? 0.0,
      freeMargin: (json['freeMargin'] as num?)?.toDouble() ?? 0.0,
      marginLevel: (json['marginLevel'] as num?)?.toDouble() ?? 0.0,
      availableSymbols: List<String>.from(json['symbols'] ?? []),
      fetchedAt: json['fetchedAt'] != null ? DateTime.parse(json['fetchedAt']) : null,
    );
  }

  Map<String, dynamic> toJson() => {
    'accountId': accountId,
    'accountType': accountType,
    'balance': balance,
    'equity': equity,
    'margin': margin,
    'freeMargin': freeMargin,
    'marginLevel': marginLevel,
    'symbols': availableSymbols,
    'fetchedAt': fetchedAt?.toIso8601String(),
  };

  String get profitLoss => (equity - balance).toStringAsFixed(2);
  bool get isHealthy => marginLevel > 100;
  bool get isWarning => marginLevel > 50 && marginLevel <= 100;
  bool get isCritical => marginLevel <= 50;
}

/// Represents a trade order
class ExnessOrder {
  final String orderId;
  final String symbol;
  final String side; // BUY or SELL
  final double volume;
  final double openPrice;
  final double? stopLoss;
  final double? takeProfit;
  final double commission;
  final double currentProfit;
  final String status; // OPEN, CLOSED, PENDING
  final DateTime openTime;
  final DateTime? closeTime;

  ExnessOrder({
    required this.orderId,
    required this.symbol,
    required this.side,
    required this.volume,
    required this.openPrice,
    this.stopLoss,
    this.takeProfit,
    required this.commission,
    required this.currentProfit,
    required this.status,
    required this.openTime,
    this.closeTime,
  });

  factory ExnessOrder.fromJson(Map<String, dynamic> json) {
    return ExnessOrder(
      orderId: json['orderId'] ?? '',
      symbol: json['symbol'] ?? '',
      side: json['side'] ?? 'BUY',
      volume: (json['volume'] as num?)?.toDouble() ?? 0.0,
      openPrice: (json['openPrice'] as num?)?.toDouble() ?? 0.0,
      stopLoss: (json['stopLoss'] as num?)?.toDouble(),
      takeProfit: (json['takeProfit'] as num?)?.toDouble(),
      commission: (json['commission'] as num?)?.toDouble() ?? 0.0,
      currentProfit: (json['currentProfit'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] ?? 'OPEN',
      openTime: DateTime.parse(json['openTime'] ?? DateTime.now().toIso8601String()),
      closeTime: json['closeTime'] != null ? DateTime.parse(json['closeTime']) : null,
    );
  }

  Map<String, dynamic> toJson() => {
    'orderId': orderId,
    'symbol': symbol,
    'side': side,
    'volume': volume,
    'openPrice': openPrice,
    'stopLoss': stopLoss,
    'takeProfit': takeProfit,
    'commission': commission,
    'currentProfit': currentProfit,
    'status': status,
    'openTime': openTime.toIso8601String(),
    'closeTime': closeTime?.toIso8601String(),
  };
}

/// Exness Trading Service - Handles MT5 trading operations
class ExnessTradingService {
  final String accountId;
  final String password;
  final String server;
  final bool isLive;

  String? _sessionToken;
  ExnessAccount? _account;
  List<ExnessOrder> _orders = [];
  DateTime? _lastAccountFetch;

  static const Duration _cacheValidityDuration = Duration(seconds: 30);

  // ==================== SYSTEM DEFAULTS ====================
  /// Default Take Profit percentage for Exness MT5 (2%)
  static const double defaultTakeProfitPercentage = 2.0;

  /// Default Stop Loss percentage for Exness MT5 (1%)
  static const double defaultStopLossPercentage = 1.0;

  ExnessTradingService({
    required this.accountId,
    required this.password,
    required this.server,
    required this.isLive,
  });

  // ==================== GETTERS ====================

  String? get sessionToken => _sessionToken;
  ExnessAccount? get account => _account;
  List<ExnessOrder> get orders => _orders;
  bool get isAuthenticated => _sessionToken != null;
  bool get isCached => _lastAccountFetch != null && 
    DateTime.now().difference(_lastAccountFetch!) < _cacheValidityDuration;

  // ==================== AUTHENTICATION ====================

  /// Authenticate with Exness MT5
  Future<bool> authenticate() async {
    try {
      print('🔐 Authenticating with Exness account: $accountId...');

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'accountId': accountId,
          'password': password,
          'server': server,
          'isLive': isLive,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _sessionToken = data['sessionToken'];
        print('✅ Exness authentication successful');
        return data['success'] ?? true;
      } else {
        final error = jsonDecode(response.body)['error'] ?? 'Unknown error';
        print('❌ Exness authentication failed: $error');
        return false;
      }
    } catch (e) {
      print('❌ Exness authentication exception: $e');
      return false;
    }
  }

  /// Logout and clear session
  Future<void> logout() async {
    try {
      if (_sessionToken != null) {
        await http.post(
          Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/logout'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $_sessionToken',
          },
        ).timeout(const Duration(seconds: 5));
      }
      _sessionToken = null;
      _account = null;
      _orders = [];
      print('✅ Logged out from Exness');
    } catch (e) {
      print('⚠️ Logout warning: $e');
      _sessionToken = null;
    }
  }

  // ==================== ACCOUNT INFO ====================

  /// Get account information (cached)
  Future<ExnessAccount?> getAccountInfo({bool forceRefresh = false}) async {
    if (!isAuthenticated) {
      if (!await authenticate()) return null;
    }

    // Return cached data if valid
    if (!forceRefresh && isCached && _account != null) {
      return _account;
    }

    try {
      print('📊 Fetching Exness account information...');

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/account'),
        headers: {'Authorization': 'Bearer $_sessionToken'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _account = ExnessAccount.fromJson(data);
        _lastAccountFetch = DateTime.now();
        print('✅ Account info: Balance: \$${_account!.balance} | Equity: \$${_account!.equity}');
        return _account;
      } else {
        final error = jsonDecode(response.body)['error'] ?? 'Unknown error';
        print('❌ Failed to fetch account info: $error');
        return null;
      }
    } catch (e) {
      print('❌ Account info exception: $e');
      return null;
    }
  }

  /// Refresh account balance
  Future<double?> getBalance() async {
    final account = await getAccountInfo(forceRefresh: true);
    return account?.balance;
  }

  // ==================== TRADING ====================

  /// Calculate Take Profit price from percentage
  static double calculateTakeProfitPrice(double entryPrice, double tpPercentage, String side) {
    if (side.toUpperCase() == 'BUY') {
      return entryPrice * (1 + (tpPercentage / 100));
    } else {
      return entryPrice * (1 - (tpPercentage / 100));
    }
  }

  /// Calculate Stop Loss price from percentage
  static double calculateStopLossPrice(double entryPrice, double slPercentage, String side) {
    if (side.toUpperCase() == 'BUY') {
      return entryPrice * (1 - (slPercentage / 100));
    } else {
      return entryPrice * (1 + (slPercentage / 100));
    }
  }

  /// Place a buy or sell order
  Future<Map<String, dynamic>> placeOrder({
    required String symbol,
    required String side, // BUY or SELL
    required double volume,
    double? stopLoss,
    double? takeProfit,
    double? useTakeProfitPercentage, // Use system default if null
    double? useStopLossPercentage, // Use system default if null
    String? comment,
  }) async {
    if (!isAuthenticated) {
      if (!await authenticate()) {
        return {'success': false, 'error': 'Authentication failed'};
      }
    }

    try {
      print('📈 Placing ${side.toUpperCase()} order: $symbol | Volume: $volume');

      // Use default percentages if not provided and absolute prices not provided
      final finalTpPercentage = useTakeProfitPercentage ?? defaultTakeProfitPercentage;
      final finalSlPercentage = useStopLossPercentage ?? defaultStopLossPercentage;

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/trade'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_sessionToken',
        },
        body: jsonEncode({
          'symbol': symbol,
          'side': side.toUpperCase(),
          'volume': volume,
          'stopLoss': stopLoss,
          'takeProfit': takeProfit,
          'takeProfitPercentage': finalTpPercentage,
          'stopLossPercentage': finalSlPercentage,
          'comment': comment ?? 'Exness MT5 Trade',
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        print('✅ Order placed successfully: ${data['orderId']}');
        print('   TP%: $finalTpPercentage% | SL%: $finalSlPercentage%');
        return {
          'success': true,
          'orderId': data['orderId'],
          'message': 'Order placed successfully',
        };
      } else {
        final data = jsonDecode(response.body);
        final error = data['error'] ?? 'Order placement failed';
        print('❌ Order placement failed: $error');
        return {
          'success': false,
          'error': error,
        };
      }
    } catch (e) {
      print('❌ Order placement exception: $e');
      return {
        'success': false,
        'error': e.toString(),
      };
    }
  }

  /// Buy order shortcut (with system defaults for TP/SL)
  Future<Map<String, dynamic>> buy({
    required String symbol,
    required double volume,
    double? stopLoss,
    double? takeProfit,
    double? takeProfitPercentage,
    double? stopLossPercentage,
  }) =>
    placeOrder(
      symbol: symbol,
      side: 'BUY',
      volume: volume,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      useTakeProfitPercentage: takeProfitPercentage,
      useStopLossPercentage: stopLossPercentage,
    );

  /// Sell order shortcut (with system defaults for TP/SL)
  Future<Map<String, dynamic>> sell({
    required String symbol,
    required double volume,
    double? stopLoss,
    double? takeProfit,
    double? takeProfitPercentage,
    double? stopLossPercentage,
  }) =>
    placeOrder(
      symbol: symbol,
      side: 'SELL',
      volume: volume,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      useTakeProfitPercentage: takeProfitPercentage,
      useStopLossPercentage: stopLossPercentage,
    );

  // ==================== POSITION MANAGEMENT ====================

  /// Get all open orders
  Future<List<ExnessOrder>> getOpenOrders() async {
    if (!isAuthenticated) {
      if (!await authenticate()) return [];
    }

    try {
      print('📋 Fetching open orders...');

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/orders'),
        headers: {'Authorization': 'Bearer $_sessionToken'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _orders = (data['orders'] as List)
            .map((o) => ExnessOrder.fromJson(o))
            .toList();
        print('✅ Retrieved ${_orders.length} open orders');
        return _orders;
      } else {
        print('❌ Failed to fetch orders');
        return [];
      }
    } catch (e) {
      print('❌ Exception fetching orders: $e');
      return [];
    }
  }

  /// Close a specific order by order ID
  Future<bool> closeOrder(String orderId) async {
    if (!isAuthenticated) {
      if (!await authenticate()) return false;
    }

    try {
      print('🔴 Closing order: $orderId');

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/orders/$orderId/close'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_sessionToken',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        print('✅ Order closed successfully');
        return true;
      } else {
        final error = jsonDecode(response.body)['error'] ?? 'Unknown error';
        print('❌ Failed to close order: $error');
        return false;
      }
    } catch (e) {
      print('❌ Exception closing order: $e');
      return false;
    }
  }

  /// Update order stop loss and take profit
  Future<bool> updateOrder({
    required String orderId,
    double? newStopLoss,
    double? newTakeProfit,
  }) async {
    if (!isAuthenticated) {
      if (!await authenticate()) return false;
    }

    try {
      print('✏️ Updating order: $orderId');

      final response = await http.patch(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/orders/$orderId'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_sessionToken',
        },
        body: jsonEncode({
          'stopLoss': newStopLoss,
          'takeProfit': newTakeProfit,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        print('✅ Order updated successfully');
        return true;
      } else {
        final error = jsonDecode(response.body)['error'] ?? 'Unknown error';
        print('❌ Failed to update order: $error');
        return false;
      }
    } catch (e) {
      print('❌ Exception updating order: $e');
      return false;
    }
  }

  // ==================== SYMBOLS & MARKET DATA ====================

  /// Get list of available trading symbols
  Future<List<String>> getAvailableSymbols() async {
    final account = await getAccountInfo();
    return account?.availableSymbols ?? _getDefaultExnessSymbols();
  }

  /// Default Exness symbols (fallback)
  static List<String> _getDefaultExnessSymbols() {
    return [
      // Only these 5 symbols are available on Exness Demo Account 298997455
      'BTCUSDm',   // Bitcoin / USD
      'ETHUSDm',   // Ethereum / USD
      'EURUSDm',   // Euro / USD
      'USDJPYm',   // USD / Japanese Yen
      'XAUUSDm',   // Gold / USD
    ];
  }

  /// Get historical price data (simplified - returns last known data)
  Future<Map<String, dynamic>?> getSymbolData(String symbol) async {
    if (!isAuthenticated) {
      if (!await authenticate()) return null;
    }

    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/symbols/$symbol'),
        headers: {'Authorization': 'Bearer $_sessionToken'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      return null;
    } catch (e) {
      print('⚠️ Failed to fetch symbol data for $symbol: $e');
      return null;
    }
  }

  // ==================== CONNECTION HEALTH ====================

  /// Test connection status
  Future<bool> testConnection() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/health'),
      ).timeout(const Duration(seconds: 5));

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  /// Validate credentials without connecting
  Future<bool> validateCredentials() async {
    try {
      print('🔍 Validating Exness credentials...');
      final authenticated = await authenticate();
      if (authenticated) {
        await logout();
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }
}
