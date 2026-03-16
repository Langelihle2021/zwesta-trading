import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/environment_config.dart';

/// Service for IG API operations from Flutter.
/// Calls backend endpoints in ig_service.py.
class IGTradingService {
  static String get _baseUrl => EnvironmentConfig.apiUrl;

  static Future<Map<String, String>> _authHeaders({bool includeContentType = true}) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token');

    final headers = <String, String>{
      if (includeContentType) 'Content-Type': 'application/json',
    };

    if (token != null && token.isNotEmpty) {
      headers['X-Session-Token'] = token;
    }

    return headers;
  }

  static Map<String, dynamic> _parseApiResponse(http.Response resp) {
    try {
      final data = jsonDecode(resp.body);
      if (data is Map<String, dynamic>) {
        return data;
      }
      return {'success': false, 'error': 'Unexpected response payload'};
    } catch (_) {
      if (resp.statusCode == 401) {
        return {'success': false, 'error': 'Session expired or invalid. Please login again.'};
      }
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    }
  }

  // ==================== BALANCE ====================

  static Future<Map<String, dynamic>> getBalance() async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/balance'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== FUNDS ====================

  static Future<Map<String, dynamic>> getFunds() async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/funds'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== POSITIONS ====================

  static Future<Map<String, dynamic>> getPositions() async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/positions'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
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
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/close-position'),
        headers: headers,
        body: jsonEncode({
          'dealId': dealId,
          'direction': direction,
          'size': size,
        }),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE ALL POSITIONS ====================

  static Future<Map<String, dynamic>> closeAllPositions() async {
    try {
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/close-all-positions'),
        headers: headers,
        body: jsonEncode({}),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
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
      final headers = await _authHeaders();
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
        headers: headers,
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
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
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/transactions?type=$type&pageSize=$pageSize'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== ACTIVITY ====================

  static Future<Map<String, dynamic>> getActivity({int pageSize = 50}) async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/activity?pageSize=$pageSize'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== MARKET SEARCH ====================

  static Future<Map<String, dynamic>> searchMarkets(String searchTerm) async {
    try {
      final encoded = Uri.encodeComponent(searchTerm);
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/markets/search?searchTerm=$encoded'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== WORKING ORDERS ====================

  static Future<Map<String, dynamic>> getWorkingOrders() async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/working-orders'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== ACCOUNTS ====================

  static Future<Map<String, dynamic>> getAccounts() async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/accounts'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== LOGIN ====================

  static Future<Map<String, dynamic>> login() async {
    try {
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/login'),
        headers: headers,
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
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
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/profit-check'),
        headers: headers,
        body: jsonEncode({
          'target_profit': targetProfit,
          'user_id': userId,
          'auto_close': autoClose,
        }),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== WITHDRAWAL NOTIFICATIONS ====================

  /// Get all withdrawal-ready notifications for a user.
  static Future<Map<String, dynamic>> getWithdrawalNotifications(String userId) async {
    try {
      final headers = await _authHeaders(includeContentType: false);
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications?user_id=$userId'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
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
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications'),
        headers: headers,
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
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Mark a withdrawal notification as completed.
  static Future<Map<String, dynamic>> markWithdrawalDone(String notifId) async {
    try {
      final headers = await _authHeaders();
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/ig/withdrawal-notifications/$notifId/mark-done'),
        headers: headers,
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return _parseApiResponse(resp);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
