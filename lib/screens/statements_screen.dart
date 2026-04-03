import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../services/statement_service.dart';
import '../services/trading_service.dart';
import '../utils/constants.dart';

class StatementsScreen extends StatefulWidget {
  const StatementsScreen({Key? key}) : super(key: key);

  @override
  State<StatementsScreen> createState() => _StatementsScreenState();
}

class _StatementsScreenState extends State<StatementsScreen> {
  late DateTime _startDate;
  late DateTime _endDate;
  String _selectedAccountId = '';

  @override
  void initState() {
    super.initState();
    _endDate = DateTime.now();
    _startDate = DateTime(_endDate.year, _endDate.month - 1, _endDate.day);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Trading Statements'),
        elevation: 0,
        backgroundColor: AppColors.primaryColor,
      ),
      body: Consumer2<TradingService, StatementService>(
        builder: (context, tradingService, statementService, _) {
          if (_selectedAccountId.isEmpty && tradingService.accounts.isNotEmpty) {
            _selectedAccountId = tradingService.accounts[0].id;
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Date Range and Account Selection
                _buildFilterSection(context, tradingService),
                const SizedBox(height: 24),

                // Generate Statement Button
                _buildGenerateButton(context, tradingService, statementService),
                const SizedBox(height: 24),

                // Generated Statements List
                _buildStatementsList(context, statementService),
              ],
            ),
          );
        },
      ),
    );

  Widget _buildFilterSection(BuildContext context, TradingService tradingService) => Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Statement Filters',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),

            // Account Selection
            if (tradingService.accounts.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Select Account',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 8),
                  DropdownButton<String>(
                    value: _selectedAccountId,
                    isExpanded: true,
                    items: tradingService.accounts
                        .map((account) => DropdownMenuItem(
                              value: account.id,
                              child: Text(account.accountNumber),
                            ))
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        _selectedAccountId = value ?? '';
                      });
                    },
                  ),
                  const SizedBox(height: 16),
                ],
              ),

            // Date Range Selection
            Row(
              children: [
                Expanded(
                  child: _buildDatePickerField(
                    context,
                    'From Date',
                    _startDate,
                    (date) {
                      setState(() => _startDate = date);
                    },
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _buildDatePickerField(
                    context,
                    'To Date',
                    _endDate,
                    (date) {
                      setState(() => _endDate = date);
                    },
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );

  Widget _buildDatePickerField(
    BuildContext context,
    String label,
    DateTime selectedDate,
    Function(DateTime) onDateSelected,
  ) {
    final dateFormat = DateFormat('MMM dd, yyyy');
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 8),
        GestureDetector(
          onTap: () async {
            final picked = await showDatePicker(
              context: context,
              initialDate: selectedDate,
              firstDate: DateTime(2020),
              lastDate: DateTime.now(),
            );
            if (picked != null) {
              onDateSelected(picked);
            }
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.grey.shade300),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(dateFormat.format(selectedDate)),
          ),
        ),
      ],
    );
  }

  Widget _buildGenerateButton(
    BuildContext context,
    TradingService tradingService,
    StatementService statementService,
  ) => SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () {
          _generateStatement(context, tradingService, statementService);
        },
        icon: const Icon(Icons.add),
        label: const Text('Generate New Statement'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primaryColor,
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
      ),
    );

  Widget _buildStatementsList(
    BuildContext context,
    StatementService statementService,
  ) {
    final statements = statementService.statements;

    if (statements.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.description_outlined,
              size: 48,
              color: Colors.grey.shade400,
            ),
            const SizedBox(height: 16),
            Text(
              'No statements generated yet',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey.shade600,
                  ),
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Generated Statements',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 16),
        ...statements.map((statement) => _buildStatementCard(context, statement)),
      ],
    );
  }

  Widget _buildStatementCard(BuildContext context, dynamic statement) {
    final dateFormat = DateFormat('MMM dd, yyyy');
    final currencyFormat = NumberFormat.currency(symbol: r'$ ');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Account: ${statement.accountNumber}',
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${dateFormat.format(statement.startDate)} - ${dateFormat.format(statement.endDate)}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.grey.shade600,
                          ),
                    ),
                  ],
                ),
                PopupMenuButton(
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      child: const Text('View Details'),
                      onTap: () {
                        _showStatementDetails(context, statement);
                      },
                    ),
                    PopupMenuItem(
                      child: const Text('Delete'),
                      onTap: () {
                        context.read<StatementService>().deleteStatement(statement.id);
                      },
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildStatementMetrics(statement, currencyFormat),
          ],
        ),
      ),
    );
  }

  Widget _buildStatementMetrics(dynamic statement, NumberFormat currencyFormat) => Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _buildMetricItem('Total Trades', '${statement.totalTrades}'),
            _buildMetricItem('Win Rate', '${statement.winRate.toStringAsFixed(2)}%'),
            _buildMetricItem('Net Profit', currencyFormat.format(statement.totalProfit - statement.totalLoss.abs())),
          ],
        ),
      ],
    );

  Widget _buildMetricItem(String label, String value) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
        ),
      ],
    );

  void _generateStatement(
    BuildContext context,
    TradingService tradingService,
    StatementService statementService,
  ) async {
    final account = tradingService.accounts
        .firstWhere((a) => a.id == _selectedAccountId,
            orElse: () => tradingService.accounts.first);

    try {
      await statementService.generateStatement(
        account,
        tradingService.trades,
        _startDate,
        _endDate,
      );

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Statement generated successfully'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showStatementDetails(BuildContext context, dynamic statement) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Statement Details'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDetailRow('Account', statement.accountNumber),
              _buildDetailRow('Total Trades', '${statement.totalTrades}'),
              _buildDetailRow('Winning Trades', '${statement.winningTrades}'),
              _buildDetailRow('Losing Trades', '${statement.losingTrades}'),
              _buildDetailRow('Win Rate', '${statement.winRate.toStringAsFixed(2)}%'),
              _buildDetailRow('Opening Balance', '\$${statement.openingBalance.toStringAsFixed(2)}'),
              _buildDetailRow('Closing Balance', '\$${statement.closingBalance.toStringAsFixed(2)}'),
              _buildDetailRow('Total Profit', '\$${statement.totalProfit.toStringAsFixed(2)}'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(value, style: const TextStyle(color: Colors.grey)),
        ],
      ),
    );
}
