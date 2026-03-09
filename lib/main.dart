import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'services/auth_service.dart';
import 'services/trading_service.dart';
import 'services/bot_service.dart';
import 'services/statement_service.dart';
import 'services/financial_service.dart';
import 'utils/theme.dart';
import 'utils/environment_config.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Set environment based on build mode
  // Release/Production builds use VPS, Debug uses localhost
  try {
    if (kReleaseMode) {
      // Production: Use VPS IP
      EnvironmentConfig.setEnvironment(Environment.production);
    } else {
      // Debug: Check environment variable or default to development
      const String envMode = String.fromEnvironment('ZWESTA_ENV', defaultValue: 'development');
      EnvironmentConfig.setEnvironment(
        envMode == 'staging'
            ? Environment.staging
            : Environment.development,
      );
    }
  } catch (_) {
    // Fallback: Production mode
    EnvironmentConfig.setEnvironment(Environment.production);
  }

  // Debug build - ready for testing
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => AuthService(),
        ),
        ChangeNotifierProxyProvider<AuthService, TradingService>(
          create: (context) => TradingService(null),
          update: (context, authService, tradingService) {
            tradingService?.updateToken(authService.token);
            return tradingService ?? TradingService(authService.token);
          },
        ),
        ChangeNotifierProvider(
          create: (_) => BotService(),
        ),
        ChangeNotifierProvider(
          create: (_) => StatementService(),
        ),
        ChangeNotifierProvider(
          create: (_) => FinancialService(),
        ),
      ],
      child: MaterialApp(
        title: 'Zwesta Trading System',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const AuthWrapper(),
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthService>(
      builder: (context, authService, _) {
        if (authService.isAuthenticated) {
          return const DashboardScreen();
        }
        return const LoginScreen();
      },
    );
  }
}


