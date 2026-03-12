import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../services/bot_service.dart';
import '../services/trading_service.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../widgets/custom_widgets.dart';
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

  @override
  void initState() {
    super.initState();
    _loadConnectedAccount();
    _startAutoRefresh();
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
    _refreshTimer = Timer.periodic(const Duration(seconds: 20), (timer) {
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
      final response = await http.delete(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/delete/$botId'),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Bot "$botId" deleted successfully'),
              backgroundColor: Colors.green,
            ),
          );
          _fetchBotStatus();
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('Failed to delete bot'),
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
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bot Dashboard'),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
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
      body: Container(
        decoration: const BoxDecoration(
          gradient: AppColors.successGradient,
        ),
        child: RefreshIndicator(
          onRefresh: _fetchBotStatus,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
              // Connected Account Info
              if (_connectedAccount != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    border: Border.all(color: Colors.blue),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.check_circle, color: Colors.blue),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Connected Account',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                            ),
                            Text(
                              'Account: $_connectedAccount • Server: $_connectedServer',
                              style: const TextStyle(
                                fontSize: 11,
                                color: Colors.white70,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Icon(Icons.autorenew, size: 18, color: Colors.blue),
                    ],
                  ),
                ),
              const SizedBox(height: 16),

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
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          height: 120,
                          width: 120,
                          color: Colors.grey[800],
                          child: const Icon(Icons.image_not_supported,
                              color: Colors.grey),
                        );
                      },
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
                          Icon(Icons.smart_toy, size: 48, color: Colors.grey),
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

                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
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
                                      Text(
                                        bot['botId'] ?? 'Unknown Bot',
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleMedium
                                            ?.copyWith(fontWeight: FontWeight.bold),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        bot['strategy'] ?? 'Strategy Unknown',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: Colors.grey,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 12,
                                    vertical: 6,
                                  ),
                                  decoration: BoxDecoration(
                                    color: bot['enabled']
                                        ? Colors.green
                                        : Colors.grey,
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: Text(
                                    bot['enabled'] ? 'ACTIVE' : 'INACTIVE',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 11,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),

                            // Trading Symbols
                            Wrap(
                              spacing: 8,
                              children: List.generate(
                                (bot['symbols'] as List).length,
                                (i) => Chip(
                                  label: Text(bot['symbols'][i]),
                                  backgroundColor: Colors.blue.withOpacity(0.2),
                                  labelStyle: const TextStyle(fontSize: 11),
                                ),
                              ),
                            ),
                            const SizedBox(height: 16),

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
                                        color: Colors.grey,
                                      ),
                                    ),
                                    Text(
                                      bot['runtimeFormatted'] ?? '0h 0m',
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
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
                                        color: Colors.grey,
                                      ),
                                    ),
                                    Text(
                                      '\$${(bot['dailyProfit'] ?? 0).toStringAsFixed(2)}',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: (bot['dailyProfit'] ?? 0) >= 0
                                            ? Colors.green
                                            : Colors.red,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),

                            // Stats Grid
                            GridView.count(
                              crossAxisCount: 3,
                              shrinkWrap: true,
                              physics:
                                  const NeverScrollableScrollPhysics(),
                              mainAxisSpacing: 12,
                              crossAxisSpacing: 12,
                              childAspectRatio: 1.2,
                              children: [
                                _StatTile(
                                  label: 'Trades',
                                  value: totalTrades.toString(),
                                  color: Colors.blue,
                                ),
                                _StatTile(
                                  label: 'Win Rate',
                                  value: '$winRate%',
                                  color: Colors.green,
                                ),
                                _StatTile(
                                  label: 'Profit',
                                  value: '\$$profit',
                                  color: double.parse(profit) >= 0
                                      ? Colors.green
                                      : Colors.red,
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
}

// Helper widget for stats tiles
class _StatTile extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatTile({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
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
}
