import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:zwesta_trading_temp/services/api_service.dart';
import 'package:zwesta_trading_temp/themes/app_colors.dart';

class WithdrawalsScreen extends StatefulWidget {
  final String accountId;
  const WithdrawalsScreen({Key? key, required this.accountId}) : super(key: key);

  @override
  State<WithdrawalsScreen> createState() => _WithdrawalsScreenState();
}

class _WithdrawalsScreenState extends State<WithdrawalsScreen> {
  final amountController = TextEditingController();
  final bankAccountController = TextEditingController();
  final bankNameController = TextEditingController();
  List<Map<String, dynamic>> withdrawals = [];
  bool isLoading = true;
  bool isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _loadWithdrawals();
  }

  @override
  void dispose() {
    amountController.dispose();
    bankAccountController.dispose();
    bankNameController.dispose();
    super.dispose();
  }

  Future<void> _loadWithdrawals() async {
    final apiService = context.read<ApiService>();
    try {
      final data = await apiService.getWithdrawals(widget.accountId);
      setState(() {
        withdrawals = List<Map<String, dynamic>>.from(data['withdrawals'] ?? []);
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to load withdrawals')));
      }
    }
  }

  Future<void> _submitWithdrawal() async {
    if (amountController.text.isEmpty ||
        bankAccountController.text.isEmpty ||
        bankNameController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please fill all fields')));
      return;
    }

    setState(() => isSubmitting = true);
    final apiService = context.read<ApiService>();
    try {
      final success = await apiService.requestWithdrawal(
        widget.accountId,
        double.parse(amountController.text),
        bankNameController.text,
        bankAccountController.text,
      );

      if (success) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Withdrawal requested')));
        amountController.clear();
        bankAccountController.clear();
        bankNameController.clear();
        await _loadWithdrawals();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to submit withdrawal')));
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Error submitting withdrawal')));
    }
    setState(() => isSubmitting = false);
  }

  Future<void> _refreshWithdrawals() async {
    await _loadWithdrawals();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Withdrawals'),
        backgroundColor: AppColors.darkBg,
      ),
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshWithdrawals,
              child: SingleChildScrollView(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Request Form
                      Text(
                        'Request Withdrawal',
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
                            TextField(
                              controller: bankNameController,
                              decoration: InputDecoration(
                                labelText: 'Bank Name',
                                prefixIcon: const Icon(Icons.account_balance),
                                filled: true,
                                fillColor: AppColors.darkBg,
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide.none,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            TextField(
                              controller: bankAccountController,
                              decoration: InputDecoration(
                                labelText: 'Bank Account Number',
                                prefixIcon: const Icon(Icons.numbers),
                                filled: true,
                                fillColor: AppColors.darkBg,
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(8),
                                  borderSide: BorderSide.none,
                                ),
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: isSubmitting ? null : _submitWithdrawal,
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
                                    : const Text('Submit Withdrawal'),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 32),

                      // Withdrawal History
                      Text(
                        'Withdrawal History',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 16),
                      if (withdrawals.isEmpty)
                        const Center(child: Text('No withdrawals'))
                      else
                        ListView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: withdrawals.length,
                          itemBuilder: (context, index) {
                            final withdrawal = withdrawals[index];
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
                                        '\$${withdrawal['amount']}',
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
                                          color: _getStatusColor(withdrawal['status'])
                                              .withOpacity(0.2),
                                          borderRadius:
                                              BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          withdrawal['status'] ?? 'PENDING',
                                          style: TextStyle(
                                            color: _getStatusColor(
                                                withdrawal['status']),
                                            fontSize: 12,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Bank: ${withdrawal['bankName']}',
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(color: Colors.white70),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Date: ${withdrawal['date'] ?? 'Unknown'}',
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
