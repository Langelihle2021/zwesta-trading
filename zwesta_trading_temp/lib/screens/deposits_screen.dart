import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';
import 'package:zwesta_trading_temp/themes/app_colors.dart';

class DepositsScreen extends StatefulWidget {
  final String accountId;
  const DepositsScreen({Key? key, required this.accountId}) : super(key: key);

  @override
  State<DepositsScreen> createState() => _DepositsScreenState();
}

class _DepositsScreenState extends State<DepositsScreen> {
  final amountController = TextEditingController();
  final paymentMethodController = TextEditingController();
  List<Map<String, dynamic>> deposits = [];
  bool isLoading = true;
  bool isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _loadDeposits();
  }

  @override
  void dispose() {
    amountController.dispose();
    paymentMethodController.dispose();
    super.dispose();
  }

  Future<void> _loadDeposits() async {
    // Simulate loading deposits
    setState(() {
      isLoading = false;
      deposits = [
        {
          'id': 1,
          'amount': 5000,
          'method': 'Bank Transfer',
          'status': 'APPROVED',
          'date': '2026-02-28',
        },
        {
          'id': 2,
          'amount': 2500,
          'method': 'Wire Transfer',
          'status': 'PENDING',
          'date': '2026-02-27',
        },
      ];
    });
  }

  Future<void> _submitDeposit() async {
    if (amountController.text.isEmpty || paymentMethodController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please fill all fields')));
      return;
    }

    setState(() => isSubmitting = true);
    try {
      // Simulate API call
      await Future.delayed(const Duration(seconds: 1));
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Deposit initiated')));
      amountController.clear();
      paymentMethodController.clear();
      await _loadDeposits();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error submitting deposit')));
    }
    setState(() => isSubmitting = false);
  }

  Future<void> _refreshDeposits() async {
    await _loadDeposits();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Deposits'),
        backgroundColor: AppColors.darkBg,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshDeposits,
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Deposit Form
                      Text(
                        'Make a Deposit',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppColors.cardBg,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          children: [
                            TextField(
                              controller: amountController,
                              keyboardType: TextInputType.number,
                              decoration: InputDecoration(
                                labelText: 'Amount (USD)',
                                prefixIcon: const Icon(Icons.money),
                                filled: true,
                                fillColor: AppColors.darkBg,
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide.none,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            DropdownButtonFormField<String>(
                              decoration: InputDecoration(
                                labelText: 'Payment Method',
                                prefixIcon: const Icon(Icons.payment),
                                filled: true,
                                fillColor: AppColors.darkBg,
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide.none,
                                ),
                              ),
                              items: ['Bank Transfer', 'Wire Transfer', 'Credit Card', 'Crypto']
                                  .map((method) =>
                                      DropdownMenuItem(value: method, child: Text(method)))
                                  .toList(),
                              onChanged: (value) {
                                if (value != null) paymentMethodController.text = value;
                              },
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: isSubmitting ? null : _submitDeposit,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppColors.primary,
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 16),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                ),
                                child: isSubmitting
                                    ? const SizedBox(
                                        height: 20,
                                        width: 20,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            valueColor:
                                                AlwaysStoppedAnimation(
                                                    Colors.white)),
                                      )
                                    : const Text('Initiate Deposit'),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),

                      // Deposit History
                      Text(
                        'Deposit History',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 16),
                      if (deposits.isEmpty)
                        const Center(child: Text('No deposits'))
                      else
                        ListView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: deposits.length,
                          itemBuilder: (context, index) {
                            final deposit = deposits[index];
                            return Container(
                              margin: const EdgeInsets.only(bottom: 12),
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppColors.cardBg,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(
                                        '\$${deposit['amount']}',
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleMedium
                                            ?.copyWith(
                                              color: AppColors.primary,
                                              fontWeight: FontWeight.bold,
                                            ),
                                      ),
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: _getStatusColor(
                                                  deposit['status'])
                                              .withOpacity(0.2),
                                          borderRadius:
                                              BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          deposit['status'] ?? 'PENDING',
                                          style: TextStyle(
                                            color: _getStatusColor(
                                                deposit['status']),
                                            fontSize: 12,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Method: ${deposit['method']}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(color: Colors.white70),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Date: ${deposit['date']}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(color: Colors.white70),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                    ],
                  ),
                ),
              ),
            ),
    );
  }

  Color _getStatusColor(String? status) {
    switch (status?.toUpperCase()) {
      case 'PENDING':
        return Colors.orange;
      case 'APPROVED':
        return AppColors.success;
      case 'REJECTED':
        return AppColors.error;
      default:
        return Colors.grey;
    }
  }
}
