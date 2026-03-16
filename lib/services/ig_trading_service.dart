import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

/// Service for IG API operations from Flutter.
/// Calls backend endpoints in ig_service.py.
class IGTradingService {
  static String get _baseUrl => EnvironmentConfig.apiUrl;

  // ==================== BALANCE ====================

  static Future<Map<String, dynamic>> getBalance() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/balance'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== FUNDS ====================

  static Future<Map<String, dynamic>> getFunds() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/funds'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== POSITIONS ====================

  static Future<Map<String, dynamic>> getPositions() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/positions'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE POSITION ====================

  static Future<Map<String, dynamic>> closePosition({
    required String dealId,
    required String direction,
    required double size,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/close-position'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'dealId': dealId,
          'direction': direction,
          'size': size,
        }),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE ALL POSITIONS ====================

  static Future<Map<String, dynamic>> closeAllPositions() async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/close-all-positions'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({}),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PLACE ORDER ====================

  static Future<Map<String, dynamic>> placeOrder({
    required String epic,
    required String direction,
    required double size,
    double? stopDistance,
    double? limitDistance,
    String currencyCode = 'USD',
  }) async {
    try {
      final body = <String, dynamic>{
        'epic': epic,
        'direction': direction,
        'size': size,
        'orderType': 'MARKET',
        'timeInForce': 'FILL_OR_KILL',
        'currencyCode': currencyCode,
        'forceOpen': true,
        'guaranteedStop': false,
      };
      if (stopDistance != null) body['stopDistance'] = stopDistance;
      if (limitDistance != null) body['limitDistance'] = limitDistance;

      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/place-order'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== TRANSACTIONS / TRADE HISTORY ====================

  static Future<Map<String, dynamic>> getTransactions({
    String type = 'ALL',
    int pageSize = 50,
  }) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/transactions?type=$type&pageSize=$pageSize'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== ACTIVITY ====================

  static Future<Map<String, dynamic>> getActivity({int pageSize = 50}) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/activity?pageSize=$pageSize'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== MARKET SEARCH ====================

  static Future<Map<String, dynamic>> searchMarkets(String searchTerm) async {
    try {
      final encoded = Uri.encodeComponent(searchTerm);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/markets/search?searchTerm=$encoded'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== WORKING ORDERS ====================

  static Future<Map<String, dynamic>> getWorkingOrders() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/working-orders'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== ACCOUNTS ====================

  static Future<Map<String, dynamic>> getAccounts() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/accounts'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== LOGIN ====================

  static Future<Map<String, dynamic>> login() async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/login'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== PROFIT CHECK & AUTO-CLOSE ====================

  /// Check IG positions against a profit target.
  /// If target is reached, positions are auto-closed and a notification is created.
  static Future<Map<String, dynamic>> profitCheck({
    required double targetProfit,
    required String userId,
    bool autoClose = true,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/profit-check'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'target_profit': targetProfit,
          'user_id': userId,
          'auto_close': autoClose,
        }),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== WITHDRAWAL NOTIFICATIONS ====================

  /// Get all withdrawal-ready notifications for a user.
  static Future<Map<String, dynamic>> getWithdrawalNotifications(String userId) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications?user_id=$userId'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Create a withdrawal notification after profits are realized.
  static Future<Map<String, dynamic>> createWithdrawalNotification({
    required String userId,
    required double realizedProfit,
    required int positionsClosed,
    required double balanceAvailable,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'realized_profit': realizedProfit,
          'positions_closed': positionsClosed,
          'balance_available': balanceAvailable,
        }),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Mark a withdrawal notification as completed.
  static Future<Map<String, dynamic>> markWithdrawalDone(String notifId) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications/$notifId/mark-done'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
