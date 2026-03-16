import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

/// Service for unified broker portfolio + crypto strategies.
class UnifiedBrokerService {
  static String get _baseUrl => EnvironmentConfig.apiUrl;

  // ==================== PORTFOLIO ====================

  static Future<Map<String, dynamic>> getPortfolio() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/unified/portfolio'),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== POSITIONS ====================

  static Future<Map<String, dynamic>> getAllPositions() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/unified/positions'),
      ).timeout(const Duration(seconds: 30));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CLOSE ALL ====================

  static Future<Map<String, dynamic>> closeAllPositions() async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/unified/close-all'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({}),
      ).timeout(const Duration(seconds: 45));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  // ==================== CRYPTO STRATEGIES ====================

  static Future<Map<String, dynamic>> getCryptoStrategies() async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/crypto/strategies'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> activateStrategy({
    required String userId,
    required String strategyId,
    required String pair,
    Map<String, dynamic> params = const {},
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/crypto/strategies/activate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'strategy_id': strategyId,
          'pair': pair,
          'params': params,
        }),
      ).timeout(const Duration(seconds: 15));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> getActiveStrategies(String userId) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/api/crypto/strategies/active?user_id=$userId'),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> deactivateStrategy(String botId) async {
    try {
      final resp = await http.post(
        Uri.parse('$_baseUrl/api/crypto/strategies/$botId/deactivate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({}),
      ).timeout(const Duration(seconds: 10));

      if (resp.statusCode == 200) return jsonDecode(resp.body);
      return {'success': false, 'error': 'Server error ${resp.statusCode}'};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
