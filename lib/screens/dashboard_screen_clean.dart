import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/trading_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    // Mock data is already loaded in TradingService constructor
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: _buildAppBar(),
      body: _buildDashboardView(),
      bottomNavigationBar: _buildBottomNavigationBar(),
    );

  PreferredSizeWidget _buildAppBar() => AppBar(
      title: const Text('Zwesta Trading System'),
      elevation: 0,
    );

  Widget _buildDashboardView() => Consumer<TradingService>(
      builder: (context, tradingService, _) => SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Portfolio Overview',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Total Balance: \$${tradingService.totalBalance.toStringAsFixed(2)}',
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Total Profit: \$${tradingService.totalProfit.toStringAsFixed(2)}',
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Open Trades: ${tradingService.activeTrades.length}',
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Closed Trades: ${tradingService.closedTrades.length}',
                        style: const TextStyle(fontSize: 16),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'Recent Trades',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 16),
              if (tradingService.trades.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'No trades available',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                )
              else
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: tradingService.trades.length,
                  itemBuilder: (context, index) {
                    final trade = tradingService.trades[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              trade.symbol,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Entry: ${trade.entryPrice} | Current: ${trade.currentPrice}',
                              style: const TextStyle(fontSize: 12),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Profit: \$${(trade.profit ?? 0).toStringAsFixed(2)}',
                              style: TextStyle(
                                fontSize: 12,
                                color: (trade.profit ?? 0) > 0
                                    ? Colors.green
                                    : Colors.red,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
            ],
          ),
        ),
    );

  BottomNavigationBar _buildBottomNavigationBar() => BottomNavigationBar(
      currentIndex: 0,
      type: BottomNavigationBarType.fixed,
      backgroundColor: Colors.blue,
      selectedItemColor: Colors.white,
      unselectedItemColor: Colors.white70,
      elevation: 8,
      items: const [
        BottomNavigationBarItem(
          icon: Icon(Icons.dashboard),
          label: 'Dashboard',
        ),
      ],
    );
}

