import 'package:flutter/foundation.dart';

enum Environment { development, staging, production }

class EnvironmentConfig {
  // VPS Configuration (Direct connection)
  static const String _vpsHost = '38.247.146.198';
  static const int _vpsPort = 9000;

  // Default API URLs — use HTTPS when SSL certs are deployed on VPS
  // Change to https:// once cert.pem/key.pem are placed on the VPS
  static const String _devApiUrl = 'http://38.247.146.198:9000';
  static const String _stagingApiUrl = 'http://38.247.146.198:9000';
  static const String _prodApiUrl = 'https://38.247.146.198:9000';

  static const String _devApiKey = 'your_generated_api_key_here_dev';
  static const String _stagingApiKey = 'your_generated_api_key_here_staging';
  static const String _prodApiKey = 'your_generated_api_key_here_prod';

  static const bool _devDebugMode = true;
  static const bool _stagingDebugMode = true;
  static const bool _prodDebugMode = false;

  static const String _devLogLevel = 'DEBUG';
  static const String _stagingLogLevel = 'INFO';
  static const String _prodLogLevel = 'ERROR';

  // Offline/Testing Mode
  static const bool _devOfflineMode = false;
  static const bool _stagingOfflineMode = false;
  static const bool _prodOfflineMode = false;

  // Override URLs from environment variables
  static String? _overrideApiUrl;
  static bool? _overrideOfflineMode;

  static Environment _currentEnvironment = kDebugMode 
      ? Environment.staging  // Use VPS in debug mode (staging = VPS IP)
      : Environment.production;

  static Environment get currentEnvironment => _currentEnvironment;

  /// Set custom API URL (useful for VPS configuration)
  static void setApiUrl(String url) {
    _overrideApiUrl = url;
  }

  /// Enable/disable offline mode (uses mock data)
  static void setOfflineMode(bool enabled) {
    _overrideOfflineMode = enabled;
  }

  /// Set environment dynamically
  static void setEnvironment(Environment env) {
    _currentEnvironment = env;
  }

  static String get apiUrl {
    // Check for override first
    if (_overrideApiUrl != null && _overrideApiUrl!.isNotEmpty) {
      return _overrideApiUrl!;
    }

    // Get from environment variable
    const String envVar = String.fromEnvironment('API_URL', defaultValue: '');
    if (envVar.isNotEmpty) {
      return envVar;
    }

    // Fall back to default based on environment
    switch (_currentEnvironment) {
      case Environment.development:
        return _devApiUrl;
      case Environment.staging:
        return _stagingApiUrl;
      case Environment.production:
        return _prodApiUrl;
    }
  }

  static String get apiKey {
    // Get from environment variable first
    const String envVar = String.fromEnvironment('API_KEY', defaultValue: '');
    if (envVar.isNotEmpty) {
      return envVar;
    }

    switch (_currentEnvironment) {
      case Environment.development:
        return _devApiKey;
      case Environment.staging:
        return _stagingApiKey;
      case Environment.production:
        return _prodApiKey;
    }
  }

  static bool get offlineMode {
    // Check override first
    if (_overrideOfflineMode != null) {
      return _overrideOfflineMode!;
    }

    // Check environment variable
    const String envVar = String.fromEnvironment('OFFLINE_MODE', defaultValue: 'false');
    if (envVar.toLowerCase() == 'true') {
      return true;
    }

    switch (_currentEnvironment) {
      case Environment.development:
        return _devOfflineMode;
      case Environment.staging:
        return _stagingOfflineMode;
      case Environment.production:
        return _prodOfflineMode;
    }
  }

  static bool get debugMode {
    switch (_currentEnvironment) {
      case Environment.development:
        return _devDebugMode;
      case Environment.staging:
        return _stagingDebugMode;
      case Environment.production:
        return _prodDebugMode;
    }
  }

  static String get logLevel {
    switch (_currentEnvironment) {
      case Environment.development:
        return _devLogLevel;
      case Environment.staging:
        return _stagingLogLevel;
      case Environment.production:
        return _prodLogLevel;
    }
  }

  static String get environmentName {
    switch (_currentEnvironment) {
      case Environment.development:
        return 'Development';
      case Environment.staging:
        return 'Staging';
      case Environment.production:
        return 'Production';
    }
  }

  // VPS Configuration
  static const String appName = 'Zwesta Trading System';
  static const String appVersion = '1.0.0';
  static const String buildNumber = '1';
  
  // Feature flags for VPS deployment
  static const bool enableOfflineMode = true;
  static const bool enableDataEncryption = true;
  static const bool enableAutoBackup = true;
  static const bool enablePdfExport = true;
  static const bool enableMultiAccount = true;
  static const bool enableBotTrading = true;
  static const bool enableAdvancedCharts = true;

  // Request timeouts (in seconds)
  static const int connectionTimeout = 30;
  static const int receiveTimeout = 30;

  // Retry configuration
  static const int maxRetries = 3;
  static const int retryDelayMs = 1000;

  static Map<String, String> getHeaders() {
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${EnvironmentConfig.apiKey}',
      'Accept': 'application/json',
    };
  }

  /// Get current configuration summary for debugging
  static String getConfigSummary() {
    return '''
=== Zwesta Trading System Configuration ===
Environment: $environmentName
API URL: $apiUrl
Offline Mode: $offlineMode
Debug Mode: $debugMode
Log Level: $logLevel
App Version: $appVersion
==========================================
''';
  }
}
