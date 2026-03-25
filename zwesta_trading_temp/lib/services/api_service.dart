import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  static const String baseUrl = 'http://38.247.146.198:5000';
  static const Duration connectionTimeout = Duration(seconds: 10);
  static const Duration receiveTimeout = Duration(seconds: 10);

  late Dio dio;
  final _secureStorage = const FlutterSecureStorage();

  ApiService() {
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: connectionTimeout,
        receiveTimeout: receiveTimeout,
        contentType: 'application/json',
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _getToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (error, handler) {
          if (error.response?.statusCode == 401) {
            _clearToken();
          }
          return handler.next(error);
        },
      ),
    );
  }

  // Auth endpoints
  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final response = await dio.post(
        '/api/auth/login',
        data: {'username': username, 'password': password},
      );
      if (response.statusCode == 200) {
        final token = response.data['token'];
        if (token != null) {
          await _saveToken(token);
        }
        return response.data;
      }
      throw Exception('Login failed');
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> register(String username, String email, String password,
      String fullName, String phoneNumber) async {
    try {
      final response = await dio.post(
        '/api/auth/register',
        data: {
          'username': username,
          'email': email,
          'password': password,
          'fullName': fullName,
          'phoneNumber': phoneNumber,
        },
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> forgotPassword(String email) async {
    try {
      final response = await dio.post(
        '/api/auth/forgot-password',
        data: {'email': email},
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> resetPassword(String token, String newPassword) async {
    try {
      final response = await dio.post(
        '/api/auth/reset-password',
        data: {'token': token, 'newPassword': newPassword},
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  // Account endpoints
  Future<Map<String, dynamic>> getUserAccounts() async {
    try {
      final response = await dio.get('/api/user/accounts');
      return {'accounts': response.data is List ? response.data : []};
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> getAccountDashboard(String accountId) async {
    try {
      final response = await dio.get('/api/accounts/$accountId/dashboard');
      return response.data is Map ? response.data as Map<String, dynamic> : {};
    } catch (e) {
      rethrow;
    }
  }

  // Trading endpoints
  Future<Map<String, dynamic>> getPositions(String accountId) async {
    try {
      final response = await dio.get('/api/positions/$accountId');
      return {'positions': response.data is List ? response.data : []};
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> getTrades(String accountId) async {
    try {
      final response = await dio.get('/api/trades/$accountId');
      return {'trades': response.data is List ? response.data : []};
    } catch (e) {
      rethrow;
    }
  }

  // Market endpoints
  Future<Map<String, dynamic>> getMarketSymbols() async {
    try {
      final response = await dio.get('/api/markets/symbols');
      return {'symbols': response.data is List ? response.data : []};
    } catch (e) {
      rethrow;
    }
  }

  // Withdrawal endpoints
  Future<Map<String, dynamic>> getWithdrawals(String accountId) async {
    try {
      final response = await dio.get('/api/withdrawals/$accountId');
      return {'withdrawals': response.data is List ? response.data : []};
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> requestWithdrawal(String accountId, double amount,
      String bankName, String bankAccount) async {
    try {
      final response = await dio.post(
        '/api/withdrawals/request',
        data: {
          'accountId': accountId,
          'amount': amount,
          'bankName': bankName,
          'bankAccount': bankAccount
        },
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  // Settings endpoints
  Future<Map<String, dynamic>> getUserSettings() async {
    try {
      final response = await dio.get('/api/user/settings');
      return response.data is Map ? response.data as Map<String, dynamic> : {};
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> updateMt5Credentials(String login, String password) async {
    try {
      final response = await dio.post(
        '/api/user/mt5-credentials',
        data: {'mt5_login': login, 'mt5_password': password},
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> updateAlertSettings(double marginThreshold,
      double priceThreshold) async {
    try {
      final response = await dio.post(
        '/api/user/alert-settings',
        data: {
          'margin_threshold': marginThreshold,
          'price_threshold': priceThreshold
        },
      );
      return response.data['success'] == true;
    } catch (e) {
      rethrow;
    }
  }

  // Token management
  Future<void> _saveToken(String token) async {
    await _secureStorage.write(key: 'auth_token', value: token);
  }

  Future<String?> _getToken() async {
    return await _secureStorage.read(key: 'auth_token');
  }

  Future<void> _clearToken() async {
    await _secureStorage.delete(key: 'auth_token');
  }

  Future<void> logout() async {
    await _clearToken();
  }
}
