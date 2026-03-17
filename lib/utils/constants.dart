import 'package:flutter/material.dart';

class AppColors {
  // Primary colors
  static const Color primaryColor = Color(0xFF1E88E5);
  static const Color primaryDark = Color(0xFF1565C0);
  static const Color primaryLight = Color(0xFF64B5F6);

  // Secondary colors
  static const Color accentColor = Color(0xFFFF6B6B);
  static const Color successColor = Color(0xFF4CAF50);
  static const Color warningColor = Color(0xFFFFC107);
  static const Color dangerColor = Color(0xFFF44336);

  // Neutral colors
  static const Color dark = Color(0xFF1F1F1F);
  static const Color darkGrey = Color(0xFF424242);
  static const Color grey = Color(0xFF757575);
  static const Color lightGrey = Color(0xFFBDBDBD);
  static const Color veryLightGrey = Color(0xFFE0E0E0);
  static const Color white = Color(0xFFFFFFFF);

  // Chart colors
  static const Color buyColor = Color(0xFF4CAF50);
  static const Color sellColor = Color(0xFFF44336);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF1E88E5),
      Color(0xFF1565C0),
    ],
  );

  static const LinearGradient successGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF4CAF50),
      Color(0xFF388E3C),
    ],
  );

  static const LinearGradient dangerGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFF44336),
      Color(0xFFC62828),
    ],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFFF6B6B),
      Color(0xFFE63946),
    ],
  );
}

class AppSpacing {
  static const double xs = 4.0;
  static const double sm = 8.0;
  static const double md = 16.0;
  static const double lg = 24.0;
  static const double xl = 32.0;
}

class AppConstants {
  static const String appName = 'Zwesta Trading System';
  static const String apiBaseUrl = 'https://api.zwesta-trading.com';
  static const Duration connectionTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);

  // ==================== EXNESS MT5 TRADING DEFAULTS ====================
  /// Default Take Profit percentage for Exness MT5 trades
  static const double exnessDefaultTakeProfitPercentage = 2.0;

  /// Default Stop Loss percentage for Exness MT5 trades
  static const double exnessDefaultStopLossPercentage = 1.0;

  /// Minimum Take Profit percentage
  static const double minTakeProfitPercentage = 0.5;

  /// Maximum Take Profit percentage
  static const double maxTakeProfitPercentage = 10.0;

  /// Minimum Stop Loss percentage
  static const double minStopLossPercentage = 0.1;

  /// Maximum Stop Loss percentage
  static const double maxStopLossPercentage = 5.0;
}
