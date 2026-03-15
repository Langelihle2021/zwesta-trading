import 'services/notification_service.dart';
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
import 'services/ig_auto_connect_service.dart';
import 'providers/currency_provider.dart';
import 'providers/fallback_status_provider.dart';
import 'utils/theme.dart';
import 'utils/environment_config.dart';
import 'l10n/app_localizations.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    // Set environment based on build mode
    // Release/Production builds use VPS, Debug uses localhost
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
    runApp(const MyApp());
  } catch (e, st) {
    print('Main init error: $e\n$st');
    runApp(MaterialApp(
      home: Scaffold(
        backgroundColor: Colors.red.shade50,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, color: Colors.red, size: 64),
              SizedBox(height: 16),
              Text(
                'App failed to start',
                style: TextStyle(fontSize: 20, color: Colors.red, fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 8),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 24),
                child: Text(
                  e.toString(),
                  style: TextStyle(color: Colors.black87),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
        ),
      ),
    ));
    }
  }

  class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    try {
      return MultiProvider(
        providers: [
          ChangeNotifierProvider(
            create: (_) => CurrencyProvider()..loadCurrency(),
          ),
          ChangeNotifierProvider(
            create: (_) => AuthService(),
          ),
          ChangeNotifierProvider(
            create: (_) => FallbackStatusProvider(),
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
          ChangeNotifierProvider(
            create: (_) => IGAutoConnectService()..autoConnect(),
          ),
        ],
        child: MaterialApp(
          title: 'ZWESTA TRADING SYSTEM',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: ThemeMode.system,
          home: const AuthWrapper(),
          debugShowCheckedModeBanner: false,
          supportedLocales: const [
            Locale('en'),
            Locale('xh'),
            Locale('zu'),
            Locale('nr'),
            Locale('ve'),
            Locale('af'),
          ],
          localizationsDelegates: [
            AppLocalizations.delegate,
            DefaultWidgetsLocalizations.delegate,
            DefaultMaterialLocalizations.delegate,
          ],
          localeResolutionCallback: (locale, supportedLocales) {
            if (locale == null) return supportedLocales.first;
            for (var supportedLocale in supportedLocales) {
              if (supportedLocale.languageCode == locale.languageCode) {
                return supportedLocale;
              }
            }
            return supportedLocales.first;
          },
        ),
      );
    } catch (e, st) {
      print('MyApp build error: $e\n$st');
      return MaterialApp(
        home: Scaffold(body: Center(child: Text('App error: $e'))),
      );
    }
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    try {
      return Consumer<AuthService>(
        builder: (context, authService, _) {
          if (authService.isAuthenticated) {
            return const DashboardScreen();
          }
          return const LoginScreen();
        },
      );
    } catch (e, st) {
      print('AuthWrapper build error: $e\n$st');
      return Scaffold(
        body: Center(child: Text('Auth error: $e')),
      );
    }
  }
}


