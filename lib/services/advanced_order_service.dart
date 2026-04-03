import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

/// Enumeration for different order types
enum OrderType {
  market,    // Immediate execution at market price
  limit,     // Execute at specific price or better
  stop,      // Execute when price reaches stop level
  stopLimit, // Stop + limit combined
}

/// Enumeration for order directions
enum OrderDirection {
  buy,
  sell,
}

/// Model for advanced trading orders
class AdvancedOrder {

  AdvancedOrder({
    required this.symbol,
    required this.orderType,
    required this.direction,
    required this.quantity,
    required this.brokerName, required this.accountId, required this.sessionToken, this.limitPrice,
    this.stopPrice,
    this.takeProfit,
    this.stopLoss,
    this.trailingStop = false,
    this.trailingStopPips,
  });
  final String symbol;
  final OrderType orderType;
  final OrderDirection direction;
  final double quantity;
  final double? limitPrice;      // For limit orders
  final double? stopPrice;        // For stop/stop-limit orders
  final double? takeProfit;       // Profit target price
  final double? stopLoss;         // Loss limit price
  final bool? trailingStop;       // Use trailing stop instead of fixed
  final double? trailingStopPips; // Distance for trailing stop
  final String brokerName;
  final String accountId;
  final String sessionToken;

  Map<String, dynamic> toJson() => {
    'symbol': symbol,
    'order_type': orderType.name,
    'direction': direction.name,
    'quantity': quantity,
    'limit_price': limitPrice,
    'stop_price': stopPrice,
    'take_profit': takeProfit,
    'stop_loss': stopLoss,
    'trailing_stop': trailingStop,
    'trailing_stop_pips': trailingStopPips,
    'broker': brokerName,
    'account_id': accountId,
  };
}

/// Service for advanced order operations
class AdvancedOrderService {
  static String get _baseUrl => EnvironmentConfig.apiUrl;

  // ==================== PLACE ADVANCED ORDER ====================

  static Future<Map<String, dynamic>> placeAdvancedOrder(
    AdvancedOrder order,
  ) async {
    try {
      final broker = order.brokerName.toLowerCase();
      
      // Route to appropriate broker endpoint
      String endpoint;
      if (broker == 'exness') {
        endpoint = '/api/broker/exness/order/advanced';
      } else if (broker == 'pxbt') {
        endpoint = '/api/broker/pxbt/order/advanced';
      } else if (broker == 'binance') {
        endpoint = '/api/binance/order/advanced';
      } else {
        return {
          'success': false,
          'error': 'Advanced orders not supported for $broker'
        };
      }

      final response = await http.post(
        Uri.parse('$_baseUrl$endpoint'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${order.sessionToken}',
        },
        body: jsonEncode(order.toJson()),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'success': true,
          'order_id': data['order_id'],
          'order_ticket': data['order_ticket'],
          'entry_price': data['entry_price'],
          'take_profit': data['take_profit'],
          'stop_loss': data['stop_loss'],
          'message': 'Advanced order placed successfully',
        };
      } else {
        final error = jsonDecode(response.body);
        return {
          'success': false,
          'error': error['error'] ?? 'Failed to place order',
          'details': error['details'],
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Exception: $e',
      };
    }
  }

  // ==================== UPDATE ORDER ====================

  static Future<Map<String, dynamic>> updateOrder({
    required String orderId,
    required String brokerName,
    required String sessionToken,
    double? newTakeProfit,
    double? newStopLoss,
    double? newLimitPrice,
  }) async {
    try {
      final broker = brokerName.toLowerCase();
      
      String endpoint;
      if (broker == 'exness') {
        endpoint = '/api/broker/exness/order/$orderId/update';
      } else if (broker == 'pxbt') {
        endpoint = '/api/broker/pxbt/order/$orderId/update';
      } else if (broker == 'binance') {
        endpoint = '/api/binance/order/$orderId/update';
      } else {
        return {
          'success': false,
          'error': 'Order updates not supported for $broker'
        };
      }

      final body = <String, dynamic>{};
      if (newTakeProfit != null) body['take_profit'] = newTakeProfit;
      if (newStopLoss != null) body['stop_loss'] = newStopLoss;
      if (newLimitPrice != null) body['limit_price'] = newLimitPrice;

      final response = await http.patch(
        Uri.parse('$_baseUrl$endpoint'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $sessionToken',
        },
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'success': true,
          'order_id': data['order_id'],
          'take_profit': data['take_profit'],
          'stop_loss': data['stop_loss'],
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to update order',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Exception: $e',
      };
    }
  }

  // ==================== CLOSE ORDER ====================

  static Future<Map<String, dynamic>> closeOrder({
    required String orderId,
    required String brokerName,
    required String sessionToken,
    double? partialQuantity,
  }) async {
    try {
      final broker = brokerName.toLowerCase();
      
      String endpoint;
      if (broker == 'exness') {
        endpoint = '/api/broker/exness/order/$orderId/close';
      } else if (broker == 'pxbt') {
        endpoint = '/api/broker/pxbt/order/$orderId/close';
      } else if (broker == 'binance') {
        endpoint = '/api/binance/order/$orderId/close';
      } else {
        return {
          'success': false,
          'error': 'Cannot close orders for $broker'
        };
      }

      final body = <String, dynamic>{};
      if (partialQuantity != null) body['quantity'] = partialQuantity;

      final response = await http.post(
        Uri.parse('$_baseUrl$endpoint'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $sessionToken',
        },
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'success': true,
          'closing_price': data['closing_price'],
          'profit_loss': data['profit_loss'],
          'profit_loss_pips': data['profit_loss_pips'],
        };
      } else {
        return {
          'success': false,
          'error': 'Failed to close order',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Exception: $e',
      };
    }
  }

  // ==================== GET PENDING ORDERS ====================

  static Future<Map<String, dynamic>> getPendingOrders({
    required String brokerName,
    required String sessionToken,
    required String accountId,
  }) async {
    try {
      final broker = brokerName.toLowerCase();
      
      String endpoint;
      if (broker == 'exness') {
        endpoint = '/api/broker/exness/orders/pending';
      } else if (broker == 'pxbt') {
        endpoint = '/api/broker/pxbt/orders/pending';
      } else if (broker == 'binance') {
        endpoint = '/api/binance/orders/pending';
      } else {
        return {
          'success': false,
          'orders': [],
        };
      }

      final response = await http.get(
        Uri.parse('$_baseUrl$endpoint?account_id=$accountId'),
        headers: {
          'Authorization': 'Bearer $sessionToken',
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'success': true,
          'orders': data['orders'] ?? [],
        };
      } else {
        return {
          'success': false,
          'orders': [],
        };
      }
    } catch (e) {
      return {
        'success': false,
        'orders': [],
        'error': '$e',
      };
    }
  }

  // ==================== VALIDATE ORDER ====================

  static Future<Map<String, dynamic>> validateOrder(
    AdvancedOrder order,
  ) async {
    try {
      final validation = <String, dynamic>{
        'valid': true,
        'warnings': <String>[],
      };

      // Validate quantities
      if (order.quantity <= 0) {
        validation['valid'] = false;
        validation['warnings'].add('Quantity must be positive');
      }

      // Validate order type specific fields
      switch (order.orderType) {
        case OrderType.limit:
          if (order.limitPrice == null || order.limitPrice! <= 0) {
            validation['valid'] = false;
            validation['warnings'].add('Limit price required and must be positive');
          }
          break;
        case OrderType.stop:
          if (order.stopPrice == null || order.stopPrice! <= 0) {
            validation['valid'] = false;
            validation['warnings'].add('Stop price required and must be positive');
          }
          break;
        case OrderType.stopLimit:
          if (order.limitPrice == null || order.limitPrice! <= 0) {
            validation['valid'] = false;
            validation['warnings'].add('Limit price required and must be positive');
          }
          if (order.stopPrice == null || order.stopPrice! <= 0) {
            validation['valid'] = false;
            validation['warnings'].add('Stop price required and must be positive');
          }
          break;
        case OrderType.market:
          break;
      }

      // Validate take profit and stop loss
      if (order.takeProfit != null && order.takeProfit! <= 0) {
        validation['warnings'].add('Take profit should be positive');
      }
      if (order.stopLoss != null && order.stopLoss! <= 0) {
        validation['warnings'].add('Stop loss should be positive');
      }

      // Validate trailing stop
      if (order.trailingStop == true) {
        if (order.trailingStopPips == null || order.trailingStopPips! <= 0) {
          validation['valid'] = false;
          validation['warnings'].add('Trailing stop distance (pips) required and must be positive');
        }
      }

      return validation;
    } catch (e) {
      return {
        'valid': false,
        'warnings': ['Validation error: $e'],
      };
    }
  }
}
