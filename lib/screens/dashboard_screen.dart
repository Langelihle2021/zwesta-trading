import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../services/auth_service.dart';
import '../services/trading_service.dart';
import '../services/bot_service.dart';
import '../services/pdf_service.dart';
import '../models/account.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../widgets/custom_widgets.dart';
import '../widgets/logo_widget.dart';
import '../widgets/bot_status_indicator.dart';
import 'trades_screen.dart';
import 'account_management_screen.dart';
import 'bot_dashboard_screen.dart';
import 'bot_configuration_screen.dart';
import 'bot_analytics_screen.dart';
import 'broker_integration_screen.dart';
import 'financials_screen.dart';
import 'rentals_and_features_screen.dart';
import 'multi_account_management_screen.dart';
import 'consolidated_reports_screen.dart';
import 'referral_dashboard_screen.dart';
import 'admin_dashboard_screen.dart';
import 'multi_broker_management_screen.dart';
import 'enhanced_dashboard_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;
  List<dynamic> _activeBotsList = [];
  bool _botsLoading = true;
  String? _botsError;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _fetchActiveBots();
    _startAutoRefresh();
  }
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingService>(
      builder: (context, tradingService, _) {
        return Scaffold(
          drawer: _buildDrawerMenu(context),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Error and API status display
                if (tradingService.errorMessage != null)
                  Card(
                    color: Colors.red[100],
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(Icons.error, color: Colors.red),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              tradingService.errorMessage!,
                              style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (!tradingService.isUsingApi)
                  Card(
                    color: Colors.orange[100],
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(Icons.warning, color: Colors.orange),
                          const SizedBox(width: 8),
                          const Expanded(
                            child: Text(
                              'App is using mock data. Check API URL and backend status.',
                              style: TextStyle(color: Colors.orange, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                Consumer<AuthService>(
                  builder: (context, authService, _) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Welcome back, ${authService.currentUser?.firstName ?? 'User'}!',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Let\'s make some profits today',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    );
                  },
                ),
                // ...existing code...
                const SizedBox(height: 24),
                // Portfolio Stats
                // ...existing code...
                // Active Trading Bots Section
                _buildActiveBotsSection(),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildActiveBotsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Active Trading Bots',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (!_botsLoading)
              ElevatedButton.icon(
                onPressed: _fetchActiveBots,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        if (_botsLoading)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Column(
                  children: const [
                    CircularProgressIndicator(),
                    SizedBox(height: 12),
                    Text('Loading active bots...'),
                  ],
                ),
              ),
            ),
          )
        else if (_botsError != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Icon(Icons.error_outline, size: 40, color: Colors.red),
                  const SizedBox(height: 8),
                  Text(
                    _botsError!,
                    style: const TextStyle(color: Colors.red),
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton(
                    onPressed: _fetchActiveBots,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          )
        else if (_activeBotsList.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.smart_toy, size: 40, color: Colors.grey),
                    const SizedBox(height: 8),
                    Text(
                      'No Active Bots',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ElevatedButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const BotConfigurationScreen(),
                          ),
                        );
                      },
                      child: const Text('Create Bot'),
                    ),
                  ],
                ),
              ),
            ),
          )
        else
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _activeBotsList.length,
            itemBuilder: (context, index) {
              final bot = _activeBotsList[index];
              return Card(
                margin: const EdgeInsets.only(bottom: 12),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              bot['botId'] ?? 'Unknown Bot',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                          ),
                          BotRunningBadge(
                            isRunning: bot['enabled'] == true || bot['enabled'] == 1,
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Runtime',
                                style: TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                              Text(
                                bot['runtimeFormatted'] ?? '0h 0m',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              const Text(
                                'Daily Profit',
                                style: TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                              Text(
                                '\$${(bot['dailyProfit'] ?? 0).toStringAsFixed(2)}',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: (bot['dailyProfit'] ?? 0) >= 0
                                      ? Colors.green
                                      : Colors.red,
                                ),
                              ),
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              const Text(
                                'Trades',
                                style: TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                              Text(
                                '${bot['totalTrades'] ?? 0}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) =>
                                    BotAnalyticsScreen(bot: bot),
                              ),
                            );
                          },
                          icon: const Icon(Icons.analytics, size: 16),
                          label: const Text('View Details'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            backgroundColor: Colors.blue,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
      ],
    );
  }

  BottomNavigationBar _buildBottomNavigationBar() {
    return BottomNavigationBar(
      currentIndex: _selectedIndex,
      type: BottomNavigationBarType.fixed,
      backgroundColor: Colors.blue,
      selectedItemColor: Colors.white,
      unselectedItemColor: Colors.white70,
      elevation: 8,
      onTap: (index) {
        setState(() {
          _selectedIndex = index;
        });
      },
      items: const [
        BottomNavigationBarItem(
          icon: Icon(Icons.dashboard),
          label: 'Dashboard',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.trending_up),
          label: 'Trades',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.account_balance),
          label: 'Accounts',
        ),
        BottomNavigationBarItem(
          icon: Icon(Icons.smart_toy),
          label: 'Bots',
        ),
      ],
    );
  }

  Drawer _buildDrawerMenu() {
    return Drawer(
      child: ListView(
        children: [
          const DrawerHeader(
            decoration: BoxDecoration(
              color: Colors.blue,
            ),
            child: Text(
              'Menu',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.dashboard),
            title: const Text('Dashboard'),
            onTap: () {
              setState(() => _selectedIndex = 0);
              Navigator.pop(context);
            },
          ),
          ListTile(
            leading: const Icon(Icons.trending_up),
            title: const Text('Trades'),
            onTap: () {
              setState(() => _selectedIndex = 1);
              Navigator.pop(context);
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_balance),
            title: const Text('Accounts'),
            onTap: () {
              setState(() => _selectedIndex = 2);
              Navigator.pop(context);
            },
          ),
          ListTile(
            leading: const Icon(Icons.smart_toy),
            title: const Text('Bot Dashboard'),
            onTap: () {
              setState(() => _selectedIndex = 3);
              Navigator.pop(context);
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Bot Configuration'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (context) => const BotConfigurationScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.card_giftcard),
            title: const Text('Rentals & Features'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const RentalsAndFeaturesScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_tree),
            title: const Text('Broker Integration'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const BrokerIntegrationScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.people),
            title: const Text('Manage Accounts'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const MultiAccountManagementScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.assessment),
            title: const Text('Consolidated Reports'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const ConsolidatedReportsScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.bar_chart),
            title: const Text('Financials'),
            onTap: () {
              Navigator.pop(context);
              final tradingService = context.read<TradingService>();
              if (tradingService.primaryAccount != null) {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => FinancialsScreen(
                      account: tradingService.primaryAccount!,
                    ),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('No account available'),
                  ),
                );
              }
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.group_add),
            title: const Text('My Referrals'),
            subtitle: const Text('Invite friends & earn 5%'),
            onTap: () {
              Navigator.pop(context);
              final userId = context.read<AuthService>().currentUser?.id ?? '0';
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => ReferralDashboardScreen(userId: userId),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.admin_panel_settings),
            title: const Text('Admin Dashboard'),
            subtitle: const Text('View all users & earnings'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const AdminDashboardScreen(),
                ),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.analytics),
            title: const Text('Trading Dashboard'),
            subtitle: const Text('Your stats & performance'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const EnhancedDashboardScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.business),
            title: const Text('Multi-Broker Management'),
            subtitle: const Text('Add/remove broker credentials'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const MultiBrokerManagementScreen(),
                ),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: () {
              context.read<AuthService>().logout();
              Navigator.pop(context);
            },
          ),
        ],
      ),
    );
  }
}


