import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/currency_provider.dart';
import '../services/notification_service.dart';
import '../services/trading_service.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../utils/session_utils.dart';
import '../widgets/bot_status_indicator.dart';
import '../widgets/global_error_banner.dart';
import '../widgets/global_loading_overlay.dart';
import 'bot_analytics_screen.dart';
import 'bot_configuration_screen.dart';

class BotDashboardScreen extends StatefulWidget {
  const BotDashboardScreen({Key? key}) : super(key: key);

  @override
  State<BotDashboardScreen> createState() => _BotDashboardScreenState();
}

class _BotDashboardScreenState extends State<BotDashboardScreen> {
  Timer? _refreshTimer;
  String? _connectedAccount;
  String? _connectedServer;
  List<dynamic> _activeBots = [];
  bool _isLoading = false;
  String? _successMessage;
  double? _brokerBalance;
  bool _isBalanceLoading = false;
  String? _userName;
  String? _globalError;
  final List<Color> _botCardColors = [
    Colors.blue.shade700,
    Colors.green.shade700,
    Colors.orange.shade700,
    Colors.purple.shade700,
    Colors.red.shade700,
    Colors.teal.shade700,
    Colors.indigo.shade700,
    Colors.deepOrange.shade700,
  ];

  Timer? _autoRefreshTimer;

  @override
  void initState() {
    super.initState();
    _loadConnectedAccount();
    _fetchBrokerBalance();
    _fetchUserName();
    _startAutoRefresh();
    _autoRefreshTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      // Refresh dashboard data
      _fetchBrokerBalance();
      _fetchBotStatus();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkForSuccessMessage();
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _autoRefreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _fetchUserName() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      setState(() {
        _userName = prefs.getString('user_name') ?? 'Trader';
      });
    } catch (e) {
      setState(() {
        _userName = 'Trader';
      });
    }
  }

  Future<void> _fetchBrokerBalance() async {
    setState(() => _isBalanceLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/account/info'),
        headers: {
          'Content-Type': 'application/json',
          if (sessionToken != null && sessionToken.isNotEmpty)
            'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _brokerBalance = data['account']?['balance']?.toDouble() ?? 0.0;
          _globalError = null;
        });
      } else if (response.statusCode == 401) {
        handleSessionExpired(context);
      } else {
        setState(() {
          _globalError = 'Failed to fetch broker balance: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _brokerBalance = null;
        _globalError = 'Error fetching broker balance: $e';
      });
    }
    setState(() => _isBalanceLoading = false);
  }

  void _checkForSuccessMessage() {
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map && args.containsKey('botCreated') && args['botCreated'] == true) {
      setState(() {
        _successMessage = args['message'] ?? 'Bot created and started successfully! 🎉';
      });
      // Show snack bar
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_successMessage ?? ''),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 5),
        ),
      );
      // Auto-refresh bots list
      _fetchBotStatus();
    }
  }

  void _loadConnectedAccount() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _connectedAccount = prefs.getString('mt5_account');
      _connectedServer = prefs.getString('mt5_server');
    });
    _fetchBotStatus();
  }

  Future<void> _fetchBotStatus() async {
    if (!mounted) return;
    setState(() => _isLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      
      // Use public endpoint for bot status (no auth required)
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/status-public'),
        headers: {
          'Content-Type': 'application/json',
          if (sessionToken != null && sessionToken.isNotEmpty)
            'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _activeBots = data['bots'] ?? [];
        });
      }
    } catch (e) {
      print('Error fetching bot status: $e');
    }
    setState(() => _isLoading = false);
  }

  void _startAutoRefresh() {
    // First refresh immediately (to catch newly created bots)
    if (mounted) _fetchBotStatus();
    
    // Second refresh at 1 second (faster for new bots)
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) _fetchBotStatus();
    });
    
    // Then refresh every 10 seconds for active monitoring
    _refreshTimer = Timer.periodic(const Duration(seconds: 10), (timer) {
      if (mounted) {
        _fetchBotStatus();
        final tradingService =
            Provider.of<TradingService>(context, listen: false);
        if (_connectedAccount != null && _connectedServer != null) {
          tradingService.refreshBrokerTrades(
            accountNumber: _connectedAccount!,
            server: _connectedServer!,
          );
        }
      }
    });
  }

  Future<void> _deleteBot(String botId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Bot'),
        content: Text('Are you sure you want to delete "$botId"? This action cannot be undone.'),
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'Activity Log',
            onPressed: () {
              // TODO: Implement ActivityLogScreen
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Activity Log feature coming soon')),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.notifications),
            tooltip: 'Test Notification',
            onPressed: () {
              NotificationService.showNotification(
                title: 'ZWESTA Notification',
                body: 'This is a test notification!',
              );
            },
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    ) ?? false;

    if (!confirm) return;

    try {
      // Get session token from preferences
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      
      if (sessionToken == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Session expired. Please login again.'),
              backgroundColor: Colors.orange,
            ),
          );
        }
        return;
      }

      final response = await http.delete(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/delete/$botId'),
        headers: {
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        if (mounted) {
          setState(() {
            _activeBots.removeWhere((b) => b['botId'] == botId);
          });
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Bot "$botId" deleted successfully'),
              backgroundColor: Colors.green,
            ),
          );
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Failed to delete bot'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      print('Error deleting bot: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Bot Dashboard'),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: BotStatusIndicator(),
          ),
          Consumer<CurrencyProvider>(
            builder: (context, currencyProvider, _) => DropdownButton<AppCurrency>(
              value: currencyProvider.currency,
              underline: const SizedBox.shrink(),
              icon: const Icon(Icons.currency_exchange, color: Colors.white),
              dropdownColor: Colors.grey[900],
              items: const [
                DropdownMenuItem(
                  value: AppCurrency.usd,
                  child: Text('USD', style: TextStyle(color: Colors.white)),
                ),
                DropdownMenuItem(
                  value: AppCurrency.zar,
                  child: Text('ZAR', style: TextStyle(color: Colors.white)),
                ),
                DropdownMenuItem(
                  value: AppCurrency.gbp,
                  child: Text('GBP', style: TextStyle(color: Colors.white)),
                ),
              ],
              onChanged: (val) {
                if (val != null) currencyProvider.setCurrency(val);
              },
            ),
          ),
          TextButton.icon(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (context) => const BotConfigurationScreen()),
              );
            },
            icon: const Icon(Icons.add_circle),
            label: const Text('New Bot'),
          ),
        ],
      ),
      body: GlobalLoadingOverlay(
        isLoading: _isLoading || _isBalanceLoading,
        child: Container(
          decoration: const BoxDecoration(
            gradient: AppColors.successGradient,
          ),
          child: Column(
            children: [
              GlobalErrorBanner(
                errorMessage: _globalError,
                show: _globalError != null,
                onRetry: () {
                  setState(() => _globalError = null);
                  _fetchBrokerBalance();
                },
              ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () async {
                    await _fetchBotStatus();
                    await _fetchBrokerBalance();
                    await _fetchUserName();
                  },
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                // Greeting Header
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Text(
                    'Welcome, ${_userName ?? 'Trader'}!',
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.amberAccent,
                    ),
                  ),
                ),
                // Summary Row
                if (_activeBots.isNotEmpty)
                  Consumer<CurrencyProvider>(
                    builder: (context, currencyProvider, _) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Card(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  children: [
                                    const Icon(Icons.smart_toy, color: Colors.blueAccent),
                                    const Text('Total Bots'),
                                    Text(_activeBots.length.toString()),
                                  ],
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Card(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  children: [
                                    const Icon(Icons.trending_up, color: Colors.greenAccent),
                                    const Text('Total Profit'),
                                    Text('${currencyProvider.symbol} ${currencyProvider.convert(_activeBots.fold<double>(0, (sum, b) => sum + ((b['totalProfit'] ?? 0).toDouble())), fromUsd: false).toStringAsFixed(2)}'),
                                  ],
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Card(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  children: [
                                    const Icon(Icons.emoji_events, color: Colors.orangeAccent),
                                    const Text('Avg Win Rate'),
                                    Text(_activeBots.isNotEmpty
                                        ? '${(_activeBots.fold<double>(0, (sum, b) {
                                            final total = (b['totalTrades'] ?? 0).toDouble();
                                            final win = (b['winningTrades'] ?? 0).toDouble();
                                            return sum + (total > 0 ? (win / total * 100) : 0);
                                          }) /
                                            _activeBots.length).toStringAsFixed(1)}%'
                                        : '0.0%'),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              // Broker Balance Card
              Consumer<CurrencyProvider>(
                builder: (context, currencyProvider, _) => Card(
                  elevation: 6,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  color: Colors.black87,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                    child: Row(
                      children: [
                        const Icon(Icons.account_balance_wallet_rounded, color: Colors.amberAccent, size: 38),
                        const SizedBox(width: 18),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Broker Balance', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 16)),
                              if (_isBalanceLoading) const Padding(
                                      padding: EdgeInsets.only(top: 6),
                                      child: SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                                    ) else Text(
                                      _brokerBalance != null
                                          ? '${currencyProvider.symbol} ${currencyProvider.convert(_brokerBalance!, fromUsd: false).toStringAsFixed(2)}'
                                          : 'Unavailable',
                                      style: const TextStyle(fontSize: 22, color: Colors.amberAccent, fontWeight: FontWeight.bold),
                                    ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.refresh, color: Colors.white70),
                          onPressed: _fetchBrokerBalance,
                          tooltip: 'Refresh Balance',
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 18),

              // Bot Rental Agreement Image
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.blue, width: 2),
                  borderRadius: BorderRadius.circular(8),
                  color: Colors.blue.withOpacity(0.05),
                ),
                child: Row(
                  children: [
                    Image.asset(
                      'assets/images/bot_rental.png',
                      height: 120,
                      width: 120,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) => Container(
                          height: 120,
                          width: 120,
                          color: Colors.grey[800],
                          child: const Icon(Icons.image_not_supported,
                              color: Colors.grey),
                        ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Your Bot Rental',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Active rental agreement',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[400],
                            ),
                          ),
                          const SizedBox(height: 8),
                          ElevatedButton.icon(
                            onPressed: () {
                              Navigator.of(context).pushNamed('/config');
                            },
                            icon: const Icon(Icons.settings, size: 16),
                            label: const Text('Configure'),
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 6,
                              ),
                              backgroundColor: Colors.blue,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Section Title
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Active Bots',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  if (_activeBots.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.green,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        '${_activeBots.length} Running',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    )
                ],
              ),
              const SizedBox(height: 12),

              // Bots List
              if (_isLoading)
                const Center(child: CircularProgressIndicator())
              else if (_activeBots.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Center(
                      child: Column(
                        children: [
                          const Icon(Icons.smart_toy, size: 48, color: Colors.grey),
                          const SizedBox(height: 12),
                          Text(
                            'No Active Bots',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Create and start a bot from Bot Configuration',
                            style: TextStyle(fontSize: 12, color: Colors.grey),
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
                  itemCount: _activeBots.length,
                  itemBuilder: (context, index) {
                    final bot = _activeBots[index];
                    final totalTrades = bot['totalTrades'] ?? 0;
                    final winningTrades = bot['winningTrades'] ?? 0;
                    final winRate = totalTrades > 0
                        ? (winningTrades / totalTrades * 100).toStringAsFixed(1)
                        : '0.0';
                    final profit = (bot['totalProfit'] ?? 0).toStringAsFixed(2);
                    final cardColor = _botCardColors[index % _botCardColors.length];

                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      elevation: 7,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                      color: cardColor.withOpacity(0.93),
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Bot Header
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          const Icon(Icons.smart_toy, color: Colors.white, size: 22),
                                          const SizedBox(width: 8),
                                          Text(
                                            bot['botId'] ?? 'Unknown Bot',
                                            style: Theme.of(context)
                                                .textTheme
                                                .titleMedium
                                                ?.copyWith(fontWeight: FontWeight.bold, color: Colors.white),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        bot['strategy'] ?? 'Strategy Unknown',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: Colors.white70,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                BotRunningBadge(
                                  isRunning: bot['enabled'] == true || bot['enabled'] == 1,
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),

                            // Trading Symbols
                            Wrap(
                              spacing: 8,
                              children: List.generate(
                                (bot['symbols'] as List).length,
                                (i) => Chip(
                                  label: Text(bot['symbols'][i]),
                                  backgroundColor: Colors.white.withOpacity(0.18),
                                  labelStyle: const TextStyle(fontSize: 11, color: Colors.white),
                                ),
                              ),
                            ),
                            const SizedBox(height: 14),

                            // Runtime and Daily Profit
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text(
                                      'Running for',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.white70,
                                      ),
                                    ),
                                    Text(
                                      bot['runtimeFormatted'] ?? '0h 0m',
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ],
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    const Text(
                                      'Today\'s Profit',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.white70,
                                      ),
                                    ),
                                    Text(
                                      '\$${(bot['dailyProfit'] ?? 0).toStringAsFixed(2)}',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: (bot['dailyProfit'] ?? 0) >= 0
                                            ? Colors.greenAccent
                                            : Colors.redAccent,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),

                            // Stats Grid
                            GridView.count(
                              crossAxisCount: 3,
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              mainAxisSpacing: 12,
                              crossAxisSpacing: 12,
                              childAspectRatio: 1.2,
                              children: [
                                _StatTile(
                                  label: 'Trades',
                                  value: totalTrades.toString(),
                                  color: Colors.white,
                                ),
                                _StatTile(
                                  label: 'Win Rate',
                                  value: '$winRate%',
                                  color: Colors.white,
                                ),
                                _StatTile(
                                  label: 'Profit',
                                  value: '\$$profit',
                                  color: double.parse(profit) >= 0
                                      ? Colors.greenAccent
                                      : Colors.redAccent,
                                ),
                                _StatTile(
                                  label: 'ROI',
                                  value: '${(bot['roi'] ?? 0).toStringAsFixed(1)}%',
                                  color: Colors.orange,
                                ),
                                _StatTile(
                                  label: 'Avg/Trade',
                                  value: '\$${(bot['avgProfitPerTrade'] ?? 0).toStringAsFixed(0)}',
                                  color: Colors.cyan,
                                ),
                                _StatTile(
                                  label: 'Max Drawdown',
                                  value: '\$${(bot['maxDrawdown'] ?? 0).toStringAsFixed(0)}',
                                  color: Colors.red,
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),

                            // Action Buttons
                            Row(
                              children: [
                                Expanded(
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
                                    icon: const Icon(Icons.analytics),
                                    label: const Text('View Analytics'),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: Colors.blue,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                ElevatedButton.icon(
                                  onPressed: () => _deleteBot(bot['botId'] ?? 'Unknown'),
                                  icon: const Icon(Icons.delete),
                                  label: const Text('Delete'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.red,
                                    foregroundColor: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.grey[900],
        selectedItemColor: Colors.blue,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard),
            label: 'Dashboard',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings),
            label: 'Config',
          ),
        ],
        currentIndex: 1,
        onTap: (index) {
          if (index == 0) {
            Navigator.of(context).popUntil((route) => route.isFirst);
          } else if (index == 2) {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (context) => const BotConfigurationScreen()),
            );
          }
        },
      ),
    );
}

// Helper widget for stats tiles
class _StatTile extends StatelessWidget {

  const _StatTile({
    required this.label,
    required this.value,
    required this.color,
  });
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        border: Border.all(color: color.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: Colors.grey,
            ),
          ),
        ],
      ),
    );
}
