import 'package:flutter/material.dart';
// import 'package:fl_chart/fl_chart.dart'; // Disabled for compatibility
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'bot_configuration_screen.dart';
import 'bot_dashboard_screen.dart';
import '../services/ig_trading_service.dart';

class BotAnalyticsScreen extends StatefulWidget {
  final Map<String, dynamic> bot;

  const BotAnalyticsScreen({
    Key? key,
    required this.bot,
  }) : super(key: key);

  @override
  State<BotAnalyticsScreen> createState() => _BotAnalyticsScreenState();
}

class _BotAnalyticsScreenState extends State<BotAnalyticsScreen> {
  late Future<void> _analyticsLoad;
  Timer? _refreshTimer;

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
    final brokerType = widget.bot['broker_type'] ?? widget.bot['broker'] ?? 'MT5';
    _isIG = brokerType.toString().toUpperCase().contains('IG');

    _analyticsLoad = _refreshAnalytics();
    _refreshTimer = Timer.periodic(const Duration(seconds: 10), (timer) {
      if (mounted) {
        setState(() {
          _analyticsLoad = _refreshAnalytics();
        });
      }
    });

    if (_isIG) {
      _loadIGData();
    }
  }

  Future<void> _loadIGData() async {
    if (!_isIG) return;
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
    // Refresh bot data
    try {
      await Future.delayed(const Duration(milliseconds: 500));
      if (mounted) {
        setState(() {});
      }
    } catch (e) {
      print('Error refreshing analytics: $e');
    }
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  List<dynamic> _getProfitChartData() {
    // Chart disabled for fl_chart compatibility
    return [];
  }

  List<dynamic> _getTradesChartData() {
    // Chart disabled for fl_chart compatibility
    return [];
  }

  @override
  Widget build(BuildContext context) {
    try {
      const textStyle = TextStyle(
        color: Colors.white,
        fontWeight: FontWeight.bold,
        fontSize: 14,
      );

      final totalProfit = (widget.bot['totalProfit'] ?? 0).toDouble();
      final totalTrades = widget.bot['totalTrades']?.toInt() ?? 0;
      final winRate = (widget.bot['winRate'] ?? 0).toDouble();
      final roi = (widget.bot['roi'] ?? 0).toDouble();
      final runtimeFormatted = widget.bot['runtimeFormatted'] ?? '0h 0m';
      final dailyProfit = (widget.bot['dailyProfit'] ?? 0).toDouble();
      final avgProfitPerTrade = (widget.bot['avgProfitPerTrade'] ?? 0).toDouble();
      final maxDrawdown = (widget.bot['maxDrawdown'] ?? 0).toDouble();
      final botStatus = widget.bot['status'] ?? 'Unknown';

      return Scaffold(
        appBar: AppBar(
          title: Text(widget.bot['botId'] ?? 'Bot Analytics'),
          backgroundColor: Colors.grey[900],
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => Navigator.of(context).pop(),
          ),
          actions: [
            TextButton.icon(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (context) => const BotConfigurationScreen()),
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
              const SizedBox(height: 24),

              // Key Metrics Grid
              _buildMetricsGrid(
                totalProfit: totalProfit,
                totalTrades: totalTrades,
                winRate: winRate,
                roi: roi,
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
              if (widget.bot['dailyProfits'] != null && (widget.bot['dailyProfits'] as Map).isNotEmpty)
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
              icon: Icon(Icons.analytics),
              label: 'Analytics',
            ),
          ],
          onTap: (index) {
            if (index == 0) {
              Navigator.of(context).popUntil((route) => route.isFirst);
            }
          },
        ),
      );
    } catch (e) {
      print('Error building BotAnalyticsScreen: $e');
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
          colors: [statusColor.withOpacity(0.15), statusColor.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: statusColor.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: statusColor.withOpacity(0.2),
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
                      boxShadow: [BoxShadow(color: statusColor.withOpacity(0.5), blurRadius: 8)],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    status,
                    style: TextStyle(
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
                  Icon(Icons.schedule, color: Colors.white54, size: 16),
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
              Text(
                'Today\'s Profit',
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: dailyProfit >= 0 ? Colors.green.withOpacity(0.15) : Colors.red.withOpacity(0.15),
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
    required double avgProfitPerTrade,
    required double maxDrawdown,
  }) {
    return GridView.count(
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
  }

  Widget _buildMetricCard({
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color.withOpacity(0.15), color.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: color.withOpacity(0.4)),
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.15),
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
              color: color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: 10),
          Text(
            label,
            style: TextStyle(
              color: Colors.white70,
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
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
  }

  Widget _buildProfitChart() {
    return Container(
      height: 300,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.blue.withOpacity(0.1), Colors.purple.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.blue.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.blue.withOpacity(0.1),
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
            Text('Profit chart will appear here', style: TextStyle(color: Colors.white70, fontSize: 14)),
          ],
        ),
      ),
    );
  }

  Widget _buildTradesChart() {
    return Container(
      height: 300,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.purple.withOpacity(0.1), Colors.indigo.withOpacity(0.05)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.purple.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: Colors.purple.withOpacity(0.1),
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
            Text('Trades chart will appear here', style: TextStyle(color: Colors.white70, fontSize: 14)),
          ],
        ),
      ),
    );
  }

  Widget _buildDailyProfitsSection() {
    final dailyProfits = widget.bot['dailyProfits'] as Map?;
    if (dailyProfits == null || dailyProfits.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('Daily Profits'),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey[900],
            borderRadius: BorderRadius.circular(8),
          ),
          height: 250,
          child: const Center(
            child: Text(
              'Daily profits chart disabled for compatibility',
              style: TextStyle(color: Colors.white70),
            ),
          ),
        ),
      ],
    );
  }

  // ==================== IG WIDGETS ====================

  Widget _buildIGControlPanel() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFE91E63).withOpacity(0.08),
        border: Border.all(color: const Color(0xFFE91E63).withOpacity(0.4)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_balance, color: Color(0xFFE91E63), size: 22),
              const SizedBox(width: 8),
              const Text(
                'IG Trading Controls',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              if (_igLoading)
                const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFE91E63))),
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
                    setState(() => _igBalance = data['success'] == true ? data : _igBalance);
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
                      if (data['success'] == true) _igPositions = data['positions'] ?? [];
                    });
                    _showIGSnackBar('${_igPositions.length} open position(s)');
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
                      if (data['success'] == true) _igTransactions = data['transactions'] ?? [];
                    });
                    _showIGSnackBar('${_igTransactions.length} transaction(s) loaded');
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
            Text(_igError!, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
          ],
        ],
      ),
    );
  }

  Widget _igActionButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  Widget _buildIGBalanceCard() {
    if (_igBalance == null) {
      return const SizedBox.shrink();
    }
    final balance = (_igBalance!['balance'] ?? 0).toDouble();
    final available = (_igBalance!['available'] ?? 0).toDouble();
    final pnl = (_igBalance!['profitLoss'] ?? 0).toDouble();
    final currency = _igBalance!['currency'] ?? 'USD';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[900],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('IG Account Balance', style: TextStyle(color: Colors.white70, fontSize: 13)),
          const SizedBox(height: 10),
          Row(
            children: [
              _balanceStat('Balance', '\$${balance.toStringAsFixed(2)}', Colors.white),
              _balanceStat('Available', '\$${available.toStringAsFixed(2)}', Colors.blue),
              _balanceStat('P&L', '\$${pnl.toStringAsFixed(2)}', pnl >= 0 ? Colors.green : Colors.red),
            ],
          ),
          const SizedBox(height: 4),
          Text('Currency: $currency', style: const TextStyle(color: Colors.white38, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _balanceStat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: TextStyle(color: color, fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildIGPositionsSection() {
    if (_igPositions.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: Colors.grey[900], borderRadius: BorderRadius.circular(8)),
        child: const Center(child: Text('No open IG positions', style: TextStyle(color: Colors.white54))),
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
              border: Border.all(color: isBuy ? Colors.green.withOpacity(0.3) : Colors.red.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: (isBuy ? Colors.green : Colors.red).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(direction, style: TextStyle(color: isBuy ? Colors.green : Colors.red, fontSize: 11, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(pos['instrumentName'] ?? pos['epic'] ?? '', style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
                      Text('Size: ${pos['size']}  |  Level: ${pos['level']}', style: const TextStyle(color: Colors.white54, fontSize: 11)),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '\$${pnl.toStringAsFixed(2)}',
                      style: TextStyle(color: pnl >= 0 ? Colors.green : Colors.red, fontSize: 14, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    InkWell(
                      onTap: () => _closeIGPosition(pos),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('Close', style: TextStyle(color: Colors.redAccent, fontSize: 11, fontWeight: FontWeight.w600)),
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

    final recent = _igTransactions.length > 10 ? _igTransactions.sublist(0, 10) : _igTransactions;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('IG Transaction History'),
        const SizedBox(height: 8),
        ...recent.map((tx) {
          final pnlStr = tx['profitAndLoss']?.toString() ?? '0';
          final pnlNum = double.tryParse(pnlStr.replaceAll(RegExp(r'[^0-9.\-]'), '')) ?? 0;
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
                      Text(tx['instrumentName'] ?? '', style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                      Text('${tx['type'] ?? ''} | ${tx['date'] ?? ''}', style: const TextStyle(color: Colors.white38, fontSize: 10)),
                    ],
                  ),
                ),
                Text(
                  pnlStr,
                  style: TextStyle(color: pnlNum >= 0 ? Colors.green : Colors.red, fontSize: 13, fontWeight: FontWeight.bold),
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
        title: const Text('Close Position?', style: TextStyle(color: Colors.white)),
        content: Text(
          'Close ${pos['instrumentName'] ?? pos['epic']} ($direction, size: $size)?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Close', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await IGTradingService.closePosition(dealId: dealId, direction: closeDirection, size: size);
    _showIGSnackBar(result['success'] == true ? 'Position closed' : 'Error: ${result['error']}');
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
        title: const Text('Close ALL Positions?', style: TextStyle(color: Colors.white)),
        content: Text(
          'This will close all ${_igPositions.length} open IG position(s). Are you sure?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
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
    String epic = '';
    String direction = 'BUY';
    String sizeStr = '1';
    String? stopStr;
    String? limitStr;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              backgroundColor: Colors.grey[900],
              title: const Text('Place IG Trade', style: TextStyle(color: Colors.white)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Epic (e.g. CS.D.EURUSD.CFD.IP)',
                        labelStyle: TextStyle(color: Colors.white54),
                        enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                      ),
                      style: const TextStyle(color: Colors.white),
                      onChanged: (v) => epic = v,
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        const Text('Direction: ', style: TextStyle(color: Colors.white54)),
                        ChoiceChip(
                          label: const Text('BUY'),
                          selected: direction == 'BUY',
                          selectedColor: Colors.green,
                          onSelected: (_) => setDialogState(() => direction = 'BUY'),
                        ),
                        const SizedBox(width: 8),
                        ChoiceChip(
                          label: const Text('SELL'),
                          selected: direction == 'SELL',
                          selectedColor: Colors.red,
                          onSelected: (_) => setDialogState(() => direction = 'SELL'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Size',
                        labelStyle: TextStyle(color: Colors.white54),
                        enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
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
                        enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
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
                        enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                      ),
                      keyboardType: TextInputType.number,
                      style: const TextStyle(color: Colors.white),
                      onChanged: (v) => limitStr = v,
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.teal),
                  onPressed: () {
                    if (epic.isEmpty) return;
                    Navigator.pop(ctx, {
                      'epic': epic,
                      'direction': direction,
                      'size': double.tryParse(sizeStr) ?? 1,
                      'stopDistance': stopStr != null ? double.tryParse(stopStr!) : null,
                      'limitDistance': limitStr != null ? double.tryParse(limitStr!) : null,
                    });
                  },
                  child: const Text('Place Order'),
                ),
              ],
            );
          },
        );
      },
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
    String searchTerm = '';
    List<dynamic> searchResults = [];

    await showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              backgroundColor: Colors.grey[900],
              title: const Text('Search IG Markets', style: TextStyle(color: Colors.white)),
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
                        enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                      ),
                      style: const TextStyle(color: Colors.white),
                      onChanged: (v) => searchTerm = v,
                      onSubmitted: (_) async {
                        if (searchTerm.isEmpty) return;
                        final data = await IGTradingService.searchMarkets(searchTerm);
                        setDialogState(() {
                          searchResults = data['success'] == true ? (data['markets'] ?? []) : [];
                        });
                      },
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.indigo),
                      onPressed: () async {
                        if (searchTerm.isEmpty) return;
                        final data = await IGTradingService.searchMarkets(searchTerm);
                        setDialogState(() {
                          searchResults = data['success'] == true ? (data['markets'] ?? []) : [];
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
                              title: Text(m['instrumentName'] ?? '', style: const TextStyle(color: Colors.white, fontSize: 13)),
                              subtitle: Text(
                                '${m['epic']} | ${m['instrumentType'] ?? ''} | Bid: ${m['bid']} / Offer: ${m['offer']}',
                                style: const TextStyle(color: Colors.white38, fontSize: 10),
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
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
              ],
            );
          },
        );
      },
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
    final tradeHistory = widget.bot['tradeHistory'] as List?;
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

    final recentTrades = tradeHistory.length > 10
        ? tradeHistory.sublist(tradeHistory.length - 10)
        : tradeHistory;

    return Column(
      children: recentTrades.map((trade) {
        final isWinning = trade['isWinning'] as bool;
        final profit = trade['profit'] as num;
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.grey[900],
            border: Border.all(
              color: isWinning ? Colors.green.withOpacity(0.3) : Colors.red.withOpacity(0.3),
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
                      '${trade['type']} • Vol: ${trade['volume']}',
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
                      color: isWinning ? Colors.green : Colors.red,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isWinning ? '✓ Win' : '✗ Loss',
                    style: TextStyle(
                      color: isWinning ? Colors.green : Colors.red,
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
}
