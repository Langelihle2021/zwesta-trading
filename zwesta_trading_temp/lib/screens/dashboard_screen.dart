import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading_temp/models/account.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';
import 'package:zwesta_trading_temp/services/auth_service.dart';
import 'package:zwesta_trading_temp/themes/app_colors.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  List<Account> accounts = [];
  Account? selectedAccount;
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    final apiService = context.read<ApiService>();
    try {
      final data = await apiService.getUserAccounts();
      setState(() {
        accounts = (data['accounts'] as List)
            .map((acc) => Account.fromJson(acc))
            .toList();
        if (accounts.isNotEmpty) {
          selectedAccount = accounts[0];
        }
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Failed to load accounts')));
      }
    }
  }

  Future<void> _refreshAccounts() async {
    await _loadAccounts();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        backgroundColor: AppColors.darkBg,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refreshAccounts,
          ),
        ],
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshAccounts,
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Account Selector
                      Text(
                        'Select Account',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 12),
                      DropdownButton<Account>(
                        value: selectedAccount,
                        isExpanded: true,
                        items: accounts
                            .map((acc) => DropdownMenuItem(
                                  value: acc,
                                  child: Text('Account ${acc.id}'),
                                ))
                            .toList(),
                        onChanged: (Account? newValue) {
                          setState(() => selectedAccount = newValue);
                        },
                      ),
                      const SizedBox(height: 24),

                      // Balance Card
                      if (selectedAccount != null)
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                AppColors.primary.withOpacity(0.3),
                                AppColors.secondary.withOpacity(0.1),
                              ],
                            ),
                            color: AppColors.cardBg,
                            borderRadius: BorderRadius.circular(12),
                            border:
                                Border.all(color: AppColors.primary.withOpacity(0.3)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Current Balance',
                                style: Theme.of(context)
                                    .textTheme
                                    .bodySmall
                                    ?.copyWith(color: Colors.white70),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                '\$${selectedAccount!.currentBalance.toStringAsFixed(2)}',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineMedium
                                    ?.copyWith(
                                        color: AppColors.primary,
                                        fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 16),
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Initial Balance',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall
                                            ?.copyWith(color: Colors.white70),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '\$${selectedAccount!.initialBalance.toStringAsFixed(2)}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodyLarge,
                                      ),
                                    ],
                                  ),
                                  Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Profit/Loss',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall
                                            ?.copyWith(color: Colors.white70),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '\$${selectedAccount!.profitLoss.toStringAsFixed(2)}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodyLarge
                                            ?.copyWith(
                                              color: selectedAccount!
                                                      .profitLoss
                                                      .isNegative
                                                  ? AppColors.error
                                                  : AppColors.success,
                                              fontWeight: FontWeight.bold,
                                            ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 24),

                      // Stats Grid
                      if (selectedAccount != null)
                        GridView.count(
                          crossAxisCount: 2,
                          crossAxisSpacing: 12,
                          mainAxisSpacing: 12,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          children: [
                            _buildStatCard(
                                context, 'Total Trades', '42', AppColors.primary),
                            _buildStatCard(context, 'Win Rate', '65%',
                                AppColors.success),
                            _buildStatCard(context, 'Margin Level',
                                '850%', AppColors.secondary),
                            _buildStatCard(context, 'Return %',
                                '+8.5%', AppColors.success),
                          ],
                        ),
                      const SizedBox(height: 32),

                      // Quick Actions
                      Text(
                        'Quick Actions',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 16),
                      GridView.count(
                        crossAxisCount: 2,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        children: [
                          _buildActionButton(
                            context,
                            Icons.trending_up,
                            'Positions',
                            '/positions/${selectedAccount?.id}',
                          ),
                          _buildActionButton(
                            context,
                            Icons.history,
                            'Trades',
                            '/trades/${selectedAccount?.id}',
                          ),
                          _buildActionButton(
                            context,
                            Icons.download,
                            'Deposits',
                            '/deposits/${selectedAccount?.id}',
                          ),
                          _buildActionButton(
                            context,
                            Icons.account_balance,
                            'Withdraw',
                            '/withdrawals/${selectedAccount?.id}',
                          ),
                          _buildActionButton(
                            context,
                            Icons.currency_exchange,
                            'Markets',
                            '/markets',
                          ),
                          _buildActionButton(
                            context,
                            Icons.settings,
                            'Settings',
                            '/settings',
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
    );
  }

  Widget _buildStatCard(BuildContext context, String title, String value,
      Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: color,
                  fontWeight: FontWeight.bold,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton(
      BuildContext context, IconData icon, String label, String route) {
    return GestureDetector(
      onTap: () => Navigator.of(context).pushNamed(route),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.primary.withOpacity(0.3)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 32, color: AppColors.primary),
            const SizedBox(height: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
