// import 'package:fl_chart/fl_chart.dart'; // Disabled for compatibility
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../services/ig_trading_service.dart';
import '../utils/environment_config.dart';
import 'bot_configuration_screen.dart';
import 'bot_dashboard_screen.dart';
import 'consolidated_reports_screen.dart';

class BotAnalyticsScreen extends StatefulWidget {
  const BotAnalyticsScreen({
    required this.bot,
    Key? key,
  }) : super(key: key);
  final Map<String, dynamic> bot;

  @override
  State<BotAnalyticsScreen> createState() => _BotAnalyticsScreenState();
}

class _BotAnalyticsScreenState extends State<BotAnalyticsScreen> {
  Timer? _refreshTimer;
  late Map<String, dynamic> _botData;

  // IG state
  bool _isIG = false;
  bool _igLoading = false;
  Map<String, dynamic>? _igBalance;
  List<dynamic> _igPositions = [];
  List<dynamic> _igTransactions = [];
  String? _igError;

  @override
  void initState() {
    super.initState();
    _botData = Map<String, dynamic>.from(widget.bot);
    final brokerType = _botData['broker_type'] ?? _botData['broker'] ?? 'MT5';
    _isIG = brokerType.toString().toUpperCase().contains('IG');

    _refreshAnalytics();
    _refreshTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (mounted) {
        _refreshAnalytics();
      }
    });

    if (_isIG) {
      _loadIGData();
    }
  }

  Future<void> _loadIGData() async {
    if (!_isIG) {
      return;
    }
    setState(() {
      _igLoading = true;
      _igError = null;
    });
    try {
      final results = await Future.wait([
        IGTradingService.getBalance(),
        IGTradingService.getPositions(),
        IGTradingService.getTransactions(pageSize: 20),
      ]);
      if (mounted) {
        setState(() {
          _igLoading = false;
          final balData = results[0];
          if (balData['success'] == true) {
            _igBalance = balData;
          }
          final posData = results[1];
          if (posData['success'] == true) {
            _igPositions = posData['positions'] ?? [];
          }
          final txData = results[2];
          if (txData['success'] == true) {
            _igTransactions = txData['transactions'] ?? [];
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _igLoading = false;
          _igError = e.toString();
        });
      }
    }
  }

  Future<void> _refreshAnalytics() async {
    // Fetch fresh bot data from backend API
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final botId = _botData['botId'];

      if (sessionToken == null || sessionToken.isEmpty) {
        debugPrint('Skipping analytics refresh: missing session token');
        _refreshTimer?.cancel();
        return;
      }

      if (botId == null || botId.toString().isEmpty) {
        return;
      }

      final url =
          '${EnvironmentConfig.apiUrl}/api/bot/$botId/analytics-snapshot';

      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          final bot = data['bot'];
          if (bot is Map<String, dynamic> && mounted) {
            setState(() {
              _botData = bot;
            });
          }
        }
      } else if (response.statusCode == 401 || response.statusCode == 403) {
        debugPrint('Stopping analytics refresh due to unauthorized session');
        _refreshTimer?.cancel();
      }
    } catch (e) {
      debugPrint('Error refreshing analytics: $e');
    }
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  List<Map<String, dynamic>> _getProfitChartData() {
    final dailyProfits = _botData['dailyProfits'] as Map?;
    if (dailyProfits == null || dailyProfits.isEmpty) {
      return [];
    }
    return dailyProfits.entries
        .map((e) => {
              'date': e.key,
              'profit': (e.value as num).toDouble(),
            })
        .toList();
  }

  List<Map<String, dynamic>> _getTradesChartData() {
    final tradeHistory = _botData['tradeHistory'] as List?;
    if (tradeHistory == null || tradeHistory.isEmpty) {
      return [];
    }
    final trades = List.from(tradeHistory)
      ..sort((a, b) {
        final aTime = a['time']?.toString() ?? '';
        final bTime = b['time']?.toString() ?? '';
        return aTime.compareTo(bTime);
      });
    return trades
        .map((t) => {
              'symbol': t['symbol'] ?? 'N/A',
              'profit': (t['profit'] as num).toDouble(),
              'isWinning': (t['profit'] as num) > 0,
            })
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    try {
      final totalProfit = (_botData['currentProfit'] ??
              _botData['profit'] ??
              _botData['totalProfit'] ??
              0)
          .toDouble();
      final totalTrades = _botData['totalTrades']?.toInt() ?? 0;
      final winRate = (_botData['winRate'] ?? 0).toDouble();
      final roi = (_botData['roi'] ?? 0).toDouble();
      final profitability = (_botData['profitability'] ?? 0).toDouble();
      final runtimeFormatted = _botData['runtimeFormatted'] ?? '0h 0m';
      final dailyProfit = (_botData['dailyProfit'] ?? 0).toDouble();
      final avgProfitPerTrade = (_botData['avgProfitPerTrade'] ?? 0).toDouble();
      final maxDrawdown = (_botData['maxDrawdown'] ?? 0).toDouble();
      final botStatus = _botData['status'] ?? 'Unknown';

      return Scaffold(
        appBar: AppBar(
          title: Text(_botData['botId'] ?? 'Bot Analytics'),
          backgroundColor: Colors.grey[900],
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.of(context).pop(),
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.home_outlined),
              tooltip: 'Home',
              onPressed: () =>
                  Navigator.of(context).popUntil((route) => route.isFirst),
            ),
            IconButton(
              icon: const Icon(Icons.assessment_outlined),
              tooltip: 'Reports',
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                      builder: (context) => const ConsolidatedReportsScreen()),
                );
              },
            ),
            TextButton.icon(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                      builder: (context) => const BotConfigurationScreen()),
                );
              },
              icon: const Icon(Icons.settings),
              label: const Text('Config'),
            ),
          ],
        ),
        backgroundColor: Colors.grey[850],
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Status and Runtime Section
              _buildStatusSection(
                runtimeFormatted: runtimeFormatted,
                status: botStatus,
                dailyProfit: dailyProfit,
              ),
              const SizedBox(height: 16),

              // Account Balance Card
              _buildBalanceCard(),
              const SizedBox(height: 16),

              // Open Positions Section
              _buildOpenPositionsSection(),
              const SizedBox(height: 24),

              // Key Metrics Grid
              _buildMetricsGrid(
                totalProfit: totalProfit,
                totalTrades: totalTrades,
                winRate: winRate,
                roi: roi,
                profitability: profitability,
                avgProfitPerTrade: avgProfitPerTrade,
                maxDrawdown: maxDrawdown,
              ),
              const SizedBox(height: 24),

              // Profit Over Time Chart
              _buildSectionHeader('Profit Over Time'),
              _buildProfitChart(),
              const SizedBox(height: 24),

              // Trades Growth Chart
              _buildSectionHeader('Trades Growth'),
              _buildTradesChart(),
              const SizedBox(height: 24),

              // Daily Profit Distribution
              if (_botData['dailyProfits'] != null &&
                  (_botData['dailyProfits'] as Map).isNotEmpty)
                _buildDailyProfitsSection(),

              // IG Controls & Data (only for IG bots)
              if (_isIG) ...[
                const SizedBox(height: 24),
                _buildIGControlPanel(),
                const SizedBox(height: 16),
                _buildIGBalanceCard(),
                const SizedBox(height: 16),
                _buildIGPositionsSection(),
                const SizedBox(height: 16),
                _buildIGTransactionsSection(),
              ],

              // Trade History
              const SizedBox(height: 24),
              _buildSectionHeader('Recent Trades'),
              _buildTradeHistorySection(),
            ],
          ),
        ),
        bottomNavigationBar: BottomNavigationBar(
          backgroundColor: const Color(0xFF111633),
          selectedItemColor: const Color(0xFF00E5FF),
          unselectedItemColor: Colors.white38,
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_rounded),
              label: 'Home',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.smart_toy_outlined),
              label: 'Bots',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.assessment_outlined),
              label: 'Reports',
            ),
          ],
          currentIndex: 1,
          onTap: (index) {
            if (index == 0) {
              Navigator.of(context).popUntil((route) => route.isFirst);
            } else if (index == 1) {
              Navigator.of(context).push(
                MaterialPageRoute(
                    builder: (context) => const BotDashboardScreen()),
              );
            } else if (index == 2) {
              Navigator.of(context).push(
                MaterialPageRoute(
                    builder: (context) => const ConsolidatedReportsScreen()),
              );
            }
          },
        ),
      );
    } catch (e) {
      debugPrint('Error building BotAnalyticsScreen: $e');
      return Scaffold(
        appBar: AppBar(
          title: const Text('Bot Analytics'),
          backgroundColor: Colors.grey[900],
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ),
        backgroundColor: Colors.grey[850],
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, color: Colors.red[400], size: 48),
              const SizedBox(height: 16),
              Text(
                'Error loading analytics',
                style: TextStyle(color: Colors.red[400]),
              ),
              const SizedBox(height: 8),
              Text(
                e.toString(),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }
  }

  Widget _buildStatusSection({
    required String runtimeFormatted,
    required String status,
    required double dailyProfit,
  }) {
    final isActive = status == 'Active';
    final statusColor = isActive ? Colors.green : Colors.red;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            statusColor.withValues(alpha: 0.15),
            statusColor.withValues(alpha: 0.05)
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: statusColor.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: statusColor.withValues(alpha: 0.2),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: statusColor,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                            color: statusColor.withValues(alpha: 0.5),
                            blurRadius: 8)
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    status,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  const Icon(Icons.schedule, color: Colors.white54, size: 16),
                  const SizedBox(width: 6),
                  Text(
                    'Running: $runtimeFormatted',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              const Text(
                'Today\'s Profit',
                style: TextStyle(
                  color: Colors.white70,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: dailyProfit >= 0
                      ? Colors.green.withValues(alpha: 0.15)
                      : Colors.red.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '\$${dailyProfit.toStringAsFixed(2)}',
                  style: TextStyle(
                    color: dailyProfit >= 0 ? Colors.green : Colors.red,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetricsGrid({
    required double totalProfit,
    required int totalTrades,
    required double winRate,
    required double roi,
    required double profitability,
    required double avgProfitPerTrade,
    required double maxDrawdown,
  }) =>
      GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        children: [
          _buildMetricCard(
            label: 'Total Profit',
            value: '\$${totalProfit.toStringAsFixed(2)}',
            color: totalProfit >= 0 ? Colors.green : Colors.red,
            icon: Icons.trending_up,
          ),
          _buildMetricCard(
            label: 'Total Trades',
            value: totalTrades.toString(),
            color: Colors.blue,
            icon: Icons.credit_card,
          ),
          _buildMetricCard(
            label: 'Win Rate',
            value: '${winRate.toStringAsFixed(1)}%',
            color: Colors.purple,
            icon: Icons.leaderboard,
          ),
          _buildMetricCard(
            label: 'ROI',
            value: '${roi.toStringAsFixed(1)}%',
            color: Colors.orange,
            icon: Icons.percent,
          ),
          _buildMetricCard(
            label: 'Profitability',
            value: '\$${profitability.toStringAsFixed(2)}',
            color: Colors.teal,
            icon: Icons.monetization_on,
          ),
          _buildMetricCard(
            label: 'Avg Profit/Trade',
            value: '\$${avgProfitPerTrade.toStringAsFixed(2)}',
            color: Colors.cyan,
            icon: Icons.bar_chart,
          ),
          _buildMetricCard(
            label: 'Max Drawdown',
            value: '\$${maxDrawdown.toStringAsFixed(2)}',
            color: Colors.red[400]!,
            icon: Icons.trending_down,
          ),
        ],
      );

  Widget _buildMetricCard({
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) =>
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              color.withValues(alpha: 0.15),
              color.withValues(alpha: 0.05)
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          border: Border.all(color: color.withValues(alpha: 0.4)),
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.15),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 18),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 6),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                value,
                style: TextStyle(
                  color: color,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      );

  Widget _buildSectionHeader(String title) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 24,
              decoration: BoxDecoration(
                color: Colors.blue,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      );

  Widget _buildProfitChart() {
    final chartData = _getProfitChartData();
    if (chartData.isEmpty) {
      return Container(
        height: 300,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Colors.blue.withValues(alpha: 0.1),
              Colors.purple.withValues(alpha: 0.05)
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.blue.withValues(alpha: 0.3)),
          boxShadow: [
            BoxShadow(
              color: Colors.blue.withValues(alpha: 0.1),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.show_chart, color: Colors.blue, size: 32),
              SizedBox(height: 12),
              Text('No profit data available yet',
                  style: TextStyle(color: Colors.white70, fontSize: 14)),
            ],
          ),
        ),
      );
    }

    final maxProfit = chartData.fold<double>(
        0, (max, p) => p['profit'] > max ? p['profit'] : max);
    final minProfit = chartData.fold<double>(
        0, (min, p) => p['profit'] < min ? p['profit'] : min);

    return Container(
      height: 300,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.blue.withValues(alpha: 0.1),
            Colors.purple.withValues(alpha: 0.05)
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.blue.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.blue.withValues(alpha: 0.1),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: chartData.map((item) {
                final profit = item['profit'] as double;
                final heightRatio = maxProfit > 0
                    ? (profit / (maxProfit > 0 ? maxProfit : 1))
                    : 0.1;
                final isPositive = profit >= 0;
                return Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Tooltip(
                        message: '\$${profit.toStringAsFixed(2)}',
                        child: Container(
                          height: (heightRatio * 200).clamp(20, 200),
                          width: double.infinity,
                          margin: const EdgeInsets.symmetric(horizontal: 2),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: isPositive
                                  ? [
                                      Colors.green.shade400,
                                      Colors.green.shade600
                                    ]
                                  : [Colors.red.shade400, Colors.red.shade600],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                            borderRadius: const BorderRadius.only(
                              topLeft: Radius.circular(4),
                              topRight: Radius.circular(4),
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: (isPositive ? Colors.green : Colors.red)
                                    .withValues(alpha: 0.3),
                                blurRadius: 4,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        item['date'].toString().length > 5
                            ? item['date'].toString().substring(5)
                            : item['date'].toString(),
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 10),
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Min: \$${minProfit.toStringAsFixed(2)}',
                  style: const TextStyle(color: Colors.white54, fontSize: 11)),
              Text('Max: \$${maxProfit.toStringAsFixed(2)}',
                  style: const TextStyle(color: Colors.white54, fontSize: 11)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTradesChart() {
    final chartData = _getTradesChartData();
    if (chartData.isEmpty) {
      return Container(
        height: 300,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Colors.purple.withValues(alpha: 0.1),
              Colors.indigo.withValues(alpha: 0.05)
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.purple.withValues(alpha: 0.3)),
          boxShadow: [
            BoxShadow(
              color: Colors.purple.withValues(alpha: 0.1),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.trending_up, color: Colors.purple, size: 32),
              SizedBox(height: 12),
              Text('No trades data available yet',
                  style: TextStyle(color: Colors.white70, fontSize: 14)),
            ],
          ),
        ),
      );
    }

    final totalTrades = chartData.length;
    final winningTrades = chartData.where((t) => t['isWinning'] == true).length;
    final cumulativeProfit =
        chartData.fold<double>(0, (sum, t) => sum + t['profit']);

    return Container(
      height: 300,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.purple.withValues(alpha: 0.1),
            Colors.indigo.withValues(alpha: 0.05)
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.purple.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.purple.withValues(alpha: 0.1),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: chartData.asMap().entries.map((entry) {
                final idx = entry.key;
                final item = entry.value;
                final isWinning = item['isWinning'] as bool;
                final cumulativeAtIndex = chartData
                    .take(idx + 1)
                    .fold<double>(0, (sum, t) => sum + t['profit']);
                final maxCumulative = chartData.fold<double>(0, (max, item) {
                  final idx = chartData.indexOf(item);
                  final cum = chartData
                      .take(idx + 1)
                      .fold<double>(0, (sum, t) => sum + t['profit']);
                  return cum > max ? cum : max;
                });
                final heightRatio = maxCumulative > 0
                    ? (cumulativeAtIndex / maxCumulative)
                    : 0.1;

                return Expanded(
                  child: Tooltip(
                    message:
                        '${item['symbol']}\n\$${cumulativeAtIndex.toStringAsFixed(2)}',
                    child: Container(
                      height: (heightRatio * 200).clamp(20, 200),
                      width: double.infinity,
                      margin: const EdgeInsets.symmetric(horizontal: 2),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: isWinning
                              ? [Colors.green.shade400, Colors.green.shade600]
                              : [Colors.red.shade400, Colors.red.shade600],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                        borderRadius: const BorderRadius.only(
                          topLeft: Radius.circular(4),
                          topRight: Radius.circular(4),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: (isWinning ? Colors.green : Colors.red)
                                .withValues(alpha: 0.3),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Trades: $totalTrades | Wins: $winningTrades',
                  style: const TextStyle(color: Colors.white54, fontSize: 11)),
              Text('Total: \$${cumulativeProfit.toStringAsFixed(2)}',
                  style: TextStyle(
                    color: cumulativeProfit >= 0 ? Colors.green : Colors.red,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  )),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDailyProfitsSection() {
    final dailyProfits = _botData['dailyProfits'] as Map?;
    if (dailyProfits == null || dailyProfits.isEmpty) {
      return const SizedBox.shrink();
    }

    // Convert to list and sort by date
    final entries = dailyProfits.entries.toList()
      ..sort((a, b) => a.key.toString().compareTo(b.key.toString()));

    // Get last 7 days
    final last7 =
        entries.length > 7 ? entries.sublist(entries.length - 7) : entries;

    // Find min/max for scaling
    double minProfit = 0, maxProfit = 0;
    for (final entry in last7) {
      final profit = double.tryParse(entry.value.toString()) ?? 0;
      if (profit < minProfit) {
        minProfit = profit;
      }
      if (profit > maxProfit) {
        maxProfit = profit;
      }
    }

    // Add 20% padding
    final range = maxProfit - minProfit;
    final padding = range * 0.2;
    minProfit -= padding;
    maxProfit += padding;
    if (maxProfit <= 0) {
      maxProfit = 100;
    }
    if (minProfit < 0 && maxProfit > 0) {
      minProfit = -maxProfit * 0.2;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('Daily Profits (Last 7 Days)'),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey[900],
            borderRadius: BorderRadius.circular(8),
          ),
          height: 250,
          child: Column(
            children: [
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: last7.map((entry) {
                    final profit = double.tryParse(entry.value.toString()) ?? 0;
                    final height = (maxProfit != minProfit
                        ? ((profit - minProfit) / (maxProfit - minProfit)) * 180
                        : 90) as double;
                    final color = profit >= 0 ? Colors.green : Colors.red;

                    return Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          '\$${profit.toStringAsFixed(0)}',
                          style: TextStyle(
                            color: color,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Container(
                          width: 30,
                          height: height.clamp(10.0, 180.0),
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.7),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                      ],
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: last7.map((entry) {
                  final date = entry.key.toString().split('-').last;
                  return Text(
                    date,
                    style: const TextStyle(color: Colors.white54, fontSize: 10),
                  );
                }).toList(),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ==================== IG WIDGETS ====================

  Widget _buildIGControlPanel() => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFFE91E63).withValues(alpha: 0.08),
          border:
              Border.all(color: const Color(0xFFE91E63).withValues(alpha: 0.4)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_balance,
                    color: Color(0xFFE91E63), size: 22),
                const SizedBox(width: 8),
                const Text(
                  'IG Trading Controls',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold),
                ),
                const Spacer(),
                if (_igLoading)
                  const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Color(0xFFE91E63))),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                _igActionButton(
                  icon: Icons.refresh,
                  label: 'Refresh',
                  color: Colors.blue,
                  onTap: _loadIGData,
                ),
                _igActionButton(
                  icon: Icons.account_balance_wallet,
                  label: 'Balance',
                  color: Colors.green,
                  onTap: () async {
                    final data = await IGTradingService.getBalance();
                    if (mounted) {
                      setState(() => _igBalance =
                          data['success'] == true ? data : _igBalance);
                      _showIGSnackBar(data['success'] == true
                          ? 'Balance: \$${data['balance']?.toStringAsFixed(2) ?? '?'}'
                          : 'Error: ${data['error']}');
                    }
                  },
                ),
                _igActionButton(
                  icon: Icons.list_alt,
                  label: 'Positions',
                  color: Colors.orange,
                  onTap: () async {
                    final data = await IGTradingService.getPositions();
                    if (mounted) {
                      setState(() {
                        if (data['success'] == true)
                          _igPositions = data['positions'] ?? [];
                      });
                      _showIGSnackBar(
                          '${_igPositions.length} open position(s)');
                    }
                  },
                ),
                _igActionButton(
                  icon: Icons.history,
                  label: 'History',
                  color: Colors.purple,
                  onTap: () async {
                    final data = await IGTradingService.getTransactions();
                    if (mounted) {
                      setState(() {
                        if (data['success'] == true)
                          _igTransactions = data['transactions'] ?? [];
                      });
                      _showIGSnackBar(
                          '${_igTransactions.length} transaction(s) loaded');
                    }
                  },
                ),
                _igActionButton(
                  icon: Icons.close_fullscreen,
                  label: 'Close All',
                  color: Colors.red,
                  onTap: _confirmCloseAllPositions,
                ),
                _igActionButton(
                  icon: Icons.add_chart,
                  label: 'Place Trade',
                  color: Colors.teal,
                  onTap: _showPlaceTradeDialog,
                ),
                _igActionButton(
                  icon: Icons.search,
                  label: 'Markets',
                  color: Colors.indigo,
                  onTap: _showMarketSearchDialog,
                ),
              ],
            ),
            if (_igError != null) ...[
              const SizedBox(height: 8),
              Text(_igError!,
                  style:
                      const TextStyle(color: Colors.redAccent, fontSize: 12)),
            ],
          ],
        ),
      );

  Widget _igActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) =>
      InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withValues(alpha: 0.4)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 6),
              Text(label,
                  style: TextStyle(
                      color: color, fontSize: 13, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      );

  Widget _buildIGBalanceCard() {
    if (_igBalance == null) {
      return const SizedBox.shrink();
    }
    final balance = (_igBalance!['balance'] ?? 0).toDouble();
    final available = (_igBalance!['available'] ?? 0).toDouble();
    final pnl = (_igBalance!['profitLoss'] ?? 0).toDouble();
    final currency = _igBalance!['currency'] ?? 'USD';
    final igSym = currency == 'ZAR' ? 'R' : (currency == 'GBP' ? '£' : (currency == 'EUR' ? '€' : r'$'));

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[900],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('IG Account Balance',
              style: TextStyle(color: Colors.white70, fontSize: 13)),
          const SizedBox(height: 10),
          Row(
            children: [
              _balanceStat(
                  'Balance', '$igSym${balance.toStringAsFixed(2)}', Colors.white),
              _balanceStat('Available', '$igSym${available.toStringAsFixed(2)}',
                  Colors.blue),
              _balanceStat('P&L', '$igSym${pnl.toStringAsFixed(2)}',
                  pnl >= 0 ? Colors.green : Colors.red),
            ],
          ),
          const SizedBox(height: 4),
          Text('Currency: $currency',
              style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _balanceStat(String label, String value, Color color) => Expanded(
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    color: color, fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
            Text(label,
                style: const TextStyle(color: Colors.white54, fontSize: 11)),
          ],
        ),
      );

  Widget _buildIGPositionsSection() {
    if (_igPositions.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
            color: Colors.grey[900], borderRadius: BorderRadius.circular(8)),
        child: const Center(
            child: Text('No open IG positions',
                style: TextStyle(color: Colors.white54))),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('IG Open Positions (${_igPositions.length})'),
        const SizedBox(height: 8),
        ..._igPositions.map((pos) {
          final direction = pos['direction'] ?? '';
          final isBuy = direction == 'BUY';
          final pnl = (pos['profitLoss'] ?? 0).toDouble();
          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey[900],
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                  color: isBuy
                      ? Colors.green.withValues(alpha: 0.3)
                      : Colors.red.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: (isBuy ? Colors.green : Colors.red)
                        .withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(direction,
                      style: TextStyle(
                          color: isBuy ? Colors.green : Colors.red,
                          fontSize: 11,
                          fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(pos['instrumentName'] ?? pos['epic'] ?? '',
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13,
                              fontWeight: FontWeight.w600)),
                      Text('Size: ${pos['size']}  |  Level: ${pos['level']}',
                          style: const TextStyle(
                              color: Colors.white54, fontSize: 11)),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '\$${pnl.toStringAsFixed(2)}',
                      style: TextStyle(
                          color: pnl >= 0 ? Colors.green : Colors.red,
                          fontSize: 14,
                          fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    InkWell(
                      onTap: () => _closeIGPosition(pos),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('Close',
                            style: TextStyle(
                                color: Colors.redAccent,
                                fontSize: 11,
                                fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _buildIGTransactionsSection() {
    if (_igTransactions.isEmpty) {
      return const SizedBox.shrink();
    }

    final recent = _igTransactions.length > 50
        ? _igTransactions.sublist(0, 50)
        : _igTransactions;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('IG Transaction History'),
        const SizedBox(height: 8),
        ...recent.map((tx) {
          final pnlStr = tx['profitAndLoss']?.toString() ?? '0';
          final pnlNum =
              double.tryParse(pnlStr.replaceAll(RegExp(r'[^0-9.\-]'), '')) ?? 0;
          return Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.grey[900],
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(tx['instrumentName'] ?? '',
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.w600)),
                      Text('${tx['type'] ?? ''} | ${tx['date'] ?? ''}',
                          style: const TextStyle(
                              color: Colors.white38, fontSize: 10)),
                    ],
                  ),
                ),
                Text(
                  pnlStr,
                  style: TextStyle(
                      color: pnlNum >= 0 ? Colors.green : Colors.red,
                      fontSize: 13,
                      fontWeight: FontWeight.bold),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  // ==================== IG ACTIONS ====================

  Future<void> _closeIGPosition(Map<String, dynamic> pos) async {
    final dealId = pos['dealId'] ?? '';
    final direction = pos['direction'] ?? 'BUY';
    final size = (pos['size'] ?? 0).toDouble();
    final closeDirection = direction == 'BUY' ? 'SELL' : 'BUY';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.grey[900],
        title: const Text('Close Position?',
            style: TextStyle(color: Colors.white)),
        content: Text(
          'Close ${pos['instrumentName'] ?? pos['epic']} ($direction, size: $size)?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Close', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await IGTradingService.closePosition(
        dealId: dealId, direction: closeDirection, size: size);
    _showIGSnackBar(result['success'] == true
        ? 'Position closed'
        : 'Error: ${result['error']}');
    if (result['success'] == true) _loadIGData();
  }

  Future<void> _confirmCloseAllPositions() async {
    if (_igPositions.isEmpty) {
      _showIGSnackBar('No open positions to close');
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Colors.grey[900],
        title: const Text('Close ALL Positions?',
            style: TextStyle(color: Colors.white)),
        content: Text(
          'This will close all ${_igPositions.length} open IG position(s). Are you sure?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Close All', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await IGTradingService.closeAllPositions();
    _showIGSnackBar(result['success'] == true
        ? 'Closed ${result['closed']}/${result['total']} positions'
        : 'Error: ${result['error']}');
    if (result['success'] == true) _loadIGData();
  }

  Future<void> _showPlaceTradeDialog() async {
    var epic = '';
    var direction = 'BUY';
    var sizeStr = '1';
    String? stopStr;
    String? limitStr;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: Colors.grey[900],
          title: const Text('Place IG Trade',
              style: TextStyle(color: Colors.white)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Epic (e.g. CS.D.EURUSD.CFD.IP)',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white24)),
                  ),
                  style: const TextStyle(color: Colors.white),
                  onChanged: (v) => epic = v,
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Text('Direction: ',
                        style: TextStyle(color: Colors.white54)),
                    ChoiceChip(
                      label: const Text('BUY'),
                      selected: direction == 'BUY',
                      selectedColor: Colors.green,
                      onSelected: (_) =>
                          setDialogState(() => direction = 'BUY'),
                    ),
                    const SizedBox(width: 8),
                    ChoiceChip(
                      label: const Text('SELL'),
                      selected: direction == 'SELL',
                      selectedColor: Colors.red,
                      onSelected: (_) =>
                          setDialogState(() => direction = 'SELL'),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Size',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white24)),
                  ),
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  controller: TextEditingController(text: sizeStr),
                  onChanged: (v) => sizeStr = v,
                ),
                const SizedBox(height: 10),
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Stop Distance (optional)',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white24)),
                  ),
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  onChanged: (v) => stopStr = v,
                ),
                const SizedBox(height: 10),
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Limit Distance (optional)',
                    labelStyle: TextStyle(color: Colors.white54),
                    enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white24)),
                  ),
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: Colors.white),
                  onChanged: (v) => limitStr = v,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: Colors.teal),
              onPressed: () {
                if (epic.isEmpty) return;
                Navigator.pop(ctx, {
                  'epic': epic,
                  'direction': direction,
                  'size': double.tryParse(sizeStr) ?? 1,
                  'stopDistance':
                      stopStr != null ? double.tryParse(stopStr!) : null,
                  'limitDistance':
                      limitStr != null ? double.tryParse(limitStr!) : null,
                });
              },
              child: const Text('Place Order'),
            ),
          ],
        ),
      ),
    );

    if (result == null) return;
    final orderResult = await IGTradingService.placeOrder(
      epic: result['epic'],
      direction: result['direction'],
      size: result['size'],
      stopDistance: result['stopDistance'],
      limitDistance: result['limitDistance'],
    );
    _showIGSnackBar(orderResult['success'] == true
        ? 'Order placed! Ref: ${orderResult['dealReference']}'
        : 'Error: ${orderResult['error']}');
    if (orderResult['success'] == true) _loadIGData();
  }

  Future<void> _showMarketSearchDialog() async {
    var searchTerm = '';
    var searchResults = <dynamic>[];

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: Colors.grey[900],
          title: const Text('Search IG Markets',
              style: TextStyle(color: Colors.white)),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  decoration: const InputDecoration(
                    labelText: 'Search (e.g. EUR, Gold, Apple)',
                    labelStyle: TextStyle(color: Colors.white54),
                    suffixIcon: Icon(Icons.search, color: Colors.white54),
                    enabledBorder: UnderlineInputBorder(
                        borderSide: BorderSide(color: Colors.white24)),
                  ),
                  style: const TextStyle(color: Colors.white),
                  onChanged: (v) => searchTerm = v,
                  onSubmitted: (_) async {
                    if (searchTerm.isEmpty) return;
                    final data =
                        await IGTradingService.searchMarkets(searchTerm);
                    setDialogState(() {
                      searchResults = data['success'] == true
                          ? (data['markets'] ?? [])
                          : [];
                    });
                  },
                ),
                const SizedBox(height: 10),
                ElevatedButton(
                  style:
                      ElevatedButton.styleFrom(backgroundColor: Colors.indigo),
                  onPressed: () async {
                    if (searchTerm.isEmpty) return;
                    final data =
                        await IGTradingService.searchMarkets(searchTerm);
                    setDialogState(() {
                      searchResults = data['success'] == true
                          ? (data['markets'] ?? [])
                          : [];
                    });
                  },
                  child: const Text('Search'),
                ),
                if (searchResults.isNotEmpty)
                  SizedBox(
                    height: 250,
                    child: ListView.builder(
                      shrinkWrap: true,
                      itemCount: searchResults.length,
                      itemBuilder: (ctx, i) {
                        final m = searchResults[i];
                        return ListTile(
                          dense: true,
                          title: Text(m['instrumentName'] ?? '',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 13)),
                          subtitle: Text(
                            '${m['epic']} | ${m['instrumentType'] ?? ''} | Bid: ${m['bid']} / Offer: ${m['offer']}',
                            style: const TextStyle(
                                color: Colors.white38, fontSize: 10),
                          ),
                          onTap: () => Navigator.pop(ctx),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Close')),
          ],
        ),
      ),
    );
  }

  void _showIGSnackBar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 3),
        backgroundColor: Colors.grey[800],
      ),
    );
  }

  Widget _buildTradeHistorySection() {
    final tradeHistory = _botData['tradeHistory'] as List?;
    if (tradeHistory == null || tradeHistory.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.grey[900],
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Center(
          child: Text(
            'No trades yet',
            style: TextStyle(color: Colors.white70),
          ),
        ),
      );
    }

    final recentTrades = tradeHistory.length > 50
        ? tradeHistory.sublist(tradeHistory.length - 50)
        : tradeHistory;

    return Column(
      children: recentTrades.map((trade) {
        final status = (trade['status']?.toString() ?? 'closed').toLowerCase();
        final isOpen = status == 'open';
        final isWinning = (trade['isWinning'] as bool?) ?? false;
        final profit = (trade['profit'] as num?) ?? 0;
        final currentPrice = (trade['currentPrice'] as num?)?.toDouble();
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.grey[900],
            border: Border.all(
              color: isOpen
                  ? Colors.cyan.withValues(alpha: 0.3)
                  : isWinning
                      ? Colors.green.withValues(alpha: 0.3)
                      : Colors.red.withValues(alpha: 0.3),
            ),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      trade['symbol'] ?? 'N/A',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${trade['type']} • Vol: ${trade['volume']}${currentPrice != null ? ' • Now: ${currentPrice.toStringAsFixed(currentPrice > 100 ? 2 : 5)}' : ''}',
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '\$${profit.toStringAsFixed(2)}',
                    style: TextStyle(
                      color: isOpen
                          ? Colors.cyan
                          : isWinning
                              ? Colors.green
                              : Colors.red,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isOpen
                        ? 'Open'
                        : isWinning
                            ? '✓ Win'
                            : '✗ Loss',
                    style: TextStyle(
                      color: isOpen
                          ? Colors.cyan
                          : isWinning
                              ? Colors.green
                              : Colors.red,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildBalanceCard() {
    final balance = (_botData['accountBalance'] ?? 0).toDouble();
    final equity = (_botData['accountEquity'] ?? 0).toDouble();
    final acctCur = ((_botData['accountCurrency'] ?? _botData['currency'] ?? 'USD') as String).toUpperCase();
    final acctSym = acctCur == 'ZAR' ? 'R' : (acctCur == 'GBP' ? '£' : (acctCur == 'EUR' ? '€' : r'$'));

    if (balance <= 0 && equity <= 0) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.blue.withValues(alpha: 0.15),
            Colors.cyan.withValues(alpha: 0.08)
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: Colors.cyan.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.cyan.withValues(alpha: 0.1),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          const Row(
            children: [
              Icon(Icons.account_balance_wallet, color: Colors.cyan, size: 22),
              SizedBox(width: 10),
              Text(
                'Account',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              Column(
                children: [
                  const Text('Balance',
                      style: TextStyle(color: Colors.white54, fontSize: 12)),
                  const SizedBox(height: 4),
                  Text(
                    '$acctSym${balance.toStringAsFixed(2)} $acctCur',
                    style: const TextStyle(
                        color: Colors.cyan,
                        fontSize: 22,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              Container(width: 1, height: 40, color: Colors.white12),
              Column(
                children: [
                  const Text('Equity',
                      style: TextStyle(color: Colors.white54, fontSize: 12)),
                  const SizedBox(height: 4),
                  Text(
                    '$acctSym${equity.toStringAsFixed(2)}',
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildOpenPositionsSection() {
    final openPositions = (_botData['openPositions'] as List?) ?? [];

    if (openPositions.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.grey[900],
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Row(
          children: [
            Icon(Icons.candlestick_chart, color: Colors.white38, size: 18),
            SizedBox(width: 10),
            Text('No open positions',
                style: TextStyle(color: Colors.white54, fontSize: 13)),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.candlestick_chart,
                color: Color(0xFFFFA726), size: 20),
            const SizedBox(width: 8),
            Text(
              'Open Positions (${openPositions.length})',
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 10),
        ...openPositions.map((pos) {
          final symbol = pos['symbol']?.toString() ?? '';
          final type = pos['type']?.toString() ?? '';
          final volume = (pos['volume'] ?? 0).toDouble();
          final entryPrice = (pos['entryPrice'] ?? 0).toDouble();
          final currentPrice = (pos['currentPrice'] ?? 0).toDouble();
          final profit = (pos['profit'] ?? 0).toDouble();
          final entryTime = pos['entryTime']?.toString() ?? '';
          final isBuy = type.toUpperCase().contains('BUY');

          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey[900],
              border: Border.all(
                color:
                    (isBuy ? Colors.green : Colors.red).withValues(alpha: 0.3),
              ),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: (isBuy ? Colors.green : Colors.red)
                        .withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    isBuy ? Icons.arrow_upward : Icons.arrow_downward,
                    color: isBuy ? Colors.green : Colors.red,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        symbol,
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '${isBuy ? "BUY" : "SELL"} • ${volume.toStringAsFixed(2)} lots • @ ${entryPrice.toStringAsFixed(entryPrice > 100 ? 2 : 5)}',
                        style: const TextStyle(
                            color: Colors.white60, fontSize: 12),
                      ),
                      if (currentPrice > 0 || profit != 0) ...[
                        const SizedBox(height: 3),
                        Text(
                          'Now: ${currentPrice.toStringAsFixed(currentPrice > 100 ? 2 : 5)} • P/L: \$${profit.toStringAsFixed(2)}',
                          style: TextStyle(
                            color: profit >= 0
                                ? Colors.greenAccent
                                : Colors.redAccent,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (entryTime.isNotEmpty)
                  Text(
                    entryTime.length > 16
                        ? entryTime.substring(11, 16)
                        : entryTime,
                    style: const TextStyle(color: Colors.white38, fontSize: 11),
                  ),
              ],
            ),
          );
        }),
      ],
    );
  }
}
