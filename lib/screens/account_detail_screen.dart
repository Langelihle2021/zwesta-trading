import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';

class AccountDetailScreen extends StatefulWidget {

  const AccountDetailScreen({required this.account, Key? key}) : super(key: key);
  final Map<String, dynamic> account;

  @override
  State<AccountDetailScreen> createState() => _AccountDetailScreenState();
}

class _AccountDetailScreenState extends State<AccountDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  Map<String, dynamic>? _details;
  bool _isLoading = true;
  String? _error;

  String get _currencyCode {
    final account = _details?['account'];
    final liveAccountInfo = account is Map<String, dynamic>
        ? account['liveAccountInfo'] as Map<String, dynamic>?
        : null;
    return (liveAccountInfo?['currency'] ??
            widget.account['currency'] ??
            widget.account['account_currency'] ??
            'USD')
        .toString()
        .toUpperCase();
  }

  String get _currencySymbol {
    switch (_currencyCode) {
      case 'ZAR':
        return 'R';
      case 'GBP':
        return '£';
      case 'EUR':
        return '€';
      default:
        return r'$';
    }
  }

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _fetchDetails();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _fetchDetails() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final credentialId = widget.account['credentialId'];

      if (sessionToken == null || credentialId == null) {
        setState(() {
          _error = 'Missing authentication or account info';
          _isLoading = false;
        });
        return;
      }

      final response = await http.get(
        Uri.parse(
            '${EnvironmentConfig.apiUrl}/api/accounts/$credentialId/details'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          setState(() {
            _details = data;
            _isLoading = false;
          });
        } else {
          setState(() {
            _error = data['error'] ?? 'Failed to load details';
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _error = 'Server error: ${response.statusCode}';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Connection error: $e';
        _isLoading = false;
      });
    }
  }

  String _fmt(dynamic amount) {
    final val = (amount is num) ? amount.toDouble() : 0.0;
    final neg = val < 0;
    final abs = val.abs();
    final formatted = abs.toStringAsFixed(2).replaceAllMapped(
        RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    return neg
        ? '-$_currencySymbol$formatted $_currencyCode'
        : '$_currencySymbol$formatted $_currencyCode';
  }

  Color _profitColor(dynamic amount) {
    final val = (amount is num) ? amount.toDouble() : 0.0;
    if (val > 0) return Colors.green;
    if (val < 0) return Colors.red;
    return Colors.grey;
  }

  @override
  Widget build(BuildContext context) {
    final broker = widget.account['broker'] ?? 'Unknown';
    final accountNum =
        widget.account['accountNumber'] ?? widget.account['account_number'] ?? 'N/A';
    final isLive = widget.account['is_live'] ?? false;

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0E21),
        elevation: 0,
        title: Text('$broker #$accountNum',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchDetails,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(isLive),
    );
  }

  Widget _buildError() => Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: Colors.red.shade400),
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _fetchDetails,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );

  Widget _buildContent(bool isLive) {
    final account = _details!['account'] ?? {};
    final stats = _details!['tradeStats'] ?? {};
    final withdrawals = _details!['withdrawals'] ?? {};
    final commissions = _details!['commissions'] ?? {};

    return Column(
      children: [
        // Account Summary Header
        _buildAccountHeader(account, isLive),

        // Profit/Loss Summary Bar
        _buildProfitSummaryBar(stats, withdrawals, commissions),

        // Tab Bar
        Container(
          color: Colors.white.withOpacity(0.05),
          child: TabBar(
            controller: _tabController,
            indicatorColor: Colors.blue,
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white38,
            tabs: const [
              Tab(text: 'Trades'),
              Tab(text: 'Withdrawals'),
              Tab(text: 'Summary'),
            ],
          ),
        ),

        // Tab Content
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildTradesTab(stats),
              _buildWithdrawalsTab(withdrawals),
              _buildSummaryTab(stats, withdrawals, commissions),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildAccountHeader(Map<String, dynamic> account, bool isLive) {
    final balance = account['balance'] ?? 0.0;
    final equity = account['equity'] ?? 0.0;
    final marginFree = account['marginFree'] ?? 0.0;
    final activeBots = account['activeBots'] ?? 0;
    final totalBots = account['totalBots'] ?? 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isLive
              ? [const Color(0xFF1A0A0A), const Color(0xFF2A1515)]
              : [const Color(0xFF0A1A0A), const Color(0xFF152A15)],
        ),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Balance',
                      style: TextStyle(
                          color: Colors.white54, fontSize: 12)),
                  Text(_fmt(balance),
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 28,
                          fontWeight: FontWeight.bold)),
                ],
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: isLive
                      ? Colors.red.withOpacity(0.2)
                      : Colors.green.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                      color: isLive
                          ? Colors.red.withOpacity(0.5)
                          : Colors.green.withOpacity(0.5)),
                ),
                child: Text(
                  isLive ? 'LIVE' : 'DEMO',
                  style: TextStyle(
                    color: isLive ? Colors.red.shade300 : Colors.green.shade300,
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _headerStatBox('Equity', _fmt(equity), Colors.purple),
              const SizedBox(width: 8),
              _headerStatBox('Free Margin', _fmt(marginFree), Colors.blue),
              const SizedBox(width: 8),
              _headerStatBox(
                  'Bots', '$activeBots / $totalBots', Colors.orange),
            ],
          ),
        ],
      ),
    );
  }

  Widget _headerStatBox(String label, String value, Color color) => Expanded(
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label,
                style: TextStyle(color: color.withOpacity(0.8), fontSize: 10)),
            const SizedBox(height: 4),
            Text(value,
                style: TextStyle(
                    color: color,
                    fontSize: 13,
                    fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );

  Widget _buildProfitSummaryBar(Map<String, dynamic> stats,
      Map<String, dynamic> withdrawals, Map<String, dynamic> commissions) {
    final netProfit = stats['netProfit'] ?? 0.0;
    final totalWithdrawn = withdrawals['totalWithdrawn'] ?? 0.0;
    final totalCommission = commissions['totalEarned'] ?? 0.0;
    final deductions =
        (stats['totalCommission'] ?? 0.0).abs() + (stats['totalSwap'] ?? 0.0).abs();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: Colors.white.withOpacity(0.03),
      child: Row(
        children: [
          _miniStat('Net P&L', _fmt(netProfit), _profitColor(netProfit)),
          _divider(),
          _miniStat('Withdrawn', _fmt(totalWithdrawn), Colors.amber),
          _divider(),
          _miniStat('Fees', _fmt(deductions), Colors.red.shade300),
          _divider(),
          _miniStat('Commission', _fmt(totalCommission), Colors.teal),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value, Color color) => Expanded(
      child: Column(
        children: [
          Text(value,
              style: TextStyle(
                  color: color, fontSize: 13, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label,
              style:
                  const TextStyle(color: Colors.white38, fontSize: 10)),
        ],
      ),
    );

  Widget _divider() => Container(
        width: 1, height: 30, color: Colors.white.withOpacity(0.1));

  // --- TRADES TAB ---
  Widget _buildTradesTab(Map<String, dynamic> stats) {
    final trades = List<Map<String, dynamic>>.from(
        _details!['recentTrades'] ?? []);
    final winRate = stats['winRate'] ?? 0.0;
    final winning = stats['winningTrades'] ?? 0;
    final losing = stats['losingTrades'] ?? 0;

    return Column(
      children: [
        // Win/Loss bar
        Container(
          padding: const EdgeInsets.all(12),
          color: Colors.white.withOpacity(0.03),
          child: Row(
            children: [
              Icon(Icons.pie_chart, color: Colors.blue.shade300, size: 18),
              const SizedBox(width: 8),
              Text('Win Rate: ${winRate.toStringAsFixed(1)}%',
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.bold)),
              const Spacer(),
              Text('$winning W',
                  style: const TextStyle(color: Colors.green, fontSize: 12)),
              const SizedBox(width: 8),
              Text('$losing L',
                  style: const TextStyle(color: Colors.red, fontSize: 12)),
              const SizedBox(width: 8),
              Text('${stats['openTrades'] ?? 0} Open',
                  style:
                      const TextStyle(color: Colors.amber, fontSize: 12)),
            ],
          ),
        ),

        // Trade list
        Expanded(
          child: trades.isEmpty
              ? const Center(
                  child: Text('No trades recorded yet',
                      style: TextStyle(color: Colors.white38)))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  itemCount: trades.length,
                  itemBuilder: (context, index) =>
                      _buildTradeRow(trades[index]),
                ),
        ),
      ],
    );
  }

  Widget _buildTradeRow(Map<String, dynamic> trade) {
    final symbol = trade['symbol'] ?? '???';
    final orderType = trade['order_type'] ?? '';
    final profit = (trade['profit'] as num?)?.toDouble() ?? 0.0;
    final volume = (trade['volume'] as num?)?.toDouble() ?? 0.0;
    final status = trade['status'] ?? 'open';
    final commission = (trade['commission'] as num?)?.toDouble() ?? 0.0;
    final swap = (trade['swap'] as num?)?.toDouble() ?? 0.0;
    final botName = trade['bot_name'] ?? trade['bot_id'] ?? '';
    final isBuy = orderType.toUpperCase().contains('BUY');
    final isClosed = status == 'closed';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        children: [
          // Buy/Sell indicator
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: (isBuy ? Colors.green : Colors.red).withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              isBuy ? Icons.trending_up : Icons.trending_down,
              color: isBuy ? Colors.green : Colors.red,
              size: 18,
            ),
          ),
          const SizedBox(width: 12),

          // Symbol & details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(symbol,
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 13)),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: isClosed
                            ? Colors.grey.withOpacity(0.2)
                            : Colors.blue.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        isClosed ? 'CLOSED' : 'OPEN',
                        style: TextStyle(
                            fontSize: 9,
                            color: isClosed ? Colors.grey : Colors.blue),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  '${orderType.toUpperCase()} ${volume.toStringAsFixed(2)} lots  |  $botName',
                  style:
                      const TextStyle(color: Colors.white38, fontSize: 11),
                ),
                if (commission != 0 || swap != 0)
                  Text(
                    'Comm: ${_fmt(commission)}  Swap: ${_fmt(swap)}',
                    style: const TextStyle(
                        color: Colors.white24, fontSize: 10),
                  ),
              ],
            ),
          ),

          // Profit
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                _fmt(profit),
                style: TextStyle(
                    color: _profitColor(profit),
                    fontWeight: FontWeight.bold,
                    fontSize: 14),
              ),
              Text(
                'net: ${_fmt(profit + commission + swap)}',
                style: const TextStyle(color: Colors.white30, fontSize: 10),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // --- WITHDRAWALS TAB ---
  Widget _buildWithdrawalsTab(Map<String, dynamic> withdrawals) {
    final history = List<Map<String, dynamic>>.from(
        withdrawals['history'] ?? []);
    final totalWithdrawn = withdrawals['totalWithdrawn'] ?? 0.0;
    final count = withdrawals['count'] ?? 0;

    return Column(
      children: [
        // Summary
        Container(
          padding: const EdgeInsets.all(12),
          color: Colors.white.withOpacity(0.03),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Total Withdrawn: ${_fmt(totalWithdrawn)}',
                  style: const TextStyle(
                      color: Colors.amber, fontWeight: FontWeight.bold)),
              Text('$count withdrawals',
                  style: const TextStyle(color: Colors.white38, fontSize: 12)),
            ],
          ),
        ),

        Expanded(
          child: history.isEmpty
              ? const Center(
                  child: Text('No withdrawals yet',
                      style: TextStyle(color: Colors.white38)))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  itemCount: history.length,
                  itemBuilder: (context, index) =>
                      _buildWithdrawalRow(history[index]),
                ),
        ),
      ],
    );
  }

  Widget _buildWithdrawalRow(Map<String, dynamic> w) {
    final amount = (w['total_amount'] as num?)?.toDouble() ?? 0.0;
    final fee = (w['fee'] as num?)?.toDouble() ?? 0.0;
    final netAmount = (w['net_amount'] as num?)?.toDouble() ?? amount - fee;
    final status = w['status'] ?? 'pending';
    final type = w['withdrawal_type'] ?? 'withdrawal';
    final method = w['withdrawal_method'] ?? '';
    final date = w['created_at'] ?? '';

    Color statusColor;
    switch (status) {
      case 'completed':
        statusColor = Colors.green;
        break;
      case 'pending':
        statusColor = Colors.amber;
        break;
      case 'failed':
        statusColor = Colors.red;
        break;
      default:
        statusColor = Colors.grey;
    }

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: Colors.amber.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.account_balance_wallet,
                color: Colors.amber, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(type.toUpperCase(),
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 13)),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(status.toUpperCase(),
                          style:
                              TextStyle(fontSize: 9, color: statusColor)),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  method.isNotEmpty
                      ? 'Via $method  |  $date'
                      : date,
                  style:
                      const TextStyle(color: Colors.white38, fontSize: 11),
                ),
                if (fee > 0)
                  Text('Fee: ${_fmt(fee)}',
                      style:
                          const TextStyle(color: Colors.white24, fontSize: 10)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_fmt(netAmount),
                  style: const TextStyle(
                      color: Colors.amber,
                      fontWeight: FontWeight.bold,
                      fontSize: 14)),
              if (fee > 0)
                Text('Gross: ${_fmt(amount)}',
                    style:
                        const TextStyle(color: Colors.white30, fontSize: 10)),
            ],
          ),
        ],
      ),
    );
  }

  // --- SUMMARY TAB ---
  Widget _buildSummaryTab(Map<String, dynamic> stats,
      Map<String, dynamic> withdrawals, Map<String, dynamic> commissions) {
    final grossProfit = stats['grossProfit'] ?? 0.0;
    final totalComm = stats['totalCommission'] ?? 0.0;
    final totalSwap = stats['totalSwap'] ?? 0.0;
    final netProfit = stats['netProfit'] ?? 0.0;
    final totalWithdrawn = withdrawals['totalWithdrawn'] ?? 0.0;
    final commissionEarned = commissions['totalEarned'] ?? 0.0;
    final deductions = totalComm.abs() + totalSwap.abs();
    final availableProfit = netProfit - totalWithdrawn;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Financial Summary',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),

          // Main P&L card
          _summaryCard(
            'Profit & Loss',
            Icons.show_chart,
            Colors.blue,
            [
              _summaryRow(
                  'Winning Trades', _fmt(stats['totalProfit'] ?? 0), Colors.green),
              _summaryRow(
                  'Losing Trades', _fmt(stats['totalLoss'] ?? 0), Colors.red),
              _summaryDivider(),
              _summaryRow('Gross P&L', _fmt(grossProfit), _profitColor(grossProfit),
                  bold: true),
            ],
          ),

          const SizedBox(height: 12),

          // Deductions card
          _summaryCard(
            'Deductions & Fees',
            Icons.receipt_long,
            Colors.red.shade300,
            [
              _summaryRow('Broker Commission', _fmt(totalComm), Colors.red.shade300),
              _summaryRow('Swap Fees', _fmt(totalSwap), Colors.red.shade300),
              _summaryDivider(),
              _summaryRow('Total Deductions', _fmt(deductions),
                  Colors.red.shade300,
                  bold: true),
            ],
          ),

          const SizedBox(height: 12),

          // Net Profit card
          _summaryCard(
            'Net Profit',
            Icons.account_balance,
            _profitColor(netProfit),
            [
              _summaryRow('Gross P&L', _fmt(grossProfit), Colors.white70),
              _summaryRow('- Deductions', _fmt(deductions), Colors.red.shade300),
              _summaryDivider(),
              _summaryRow(
                  'Net Profit', _fmt(netProfit), _profitColor(netProfit),
                  bold: true, large: true),
            ],
          ),

          const SizedBox(height: 12),

          // Withdrawals & Available
          _summaryCard(
            'Withdrawals & Available',
            Icons.account_balance_wallet,
            Colors.amber,
            [
              _summaryRow(
                  'Total Withdrawn', _fmt(totalWithdrawn), Colors.amber),
              _summaryRow('Commission Earned', _fmt(commissionEarned),
                  Colors.teal),
              _summaryDivider(),
              _summaryRow('Available Profit', _fmt(availableProfit),
                  _profitColor(availableProfit),
                  bold: true),
            ],
          ),

          const SizedBox(height: 12),

          // Trade Statistics card
          _summaryCard(
            'Trade Statistics',
            Icons.bar_chart,
            Colors.purple,
            [
              _summaryRow('Total Trades',
                  '${stats['totalTrades'] ?? 0}', Colors.white70),
              _summaryRow('Open Trades',
                  '${stats['openTrades'] ?? 0}', Colors.blue),
              _summaryRow('Closed Trades',
                  '${stats['closedTrades'] ?? 0}', Colors.grey),
              _summaryRow('Win Rate',
                  '${(stats['winRate'] ?? 0.0).toStringAsFixed(1)}%',
                  Colors.green),
            ],
          ),

          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _summaryCard(
      String title, IconData icon, Color color, List<Widget> children) => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Text(title,
                  style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.bold,
                      fontSize: 14)),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );

  Widget _summaryRow(String label, String value, Color valueColor,
      {bool bold = false, bool large = false}) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(
                  color: Colors.white54,
                  fontSize: large ? 14 : 13)),
          Text(value,
              style: TextStyle(
                  color: valueColor,
                  fontWeight: bold ? FontWeight.bold : FontWeight.normal,
                  fontSize: large ? 18 : 13)),
        ],
      ),
    );

  Widget _summaryDivider() => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Divider(color: Colors.white.withOpacity(0.1), height: 1),
    );
}
