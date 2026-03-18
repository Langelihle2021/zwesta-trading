import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/environment_config.dart';

class WithdrawalService {
  static const String _baseUrl = '${EnvironmentConfig.apiUrl}';

  /// Get user's wallet balance
  static Future<Map<String, dynamic>> getWalletBalance(String userId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$_baseUrl/api/wallet/balance/$userId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch wallet balance');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Request a withdrawal
  static Future<Map<String, dynamic>> requestWithdrawal({
    required String userId,
    required double amount,
    required String method,
    required String accountDetails,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.post(
        Uri.parse('$_baseUrl/api/withdrawal/request'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({
          'user_id': userId,
          'amount': amount,
          'method': method,
          'account_details': accountDetails,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200 || response.statusCode == 201) {
        return jsonDecode(response.body);
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? 'Failed to request withdrawal');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Get withdrawal history
  static Future<Map<String, dynamic>> getWithdrawalHistory(String userId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$_baseUrl/api/withdrawal/history/$userId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch withdrawal history');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Get Exness withdrawal balance
  static Future<Map<String, dynamic>> getExnessBalance(String userId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$_baseUrl/api/broker/exness/balance/$userId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch Exness balance');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Admin: Get pending withdrawals
  static Future<Map<String, dynamic>> getPendingWithdrawals(String apiKey) async {
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/admin/withdrawals/pending'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch pending withdrawals');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Admin: Verify and split commission
  static Future<Map<String, dynamic>> verifyWithdrawal({
    required String withdrawalId,
    required String notes,
    required String apiKey,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/admin/withdrawal/exness/verify'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: jsonEncode({
          'withdrawal_id': withdrawalId,
          'notes': notes,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? 'Failed to verify withdrawal');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Get Exness withdrawal history
  static Future<Map<String, dynamic>> getExnessWithdrawalHistory(String userId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');

      if (sessionToken == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$_baseUrl/api/broker/exness/withdrawal/history/$userId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch Exness withdrawal history');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }
}
