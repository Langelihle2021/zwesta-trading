import 'dart:convert';

import 'package:http/http.dart' as http;

import '../utils/environment_config.dart';

class ApiService {

  ApiService({String? apiKey}) : _apiKey = apiKey ?? _defaultApiKey {
    _baseUrl = EnvironmentConfig.apiUrl;
  }
  static const String _defaultApiKey = 'default_api_key_for_demo';

  final String? _apiKey;
  late String _baseUrl;

  Map<String, String> _getHeaders() => {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $_apiKey',
      'X-User-ID': 'default_user', // Can be updated with actual user ID
    };

  Future<Map<String, dynamic>> get(String endpoint) async {
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl$endpoint'),
        headers: _getHeaders(),
      ).timeout(const Duration(seconds: 30));

      return _handleResponse(response);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<Map<String, dynamic>> post(String endpoint, Map<String, dynamic> body) async {
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl$endpoint'),
        headers: _getHeaders(),
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      return _handleResponse(response);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<Map<String, dynamic>> put(String endpoint, Map<String, dynamic> body) async {
    try {
      final response = await http.put(
        Uri.parse('$_baseUrl$endpoint'),
        headers: _getHeaders(),
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 30));

      return _handleResponse(response);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<Map<String, dynamic>> delete(String endpoint) async {
    try {
      final response = await http.delete(
        Uri.parse('$_baseUrl$endpoint'),
        headers: _getHeaders(),
      ).timeout(const Duration(seconds: 30));

      return _handleResponse(response);
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Map<String, dynamic> _handleResponse(http.Response response) {
    try {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      return decoded;
    } catch (e) {
      return {
        'success': response.statusCode == 200,
        'status_code': response.statusCode,
        'error': 'Failed to decode response',
        'raw_body': response.body,
      };
    }
  }
}
