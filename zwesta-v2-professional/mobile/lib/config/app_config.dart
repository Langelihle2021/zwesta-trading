import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  // API Configuration
  static String get apiBaseUrl => dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000/api';
  static String get apiTimeout => dotenv.env['API_TIMEOUT'] ?? '30';
  
  // MT5 Configuration
  static String get mt5Account => dotenv.env['MT5_ACCOUNT'] ?? '136372035';
  static String get mt5Server => dotenv.env['MT5_SERVER'] ?? 'MetaQuotes-Demo';
  
  // Trading Configuration
  static double get positionSizePercent => 
    double.parse(dotenv.env['POSITION_SIZE_PERCENT'] ?? '2.0');
  static int get stopLossPoints => 
    int.parse(dotenv.env['STOP_LOSS_POINTS'] ?? '50');
  static double get takeProfitPercent => 
    double.parse(dotenv.env['TAKE_PROFIT_PERCENT'] ?? '1.5');
  static int get consecutiveLossLimit => 
    int.parse(dotenv.env['CONSECUTIVE_LOSS_LIMIT'] ?? '3');
  static double get dailyLossLimit => 
    double.parse(dotenv.env['DAILY_LOSS_LIMIT'] ?? '500');
  
  // App Configuration
  static String get appName => 'Zwesta Trading';
  static String get appVersion => '1.0.0';
  static String get timezone => dotenv.env['TIMEZONE'] ?? 'Africa/Johannesburg';
  
  // Demo Credentials
  static String get demoUsername => 'demo';
  static String get demoPassword => 'demo';
}
