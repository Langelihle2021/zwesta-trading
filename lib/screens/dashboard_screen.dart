import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
// import 'package:fl_chart/fl_chart.dart'; // Disabled for compatibility
import '../l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import '../services/auth_service.dart';
import '../services/trading_service.dart';
import '../services/bot_service.dart';
import '../services/pdf_service.dart';
import '../providers/fallback_status_provider.dart';
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
  List<dynamic> _realBotsList = [];
  bool _botsLoading = true;
  String? _botsError;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _fetchRealBots();
    _startAutoRefresh();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  /// Fetch real bots from BotService and filter out demo bots
  void _fetchRealBots() {
    setState(() {
      _botsLoading = true;
      _botsError = null;
    });

    try {
      final botService = context.read<BotService>();
      
      // Fetch bots from backend via BotService
      botService.fetchActiveBots().then((_) {
        if (mounted) {
          setState(() {
            // Filter out demo bots (botId starts with 'DemoBot_' or 'demo')
            _realBotsList = botService.activeBots
                .where((bot) {
                  final botId = (bot['botId'] ?? '').toString().toLowerCase();
                  return !botId.startsWith('demobot_') && !botId.startsWith('demo_');
                })
                .toList();
            
            _botsError = botService.errorMessage;
            _botsLoading = false;
            
            print('✅ Loaded ${_realBotsList.length} real bots (filtered demo bots)');
          });
        }
      }).catchError((e) {
        if (mounted) {
          setState(() {
            _botsError = 'Error fetching bots: $e';
            _realBotsList = [];
            _botsLoading = false;
          });
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _botsError = 'Error loading bots: $e';
          _realBotsList = [];
          _botsLoading = false;
        });
      }
    }
  }

  void _startAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
      if (mounted) {
        _fetchRealBots();
      }
    });
  }

  /// Get the current screen based on selected index
  Widget _getScreenForIndex(int index) {
    switch (index) {
      case 0:
        return _buildDashboardTab();
      case 1:
        return const TradesScreen();
      case 2:
        return const AccountManagementScreen();
      case 3:
        return const BotDashboardScreen();
      default:
        return _buildDashboardTab();
    }
  }

  /// Build the dashboard tab (home screen)
  /// Build the dashboard tab - Modern layout
  Widget _buildDashboardTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Welcome Section
          _buildWelcomeSection(),
          const SizedBox(height: 24),
          
          // System Overview Card
          _buildSystemOverviewCard(),
          const SizedBox(height: 24),
          
          // Cumulative Trade Results
          _buildCumulativeResultsSection(),
          const SizedBox(height: 24),
          
          // Top 5 Performing Pairs
          _buildTopPerformingPairsSection(),
          const SizedBox(height: 24),
          
          // Recent Trades
          _buildRecentTradesSection(),
          const SizedBox(height: 24),
          
          // Portfolio Overview
          _buildPortfolioOverviewSection(),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  /// Welcome & System Overview
  Widget _buildWelcomeSection() {
    return Consumer<AuthService>(
      builder: (context, authService, _) {
        return Card(
          elevation: 4,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: LinearGradient(
                colors: [Colors.blue.shade700, Colors.blue.shade500],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Consumer<AuthService>(
                          builder: (context, authService, _) {
                            return Text(
                              'Welcome back, ${authService.currentUser?.firstName ?? 'Trader'}!',
                              style: Theme.of(context).textTheme.displayMedium?.copyWith(color: Colors.white),
                            );
                          },
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Multi-Broker Trading & Auto-Bot System',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.trending_up,
                        color: Colors.white,
                        size: 32,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Divider(color: Colors.white30),
                const SizedBox(height: 12),
                Text(
                  'About ZWESTA Trading System',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white),
                ),
                const SizedBox(height: 8),
                Text(
                  '🤖 Automated trading bots across multiple brokers (IG Markets, XM Global)\n'
                  '📊 Real-time analytics with cumulative profit tracking\n'
                  '💰 Commission system & referral rewards (5%)\n'
                  '🔄 Multi-pair support (Forex, Crypto, Commodities, Indices)\n'
                  '📈 Portfolio management with performance charts',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.white, height: 1.6, fontSize: 13),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  /// System Overview - Key Metrics
  Widget _buildSystemOverviewCard() {
    final activeBots = _realBotsList.where((bot) => bot['enabled'] == true).length;
    final totalProfit = _realBotsList.fold<double>(
      0,
      (sum, bot) => sum + (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0),
    );
    final totalTrades = _realBotsList.fold<int>(
      0,
      (sum, bot) => sum + (int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0),
    );

    return Row(
      children: [
        Expanded(
          child: _buildMetricCard(
            icon: Icons.smart_toy,
            label: 'Active Bots',
            value: '$activeBots',
            color: Colors.green,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildMetricCard(
            icon: Icons.attach_money,
            label: 'Total Profit',
            value: '\$${totalProfit.toStringAsFixed(0)}',
            color: totalProfit >= 0 ? Colors.green : Colors.red,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildMetricCard(
            icon: Icons.swap_horiz,
            label: 'Total Trades',
            value: '$totalTrades',
            color: Colors.blue,
          ),
        ),
      ],
    );
  }

  /// Metric Card Widget
  Widget _buildMetricCard({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 12),
            Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey.shade600,
                fontWeight: FontWeight.w500,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              value,
              style: Theme.of(context).textTheme.displayMedium?.copyWith(
                fontSize: 22,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Cumulative Trade Results
  Widget _buildCumulativeResultsSection() {
    final totalProfit = _realBotsList.fold<double>(
      0,
      (sum, bot) => sum + (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0),
    );
    final winningBots = _realBotsList.where((bot) => (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final totalBots = _realBotsList.length;
    final winRate = totalBots > 0 ? ((winningBots / totalBots) * 100).toStringAsFixed(1) : '0.0';

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Cumulative Trade Results',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                Column(
                  children: [
                    Text(
                      '\$${totalProfit.toStringAsFixed(2)}',
                      style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        color: totalProfit >= 0 ? Colors.green : Colors.red,
                        fontSize: 28,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Total Return',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 12, color: Colors.grey.shade600),
                    ),
                  ],
                ),
                Container(
                  width: 1,
                  height: 60,
                  color: Colors.grey.shade300,
                ),
                Column(
                  children: [
                    Text(
                      '$winRate%',
                      style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        color: Colors.blue,
                        fontSize: 28,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Win Rate',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 12, color: Colors.grey.shade600),
                    ),
                  ],
                ),
                Container(
                  width: 1,
                  height: 60,
                  color: Colors.grey.shade300,
                ),
                Column(
                  children: [
                    Text(
                      '$winningBots/$totalBots',
                      style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        color: Colors.purple,
                        fontSize: 28,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Winning Bots',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 12, color: Colors.grey.shade600),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Top 5 Performing Trading Pairs
  Widget _buildTopPerformingPairsSection() {
    // Get top 5 symbols by profit
    final symbolProfits = <String, double>{};
    for (final bot in _realBotsList) {
      final symbols = bot['symbol'] ?? 'EURUSD';
      final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
      symbolProfits[symbols] = (symbolProfits[symbols] ?? 0) + profit;
    }

    final topPairs = symbolProfits.entries
        .toList()
        ..sort((a, b) => b.value.compareTo(a.value));

    // Bar chart data
    final barSpots = topPairs.take(5).toList();
    final barColors = [Colors.blue, Colors.green, Colors.orange, Colors.red, Colors.purple];

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Top 5 Performing Pairs',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            if (barSpots.isEmpty)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Text(
                    'No trading pairs yet',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey.shade600),
                  ),
                ),
              )
            else ...[
              SizedBox(
                height: 180,
                child: Container(
                  alignment: Alignment.center,
                  color: Colors.grey[100],
                  child: const Text(
                    'Price distribution chart disabled for compatibility',
                    style: TextStyle(color: Colors.grey),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: barSpots.length,
                separatorBuilder: (_, __) => const Divider(),
                itemBuilder: (context, index) {
                  final pair = barSpots[index];
                  return Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              pair.key,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            Text(
                              '${index + 1}. Most Profitable',
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 12, color: Colors.grey.shade600),
                            ),
                          ],
                        ),
                      ),
                      Text(
                        '\$${pair.value.toStringAsFixed(2)}',
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: pair.value >= 0 ? Colors.green : Colors.red,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  );
                },
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Recent Trades Section
  Widget _buildRecentTradesSection() {
    final allTrades = <Map<String, dynamic>>[];
    for (final bot in _realBotsList) {
      final trades = bot['tradeHistory'] ?? [];
      if (trades is List) {
        allTrades.addAll(trades.cast<Map<String, dynamic>>());
      }
    }
    
    allTrades.sort((a, b) {
      final timeA = DateTime.tryParse(a['time']?.toString() ?? '') ?? DateTime.now();
      final timeB = DateTime.tryParse(b['time']?.toString() ?? '') ?? DateTime.now();
      return timeB.compareTo(timeA);
    });

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Recent Trades',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            allTrades.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text(
                        'No recent trades',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey.shade600),
                      ),
                    ),
                  )
                : ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: allTrades.take(5).length,
                    separatorBuilder: (_, __) => const Divider(),
                    itemBuilder: (context, index) {
                      final trade = allTrades[index];
                      final profit = double.tryParse(trade['profit']?.toString() ?? '0') ?? 0;
                      return Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${trade['symbol'] ?? 'EURUSD'} - ${trade['direction'] ?? 'BUY'}',
                                  style: Theme.of(context).textTheme.titleMedium,
                                ),
                                Text(
                                  trade['time']?.toString().split('.')[0] ?? 'N/A',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontSize: 12, color: Colors.grey.shade600),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            '\$${profit.toStringAsFixed(2)}',
                            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: profit >= 0 ? Colors.green : Colors.red,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
          ],
        ),
      ),
    );
  }

  /// Portfolio Overview
  Widget _buildPortfolioOverviewSection() {
    final activeBots = _realBotsList.where((bot) => bot['enabled'] == true).length;
    final totalProfit = _realBotsList.fold<double>(
      0,
      (sum, bot) => sum + (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0),
    );

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Portfolio Overview',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 20),
            SizedBox(
              height: 200,
              child: activeBots > 0
                  ? Container(
                      alignment: Alignment.center,
                      color: Colors.grey[100],
                      child: const Text(
                        'Portfolio overview chart disabled for compatibility',
                        style: TextStyle(color: Colors.grey),
                      ),
                    )
                  : Center(
                      child: Text(
                        'No active bots to display',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey.shade600),
                      ),
                    ),
            ),
            const SizedBox(height: 16),
            Center(
              child: ElevatedButton.icon(
                onPressed: () => setState(() => _selectedIndex = 3),
                icon: const Icon(Icons.smart_toy),
                label: const Text('Create New Bot'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Scaffold(
      drawer: _buildDrawerMenu(loc),
      appBar: AppBar(
        title: Text(loc.translate('dashboard_title')),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchRealBots,
            tooltip: loc.translate('refresh_bots'),
          ),
        ],
      ),
      body: Column(
        children: [
          Consumer<FallbackStatusProvider>(
            builder: (context, fallback, _) {
              if (fallback.usingFallback) {
                return MaterialBanner(
                  content: Text(
                    fallback.fallbackReason ?? loc.translate('You are viewing cached or mock data. Some features may be limited.'),
                    style: const TextStyle(color: Colors.black),
                  ),
                  backgroundColor: Colors.amber.shade200,
                  actions: [
                    TextButton(
                      onPressed: () => fallback.clearFallback(),
                      child: const Text('DISMISS'),
                    ),
                  ],
                );
              }
              return const SizedBox.shrink();
            },
          ),
          Expanded(child: _getScreenForIndex(_selectedIndex)),
        ],
      ),
      bottomNavigationBar: _buildBottomNavigationBar(loc),
    );
  }

  BottomNavigationBar _buildBottomNavigationBar(AppLocalizations loc) {
    return BottomNavigationBar(
      currentIndex: _selectedIndex,
      type: BottomNavigationBarType.fixed,
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard), label: 'Dashboard'),
        BottomNavigationBarItem(icon: Icon(Icons.swap_horiz), label: 'Trades'),
        BottomNavigationBarItem(icon: Icon(Icons.account_circle), label: 'Accounts'),
        BottomNavigationBarItem(icon: Icon(Icons.smart_toy), label: 'Bots'),
      ],
      onTap: (index) {
        setState(() {
          _selectedIndex = index;
        });
      },
    );
  }

  Widget _buildDrawerMenu(AppLocalizations loc) {
    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              color: Colors.blue.shade700,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  loc.translate('dashboard_title'),
                  style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  'Multi-Broker Trading & Auto-Bot System',
                  style: const TextStyle(color: Colors.white70, fontSize: 14),
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.dashboard),
            title: const Text('Dashboard'),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 0);
            },
          ),
          ListTile(
            leading: const Icon(Icons.swap_horiz),
            title: const Text('Trades'),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 1);
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_circle),
            title: const Text('Accounts'),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 2);
            },
          ),
          ListTile(
            leading: const Icon(Icons.smart_toy),
            title: const Text('Bots'),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 3);
            },
          ),
          const Divider(),
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


