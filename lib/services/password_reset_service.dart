import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../utils/environment_config.dart';

class PasswordResetService extends ChangeNotifier {

  PasswordResetService() {
    _apiUrl = EnvironmentConfig.apiUrl;
  }
  String? _apiUrl;
  bool _isLoading = false;
  String? _errorMessage;
  String? _successMessage;
  
  // OTP state
  String? _otpSent;
  String? _resetEmail;
  int _otpAttempts = 0;
  final int _maxOtpAttempts = 3;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String? get successMessage => _successMessage;
  bool get isOtpSent => _otpSent != null;
  String? get resetEmail => _resetEmail;

  /// Request password reset - sends OTP via email or WhatsApp
  Future<bool> requestPasswordReset({
    required String email,
    required String method, // 'email' or 'whatsapp'
  }) async {
    _isLoading = true;
    _errorMessage = null;
    _successMessage = null;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/auth/password-reset/request'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'method': method, // 'email' or 'whatsapp'
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _otpSent = data['otpToken'] ?? 'sent';
          _resetEmail = email;
          _otpAttempts = 0;
          _successMessage = 'OTP sent to $method. Please check your ${method == 'email' ? 'email' : 'WhatsApp'}.';
          print('OTP sent successfully via $method');
          _isLoading = false;
          notifyListeners();
          return true;
        }
      }
      _errorMessage = 'Failed to send OTP. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'Error: $e';
      _isLoading = false;
      notifyListeners();
      print('Password reset request error: $e');
      return false;
    }
  }

  /// Verify OTP code
  Future<bool> verifyOtp({required String otp}) async {
    if (_otpAttempts >= _maxOtpAttempts) {
      _errorMessage = 'Too many OTP attempts. Please request a new OTP.';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/auth/password-reset/verify-otp'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': _resetEmail,
          'otpToken': _otpSent,
          'otp': otp,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _otpAttempts = 0;
          _successMessage = 'OTP verified. You can now reset your password.';
          _isLoading = false;
          notifyListeners();
          return true;
        }
      }

      _otpAttempts++;
      _errorMessage = 'Invalid OTP. Attempts remaining: ${_maxOtpAttempts - _otpAttempts}';
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'Error verifying OTP: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Reset password with new password
  Future<bool> resetPassword({required String newPassword}) async {
    if (!isOtpSent) {
      _errorMessage = 'Please verify OTP first';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/auth/password-reset/confirm'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': _resetEmail,
          'otpToken': _otpSent,
          'newPassword': newPassword,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _successMessage = 'Password reset successfully. Please login with your new password.';
          _otpSent = null;
          _resetEmail = null;
          _isLoading = false;
          notifyListeners();
          return true;
        }
      }

      _errorMessage = 'Failed to reset password. Please try again.';
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _errorMessage = 'Error resetting password: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Cancel password reset
  void cancelReset() {
    _otpSent = null;
    _resetEmail = null;
    _otpAttempts = 0;
    _errorMessage = null;
    _successMessage = null;
    notifyListeners();
  }
}
