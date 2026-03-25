import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/credential_manager.dart';
import 'services/bot_service.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/help_contact_screen.dart';
import 'screens/bot_dashboard_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ZwestaTraderApp());
}

class ZwestaTraderApp extends StatelessWidget {
  const ZwestaTraderApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => CredentialManager()..initialize(),
        ),
        ChangeNotifierProvider(
          create: (_) => BotService(),
        ),
      ],
      child: MaterialApp(
        title: 'Zwesta Trading',
        theme: ThemeData(
          brightness: Brightness.dark,
          useMaterial3: true,
          colorScheme: ColorScheme.dark(
            primary: Colors.cyan,
            secondary: Colors.cyanAccent,
            surface: const Color(0xFF121212),
          ),
          scaffoldBackgroundColor: const Color(0xFF121212),
        ),
        home: Consumer<CredentialManager>(
          builder: (context, credentialManager, _) {
            if (credentialManager.currentUser == null) {
              return const LoginScreen();
            }
            return const DashboardScreen();
          },
        ),
        onGenerateRoute: (settings) {
          if (settings.name == '/help') {
            return MaterialPageRoute(
              builder: (context) => const HelpContactScreen(),
              settings: settings,
            );
          }
          if (settings.name?.startsWith('/bot-dashboard') ?? false) {
            final args = settings.arguments as Map<String, dynamic>;
            return MaterialPageRoute(
              builder: (context) => BotDashboardScreen(
                accountId: args['accountId'],
                accountBalance: args['accountBalance'],
              ),
              settings: settings,
            );
          }
          return null;
        },
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
