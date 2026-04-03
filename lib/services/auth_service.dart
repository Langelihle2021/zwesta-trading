import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/user.dart';
import '../utils/environment_config.dart';

class AuthService extends ChangeNotifier {

  AuthService() {
    _token = null;
    _currentUser = null;
    _initializePreferences();
  }
    // Clear error message and notify listeners
    void clearError() {
      _errorMessage = null;
      _successMessage = null;
      notifyListeners();
    }
  late SharedPreferences _prefs;
  
  User? _currentUser;
  String? _token;
  bool _isLoading = false;
  String? _errorMessage;
  String? _successMessage;

  Future<void> _initializePreferences() async {
    try {
      _prefs = await SharedPreferences.getInstance();
      _loadFromStorage();
      notifyListeners();
    } catch (e) {
      debugPrint('SharedPreferences initialization error: $e');
      notifyListeners();
    }
  }

  User? get currentUser => _currentUser;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String? get successMessage => _successMessage;
  bool get isAuthenticated => _token != null && _currentUser != null;

  void _loadFromStorage() {
    try {
      final tokenJson = _prefs.getString('auth_token');
      final userJson = _prefs.getString('current_user');
      
      if (tokenJson != null && userJson != null) {
        _token = tokenJson;
        _currentUser = User.fromJson(jsonDecode(userJson));
      }
    } catch (e) {
      debugPrint('AuthService._loadFromStorage error: $e');
      _token = null;
      _currentUser = null;
    }
    notifyListeners();
  }

  // Pending 2FA temp token (set during login when 2FA required)
  String? _pending2faToken;
  String? get pending2faToken => _pending2faToken;

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    _pending2faToken = null;
    notifyListeners();

    try {
      if (username.isEmpty || password.isEmpty) {
        throw Exception('Username and password are required');
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': username, 'password': password}),
      ).timeout(const Duration(seconds: 30));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        if (data['success'] == true) {
          // Check if 2FA is required
          if (data['requires_2fa'] == true) {
            _pending2faToken = data['temp_token'];
            _isLoading = false;
            notifyListeners();
            return true; // Caller checks pending2faToken to know 2FA is needed
          }

          _token = data['session_token'];
          _currentUser = User(
            id: data['user_id'] ?? '0',
            username: username,
            email: data['email'] ?? '$username@zwesta.com',
            firstName: data['name']?.split(' ')[0] ?? 'Trading',
            lastName: data['name']?.split(' ').length > 1 ? data['name'].split(' ')[1] : 'User',
            accountType: 'Premium',
          );

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

  // 2FA/MFA verification
  Future<bool> verifyMfaCode(String? tempToken, String code) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/verify-2fa'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'temp_token': tempToken, 'code': code}),
      ).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _token = data['session_token'];
          _currentUser = User(
            id: data['user_id'] ?? '0',
            username: data['email'] ?? '',
            email: data['email'] ?? '',
            firstName: data['name']?.split(' ')[0] ?? 'Trading',
            lastName: data['name']?.split(' ').length > 1 ? data['name'].split(' ')[1] : 'User',
            accountType: 'Premium',
          );
          await _prefs.setString('auth_token', _token!);
          await _prefs.setString('user_id', data['user_id'] ?? '');
          await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));
          _isLoading = false;
          notifyListeners();
          return true;
        } else {
          throw Exception(data['error'] ?? '2FA verification failed');
        }
      } else {
        final data = jsonDecode(response.body);
        throw Exception(data['error'] ?? '2FA failed with code ${response.statusCode}');
      }
    } catch (e) {
      _errorMessage = '2FA Error: ${e.toString()}';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> resendMfaCode(String? tempToken) async {
    try {
      await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/resend-2fa'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'temp_token': tempToken}),
      ).timeout(const Duration(seconds: 10));
    } catch (_) {}
  }

  // Register function
  Future<bool> register(String username, String email, String password, 
      String firstName, String lastName, {String referralCode = ''}) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (username.isEmpty || email.isEmpty || password.isEmpty) {
        throw Exception('All fields are required');
      }

      final body = {
        'name': '$firstName $lastName',
        'email': email,
        'username': username,
        'password': password,
      };
      if (referralCode.isNotEmpty) {
        body['referrer_code'] = referralCode;
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        
        _token = data['session_token'] ?? 'session_token_${DateTime.now().millisecondsSinceEpoch}';
        _currentUser = User(
          id: data['user_id'] ?? '${DateTime.now().millisecondsSinceEpoch}',
          username: username,
          email: email,
          firstName: firstName,
          lastName: lastName,
          accountType: 'Standard',
        );

        final referralCode = data['referral_code'] ?? '';
        await _prefs.setString('referral_code', referralCode);
        await _prefs.setString('user_id', _currentUser!.id);
        await _prefs.setString('auth_token', _token!);
        await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));

        _isLoading = false;
        _errorMessage = null;
        _successMessage = 'Registration successful! Your referral code: $referralCode';
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
    await _prefs.remove('user_id');
    await _prefs.remove('mt5_account');
    await _prefs.remove('mt5_server');
    await _prefs.remove('active_bots');
    await _prefs.remove('last_bot_sync');
    debugPrint('✅ Session cleared');
    notifyListeners();
  }

  // Update user profile
  Future<bool> updateProfile(String firstName, String lastName, String email) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_currentUser == null || _token == null) throw Exception('User not logged in');

      final response = await http.put(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/update-profile'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': _token!,
        },
        body: jsonEncode({
          'name': '$firstName $lastName',
          'email': email,
        }),
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 && data['success'] == true) {
        _currentUser = User(
          id: _currentUser!.id,
          username: _currentUser!.username,
          email: email,
          firstName: firstName,
          lastName: lastName,
          profileImage: _currentUser!.profileImage,
          accountType: _currentUser!.accountType,
        );
        await _prefs.setString('current_user', jsonEncode(_currentUser!.toJson()));
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        throw Exception(data['error'] ?? 'Profile update failed');
      }
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
      if (_token == null) throw Exception('User not logged in');
      if (oldPassword.isEmpty || newPassword.isEmpty) {
        throw Exception('Both passwords are required');
      }
      if (newPassword.length < 6) {
        throw Exception('New password must be at least 6 characters');
      }

      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/change-password'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': _token!,
        },
        body: jsonEncode({
          'old_password': oldPassword,
          'new_password': newPassword,
        }),
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 && data['success'] == true) {
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        throw Exception(data['error'] ?? 'Password change failed');
      }
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
