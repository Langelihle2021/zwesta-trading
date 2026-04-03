import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

/// Service for Binance API operations from Flutter.
/// Calls backend endpoints in binance_service.py.
class BinanceTradingService {
  static String get _baseUrl => EnvironmentConfig.apiUrl;

  // ==================== LOGIN ====================

  static Future<Map<String, dynamic>> login({String? apiKey, String? apiSecret}) async {
    try {
      final body = <String, dynamic>{};
      if (apiKey != null) body['api_key'] = apiKey;
      if (apiSecret != null) body['api_secret'] = apiSecret;

      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== ACCOUNTS ====================

  static Future<Map<String, dynamic>> getAccounts() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/accounts'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== BALANCE ====================

  static Future<Map<String, dynamic>> getBalance() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/balance'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== FUNDS ====================

  static Future<Map<String, dynamic>> getFunds() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/funds'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== POSITIONS ====================

  static Future<Map<String, dynamic>> getPositions() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/positions'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== FUTURES POSITIONS ====================

  static Future<Map<String, dynamic>> getFuturesPositions() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/futures-positions'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE POSITION ====================

  static Future<Map<String, dynamic>> closePosition({
    required String symbol,
    String? orderId,
    double? size,
    String direction = 'SELL',
  }) async {
    try {
      final body = <String, dynamic>{'symbol': symbol, 'direction': direction};
      if (orderId != null) body['dealId'] = orderId;
      if (size != null) body['size'] = size;

      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/close-position'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE ALL POSITIONS ====================

  static Future<Map<String, dynamic>> closeAllPositions() async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/close-all-positions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({}),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PLACE ORDER ====================

  static Future<Map<String, dynamic>> placeOrder({
    required String symbol,
    required String direction,
    required double size,
    String orderType = 'MARKET',
    double? price,
    String market = 'spot',
  }) async {
    try {
      final body = <String, dynamic>{
        'instrument': symbol,
        'direction': direction,
        'size': size,
        'orderType': orderType,
        'market': market,
      };
      if (price != null) body['price'] = price;

      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/place-order'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PENDING ORDERS ====================

  static Future<Map<String, dynamic>> getPendingOrders({String? symbol}) async {
    try {
      var url = '$_baseUrl/api/binance/pending-orders';
      if (symbol != null) url += '?symbol=$symbol';

      final resp = await http.get(
        Uri.parse(url),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> cancelOrder(String orderId, {required String symbol}) async {
    try {
      final resp = await http.delete(
        Uri.parse('$_baseUrl/api/binance/pending-orders/$orderId?symbol=$symbol'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== TRANSACTIONS ====================

  static Future<Map<String, dynamic>> getTransactions({String symbol = 'BTCUSDT', int pageSize = 50}) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/transactions?symbol=$symbol&pageSize=$pageSize'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== INSTRUMENTS ====================

  static Future<Map<String, dynamic>> searchInstruments(String searchTerm) async {
    try {
      final encoded = Uri.encodeComponent(searchTerm);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/instruments?searchTerm=$encoded'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PRICING ====================

  static Future<Map<String, dynamic>> getPricing(String instruments) async {
    try {
      final encoded = Uri.encodeComponent(instruments);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/pricing?instruments=$encoded'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CANDLES ====================

  static Future<Map<String, dynamic>> getCandles(
    String symbol, {
    String interval = '1h',
    int limit = 100,
  }) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/candles/$symbol?interval=$interval&limit=$limit'),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PROFIT CHECK & AUTO-CLOSE ====================

  static Future<Map<String, dynamic>> profitCheck({
    required double targetProfit,
    required String userId,
    bool autoClose = true,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/profit-check'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'target_profit': targetProfit,
          'user_id': userId,
          'auto_close': autoClose,
        }),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== USDT WITHDRAWAL ====================

  static Future<Map<String, dynamic>> withdrawUsdt({
    required double amount,
    required String address,
    String network = 'TRC20',
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/withdraw'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'amount': amount,
          'address': address,
          'network': network,
        }),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== WITHDRAWAL NOTIFICATIONS ====================

  static Future<Map<String, dynamic>> getWithdrawalNotifications(String userId) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/binance/withdrawal-notifications?user_id=$userId'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> createWithdrawalNotification({
    required String userId,
    required double realizedProfit,
    required int positionsClosed,
    required double balanceAvailable,
    String walletAddress = '',
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/binance/withdrawal-notifications'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'realized_profit': realizedProfit,
          'positions_closed': positionsClosed,
          'balance_available': balanceAvailable,
          'wallet_address': walletAddress,
        }),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
