import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class FundService with ChangeNotifier {
  final String _apiUrl = 'http://localhost:5000'; // Update to your backend URL
  String? _errorMessage;
  bool _isLoading = false;

  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;

  Future<bool> transferFunds(String fromAccount, String toAccount, double amount) async {
    _isLoading = true;
    notifyListeners();
    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/funds/transfer'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'from_account': fromAccount,
          'to_account': toAccount,
          'amount': amount,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _isLoading = false;
          notifyListeners();
          return true;
        } else {
          _errorMessage = data['error'] ?? 'Transfer failed';
        }
      } else {
        _errorMessage = 'Failed: ${response.statusCode}';
      }
    } catch (e) {
      _errorMessage = 'Error: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
    return false;
  }
}
