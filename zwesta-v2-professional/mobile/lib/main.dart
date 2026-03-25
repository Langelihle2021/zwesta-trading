import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading/config/app_config.dart';
import 'package:zwesta_trading/providers/auth_provider.dart';
import 'package:zwesta_trading/providers/trading_provider.dart';
import 'package:zwesta_trading/screens/splash_screen.dart';
import 'package:zwesta_trading/screens/login_screen.dart';
import 'package:zwesta_trading/screens/dashboard_screen.dart';
import 'package:zwesta_trading/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Load environment variables
  await dotenv.load();
  
  // Initialize Hive for local storage
  await Hive.initFlutter();
  
  runApp(const ZwestaApp());
}

class ZwestaApp extends StatelessWidget {
  const ZwestaApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider()),
        ChangeNotifierProvider<TradingProvider>(create: (_) => TradingProvider()),
      ],
      child: MaterialApp(
        title: 'Zwesta Trading',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: Consumer<AuthProvider>(
          builder: (context, authProvider, _) {
            // Show splash while checking authentication
            if (authProvider.isLoading) {
              return const SplashScreen();
            }
            
            // Navigate based on authentication state
            return authProvider.isAuthenticated
                ? const DashboardScreen()
                : const LoginScreen();
          },
        ),
        onGenerateRoute: _generateRoute,
      ),
    );
  }

  static Route<dynamic> _generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case '/login':
        return MaterialPageRoute(builder: (_) => const LoginScreen());
      case '/dashboard':
        return MaterialPageRoute(builder: (_) => const DashboardScreen());
      case '/splash':
        return MaterialPageRoute(builder: (_) => const SplashScreen());
      default:
        return MaterialPageRoute(
          builder: (_) => Scaffold(
            appBar: AppBar(title: const Text('Not Found')),
            body: const Center(child: Text('Page not found')),
          ),
        );
    }
  }
}
