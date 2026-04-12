import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/account.dart';
import '../models/financial_statement.dart';
import '../services/financial_service.dart';
import '../services/trading_service.dart';
import '../utils/environment_config.dart';
import '../utils/constants.dart';
import '../widgets/logo_widget.dart';

class FinancialsScreen extends StatefulWidget {

  const FinancialsScreen({required this.account, Key? key}) : super(key: key);
  final Account account;

  @override
  State<FinancialsScreen> createState() => _FinancialsScreenState();
}

class _FinancialsScreenState extends State<FinancialsScreen> {
  late DateTime startDate;
  late DateTime endDate;
  FinancialStatement? selectedStatement;
  String _selectedMode = 'DEMO';
  Account? _selectedAccount;
  bool _loadingAccount = false;
  String? _accountWarning;

  String _formatCurrency(FinancialStatement stmt, double amount) {
    return FinancialMetrics.formatCurrency(amount, stmt.currency);
  }

  @override
  void initState() {
    super.initState();
    endDate = DateTime.now();
    startDate = DateTime(endDate.year, endDate.month - 1, endDate.day);
    _selectedAccount = widget.account;
    _initializeMode();
  }

  Future<void> _initializeMode() async {
    final prefs = await SharedPreferences.getInstance();
    final mode = (prefs.getString('trading_mode') ?? 'DEMO').toUpperCase();
    if (!mounted) {
      return;
    }
    setState(() {
      _selectedMode = mode;
    });
    await _loadAccountForMode(mode);
  }

  Future<void> _loadAccountForMode(String mode) async {
    setState(() {
      _loadingAccount = true;
      _accountWarning = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      await prefs.setString('trading_mode', mode);

      if (sessionToken == null || sessionToken.isEmpty) {
        setState(() {
          _accountWarning = 'Session expired. Please login again.';
          _loadingAccount = false;
        });
        return;
      }

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/account/detailed?mode=$mode'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final account = data['account'] as Map<String, dynamic>?;
        if (account != null) {
          final updatedAccount = Account(
            id: data['credential_id']?.toString() ?? mode,
            accountNumber: account['accountNumber']?.toString() ?? 'N/A',
            balance: ((account['balance'] ?? 0) as num).toDouble(),
            usedMargin: ((account['margin'] ?? 0) as num).toDouble(),
            availableMargin: ((account['marginFree'] ?? 0) as num).toDouble(),
            profit: ((account['profit'] ?? 0) as num).toDouble(),
            currency: account['currency']?.toString() ?? widget.account.currency,
            status: account['connected'] == false ? 'inactive' : 'active',
            createdAt: DateTime.now(),
            leverage: account['leverage'] != null ? '1:${account['leverage']}' : widget.account.leverage,
            broker: account['broker']?.toString() ?? widget.account.broker,
            server: account['server']?.toString(),
          );

          if (mounted) {
            setState(() {
              _selectedAccount = updatedAccount;
              _accountWarning = account['warning']?.toString();
            });
          }
        }
      }

      if (mounted) {
        final tradingService = context.read<TradingService>();
        await tradingService.fetchAccounts();
        await tradingService.fetchTrades();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _accountWarning = 'Could not refresh $mode financial data: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _loadingAccount = false;
        });
      }
    }
  }

  void _generateFinancialStatement() async {
    final tradingService = context.read<TradingService>();
    final financialService = context.read<FinancialService>();
    final selectedAccount = _selectedAccount ?? widget.account;

    try {
      final trades = tradingService.trades;
      final statement = await financialService.generateFinancialStatement(
        selectedAccount,
        trades,
        startDate,
        endDate,
        initialCapital: selectedAccount.balance,
      );

      setState(() {
        selectedStatement = statement;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Financial statement generated successfully'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
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
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Financial Analytics'),
          ],
        ),
        backgroundColor: AppColors.primaryColor,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                ChoiceChip(
                  label: const Text('Live'),
                  selected: _selectedMode == 'LIVE',
                  onSelected: (selected) {
                    if (!selected) return;
                    setState(() => _selectedMode = 'LIVE');
                    _loadAccountForMode('LIVE');
                  },
                ),
                ChoiceChip(
                  label: const Text('Demo'),
                  selected: _selectedMode == 'DEMO',
                  onSelected: (selected) {
                    if (!selected) return;
                    setState(() => _selectedMode = 'DEMO');
                    _loadAccountForMode('DEMO');
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey[900],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${_selectedMode == 'LIVE' ? 'Live' : 'Demo'} account basis: ${(_selectedAccount ?? widget.account).accountNumber}',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Balance basis: ${FinancialMetrics.formatCurrency((_selectedAccount ?? widget.account).balance, (_selectedAccount ?? widget.account).currency)}',
                    style: TextStyle(color: Colors.grey[400]),
                  ),
                  if (_loadingAccount)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: LinearProgressIndicator(),
                    ),
                  if (_accountWarning != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        _accountWarning!,
                        style: const TextStyle(color: Colors.orangeAccent, fontSize: 12),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            // Date Range Selection
            _buildDateRangeSection(),
            const SizedBox(height: 24),

            // Generate Button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _generateFinancialStatement,
                icon: const Icon(Icons.refresh),
                label: const Text('Generate Financial Statement'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.accentColor,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Display Statement if Available
            if (selectedStatement != null) ...[
              _buildCapitalSection(selectedStatement!),
              const SizedBox(height: 16),
              _buildRevenueSection(selectedStatement!),
              const SizedBox(height: 16),
              _buildCostsSection(selectedStatement!),
              const SizedBox(height: 16),
              _buildProfitSection(selectedStatement!),
              const SizedBox(height: 16),
              _buildCashFlowSection(selectedStatement!),
              const SizedBox(height: 16),
              _buildBalanceSection(selectedStatement!),
            ] else
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Colors.grey[900],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    Icon(
                      Icons.analytics_outlined,
                      size: 48,
                      color: Colors.grey[600],
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Generate a financial statement to view detailed analytics',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.grey[400],
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),

            // History Section
            const SizedBox(height: 24),
            _buildHistorySection(),
          ],
        ),
      ),
    );

  Widget _buildDateRangeSection() => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Period',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'From',
                        style: TextStyle(color: Colors.grey[400], fontSize: 12),
                      ),
                      const SizedBox(height: 4),
                      GestureDetector(
                        onTap: () async {
                          final date = await showDatePicker(
                            context: context,
                            initialDate: startDate,
                            firstDate: DateTime(2020),
                            lastDate: DateTime.now(),
                          );
                          if (date != null) {
                            setState(() => startDate = date);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey[700]!),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${startDate.year}-${startDate.month.toString().padLeft(2, '0')}-${startDate.day.toString().padLeft(2, '0')}',
                            style: const TextStyle(color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'To',
                        style: TextStyle(color: Colors.grey[400], fontSize: 12),
                      ),
                      const SizedBox(height: 4),
                      GestureDetector(
                        onTap: () async {
                          final date = await showDatePicker(
                            context: context,
                            initialDate: endDate,
                            firstDate: startDate,
                            lastDate: DateTime.now(),
                          );
                          if (date != null) {
                            setState(() => endDate = date);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey[700]!),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${endDate.year}-${endDate.month.toString().padLeft(2, '0')}-${endDate.day.toString().padLeft(2, '0')}',
                            style: const TextStyle(color: Colors.white),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );

  Widget _buildCapitalSection(FinancialStatement stmt) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Capital & Investment',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Initial Capital Invested',
              _formatCurrency(stmt, stmt.capitalInvested),
              Colors.blue,
            ),
            _buildMetricRow(
              'Additional Investments',
              _formatCurrency(stmt, stmt.additionalInvestments),
              Colors.lightBlue,
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: _buildMetricRow(
                'Total Capital',
                _formatCurrency(stmt, stmt.totalCapital),
                Colors.cyan,
              ),
            ),
          ],
        ),
      ),
    );

  Widget _buildRevenueSection(FinancialStatement stmt) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Revenue Generated',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Trading Profit',
              _formatCurrency(stmt, stmt.tradingProfit),
              Colors.green,
            ),
            _buildMetricRow(
              'Dividends',
              _formatCurrency(stmt, stmt.dividends),
              Colors.greenAccent,
            ),
            _buildMetricRow(
              'Interest Income',
              _formatCurrency(stmt, stmt.interest),
              Colors.lightGreen,
            ),
            _buildMetricRow(
              'Other Income',
              _formatCurrency(stmt, stmt.otherIncome),
              Colors.lime,
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: _buildMetricRow(
                'Total Revenue',
                _formatCurrency(stmt, stmt.totalRevenue),
                Colors.greenAccent,
              ),
            ),
          ],
        ),
      ),
    );

  Widget _buildCostsSection(FinancialStatement stmt) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Operating Costs & Expenses',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Trading Commissions',
              _formatCurrency(stmt, stmt.commissions),
              Colors.orange,
            ),
            _buildMetricRow(
              'Bid-Ask Spreads',
              _formatCurrency(stmt, stmt.spreads),
              Colors.orangeAccent,
            ),
            _buildMetricRow(
              'Platform Fees',
              _formatCurrency(stmt, stmt.platformFees),
              Colors.deepOrange,
            ),
            _buildMetricRow(
              'Withdrawal Fees',
              _formatCurrency(stmt, stmt.withdrawalFees),
              Colors.deepOrangeAccent,
            ),
            _buildMetricRow(
              'Other Costs',
              _formatCurrency(stmt, stmt.otherCosts),
              Colors.amber,
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: _buildMetricRow(
                'Total Costs',
                _formatCurrency(stmt, stmt.totalCosts),
                Colors.redAccent,
              ),
            ),
          ],
        ),
      ),
    );

  Widget _buildProfitSection(FinancialStatement stmt) {
    final isProfitable = stmt.netProfit >= 0;
    return Card(
      color: isProfitable ? Colors.green[900] : Colors.red[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Net Profit & Returns',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: isProfitable ? Colors.green : Colors.red,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    FinancialMetrics.getProfitStatus(stmt.netProfit),
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Gross Profit',
              _formatCurrency(stmt, stmt.grossProfit),
              Colors.lightGreen,
            ),
            _buildMetricRow(
              'Operating Profit',
              _formatCurrency(stmt, stmt.operatingProfit),
              Colors.green,
            ),
            Container(
              margin: const EdgeInsets.symmetric(vertical: 8),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: Column(
                children: [
                  _buildMetricRow(
                    'Net Profit/Loss',
                    _formatCurrency(stmt, stmt.netProfit),
                    isProfitable ? Colors.lightGreen : Colors.red[300]!,
                  ),
                  const SizedBox(height: 8),
                  _buildMetricRow(
                    'Return on Investment (ROI)',
                    FinancialMetrics.formatPercentage(stmt.ROI),
                    isProfitable ? Colors.lightGreen : Colors.red[300]!,
                  ),
                  const SizedBox(height: 8),
                  _buildMetricRow(
                    'Profit Margin',
                    FinancialMetrics.formatPercentage(stmt.profitMargin),
                    isProfitable ? Colors.lightGreen : Colors.red[300]!,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCashFlowSection(FinancialStatement stmt) {
    final isCashFlowPositive = stmt.netCashFlow >= 0;
    return Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Cash Flow Analysis',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: isCashFlowPositive ? Colors.green : Colors.red,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    FinancialMetrics.getCashFlowStatus(stmt.netCashFlow),
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Total Cash In',
              _formatCurrency(stmt, stmt.totalCashIn),
              Colors.green,
            ),
            _buildMetricRow(
              'Total Cash Out',
              _formatCurrency(stmt, stmt.totalCashOut),
              Colors.red,
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: _buildMetricRow(
                'Net Cash Flow',
                _formatCurrency(stmt, stmt.netCashFlow),
                isCashFlowPositive ? Colors.lightGreen : Colors.red[300]!,
              ),
            ),
            const SizedBox(height: 16),
            // Cash Flow Breakdown
            if (stmt.cashFlowIn.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cash In Breakdown',
                    style: TextStyle(
                      color: Colors.grey[400],
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...stmt.cashFlowIn.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            e.description,
                            style: TextStyle(color: Colors.grey[300]),
                          ),
                        ),
                        Text(
                          _formatCurrency(stmt, e.amount),
                          style: const TextStyle(color: Colors.green),
                        ),
                      ],
                    ),
                  )),
                  const SizedBox(height: 12),
                ],
              ),
            if (stmt.cashFlowOut.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cash Out Breakdown',
                    style: TextStyle(
                      color: Colors.grey[400],
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...stmt.cashFlowOut.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            e.description,
                            style: TextStyle(color: Colors.grey[300]),
                          ),
                        ),
                        Text(
                          _formatCurrency(stmt, e.amount),
                          style: const TextStyle(color: Colors.red),
                        ),
                      ],
                    ),
                  )),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildBalanceSection(FinancialStatement stmt) => Card(
      color: Colors.grey[900],
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Account Balance Change',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            _buildMetricRow(
              'Opening Balance',
              _formatCurrency(stmt, stmt.openingBalance),
              Colors.blue,
            ),
            _buildMetricRow(
              'Closing Balance',
              _formatCurrency(stmt, stmt.closingBalance),
              Colors.blue,
            ),
            Container(
              margin: const EdgeInsets.only(top: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(4),
              ),
              child: _buildMetricRow(
                'Total Change',
                _formatCurrency(stmt, stmt.balanceChange),
                stmt.balanceChange >= 0 ? Colors.lightGreen : Colors.red[300]!,
              ),
            ),
          ],
        ),
      ),
    );

  Widget _buildHistorySection() => Consumer<FinancialService>(
      builder: (context, service, _) {
        final statements = service.financialStatements
            .where((s) => s.accountId == widget.account.id)
            .toList();

        if (statements.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Financial Statement History',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            ...statements.map((stmt) {
              final isProfitable = stmt.netProfit >= 0;
              return Card(
                color: Colors.grey[900],
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  onTap: () {
                    setState(() => selectedStatement = stmt);
                  },
                  title: Text(
                    '${stmt.startDate.year}-${stmt.startDate.month.toString().padLeft(2, '0')}-${stmt.startDate.day.toString().padLeft(2, '0')} to ${stmt.endDate.year}-${stmt.endDate.month.toString().padLeft(2, '0')}-${stmt.endDate.day.toString().padLeft(2, '0')}',
                    style: TextStyle(
                      color: isProfitable ? Colors.lightGreen : Colors.red[300],
                    ),
                  ),
                  subtitle: Text(
                    'Net Profit: ${_formatCurrency(stmt, stmt.netProfit)} | ROI: ${FinancialMetrics.formatPercentage(stmt.ROI)}',
                    style: TextStyle(color: Colors.grey[400]),
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    onPressed: () => _deleteStatement(stmt.id),
                  ),
                ),
              );
            }),
          ],
        );
      },
    );

  void _deleteStatement(String id) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Financial Statement'),
        content: const Text('Are you sure you want to delete this statement?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () async {
              await context.read<FinancialService>().deleteFinancialStatement(id);
              Navigator.pop(context);
              setState(() {
                if (selectedStatement?.id == id) {
                  selectedStatement = null;
                }
              });
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricRow(String label, String value, Color valueColor) => Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(color: Colors.grey[300]),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontWeight: FontWeight.bold,
            fontSize: 14,
          ),
        ),
      ],
    );
}
