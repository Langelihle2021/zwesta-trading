import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';

class AuthService extends ChangeNotifier {
  late SharedPreferences _prefs;
  
  User? _currentUser;
  String? _token;
  bool _isLoading = false;
  String? _errorMessage;
  bool _isInitialized = false;

  AuthService() {
    // Start with no user - show login page
    _token = null;
    _currentUser = null;
    
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
      }
      // If no saved token, stay logged out (show login page)
    } catch (e, stackTrace) {
      // Log error but don't auto-login
      debugPrintStack(label: 'AuthService._loadFromStorage error: $e', stackTrace: stackTrace);
      _token = null;
      _currentUser = null;
    }
    notifyListeners();
  }

  // Mock login function - replace with actual API call
  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (username.isEmpty || password.isEmpty) {
        throw Exception('Username and password are required');
      }

      // Call real backend login API
      // The backend login endpoint accepts email (username is email)
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': username, // Backend expects email
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        if (data['success'] == true) {
          _token = data['session_token']; // Get real session token from backend
          _currentUser = User(
            id: data['user_id'] ?? '0',
            username: username,
            email: data['email'] ?? '$username@zwesta.com',
            firstName: data['name']?.split(' ')[0] ?? 'Trading',
            lastName: data['name']?.split(' ').length > 1 ? data['name'].split(' ')[1] : 'User',
            accountType: 'Premium',
          );

          // Save to storage - use the REAL session token from backend
          await _prefs.setString('auth_token', _token!);
          await _prefs.setString('user_id', data['user_id'] ?? '');
          await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

          _isLoading = false;
          notifyListeners();
          return true;
        } else {
          throw Exception(data['error'] ?? 'Login failed');
        }
      } else {
        final data = jsonDecode(response.body);
        throw Exception(data['error'] ?? 'Login failed with code ${response.statusCode}');
      }
    } catch (e) {
      _errorMessage = 'Login Error: ${e.toString()}';
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

      // Call real backend API
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'name': '$firstName $lastName',
          'email': email,
          'username': username,
          'password': password,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        _token = 'session_token_${DateTime.now().millisecondsSinceEpoch}';
        _currentUser = User(
          id: data['user_id'] ?? '${DateTime.now().millisecondsSinceEpoch}',
          username: username,
          email: email,
          firstName: firstName,
          lastName: lastName,
          accountType: 'Standard',
        );

        // Save referral code to preferences for display on dashboard
        final referralCode = data['referral_code'] ?? '';
        await _prefs.setString('referral_code', referralCode);
        await _prefs.setString('user_id', _currentUser!.id);

        // Save to storage
        await _prefs.setString('auth_token', _token!);
        await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

        _isLoading = false;
        _errorMessage = 'Registration successful! Your referral code: $referralCode';
        notifyListeners();
        return true;
      } else {
        final data = jsonDecode(response.body);
        throw Exception(data['error'] ?? 'Registration failed');
      }
    } catch (e) {
      _errorMessage = 'Registration Error: ${e.toString()}';
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
