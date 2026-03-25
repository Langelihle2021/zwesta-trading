import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:zwesta_trading/config/app_config.dart';

class ApiService {
  late Dio _dio;
  final _secureStorage = const FlutterSecureStorage();

  ApiService() {
    _initializeDio();
  }

  void _initializeDio() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: Duration(seconds: int.parse(AppConfig.apiTimeout)),
        receiveTimeout: Duration(seconds: int.parse(AppConfig.apiTimeout)),
        contentType: 'application/json',
      ),
    );

    // Add interceptors
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _secureStorage.read(key: 'auth_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onError: (error, handler) {
        if (error.response?.statusCode == 401) {
          // Token expired - clear and redirect to login
          _secureStorage.delete(key: 'auth_token');
        }
        return handler.next(error);
      },
    ));
  }

  // Auth Endpoints
  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final response = await _dio.post(
        '/auth/login',
        data: {
          'username': username,
          'password': password,
        },
      );
      return {
        'success': true,
        'token': response.data['access_token'],
        'message': 'Login successful',
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'Login failed: $e',
      };
    }
  }

  Future<Map<String, dynamic>> signup(
      String username, String email, String password) async {
    try {
      final response = await _dio.post(
        '/auth/signup',
        data: {
          'username': username,
          'email': email,
          'password': password,
        },
      );
      return {
        'success': true,
        'token': response.data['access_token'],
        'message': 'Signup successful',
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'Signup failed: $e',
      };
    }
  }

  // Trading Endpoints
  Future<Map<String, dynamic>> getTrades() async {
    try {
      final response = await _dio.get('/trading/trades');
      return {'trades': response.data['trades'] ?? []};
    } catch (e) {
      throw Exception('Failed to fetch trades: $e');
    }
  }

  Future<Map<String, dynamic>> getPositions() async {
    try {
      final response = await _dio.get('/trading/positions');
      return {'positions': response.data['positions'] ?? []};
    } catch (e) {
      throw Exception('Failed to fetch positions: $e');
    }
  }

  Future<Map<String, dynamic>> getMarketData(String symbol) async {
    try {
      final response = await _dio.get('/market/data/$symbol');
      return response.data;
    } catch (e) {
      throw Exception('Failed to fetch market data: $e');
    }
  }

  Future<Map<String, dynamic>> getStatistics() async {
    try {
      final response = await _dio.get('/trading/statistics');
      return response.data;
    } catch (e) {
      throw Exception('Failed to fetch statistics: $e');
    }
  }

  // Position Management
  Future<bool> closeTrade(String tradeId) async {
    try {
      await _dio.post('/trading/positions/$tradeId/close');
      return true;
    } catch (e) {
      throw Exception('Failed to close trade: $e');
    }
  }

  Future<Map<String, dynamic>> updateStopLoss(
      String positionId, double newSL) async {
    try {
      final response = await _dio.put(
        '/trading/positions/$positionId/stop-loss',
        data: {'stop_loss': newSL},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update stop loss: $e');
    }
  }

  Future<Map<String, dynamic>> updateTakeProfit(
      String positionId, double newTP) async {
    try {
      final response = await _dio.put(
        '/trading/positions/$positionId/take-profit',
        data: {'take_profit': newTP},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to update take profit: $e');
    }
  }

  // Account Endpoints
  Future<Map<String, dynamic>> getAccountInfo() async {
    try {
      final response = await _dio.get('/accounts/me');
      return response.data;
    } catch (e) {
      throw Exception('Failed to fetch account info: $e');
    }
  }

  // Reports
  Future<Map<String, dynamic>> generateReport(String type) async {
    try {
      final response = await _dio.post(
        '/reports/generate',
        data: {'type': type},
      );
      return response.data;
    } catch (e) {
      throw Exception('Failed to generate report: $e');
    }
  }
}
