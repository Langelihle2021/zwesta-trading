import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:zwesta_trading/services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  final _apiService = ApiService();
  final _secureStorage = const FlutterSecureStorage();

  String? _token;
  String? _username;
  bool _isLoading = false;
  String? _error;

  // Getters
  String? get token => _token;
  String? get username => _username;
  bool get isLoading => _isLoading;
  bool get isAuthenticated => _token != null;
  String? get error => _error;

  // Constructor - check for existing token
  AuthProvider() {
    _checkExistingToken();
  }

  Future<void> _checkExistingToken() async {
    _isLoading = true;
    notifyListeners();

    try {
      final storedToken = await _secureStorage.read(key: 'auth_token');
      final storedUsername = await _secureStorage.read(key: 'username');

      if (storedToken != null) {
        _token = storedToken;
        _username = storedUsername;
        _error = null;
      }
    } catch (e) {
      _error = 'Failed to load stored credentials';
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _apiService.login(username, password);

      if (response['success'] == true) {
        _token = response['token'];
        _username = username;

        // Store token securely
        await _secureStorage.write(key: 'auth_token', value: _token!);
        await _secureStorage.write(key: 'username', value: username);

        _error = null;
        notifyListeners();
        return true;
      } else {
        _error = response['message'] ?? 'Login failed';
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = 'Login error: $e';
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> logout() async {
    try {
      await _secureStorage.delete(key: 'auth_token');
      await _secureStorage.delete(key: 'username');

      _token = null;
      _username = null;
      _error = null;

      notifyListeners();
      return true;
    } catch (e) {
      _error = 'Logout error: $e';
      notifyListeners();
      return false;
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
