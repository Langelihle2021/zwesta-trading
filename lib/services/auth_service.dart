import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../utils/constants.dart';

class AuthService extends ChangeNotifier {
  late SharedPreferences _prefs;
  
  User? _currentUser;
  String? _token;
  bool _isLoading = false;
  String? _errorMessage;
  bool _isInitialized = false;

  AuthService() {
    // Set demo user immediately - synchronously available
    _token = 'demo_token_mobile';
    _currentUser = User(
      id: '123',
      username: 'demo',
      email: 'demo@zwesta.com',
      firstName: 'Demo',
      lastName: 'User',
      profileImage: '',
      accountType: 'Premium',
    );
    
    // Initialize preferences asynchronously in background
    _initializePreferences();
  }

  Future<void> _initializePreferences() async {
    try {
      _prefs = await SharedPreferences.getInstance();
      _loadFromStorage();
      _isInitialized = true;
      notifyListeners();
    } catch (e) {
      debugPrint('SharedPreferences initialization error: $e');
      // Already have demo user set, no need to reset
      _isInitialized = true;
      notifyListeners();
    }
  }

  // Getters
  User? get currentUser => _currentUser;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _token != null && _currentUser != null;

  // Load saved authentication from local storage
  void _loadFromStorage() {
    try {
      final tokenJson = _prefs.getString('auth_token');
      final userJson = _prefs.getString('current_user');
      
      if (tokenJson != null && userJson != null) {
        _token = tokenJson;
        _currentUser = User.fromJson(jsonDecode(userJson));
      } else {
        // For mobile demo, auto-login with mock user
        _token = 'demo_token_mobile';
        _currentUser = User(
          id: '123',
          username: 'demo',
          email: 'demo@zwesta.com',
          firstName: 'Demo',
          lastName: 'User',
          profileImage: '',
          accountType: 'Premium',
        );
      }
    } catch (e, stackTrace) {
      // Log error but don't crash
      debugPrintStack(label: 'AuthService._loadFromStorage error: $e', stackTrace: stackTrace);
      // Reset to demo user on error
      _token = 'demo_token_mobile';
      _currentUser = User(
        id: '123',
        username: 'demo',
        email: 'demo@zwesta.com',
        firstName: 'Demo',
        lastName: 'User',
        profileImage: '',
        accountType: 'Premium',
      );
    }
    notifyListeners();
  }

  // Mock login function - replace with actual API call
  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // Mock API call - replace with actual endpoint
      await Future.delayed(const Duration(seconds: 2));
      
      if (username.isEmpty || password.isEmpty) {
        throw Exception('Username and password are required');
      }

      // Mock successful login
      _token = 'mock_token_${DateTime.now().millisecondsSinceEpoch}';
      _currentUser = User(
        id: '123',
        username: username,
        email: '$username@zwesta.com',
        firstName: 'Trading',
        lastName: 'User',
        accountType: 'Premium',
      );

      // Save to storage
      await _prefs.setString('auth_token', _token!);
      await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Register function
  Future<bool> register(String username, String email, String password, 
      String firstName, String lastName) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (username.isEmpty || email.isEmpty || password.isEmpty) {
        throw Exception('All fields are required');
      }

      // Mock API call
      await Future.delayed(const Duration(seconds: 2));

      _token = 'mock_token_${DateTime.now().millisecondsSinceEpoch}';
      _currentUser = User(
        id: '${DateTime.now().millisecondsSinceEpoch}',
        username: username,
        email: email,
        firstName: firstName,
        lastName: lastName,
        accountType: 'Standard',
      );

      // Save to storage
      await _prefs.setString('auth_token', _token!);
      await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Logout function
  Future<void> logout() async {
    _token = null;
    _currentUser = null;
    await _prefs.remove('auth_token');
    await _prefs.remove('current_user');
    notifyListeners();
  }

  // Update user profile
  Future<bool> updateProfile(String firstName, String lastName, String email) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_currentUser == null) throw Exception('User not logged in');

      // Mock API call
      await Future.delayed(const Duration(seconds: 1));

      _currentUser = User(
        id: _currentUser!.id,
        username: _currentUser!.username,
        email: email,
        firstName: firstName,
        lastName: lastName,
        profileImage: _currentUser!.profileImage,
        accountType: _currentUser!.accountType,
      );

      // Save to storage
      await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Change password
  Future<bool> changePassword(String oldPassword, String newPassword) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (oldPassword.isEmpty || newPassword.isEmpty) {
        throw Exception('Both passwords are required');
      }

      // Mock API call
      await Future.delayed(const Duration(seconds: 2));

      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  // Clear error message
  void clearErrorMessage() {
    _errorMessage = null;
    notifyListeners();
  }
}
