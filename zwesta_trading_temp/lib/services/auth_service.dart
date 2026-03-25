import 'package:flutter/material.dart';
import 'package:zwesta_trading_temp/models/user.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';

class AuthService extends ChangeNotifier {
  final ApiService apiService;
  bool _isLoggedIn = false;
  bool _isInitializing = true;
  User? _currentUser;
  String? _token;

  AuthService({required this.apiService}) {
    _initialize();
  }

  bool get isLoggedIn => _isLoggedIn;
  bool get isInitializing => _isInitializing;
  User? get currentUser => _currentUser;

  void _initialize() async {
    await Future.delayed(const Duration(seconds: 2));
    _isInitializing = false;
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    try {
      final response = await apiService.login(username, password);
      if (response['success'] == true) {
        _currentUser = User.fromJson(response['user']);
        _token = response['token'];
        _isLoggedIn = true;
        notifyListeners();
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<bool> register(String username, String email, String password,
      String fullName, String phoneNumber) async {
    try {
      final success =
          await apiService.register(username, email, password, fullName, phoneNumber);
      return success;
    } catch (e) {
      return false;
    }
  }

  Future<bool> forgotPassword(String email) async {
    try {
      return await apiService.forgotPassword(email);
    } catch (e) {
      return false;
    }
  }

  Future<bool> resetPassword(String token, String newPassword) async {
    try {
      return await apiService.resetPassword(token, newPassword);
    } catch (e) {
      return false;
    }
  }

  Future<void> logout() async {
    _isLoggedIn = false;
    _currentUser = null;
    _token = null;
    await apiService.logout();
    notifyListeners();
  }
}
