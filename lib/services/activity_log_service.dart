import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/environment_config.dart';

class ActivityLogEntry {
  final String title;
  final String description;
  final String timestamp;

  ActivityLogEntry({required this.title, required this.description, required this.timestamp});

  factory ActivityLogEntry.fromJson(Map<String, dynamic> json) => ActivityLogEntry(
        title: json['title'] ?? '',
        description: json['description'] ?? '',
        timestamp: json['timestamp'] ?? '',
      );
}

class ActivityLogService {
  static const _cacheKey = 'activity_log_cache';

  static Future<List<ActivityLogEntry>> fetchLogs(context) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/activity-log'),
        headers: {
          'Content-Type': 'application/json',
          if (sessionToken != null && sessionToken.isNotEmpty)
            'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final logs = (data['logs'] as List?)?.map((e) => ActivityLogEntry.fromJson(e)).toList() ?? [];
        await prefs.setString(_cacheKey, jsonEncode(data['logs']));
        return logs;
      } else {
        // fallback to cache
        final cached = prefs.getString(_cacheKey);
        if (cached != null) {
          final logs = (jsonDecode(cached) as List).map((e) => ActivityLogEntry.fromJson(e)).toList();
          return logs;
        }
        throw Exception('Failed to fetch logs');
      }
    } catch (_) {
      // fallback to cache
      final prefs = await SharedPreferences.getInstance();
      final cached = prefs.getString(_cacheKey);
      if (cached != null) {
        final logs = (jsonDecode(cached) as List).map((e) => ActivityLogEntry.fromJson(e)).toList();
        return logs;
      }
      rethrow;
    }
  }
}
