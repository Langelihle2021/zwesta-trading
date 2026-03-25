import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading/providers/auth_provider.dart';
import 'package:zwesta_trading/providers/trading_provider.dart';
import 'package:zwesta_trading/theme/app_colors.dart';
import 'package:zwesta_trading/widgets/stat_card.dart';
import 'package:zwesta_trading/widgets/chart_widget.dart';
import 'package:zwesta_trading/widgets/positions_list.dart';
import 'package:zwesta_trading/screens/login_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    // Load trading data when screen initializes
    Future.delayed(const Duration(milliseconds: 100), () {
      context.read<TradingProvider>().refreshData();
    });
  }

  void _handleLogout(BuildContext context, AuthProvider authProvider) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await authProvider.logout();
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Zwesta Trading'),
        elevation: 0,
        actions: [
          Consumer<AuthProvider>(
            builder: (context, authProvider, _) => IconButton(
              icon: const Icon(Icons.logout),
              onPressed: () =>
                  _handleLogout(context, authProvider),
            ),
          ),
        ],
      ),
      body: Consumer<TradingProvider>(
        builder: (context, tradingProvider, _) => RefreshIndicator(
          onRefresh: tradingProvider.refreshData,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Greeting
                  Consumer<AuthProvider>(
                    builder: (context, authProvider, _) => Text(
                      'Welcome, ${authProvider.username}!',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Stats Row 1
                  Row(
                    children: [
                      Expanded(
                        child: StatCard(
                          title: 'Total P&L',
                          value: '\$${tradingProvider.totalPnL.toStringAsFixed(2)}',
                          icon: Icons.trending_up,
                          color: tradingProvider.totalPnL >= 0
                              ? Colors.green
                              : Colors.red,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: StatCard(
                          title: 'Win Rate',
                          value:
                              '${tradingProvider.winRate.toStringAsFixed(1)}%',
                          icon: Icons.percent,
                          color: AppColors.primary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Stats Row 2
                  Row(
                    children: [
                      Expanded(
                        child: StatCard(
                          title: 'Total Trades',
                          value: tradingProvider.totalTrades.toString(),
                          icon: Icons.receipt,
                          color: AppColors.secondary,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: StatCard(
                          title: 'Positions',
                          value: tradingProvider.openPositions.toString(),
                          icon: Icons.open_in_new,
                          color: Colors.orange,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Charts Section
                  Text(
                    'Analytics',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 12),
                  ChartWidget(trades: tradingProvider.trades),
                  const SizedBox(height: 24),

                  // Positions Section
                  Text(
                    'Open Positions',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 12),
                  PositionsList(
                    positions: tradingProvider.positions,
                    onClose: (positionId) {
                      tradingProvider.closeTrade(positionId);
                    },
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
