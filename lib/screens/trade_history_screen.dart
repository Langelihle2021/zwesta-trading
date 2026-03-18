import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';
import '../services/auth_service.dart';

class TradeHistoryScreen extends StatefulWidget {
  const TradeHistoryScreen({Key? key}) : super(key: key);

  @override
  State<TradeHistoryScreen> createState() => _TradeHistoryScreenState();
}

class _TradeHistoryScreenState extends State<TradeHistoryScreen> {
  late Future<Map<String, dynamic>> _tradeDataFuture;
  late Future<Map<String, dynamic>> _tradeSummaryFuture;
  int _selectedTabIndex = 0;

  @override
  void initState() {
    super.initState();
    _refreshData();
  }

  void _refreshData() {
    setState(() {
      _tradeDataFuture = _fetchTradeHistory();
      _tradeSummaryFuture = _fetchTradeSummary();
    });
  }

  Future<Map<String, dynamic>> _fetchTradeHistory() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final userId = authService.currentUser?.id ?? 'unknown';

      final response = await http
          .get(
            Uri.parse(
              '${EnvironmentConfig.apiUrl}/api/broker/exness/trades?user_id=$userId&limit=100',
            ),
            headers: {
              'Authorization': 'Bearer ${authService.token}',
            },
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch trades');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  Future<Map<String, dynamic>> _fetchTradeSummary() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final userId = authService.currentUser?.id ?? 'unknown';

      final response = await http
          .get(
            Uri.parse(
              '${EnvironmentConfig.apiUrl}/api/broker/exness/trade-summary?user_id=$userId',
            ),
            headers: {
              'Authorization': 'Bearer ${authService.token}',
            },
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch summary');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  Future<Map<String, dynamic>> _fetchWithdrawalHistory() async {
    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      final userId = authService.currentUser?.id ?? 'unknown';

      final response = await http
          .get(
            Uri.parse(
              '${EnvironmentConfig.apiUrl}/api/broker/exness/withdrawal/history/$userId',
            ),
            headers: {
              'Authorization': 'Bearer ${authService.token}',
            },
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch withdrawals');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E27),
      appBar: AppBar(
        title: const Text('Trade History & Withdrawals'),
        backgroundColor: const Color(0xFF1A1F3A),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refreshData,
          ),
        ],
      ),
      body: Column(
        children: [
          // Tab selector
          TabSelector(
            selectedIndex: _selectedTabIndex,
            onTabChanged: (index) {
              setState(() {
                _selectedTabIndex = index;
              });
            },
          ),
          // Tab content
          Expanded(
            child: IndexedStack(
              index: _selectedTabIndex,
              children: [
                _buildTradesTab(),
                _buildWithdrawalsTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTradesTab() {
    return FutureBuilder<Map<String, dynamic>>(
      future: _tradeDataFuture,
      builder: (context, tradeSnapshot) {
        return FutureBuilder<Map<String, dynamic>>(
          future: _tradeSummaryFuture,
          builder: (context, summarySnapshot) {
            if (tradeSnapshot.connectionState == ConnectionState.waiting ||
                summarySnapshot.connectionState == ConnectionState.waiting) {
              return const Center(
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
                ),
              );
            }

            if (tradeSnapshot.hasError || summarySnapshot.hasError) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, color: Colors.red, size: 48),
                    const SizedBox(height: 16),
                    Text(
                      tradeSnapshot.hasError
                          ? 'Failed to load trades'
                          : 'Failed to load summary',
                      style: const TextStyle(color: Colors.white),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: _refreshData,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              );
            }

            final tradeData =
                tradeSnapshot.data?['trades'] as List<dynamic>? ?? [];
            final summary =
                summarySnapshot.data?['summary'] as Map<String, dynamic>? ?? {};

            return SingleChildScrollView(
              child: Column(
                children: [
                  // Summary Stats
                  if (summary.isNotEmpty) ...[
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        children: [
                          _buildSummaryCard(summary),
                          const SizedBox(height: 16),
                          _buildStatsGrid(summary),
                        ],
                      ),
                    ),
                  ],
                  // Trade List
                  if (tradeData.isEmpty)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        children: [
                          Icon(
                            Icons.trending_up,
                            size: 64,
                            color: Colors.blue.withOpacity(0.3),
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'No trades yet',
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 16,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Trade History (${tradeData.length})',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 12),
                          ListView.builder(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: tradeData.length,
                            itemBuilder: (context, index) {
                              final trade =
                                  tradeData[index] as Map<String, dynamic>;
                              return _buildTradeCard(trade);
                            },
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildSummaryCard(Map<String, dynamic> summary) {
    final netProfit = (summary['netProfit'] as num?)?.toDouble() ?? 0;
    final color =
        netProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          const Text(
            'Net Profit',
            style: TextStyle(
              color: Colors.white70,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '\$${netProfit.toStringAsFixed(2)}',
            style: TextStyle(
              color: color,
              fontSize: 32,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatsGrid(Map<String, dynamic> summary) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [
        _buildStatCard(
          'Total Trades',
          '${summary['totalTrades'] ?? 0}',
          Colors.blue,
        ),
        _buildStatCard(
          'Win Rate',
          '${(summary['winRate'] ?? 0).toStringAsFixed(1)}%',
          Colors.green,
        ),
        _buildStatCard(
          'Winning Trades',
          '${summary['winningTrades'] ?? 0}',
          const Color(0xFF69F0AE),
        ),
        _buildStatCard(
          'Losing Trades',
          '${summary['losingTrades'] ?? 0}',
          const Color(0xFFFF8A80),
        ),
        _buildStatCard(
          'Avg Win',
          '\$${(summary['avgProfit'] ?? 0).toStringAsFixed(2)}',
          const Color(0xFF69F0AE),
        ),
        _buildStatCard(
          'Avg Loss',
          '\$${(summary['avgLoss'] ?? 0).toStringAsFixed(2)}',
          const Color(0xFFFF8A80),
        ),
        _buildStatCard(
          'Largest Win',
          '\$${(summary['largestWin'] ?? 0).toStringAsFixed(2)}',
          const Color(0xFF69F0AE),
        ),
        _buildStatCard(
          'Largest Loss',
          '\$${(summary['largestLoss'] ?? 0).toStringAsFixed(2)}',
          const Color(0xFFFF8A80),
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 11,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTradeCard(Map<String, dynamic> trade) {
    final profitLoss = (trade['profitLoss'] as num?)?.toDouble() ?? 0;
    final pnlPercent = (trade['pnlPercentage'] as num?)?.toDouble() ?? 0;
    final color = profitLoss >= 0
        ? const Color(0xFF69F0AE)
        : const Color(0xFFFF8A80);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Symbol and P&L
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    trade['symbol'] ?? 'Unknown',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '${trade['side'] ?? 'N/A'} • ${trade['volume'] ?? 0}',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '\$${profitLoss.toStringAsFixed(2)}',
                    style: TextStyle(
                      color: color,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '${pnlPercent.toStringAsFixed(2)}%',
                    style: TextStyle(
                      color: color.withOpacity(0.7),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Details
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildTradeDetail('Entry', '\$${trade['entryPrice'] ?? 0}'),
              _buildTradeDetail('Exit', '\$${trade['exitPrice'] ?? 0}'),
              _buildTradeDetail('Commission', '\$${(trade['commission'] ?? 0).toStringAsFixed(2)}'),
            ],
          ),
          const SizedBox(height: 8),
          // Date
          Text(
            trade['closedAt'] ?? 'N/A',
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTradeDetail(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withOpacity(0.5),
            fontSize: 10,
          ),
        ),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _buildWithdrawalsTab() {
    return FutureBuilder<Map<String, dynamic>>(
      future: _fetchWithdrawalHistory(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
            ),
          );
        }

        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: Colors.red, size: 48),
                const SizedBox(height: 16),
                const Text(
                  'Failed to load withdrawals',
                  style: TextStyle(color: Colors.white),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: _refreshData,
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }

        final withdrawals =
            snapshot.data?['withdrawals'] as List<dynamic>? ?? [];

        if (withdrawals.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.account_balance_wallet,
                  size: 64,
                  color: Colors.blue.withOpacity(0.3),
                ),
                const SizedBox(height: 16),
                const Text(
                  'No withdrawals yet',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          );
        }

        return SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Withdrawal History (${withdrawals.length})',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: withdrawals.length,
                  itemBuilder: (context, index) {
                    final withdrawal =
                        withdrawals[index] as Map<String, dynamic>;
                    return _buildWithdrawalCard(withdrawal);
                  },
                ),
              ],
            ),
          );
      },
    );
  }

  Widget _buildWithdrawalCard(Map<String, dynamic> withdrawal) {
    final status = withdrawal['status'] ?? 'pending';
    final statusColor = _getStatusColor(status);
    final amount = (withdrawal['total_amount'] as num?)?.toDouble() ?? 0;
    final fee = (withdrawal['fee'] as num?)?.toDouble() ?? 0;
    final netAmount = (withdrawal['net_amount'] as num?)?.toDouble() ?? 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: statusColor.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: Amount and Status
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '\$${amount.toStringAsFixed(2)}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    withdrawal['withdrawal_method'] ?? 'Unknown',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      status.toUpperCase(),
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Details
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildTradeDetail('Profit', '\$${(withdrawal['profit_from_trades'] ?? 0).toStringAsFixed(2)}'),
              _buildTradeDetail('Commission', '\$${(withdrawal['commission_earned'] ?? 0).toStringAsFixed(2)}'),
              _buildTradeDetail('Fee', '\$${fee.toStringAsFixed(2)}'),
              _buildTradeDetail('Net', '\$${netAmount.toStringAsFixed(2)}'),
            ],
          ),
          const SizedBox(height: 8),
          // Date
          Text(
            'Created: ${withdrawal['created_at'] ?? 'N/A'}',
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 11,
            ),
          ),
          if (withdrawal['completed_at'] != null)
            Text(
              'Completed: ${withdrawal['completed_at']}',
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 11,
              ),
            ),
        ],
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'success':
        return const Color(0xFF69F0AE);
      case 'pending':
      case 'submitted':
      case 'processing':
        return const Color(0xFFFFD600);
      case 'failed':
      case 'rejected':
        return const Color(0xFFFF8A80);
      default:
        return Colors.blue;
    }
  }
}

class TabSelector extends StatelessWidget {
  final int selectedIndex;
  final Function(int) onTabChanged;

  const TabSelector({
    Key? key,
    required this.selectedIndex,
    required this.onTabChanged,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF1A1F3A),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          _buildTabButton(
            'Trades',
            0,
          ),
          const SizedBox(width: 8),
          _buildTabButton(
            'Withdrawals',
            1,
          ),
        ],
      ),
    );
  }

  Widget _buildTabButton(String label, int index) {
    final isSelected = selectedIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => onTabChanged(index),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: isSelected ? Colors.blue : Colors.transparent,
                width: 2,
              ),
            ),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isSelected ? Colors.blue : Colors.white70,
              fontSize: 14,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ),
      ),
    );
  }
}
