import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'services/auth_service.dart';
import 'services/trading_service.dart';
import 'services/bot_service.dart';
import 'services/statement_service.dart';
import 'services/financial_service.dart';
import 'utils/theme.dart';
import 'utils/environment_config.dart';

void main() async {
  // Catch any startup errors
  FlutterError.onError = (FlutterErrorDetails details) {
    debugPrintStack(
      label: 'Flutter Error',
      stackTrace: details.stack,
    );
  };

  try {
    // Don't show error widget - let Flutter handle it
    WidgetsFlutterBinding.ensureInitialized();
    final prefs = await SharedPreferences.getInstance();
    
    // Set environment based on app mode
    EnvironmentConfig.setEnvironment(
      const String.fromEnvironment('ZWESTA_ENV', defaultValue: 'production') == 'production'
          ? Environment.production
          : const String.fromEnvironment('ZWESTA_ENV') == 'staging'
              ? Environment.staging
              : Environment.development,
    );

    // Enable offline mode if specified
    const String offlineEnv = String.fromEnvironment('OFFLINE_MODE', defaultValue: 'false');
    if (offlineEnv.toLowerCase() == 'true') {
      EnvironmentConfig.setOfflineMode(true);
    }

    // Override API URL if provided
    const String apiUrlEnv = String.fromEnvironment('API_URL', defaultValue: '');
    if (apiUrlEnv.isNotEmpty) {
      EnvironmentConfig.setApiUrl(apiUrlEnv);
    }

    // Log configuration if in debug mode
    if (EnvironmentConfig.debugMode) {
      debugPrint(EnvironmentConfig.getConfigSummary());
    }
    
    runApp(MyApp(prefs: prefs));
  } catch (e, stackTrace) {
    debugPrintStack(
      label: 'Main startup error: $e',
      stackTrace: stackTrace,
    );
    rethrow;
  }
}

class MyApp extends StatelessWidget {
  final SharedPreferences prefs;

  const MyApp({Key? key, required this.prefs}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => AuthService(prefs),
        ),
        ChangeNotifierProxyProvider<AuthService, TradingService>(
          create: (context) => TradingService(null),
          update: (context, authService, previousTradingService) {
            return TradingService(authService.token);
          },
        ),
        // Lazy create - don't initialize in constructor
        ChangeNotifierProvider(
          create: (_) => BotService(),
        ),
        // Lazy create - don't initialize in constructor
        ChangeNotifierProvider(
          create: (_) => StatementService(),
        ),
        // Lazy create - don't initialize in constructor
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

