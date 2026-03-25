import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';
import 'package:zwesta_trading_temp/services/auth_service.dart';
import 'package:zwesta_trading_temp/themes/app_colors.dart';
import 'package:zwesta_trading_temp/themes/app_theme.dart';
import 'package:zwesta_trading_temp/screens/splash_screen.dart';
import 'package:zwesta_trading_temp/screens/login_screen.dart';
import 'package:zwesta_trading_temp/screens/dashboard_screen.dart';
import 'package:zwesta_trading_temp/screens/positions_screen.dart';
import 'package:zwesta_trading_temp/screens/trades_screen.dart';
import 'package:zwesta_trading_temp/screens/settings_screen.dart';
import 'package:zwesta_trading_temp/screens/profile_screen.dart';
import 'package:zwesta_trading_temp/screens/withdrawals_screen.dart';
import 'package:zwesta_trading_temp/screens/deposits_screen.dart';
import 'package:zwesta_trading_temp/screens/markets_screen.dart';

void main() {
  runApp(const ZwestaTrading());
}

class ZwestaTrading extends StatelessWidget {
  const ZwestaTrading({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
        ChangeNotifierProvider<AuthService>(
          create: (context) => AuthService(
            apiService: context.read<ApiService>(),
          ),
        ),
      ],
      child: MaterialApp(
        title: 'Zwesta Trading',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.dark,
        debugShowCheckedModeBanner: false,
        home: Consumer<AuthService>(
          builder: (context, authService, _) {
            if (authService.isInitializing) {
              return const SplashScreen();
            }
            return authService.isLoggedIn
                ? const DashboardScreen()
                : const LoginScreen();
          },
        ),
        routes: {
          '/': (context) => Consumer<AuthService>(
            builder: (context, authService, _) {
              if (authService.isInitializing) {
                return const SplashScreen();
              }
              return authService.isLoggedIn
                  ? const DashboardScreen()
                  : const LoginScreen();
            },
          ),
          '/dashboard': (context) => const DashboardScreen(),
          '/settings': (context) => const SettingsScreen(),
          '/profile': (context) => const ProfileScreen(),
          '/markets': (context) => const MarketsScreen(),
        },
        onGenerateRoute: (settings) {
          if (settings.name?.startsWith('/positions/') ?? false) {
            final accountId = settings.name!.replaceFirst('/positions/', '');
            return MaterialPageRoute(
              builder: (context) => PositionsScreen(accountId: accountId),
            );
          } else if (settings.name?.startsWith('/trades/') ?? false) {
            final accountId = settings.name!.replaceFirst('/trades/', '');
            return MaterialPageRoute(
              builder: (context) => TradesScreen(accountId: accountId),
            );
          } else if (settings.name?.startsWith('/withdrawals/') ?? false) {
            final accountId = settings.name!.replaceFirst('/withdrawals/', '');
            return MaterialPageRoute(
              builder: (context) => WithdrawalsScreen(accountId: accountId),
            );
          } else if (settings.name?.startsWith('/deposits/') ?? false) {
            final accountId = settings.name!.replaceFirst('/deposits/', '');
            return MaterialPageRoute(
              builder: (context) => DepositsScreen(accountId: accountId),
            );
          }
          return null;
        },
      ),
    );
  }
}
