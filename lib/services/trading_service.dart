import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/account.dart';
import '../models/trade.dart';
import '../utils/environment_config.dart';
import 'mock_data_provider.dart';

class TradingService extends ChangeNotifier {

  TradingService(String? token) : _token = token {
    _apiUrl = EnvironmentConfig.apiUrl;
    // Try to use API in production, fall back to mock data
    _useApi = !EnvironmentConfig.offlineMode;
    
    try {
      if (_useApi) {
        _checkApiConnection();
      } else {
        _initializeMockData();
      }
    } catch (e) {
      _initializeMockData();
    }
    
    // Start auto-refresh of trades every 30 seconds
    _startAutoRefresh();
  }
  late String? _token;
  String? _apiUrl;
  bool _useApi = false;
  bool _isConnected = false;
  Timer? _priceRefreshTimer; // Auto-refresh trades every 30 seconds
  
  List<Trade> _trades = [];
  List<Account> _accounts = [];
  Trade? _selectedTrade;
  bool _isLoading = false;
  String? _errorMessage;
  
  void _startAutoRefresh() {
    _priceRefreshTimer?.cancel();
    _priceRefreshTimer = Timer.periodic(
      const Duration(seconds: 30),
      (_) {
        if (_useApi && _isConnected) {
          fetchTrades();
          fetchAccounts();
        }
      },
    );
  }

  void updateToken(String? token) {
    if (_token != token) {
      _token = token;
      notifyListeners();
    }
  }

  // Getters
  List<Trade> get trades => _trades;
  List<Account> get accounts => _accounts;
  Trade? get selectedTrade => _selectedTrade;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isConnected => _isConnected;
  bool get isUsingApi => _useApi && _isConnected;
  
  // Get live open positions only (status = open)
  List<Trade> get liveOpenPositions => _trades.where((t) => t.status == TradeStatus.open).toList();

  // Account metrics getters
  double get accountBalance => primaryAccount?.balance ?? 0.0;
  double get accountEquity => (primaryAccount?.balance ?? 0.0) + (primaryAccount?.profit ?? 0.0);
  double get freeMargin => primaryAccount?.availableMargin ?? 0.0;
  double get accountProfit => primaryAccount?.profit ?? 0.0;

  /// Currency code for the primary (first) account, e.g. 'USD', 'ZAR'
  String get accountCurrency => primaryAccount?.currency ?? 'USD';

  /// Currency symbol for display: '$' for USD, 'R' for ZAR, '£' for GBP, etc.
  String get accountCurrencySymbol {
    switch (accountCurrency.toUpperCase()) {
      case 'ZAR': return 'R';
      case 'GBP': return '£';
      case 'EUR': return '€';
      case 'USD':
      default:    return r'$';
    }
  }

  Account? get primaryAccount => _accounts.isNotEmpty ? _accounts[0] : null;

  List<Trade> get activeTrades => _trades.where((t) => t.status == TradeStatus.open).toList();
  List<Trade> get closedTrades => _trades.where((t) => t.status == TradeStatus.closed).toList();

  double get totalBalance => _accounts.fold(0, (sum, acc) => sum + acc.balance);
  double get totalProfit => _trades
        .where((t) => t.status == TradeStatus.closed)
        .fold(0, (sum, trade) => sum + (trade.profit ?? 0));

  int get winningTrades => _trades.where((t) => t.status == TradeStatus.closed && t.profit != null && t.profit! > 0).length;

  // Check API connection
  Future<void> _checkApiConnection() async {
    try {
      final response = await http.get(
        Uri.parse('$_apiUrl/api/health'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        _isConnected = true;
        _useApi = true;
        print('Connected to trading backend at $_apiUrl');
        await fetchAccounts();
        await fetchTrades();
      } else {
        _useApi = false;
        _initializeMockData();
      }
    } catch (e) {
      print('Could not connect to API: $e, falling back to mock data');
      _useApi = false;
      _initializeMockData();
    }
  }

  /// Connect to MT5 trading account
  Future<bool> connectToMT5Account({
    required int accountNumber,
    required String password,
    required String server,
  }) async {
    if (!_useApi || !_isConnected) {
      _errorMessage = 'API not connected';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/account/connect'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'account': accountNumber,
          'password': password,
          'server': server,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          final accountData = data['account'];
          _accounts = [
            Account(
              id: '1',
              accountNumber: accountData['accountNumber'].toString(),
              balance: (accountData['balance'] as num).toDouble(),
              usedMargin: ((accountData['marginUsed'] ?? 0) as num).toDouble(),
              availableMargin: ((accountData['marginFree'] ?? 0) as num).toDouble(),
              profit: (accountData['profit'] ?? 0.0).toDouble(),
              currency: accountData['currency'] ?? 'USD',
              status: 'active',
              createdAt: DateTime.now().subtract(const Duration(days: 365)),
              leverage: '1:${accountData['leverage'] ?? 100}',
              broker: accountData['broker'] ?? 'MetaTrader 5',
              server: server,
            )
          ];
          await fetchTrades();
          _isLoading = false;
          notifyListeners();
          return true;
        } else {
          _errorMessage = data['message'] ?? 'Connection failed';
        }
      } else {
        _errorMessage = 'Server error: ${response.statusCode}';
      }
    } catch (e) {
      _errorMessage = 'Connection error: $e';
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  // Initialize with mock data from MockDataProvider (synchronous)
  void _initializeMockData() {
    try {
      _accounts = MockDataProvider.getMockAccounts();
      _trades = MockDataProvider.getMockTrades();
      _useApi = false;
      // Note: Fallback provider notification would be done from UI layer
      // Services should not directly access context/navigator
      debugPrint('DEBUG: Loaded ${_trades.length} trades and ${_accounts.length} accounts (mock)');
    } catch (e) {
      print('ERROR loading mock data: $e');
      _trades = [];
      _accounts = [];
    }
  }

  // Fetch trades from API or mock
  Future<void> fetchTrades() async {
    if (_useApi && _isConnected) {
      try {
        final prefs = await SharedPreferences.getInstance();
        final sessionToken = prefs.getString('auth_token');
        if (sessionToken == null || sessionToken.isEmpty) {
          _errorMessage = 'Session token missing. Please login again.';
          _trades = [];
          _isLoading = false;
          notifyListeners();
          return;
        }

        DateTime _parseBackendTime(dynamic raw) {
          if (raw == null) return DateTime.now();
          if (raw is int) {
            // MT5 timestamps are unix seconds.
            return DateTime.fromMillisecondsSinceEpoch(raw * 1000);
          }
          final s = raw.toString();
          final asInt = int.tryParse(s);
          if (asInt != null) {
            return DateTime.fromMillisecondsSinceEpoch(asInt * 1000);
          }
          return DateTime.tryParse(s) ?? DateTime.now();
        }

        double _asDouble(dynamic raw, [double fallback = 0.0]) {
          if (raw == null) return fallback;
          if (raw is num) return raw.toDouble();
          return double.tryParse(raw.toString()) ?? fallback;
        }
        
        final allTrades = <Trade>[];

        // Fetch 1: Closed trade history (user-scoped)
        try {
          final response = await http.get(
            Uri.parse('$_apiUrl/api/trades/history?days=30'),
            headers: {
              'Content-Type': 'application/json',
              'X-Session-Token': sessionToken,
            },
          ).timeout(const Duration(seconds: 10));

          if (response.statusCode == 200) {
            final data = jsonDecode(response.body);
            final tradesData = data['trades'] as List;

            allTrades.addAll(tradesData.map((t) => Trade(
                id: t['ticket'].toString(),
                symbol: t['symbol'],
                type: t['type'] == 'BUY' ? TradeType.buy : TradeType.sell,
                quantity: (t['volume'] as num).toDouble(),
                entryPrice: ((t['openPrice'] ?? t['price']) as num).toDouble(),
                currentPrice: ((t['openPrice'] ?? t['price']) as num).toDouble(),
                takeProfit: null,
                stopLoss: null,
                status: TradeStatus.closed,
                openedAt: _parseBackendTime(t['openTime'] ?? t['time']),
                closedAt: _parseBackendTime(t['closeTime']),
                profit: ((t['profit'] ?? 0) as num).toDouble(),
                profitPercentage: null,
              )));
          }
        } catch (e) {
          print('Error fetching closed trade history: $e');
        }

        // Fetch 1b: User bot/database trades (user-scoped)
        try {
          final dbTradesResponse = await http.get(
            Uri.parse('$_apiUrl/api/trades'),
            headers: {
              'Content-Type': 'application/json',
              'X-Session-Token': sessionToken,
            },
          ).timeout(const Duration(seconds: 10));

          if (dbTradesResponse.statusCode == 200) {
            final data = jsonDecode(dbTradesResponse.body);
            final tradesData = data['trades'] as List? ?? [];

            allTrades.addAll(tradesData.map((tRaw) {
              final t = (tRaw as Map).cast<String, dynamic>();
              final typeRaw = (t['type'] ?? t['order_type'] ?? t['direction'] ?? 'BUY')
                  .toString()
                  .toUpperCase();
              final statusRaw =
                  (t['status'] ?? (t['time_close'] != null ? 'closed' : 'open'))
                      .toString()
                      .toLowerCase();

              TradeStatus status;
              if (statusRaw == 'closed') {
                status = TradeStatus.closed;
              } else if (statusRaw == 'open') {
                status = TradeStatus.open;
              } else {
                status = TradeStatus.pending;
              }

              return Trade(
                id: (t['ticket'] ?? t['trade_id'] ?? t['id'] ?? DateTime.now().millisecondsSinceEpoch)
                    .toString(),
                symbol: (t['symbol'] ?? 'UNKNOWN').toString(),
                type: typeRaw == 'SELL' ? TradeType.sell : TradeType.buy,
                quantity: _asDouble(t['volume'] ?? t['quantity']),
                entryPrice: _asDouble(t['openPrice'] ?? t['price'] ?? t['entryPrice']),
                currentPrice: _asDouble(
                  t['currentPrice'] ?? t['closePrice'] ?? t['openPrice'] ?? t['price']),
                takeProfit: t['takeProfit'] != null ? _asDouble(t['takeProfit']) : null,
                stopLoss: t['stopLoss'] != null ? _asDouble(t['stopLoss']) : null,
                status: status,
                openedAt: _parseBackendTime(
                    t['time_open'] ?? t['openTime'] ?? t['entryTime'] ?? t['time']),
                closedAt: status == TradeStatus.closed
                    ? _parseBackendTime(t['time_close'] ?? t['closeTime'])
                    : null,
                profit: _asDouble(t['profit']),
                profitPercentage: t['profitPercentage'] != null
                    ? _asDouble(t['profitPercentage'])
                    : null,
              );
            }));
          }
        } catch (e) {
          print('Error fetching user database trades: $e');
        }

        // Fetch 2: Live open positions (user-scoped)
        try {
          final posResponse = await http.get(
            Uri.parse('$_apiUrl/api/positions/detailed'),
            headers: {
              'Content-Type': 'application/json',
              'X-Session-Token': sessionToken,
            },
          ).timeout(const Duration(seconds: 10));

          if (posResponse.statusCode == 200) {
            final posData = jsonDecode(posResponse.body);
            final positions = posData['positions'] as List? ?? [];
            
            if (positions.isNotEmpty) {
              print('✅ Fetched ${positions.length} live MT5 positions');
            }
            
            allTrades.addAll(positions.map((p) => Trade(
                id: p['ticket'].toString(),
                symbol: p['symbol'],
                type: p['type'] == 'BUY' ? TradeType.buy : TradeType.sell,
                quantity: (p['volume'] as num).toDouble(),
                entryPrice: (p['openPrice'] as num).toDouble(),
                currentPrice: (p['currentPrice'] as num).toDouble(),
                takeProfit: null,
                stopLoss: null,
                status: TradeStatus.open, // MT5 positions are always open
                openedAt: _parseBackendTime(p['openTime'] ?? p['time']),
                profit: ((p['pnl'] ?? p['profit'] ?? 0) as num).toDouble(),
                profitPercentage: ((p['pnlPercentage'] ?? p['profitPercent'] ?? 0) as num).toDouble(),
              )));
          }
        } catch (e) {
          print('Note: Live MT5 positions not available: $e');
        }

        // De-duplicate by ticket/id and keep recent first for the Trades screen.
        final deduped = <String, Trade>{};
        for (final trade in allTrades) {
          deduped[trade.id] = trade;
        }
        final mergedTrades = deduped.values.toList();
        mergedTrades.sort((a, b) => b.openedAt.compareTo(a.openedAt));
        _trades = mergedTrades;
        _errorMessage = null;
      } catch (e) {
        print('Error fetching trades from API: $e');
        _errorMessage = 'Failed to fetch real trades: $e';
        _trades = [];
      }
    } else {
      // Use mock data
      _initializeMockData();
    }

    _isLoading = false;
    notifyListeners();
  }

  // Fetch accounts from API or mock
  Future<void> fetchAccounts() async {
    if (_useApi && _isConnected) {
      try {
        final prefs = await SharedPreferences.getInstance();
        final sessionToken = prefs.getString('auth_token');
        if (sessionToken == null || sessionToken.isEmpty) {
          _errorMessage = 'Session token missing. Please login again.';
          _accounts = [];
          _isLoading = false;
          notifyListeners();
          return;
        }
        
        // Use detailed endpoint to get all account metrics including profit
        final response = await http.get(
          Uri.parse('$_apiUrl/api/account/detailed'),
          headers: {
            'Content-Type': 'application/json',
            'X-Session-Token': sessionToken,
          },
        ).timeout(const Duration(seconds: 10));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final accData = data['account'];
          
          _accounts = [
            Account(
              id: '1',
              accountNumber: accData['accountNumber'].toString(),
              balance: (accData['balance'] as num).toDouble(),
              usedMargin: ((accData['margin'] ?? 0) as num).toDouble(),
              availableMargin: ((accData['marginFree'] ?? 0) as num).toDouble(),
              profit: (accData['profit'] ?? 0.0).toDouble(),
              currency: accData['currency'] ?? 'USD',
              status: 'active',
              createdAt: DateTime.now().subtract(const Duration(days: 365)),
              leverage: '1:${accData['leverage'] ?? 100}',
              broker: accData['broker'] ?? 'Exness',
            )
          ];

          _errorMessage = null;
        } else {
          _errorMessage = 'Failed to fetch account details (${response.statusCode})';
          _accounts = [];
        }
      } catch (e) {
        print('Error fetching accounts from API: $e');
        _errorMessage = 'Failed to fetch real account details: $e';
        _accounts = [];
      }
    } else {
      _initializeMockData();
    }

    _isLoading = false;
    notifyListeners();
  }

  // Open new trade via API or mock
  Future<bool> openTrade(String symbol, TradeType type, double quantity, 
      double entryPrice, double? takeProfit, double? stopLoss) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_useApi && _isConnected) {
        final response = await http.post(
          Uri.parse('$_apiUrl/api/trade/place'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'accountId': 'Default MT5',
            'symbol': symbol.toUpperCase(),
            'type': type == TradeType.buy ? 'BUY' : 'SELL',
            'volume': quantity,
            'entryPrice': entryPrice,
            'takeProfit': takeProfit,
            'stopLoss': stopLoss,
            'comment': 'Zwesta Trade',
          }),
        ).timeout(const Duration(seconds: 15));

        if (response.statusCode == 200 || response.statusCode == 201) {
          final data = jsonDecode(response.body);
          if (data['success'] == true) {
            await fetchTrades(); // Refresh trades
            _isLoading = false;
            _errorMessage = null;
            notifyListeners();
            return true;
          } else {
            _errorMessage = data['error'] ?? data['message'] ?? 'Trade failed';
          }
        } else {
          _errorMessage = 'Server error: ${response.statusCode} - ${response.body}';
        }
      } else {
        // Mock data
        await Future.delayed(const Duration(seconds: 1));

        final newTrade = Trade(
          id: '${DateTime.now().millisecondsSinceEpoch}',
          symbol: symbol,
          type: type,
          quantity: quantity,
          entryPrice: entryPrice,
          currentPrice: entryPrice,
          takeProfit: takeProfit,
          stopLoss: stopLoss,
          status: TradeStatus.open,
          openedAt: DateTime.now(),
        );

        _trades.add(newTrade);
        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      _errorMessage = e.toString();
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  // Close trade via API or mock
  Future<bool> closeTrade(String tradeId, double closingPrice) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_useApi && _isConnected) {
        final response = await http.post(
          Uri.parse('$_apiUrl/api/trade/close'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'ticket': int.parse(tradeId),
          }),
        ).timeout(const Duration(seconds: 15));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          if (data['success']) {
            await fetchTrades(); // Refresh trades
            _isLoading = false;
            notifyListeners();
            return true;
          } else {
            _errorMessage = data['message'] ?? 'Close failed';
          }
        } else {
          _errorMessage = 'Server error: ${response.statusCode}';
        }
      } else {
        // Mock data
        await Future.delayed(const Duration(seconds: 1));

        final tradeIndex = _trades.indexWhere((t) => t.id == tradeId);
        if (tradeIndex != -1) {
          final trade = _trades[tradeIndex];
          final profit = (closingPrice - trade.entryPrice) * trade.quantity;
          final profitPercentage = ((closingPrice - trade.entryPrice) / trade.entryPrice) * 100;

          _trades[tradeIndex] = Trade(
            id: trade.id,
            symbol: trade.symbol,
            type: trade.type,
            quantity: trade.quantity,
            entryPrice: trade.entryPrice,
            currentPrice: closingPrice,
            takeProfit: trade.takeProfit,
            stopLoss: trade.stopLoss,
            status: TradeStatus.closed,
            openedAt: trade.openedAt,
            closedAt: DateTime.now(),
            profit: profit,
            profitPercentage: profitPercentage,
          );
        }

        _isLoading = false;
        notifyListeners();
        return true;
      }
    } catch (e) {
      _errorMessage = e.toString();
    }

    _isLoading = false;
    notifyListeners();
    return false;
  }

  // Update trade
  Future<bool> updateTrade(String tradeId, double? takeProfit, double? stopLoss) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await Future.delayed(const Duration(seconds: 1));

      final tradeIndex = _trades.indexWhere((t) => t.id == tradeId);
      if (tradeIndex != -1) {
        final trade = _trades[tradeIndex];
        _trades[tradeIndex] = Trade(
          id: trade.id,
          symbol: trade.symbol,
          type: trade.type,
          quantity: trade.quantity,
          entryPrice: trade.entryPrice,
          currentPrice: trade.currentPrice,
          takeProfit: takeProfit ?? trade.takeProfit,
          stopLoss: stopLoss ?? trade.stopLoss,
          status: trade.status,
          openedAt: trade.openedAt,
          closedAt: trade.closedAt,
          profit: trade.profit,
          profitPercentage: trade.profitPercentage,
        );
      }

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Select trade for details view
  void selectTrade(Trade trade) {
    _selectedTrade = trade;
    notifyListeners();
  }

  // Clear selected trade
  void clearSelectedTrade() {
    _selectedTrade = null;
    notifyListeners();
  }

  // Clear error message
  void clearErrorMessage() {
    _errorMessage = null;
    notifyListeners();
  }

  // Sync with connected broker account
  Future<void> syncBrokerAccount({
    required String brokerName,
    required String accountNumber,
    required String server,
  }) async {
    _isLoading = true;
    notifyListeners();

    try {
      // Update primary account with broker info
      if (_accounts.isNotEmpty) {
        _accounts[0] = Account(
          id: '1',
          accountNumber: accountNumber,
          balance: 50000, // Would fetch from broker API
          usedMargin: 5000,
          availableMargin: 45000,
          profit: 0,
          currency: 'USD',
          status: 'active',
          createdAt: DateTime.now().subtract(const Duration(days: 365)),
          leverage: '1:100',
          broker: brokerName,
          server: server,
        );
      }

      // If using API, refresh from it
      if (_useApi && _isConnected) {
        await fetchAccounts();
        await fetchTrades();
      } else {
        // Simulate fetching live trades from broker
        await Future.delayed(const Duration(milliseconds: 500));
      }

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to sync broker account: $e';
      _isLoading = false;
      notifyListeners();
    }
  }

  // Refresh trades from broker (auto-refresh)
  Future<void> refreshBrokerTrades({
    required String accountNumber,
    required String server,
  }) async {
    try {
      if (_useApi && _isConnected) {
        await fetchTrades(); // Fresh data from API
      } else {
        // Simulate fetching updated trades from broker
        await Future.delayed(const Duration(milliseconds: 300));

        // For mock data, update timestamp to show refresh happened
        for (var i = 0; i < _trades.length; i++) {
          _trades[i] = Trade(
            id: _trades[i].id,
            symbol: _trades[i].symbol,
            type: _trades[i].type,
            quantity: _trades[i].quantity,
            entryPrice: _trades[i].entryPrice,
            currentPrice: (_trades[i].currentPrice ?? 0) +
                (DateTime.now().millisecondsSinceEpoch % 10) / 10000,
            takeProfit: _trades[i].takeProfit,
            stopLoss: _trades[i].stopLoss,
            status: _trades[i].status,
            openedAt: _trades[i].openedAt,
            profit: _trades[i].profit,
            profitPercentage: _trades[i].profitPercentage,
          );
        }
      }

      notifyListeners();
    } catch (e) {
      _errorMessage = 'Failed to refresh trades: $e';
      notifyListeners();
    }
  }
}
