import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:logger/logger.dart';

import '../utils/environment_config.dart';

class ExnessWithdrawalService {
  final Logger logger = Logger();

  /// Request a withdrawal from Exness account
  Future<Map<String, dynamic>> requestWithdrawal({
    required String userId,
    required String brokerAccountId,
    required String withdrawalType, // 'profits', 'commission', 'both'
    required double amount,
    String withdrawalMethod = 'bank_transfer',
    String? paymentDetails,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/withdrawal/request'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${EnvironmentConfig.apiKey}',
        },
        body: jsonEncode({
          'user_id': userId,
          'broker_account_id': brokerAccountId,
          'withdrawal_type': withdrawalType,
          'amount': amount,
          'withdrawal_method': withdrawalMethod,
          'payment_details': paymentDetails,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        logger.i('✅ Withdrawal request successful: ${data['withdrawal_id']}');
        return {
          'success': true,
          'withdrawal_id': data['withdrawal_id'],
          'net_amount': data['net_amount'],
          'fee': data['fee'],
        };
      } else {
        final error = jsonDecode(response.body);
        logger.e('❌ Withdrawal request failed: ${error['error']}');
        return {
          'success': false,
          'error': error['error'] ?? 'Withdrawal request failed',
        };
      }
    } catch (e) {
      logger.e('❌ Withdrawal request exception: $e');
      return {
        'success': false,
        'error': e.toString(),
      };
    }
  }

  /// Get withdrawal history for user
  Future<List<Map<String, dynamic>>> getWithdrawalHistory(String userId) async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/withdrawal/history/$userId'),
        headers: {'Authorization': 'Bearer ${EnvironmentConfig.apiKey}'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final withdrawals = List<Map<String, dynamic>>.from(data['withdrawals'] ?? []);
        logger.i('✅ Retrieved ${withdrawals.length} withdrawals');
        return withdrawals;
      } else {
        logger.e('❌ Failed to fetch withdrawal history');
        return [];
      }
    } catch (e) {
      logger.e('❌ Error fetching withdrawal history: $e');
      return [];
    }
  }

  /// Get withdrawal status
  Future<Map<String, dynamic>> getWithdrawalStatus(String withdrawalId) async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/withdrawal/status/$withdrawalId'),
        headers: {'Authorization': 'Bearer ${EnvironmentConfig.apiKey}'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        logger.i('✅ Withdrawal status: ${data['status']}');
        return {
          'success': true,
          ...data,
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to fetch withdrawal status',
        };
      }
    } catch (e) {
      logger.e('❌ Error fetching withdrawal status: $e');
      return {
        'success': false,
        'error': e.toString(),
      };
    }
  }

  /// Get available balance for withdrawal
  Future<Map<String, dynamic>> getWithdrawalBalance(String userId) async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/balance/$userId'),
        headers: {'Authorization': 'Bearer ${EnvironmentConfig.apiKey}'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        logger.i('✅ Available balance: \$${data['total_available']}');
        return {
          'success': true,
          'available_profits': data['available_profits'] ?? 0.0,
          'available_commission': data['available_commission'] ?? 0.0,
          'total_available': data['total_available'] ?? 0.0,
          'pending_withdrawals': data['pending_withdrawals'] ?? 0.0,
          'net_available': data['net_available'] ?? 0.0,
        };
      } else {
        logger.e('❌ Failed to fetch balance');
        return {
          'success': false,
          'available_profits': 0.0,
          'available_commission': 0.0,
          'total_available': 0.0,
          'pending_withdrawals': 0.0,
          'net_available': 0.0,
        };
      }
    } catch (e) {
      logger.e('❌ Error fetching balance: $e');
      return {
        'success': false,
        'available_profits': 0.0,
        'available_commission': 0.0,
        'total_available': 0.0,
        'pending_withdrawals': 0.0,
        'net_available': 0.0,
      };
    }
  }

  /// Record a closed trade profit
  Future<bool> recordTradeProfitClosed({
    required String userId,
    required String brokerAccountId,
    required String orderId,
    required String symbol,
    required double entryPrice,
    required double exitPrice,
    required double volume,
    required String side,
    required double profitLoss,
    double commission = 0,
    int? tradeDurationSeconds,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/trade/closed'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${EnvironmentConfig.apiKey}',
        },
        body: jsonEncode({
          'user_id': userId,
          'broker_account_id': brokerAccountId,
          'order_id': orderId,
          'symbol': symbol,
          'entry_price': entryPrice,
          'exit_price': exitPrice,
          'volume': volume,
          'side': side,
          'profit_loss': profitLoss,
          'commission': commission,
          'trade_duration_seconds': tradeDurationSeconds,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 201) {
        logger.i('✅ Trade profit recorded: $symbol P&L \$$profitLoss');
        return true;
      } else {
        logger.e('❌ Failed to record trade profit');
        return false;
      }
    } catch (e) {
      logger.e('❌ Error recording trade profit: $e');
      return false;
    }
  }
}
