import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/account.dart';
import '../models/financial_statement.dart';
import '../services/financial_service.dart';
import '../services/trading_service.dart';
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

  @override
  void initState() {
    super.initState();
    endDate = DateTime.now();
    startDate = DateTime(endDate.year, endDate.month - 1, endDate.day);
  }

  void _generateFinancialStatement() async {
    final tradingService = context.read<TradingService>();
    final financialService = context.read<FinancialService>();

    try {
      final trades = tradingService.trades;
      final statement = await financialService.generateFinancialStatement(
        widget.account,
        trades,
        startDate,
        endDate,
        initialCapital: 10000,
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
              FinancialMetrics.formatCurrency(stmt.capitalInvested),
              Colors.blue,
            ),
            _buildMetricRow(
              'Additional Investments',
              FinancialMetrics.formatCurrency(stmt.additionalInvestments),
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
                FinancialMetrics.formatCurrency(stmt.totalCapital),
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
              FinancialMetrics.formatCurrency(stmt.tradingProfit),
              Colors.green,
            ),
            _buildMetricRow(
              'Dividends',
              FinancialMetrics.formatCurrency(stmt.dividends),
              Colors.greenAccent,
            ),
            _buildMetricRow(
              'Interest Income',
              FinancialMetrics.formatCurrency(stmt.interest),
              Colors.lightGreen,
            ),
            _buildMetricRow(
              'Other Income',
              FinancialMetrics.formatCurrency(stmt.otherIncome),
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
                FinancialMetrics.formatCurrency(stmt.totalRevenue),
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
              FinancialMetrics.formatCurrency(stmt.commissions),
              Colors.orange,
            ),
            _buildMetricRow(
              'Bid-Ask Spreads',
              FinancialMetrics.formatCurrency(stmt.spreads),
              Colors.orangeAccent,
            ),
            _buildMetricRow(
              'Platform Fees',
              FinancialMetrics.formatCurrency(stmt.platformFees),
              Colors.deepOrange,
            ),
            _buildMetricRow(
              'Withdrawal Fees',
              FinancialMetrics.formatCurrency(stmt.withdrawalFees),
              Colors.deepOrangeAccent,
            ),
            _buildMetricRow(
              'Other Costs',
              FinancialMetrics.formatCurrency(stmt.otherCosts),
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
                FinancialMetrics.formatCurrency(stmt.totalCosts),
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
              FinancialMetrics.formatCurrency(stmt.grossProfit),
              Colors.lightGreen,
            ),
            _buildMetricRow(
              'Operating Profit',
              FinancialMetrics.formatCurrency(stmt.operatingProfit),
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
                    FinancialMetrics.formatCurrency(stmt.netProfit),
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
              FinancialMetrics.formatCurrency(stmt.totalCashIn),
              Colors.green,
            ),
            _buildMetricRow(
              'Total Cash Out',
              FinancialMetrics.formatCurrency(stmt.totalCashOut),
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
                FinancialMetrics.formatCurrency(stmt.netCashFlow),
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
                          FinancialMetrics.formatCurrency(e.amount),
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
                          FinancialMetrics.formatCurrency(e.amount),
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
              FinancialMetrics.formatCurrency(stmt.openingBalance),
              Colors.blue,
            ),
            _buildMetricRow(
              'Closing Balance',
              FinancialMetrics.formatCurrency(stmt.closingBalance),
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
                FinancialMetrics.formatCurrency(stmt.balanceChange),
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
                    'Net Profit: ${FinancialMetrics.formatCurrency(stmt.netProfit)} | ROI: ${FinancialMetrics.formatPercentage(stmt.ROI)}',
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
