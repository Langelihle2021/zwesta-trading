import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/bot_service.dart';
import 'bot_configuration_screen.dart';

class BotDashboardScreen extends StatefulWidget {
  final String accountId;
  final double accountBalance;

  const BotDashboardScreen({
    Key? key,
    required this.accountId,
    required this.accountBalance,
  }) : super(key: key);

  @override
  State<BotDashboardScreen> createState() => _BotDashboardScreenState();
}

class _BotDashboardScreenState extends State<BotDashboardScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.grey.shade900,
        title: Row(
          children: [
            Image.asset(
              'assets/images/logo.jpeg',
              height: 32,
              width: 32,
              fit: BoxFit.contain,
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ZWESTA BOT DASHBOARD',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  'Automated Trading Bot',
                  style: TextStyle(
                    color: Colors.cyan,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => BotConfigurationScreen(
                    accountId: widget.accountId,
                  ),
                ),
              );
            },
            tooltip: 'Configure Bot',
          ),
        ],
      ),
      body: Consumer<BotService>(
        builder: (context, botService, _) {
          final config = botService.getConfig(widget.accountId);
          final stats = botService.getStats(widget.accountId);

          if (config == null || stats == null) {
            return const Center(child: CircularProgressIndicator());
          }

          final winRate = botService.getWinRate(widget.accountId);
          final monthlyFee = 1000.0; // R1000
          final commissionRate = 0.15; // 15%
          final grossProfit = stats.totalProfitLoss;
          final commission = grossProfit > 0 ? grossProfit * commissionRate : 0;
          final netProfit = grossProfit - commission;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Bot Status Card
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Bot Status',
                            style: TextStyle(color: Colors.grey),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Container(
                                width: 10,
                                height: 10,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: config.isEnabled ? Colors.green : Colors.red,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                config.isEnabled ? 'ACTIVE' : 'INACTIVE',
                                style: TextStyle(
                                  color: config.isEnabled ? Colors.green : Colors.red,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
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
                            'Current Balance',
                            style: TextStyle(color: Colors.grey),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '\$${widget.accountBalance.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Colors.cyan,
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Performance Metrics
              Row(
                children: [
                  Expanded(
                    child: _buildMetricCard(
                      'Total Trades',
                      stats.totalTrades.toString(),
                      Colors.cyan,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildMetricCard(
                      'Win Rate',
                      '${winRate.toStringAsFixed(1)}%',
                      winRate >= 50 ? Colors.green : Colors.orange,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              Row(
                children: [
                  Expanded(
                    child: _buildMetricCard(
                      'Winning Trades',
                      stats.winningTrades.toString(),
                      Colors.green,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildMetricCard(
                      'Losing Trades',
                      stats.losingTrades.toString(),
                      Colors.red,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Profit/Loss Summary
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Profit & Loss Summary',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Gross Profit',
                            style: TextStyle(color: Colors.grey),
                          ),
                          Text(
                            '\$${grossProfit.toStringAsFixed(2)}',
                            style: TextStyle(
                              color: grossProfit >= 0 ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                      const Divider(color: Colors.grey),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Commission (15%)',
                            style: TextStyle(color: Colors.grey),
                          ),
                          Text(
                            '-\$${commission.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Colors.amber,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Monthly Fee (R1000)',
                            style: TextStyle(color: Colors.grey),
                          ),
                          const Text(
                            '-\$500.00',
                            style: TextStyle(
                              color: Colors.red,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const Divider(color: Colors.grey),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Net Profit',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                            ),
                          ),
                          Text(
                            '\$${(netProfit - 500).toStringAsFixed(2)}',
                            style: TextStyle(
                              color: (netProfit - 500) >= 0 ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Today's Performance
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Today\'s Performance',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Daily Profit/Loss',
                            style: TextStyle(color: Colors.grey),
                          ),
                          Text(
                            '\$${stats.dailyProfitLoss.toStringAsFixed(2)}',
                            style: TextStyle(
                              color: stats.dailyProfitLoss >= 0 ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Daily Loss Limit',
                            style: TextStyle(color: Colors.grey),
                          ),
                          Text(
                            '\$${config.maxDailyLossLimit.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Colors.orange,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Trading Configuration
              Card(
                color: Colors.grey.shade900,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Bot Configuration',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      _buildConfigItem(
                        'Risk Type',
                        config.riskType == 'fixed' ? 'Fixed \$ Amount' : 'Percentage %',
                      ),
                      _buildConfigItem(
                        'Risk per Trade',
                        config.riskType == 'fixed'
                          ? '\$${config.riskAmount.toStringAsFixed(2)}'
                          : '${config.riskAmount.toStringAsFixed(2)}%',
                      ),
                      _buildConfigItem(
                        'Trading Pairs',
                        config.tradingPairs.join(', '),
                      ),
                      _buildConfigItem(
                        'Strategies',
                        '${config.enableScalping ? 'Scalping' : ''} ${config.enableEconomicEventTrading ? 'Economic Events' : ''}',
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Configure Button
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.cyan,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                icon: const Icon(Icons.settings, color: Colors.black),
                label: const Text(
                  'Configure Bot',
                  style: TextStyle(
                    color: Colors.black,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => BotConfigurationScreen(
                        accountId: widget.accountId,
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 20),
            ],
          );
        },
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, Color color) {
    return Card(
      color: Colors.grey.shade800,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(color: Colors.grey, fontSize: 12),
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: TextStyle(
                color: color,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfigItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(color: Colors.grey, fontSize: 12),
          ),
          Text(
            value,
            style: const TextStyle(color: Colors.cyan, fontWeight: FontWeight.bold),
            textAlign: TextAlign.right,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
