import 'package:flutter/material.dart';

import '../models/broker_connection_model.dart';
import '../services/broker_connection_service.dart';
import '../services/connection_analytics_service.dart';
import '../utils/constants.dart';
import '../widgets/logo_widget.dart';

class BrokerAnalyticsDashboard extends StatefulWidget {

  const BrokerAnalyticsDashboard({
    Key? key,
    this.onBackPressed,
  }) : super(key: key);
  final VoidCallback? onBackPressed;

  @override
  State<BrokerAnalyticsDashboard> createState() =>
      _BrokerAnalyticsDashboardState();
}

class _BrokerAnalyticsDashboardState extends State<BrokerAnalyticsDashboard>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  List<BrokerAccount> _accounts = [];
  BrokerAccount? _selectedAccount;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadAccounts();
  }

  void _loadAccounts() async {
    setState(() => _isLoading = true);
    final accounts = BrokerConnectionService.getSavedAccounts();
    setState(() {
      _accounts = accounts;
      if (accounts.isNotEmpty && _selectedAccount == null) {
        _selectedAccount = accounts.first;
      }
      _isLoading = false;
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    BrokerConnectionService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Row(
            children: [
              LogoWidget(size: 40, showText: false),
              SizedBox(width: 12),
              Text('Broker Analytics Dashboard'),
            ],
          ),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed:
                widget.onBackPressed ?? () => Navigator.of(context).pop(),
          ),
          elevation: 0,
          bottom: TabBar(
            controller: _tabController,
            tabs: const [
              Tab(icon: Icon(Icons.dashboard), text: 'Overview'),
              Tab(icon: Icon(Icons.show_chart), text: 'Performance'),
              Tab(icon: Icon(Icons.assessment), text: 'Analytics'),
              Tab(icon: Icon(Icons.account_balance), text: 'Accounts'),
            ],
          ),
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                controller: _tabController,
                children: [
                  _buildOverviewTab(),
                  _buildPerformanceTab(),
                  _buildAnalyticsTab(),
                  _buildAccountsTab(),
                ],
              ),
      ),
    );

  Widget _buildOverviewTab() {
    if (_selectedAccount == null) {
      return const Center(child: Text('No accounts connected'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAccountSelector(),
          const SizedBox(height: 24),
          _buildHealthScoreWidget(),
          const SizedBox(height: 24),
          _buildConnectionStatusCard(),
          const SizedBox(height: 24),
          _buildAccountBalanceCard(),
          const SizedBox(height: 24),
          _buildQuickStatsGrid(),
        ],
      ),
    );
  }

  Widget _buildAccountSelector() => Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: DropdownButton<BrokerAccount>(
          value: _selectedAccount,
          isExpanded: true,
          underline: const SizedBox(),
          onChanged: (newValue) {
            if (newValue != null) {
              setState(() => _selectedAccount = newValue);
            }
          },
          items: _accounts.map((account) => DropdownMenuItem<BrokerAccount>(
              value: account,
              child: Text(
                '${account.brokerName} - ${account.accountNumber}',
                style: const TextStyle(fontSize: 12),
              ),
            )).toList(),
        ),
      ),
    );

  Widget _buildHealthScoreWidget() {
    if (_selectedAccount == null) return const SizedBox();

    final healthScore = ConnectionAnalyticsService.getConnectionHealthScore(
        _selectedAccount!.id);
    final Color scoreColor =
        healthScore > 80 ? Colors.green : healthScore > 50 ? Colors.orange : Colors.red;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Text(
              'CONNECTION HEALTH SCORE',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 150,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 120,
                    height: 120,
                    child: CircularProgressIndicator(
                      value: healthScore / 100,
                      strokeWidth: 8,
                      valueColor: AlwaysStoppedAnimation(scoreColor),
                      backgroundColor: Colors.grey[700],
                    ),
                  ),
                  Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$healthScore',
                        style: TextStyle(
                          fontSize: 48,
                          fontWeight: FontWeight.bold,
                          color: scoreColor,
                        ),
                      ),
                      const Text(
                        'Health %',
                        style: TextStyle(fontSize: 12, color: Colors.white70),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Text(
              _getHealthDescription(healthScore),
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, color: Colors.white70),
            ),
          ],
        ),
      ),
    );
  }

  String _getHealthDescription(int score) {
    if (score > 85) return '✓ Excellent connection stability';
    if (score > 70) return '⚠ Good connection, minor issues detected';
    if (score > 50) return '⚠ Fair connection quality';
    return '✗ Poor connection - consider reconnecting';
  }

  Widget _buildConnectionStatusCard() {
    final stats = ConnectionAnalyticsService.getPerformanceSummary(
        _selectedAccount?.id ?? '');

    return Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Connection Status',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatItem(
                  'Uptime',
                  '${stats.uptime.toStringAsFixed(1)}%',
                  Icons.access_time,
                ),
                _buildStatItem(
                  'Latency',
                  '${stats.averageLatency.toStringAsFixed(0)}ms',
                  Icons.speed,
                ),
                _buildStatItem(
                  'Connections',
                  '${stats.totalConnections}',
                  Icons.cloud_done,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon) => Column(
      children: [
        Icon(icon, color: AppColors.primaryColor),
        const SizedBox(height: 8),
        Text(
          value,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: Colors.white70),
        ),
      ],
    );

  Widget _buildAccountBalanceCard() {
    if (_selectedAccount == null) return const SizedBox();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Account Balance',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            StreamBuilder<ConnectionMetric>(
              stream: BrokerConnectionService.monitorConnection(
                accountId: _selectedAccount!.id,
              ),
              builder: (context, snapshot) {
                final balance = snapshot.hasData
                    ? snapshot.data!.accountBalance
                    : _selectedAccount!.accountBalance;

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '\$${balance.toStringAsFixed(2)}',
                      style: const TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: AppColors.successColor,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Text(
                          '${_selectedAccount!.isDemo ? 'DEMO' : 'LIVE'} Account',
                          style: TextStyle(
                            fontSize: 12,
                            color: _selectedAccount!.isDemo
                                ? Colors.orange
                                : Colors.red,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Text(
                          'Leverage: ${_selectedAccount!.leverage}x',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
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

  Widget _buildQuickStatsGrid() {
    final requirements =
        BrokerConnectionService.getBrokerRequirements(_selectedAccount?.brokerName ?? '');

    return GridView.count(
      crossAxisCount: 2,
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      children: [
        _buildStatCard(
          'Min Balance',
          '\$${requirements?.minBalance.toStringAsFixed(0) ?? 'N/A'}',
          Icons.account_balance_wallet,
        ),
        _buildStatCard(
          'Max Leverage',
          '${requirements?.maxLeverage.toStringAsFixed(0)}x',
          Icons.trending_up,
        ),
        _buildStatCard(
          'Avg Spread',
          '${_selectedAccount?.spreadAverage.toStringAsFixed(1)}',
          Icons.show_chart,
        ),
        _buildStatCard(
          'Min Spread',
          '${requirements?.minSpread.toStringAsFixed(1)}',
          Icons.arrow_downward,
        ),
      ],
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: AppColors.primaryColor),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(
              title,
              style: const TextStyle(fontSize: 10, color: Colors.white70),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );

  Widget _buildPerformanceTab() {
    if (_selectedAccount == null) {
      return const Center(child: Text('No account selected'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Performance Metrics',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Account Equity Growth'),
                  const SizedBox(height: 20),
                  Container(
                    height: 200,
                    decoration: BoxDecoration(
                      color: Colors.grey[900],
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.show_chart, size: 64, color: Colors.grey),
                          SizedBox(height: 16),
                          Text('Real-time Equity Chart'),
                          Text('Streaming data enabled',
                              style: TextStyle(
                                  fontSize: 12, color: Colors.white70)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'Latency Trends (24H)',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Container(
                height: 200,
                decoration: BoxDecoration(
                  color: Colors.grey[900],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.bar_chart, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text('Latency Analytics'),
                      Text('Historical data tracking',
                          style: TextStyle(fontSize: 12, color: Colors.white70)),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalyticsTab() {
    if (_selectedAccount == null) {
      return const Center(child: Text('No account selected'));
    }

    final summary = ConnectionAnalyticsService.getPerformanceSummary(
        _selectedAccount!.id);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Performance Analytics',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 16),
          _buildAnalyticsCard(
            'Connection Success Rate',
            '${summary.successfulConnections}/${summary.totalConnections}',
            '${((summary.successfulConnections / (summary.totalConnections > 0 ? summary.totalConnections : 1)) * 100).toStringAsFixed(1)}%',
          ),
          const SizedBox(height: 12),
          _buildAnalyticsCard(
            'Average Latency',
            '${summary.averageLatency.toStringAsFixed(1)}ms',
            'milliseconds',
          ),
          const SizedBox(height: 12),
          _buildAnalyticsCard(
            'Peak Latency',
            '${summary.peakLatency.toStringAsFixed(1)}ms',
            'maximum',
          ),
          const SizedBox(height: 12),
          _buildAnalyticsCard(
            'Minimum Latency',
            '${summary.minLatency.toStringAsFixed(1)}ms',
            'minimum',
          ),
          const SizedBox(height: 24),
          Card(
            color: Colors.grey[900],
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Uptime Analysis',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: summary.uptime / 100,
                      minHeight: 40,
                      backgroundColor: Colors.grey[800],
                      valueColor: AlwaysStoppedAnimation(
                        summary.uptime > 95 ? Colors.green : Colors.orange,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '${summary.uptime.toStringAsFixed(2)}% Uptime',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalyticsCard(
      String title, String value, String subtitle) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 10,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
            Text(
              value,
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 18,
                color: AppColors.primaryColor,
              ),
            ),
          ],
        ),
      ),
    );

  Widget _buildAccountsTab() => ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _accounts.length,
      itemBuilder: (context, index) {
        final account = _accounts[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: Icon(
              account.isDemo ? Icons.school : Icons.trending_up,
              color: account.isDemo ? Colors.orange : Colors.green,
            ),
            title: Text('${account.brokerName} - ${account.accountNumber}'),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                Text('Server: ${account.server}'),
                Text(
                  'Balance: \$${account.accountBalance.toStringAsFixed(2)}',
                ),
              ],
            ),
            trailing: Chip(
              label: Text(
                account.isDemo ? 'DEMO' : 'LIVE',
                style: const TextStyle(fontSize: 10),
              ),
              backgroundColor:
                  account.isDemo ? Colors.orange : Colors.green,
            ),
            selected: _selectedAccount?.id == account.id,
            onTap: () => setState(() => _selectedAccount = account),
          ),
        );
      },
    );
}
