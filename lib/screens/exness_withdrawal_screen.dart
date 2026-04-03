import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';

import '../services/exness_withdrawal_service.dart';
import '../utils/constants.dart';

class ExnessWithdrawalScreen extends StatefulWidget {

  const ExnessWithdrawalScreen({
    required this.userId, required this.brokerAccountId, Key? key,
  }) : super(key: key);
  final String userId;
  final String brokerAccountId;

  @override
  State<ExnessWithdrawalScreen> createState() => _ExnessWithdrawalScreenState();
}

class _ExnessWithdrawalScreenState extends State<ExnessWithdrawalScreen>
    with SingleTickerProviderStateMixin {
  late ExnessWithdrawalService _withdrawalService;
  late TabController _tabController;
  
  late TextEditingController _amountController;
  late TextEditingController _paymentDetailsController;
  
  String _withdrawalType = 'profits'; // 'profits', 'commission', 'both'
  String _withdrawalMethod = 'bank_transfer';
  
  double _availableProfits = 0;
  double _availableCommission = 0;
  double _totalAvailable = 0;
  double _pendingWithdrawals = 0;
  
  bool _isLoading = true;
  bool _isSubmitting = false;
  List<Map<String, dynamic>> _withdrawalHistory = [];

  @override
  void initState() {
    super.initState();
    _withdrawalService = ExnessWithdrawalService();
    _tabController = TabController(length: 2, vsync: this);
    _amountController = TextEditingController();
    _paymentDetailsController = TextEditingController();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    
    final balanceData = await _withdrawalService.getWithdrawalBalance(widget.userId);
    final historyData = await _withdrawalService.getWithdrawalHistory(widget.userId);
    
    setState(() {
      _availableProfits = balanceData['available_profits'] ?? 0.0;
      _availableCommission = balanceData['available_commission'] ?? 0.0;
      _totalAvailable = balanceData['total_available'] ?? 0.0;
      _pendingWithdrawals = balanceData['pending_withdrawals'] ?? 0.0;
      _withdrawalHistory = historyData;
      _isLoading = false;
    });
  }

  Future<void> _submitWithdrawal() async {
    if (_amountController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter withdrawal amount')),
      );
      return;
    }

    final amount = double.tryParse(_amountController.text);
    if (amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid amount')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    final result = await _withdrawalService.requestWithdrawal(
      userId: widget.userId,
      brokerAccountId: widget.brokerAccountId,
      withdrawalType: _withdrawalType,
      amount: amount,
      withdrawalMethod: _withdrawalMethod,
      paymentDetails: _paymentDetailsController.text,
    );

    setState(() => _isSubmitting = false);

    if (result['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('✅ Withdrawal request submitted!\nNet amount: \$${result['net_amount']}'),
          backgroundColor: Colors.green,
        ),
      );
      _amountController.clear();
      _paymentDetailsController.clear();
      await _loadData();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('❌ ${result['error']}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _amountController.dispose();
    _paymentDetailsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Exness Withdrawal'),
          elevation: 0,
          backgroundColor: AppColors.primaryColor,
          bottom: TabBar(
            controller: _tabController,
            tabs: const [
              Tab(text: 'Request Withdrawal'),
              Tab(text: 'History'),
            ],
          ),
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                controller: _tabController,
                children: [
                  _buildWithdrawalForm(),
                  _buildWithdrawalHistory(),
                ],
              ),
      ),
    );

  Widget _buildWithdrawalForm() => SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Balance Summary
          _buildBalanceSummary(),
          const SizedBox(height: 24),

          // Withdrawal Type
          Text(
            'Withdrawal Type',
            style: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          _buildWithdrawalTypeSelection(),
          const SizedBox(height: 24),

          // Amount Input
          Text(
            'Amount to Withdraw',
            style: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _amountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              hintText: 'Enter amount in USD',
              prefixText: r'$ ',
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              filled: true,
              fillColor: Colors.grey[100],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Available: \$${_getAvailableForType().toStringAsFixed(2)}',
            style: GoogleFonts.poppins(fontSize: 12, color: Colors.grey[600]),
          ),
          const SizedBox(height: 24),

          // Withdrawal Method
          Text(
            'Withdrawal Method',
            style: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          DropdownButton<String>(
            value: _withdrawalMethod,
            isExpanded: true,
            items: const [
              DropdownMenuItem(value: 'bank_transfer', child: Text('Bank Transfer')),
              DropdownMenuItem(value: 'crypto_wallet', child: Text('Crypto Wallet')),
              DropdownMenuItem(value: 'payment_system', child: Text('Payment System')),
            ],
            onChanged: (value) {
              setState(() => _withdrawalMethod = value ?? 'bank_transfer');
            },
          ),
          const SizedBox(height: 24),

          // Payment Details (optional)
          Text(
            'Payment Details (Optional)',
            style: GoogleFonts.poppins(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _paymentDetailsController,
            decoration: InputDecoration(
              hintText: 'Bank account, wallet address, etc.',
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              filled: true,
              fillColor: Colors.grey[100],
            ),
            minLines: 3,
            maxLines: 5,
          ),
          const SizedBox(height: 32),

          // Fee Information
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue[50],
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue[300]!),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Withdrawal Fee: 1%',
                  style: GoogleFonts.poppins(fontSize: 12, fontWeight: FontWeight.w500),
                ),
                const SizedBox(height: 8),
                if (_amountController.text.isNotEmpty)
                  Text(
                    'Net Amount: \$${_calculateNetAmount().toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.green[700],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 32),

          // Submit Button
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: _isSubmitting ? null : _submitWithdrawal,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryColor,
                disabledBackgroundColor: Colors.grey[400],
              ),
              child: _isSubmitting
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : Text(
                      'Request Withdrawal',
                      style: GoogleFonts.poppins(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: Colors.white,
                      ),
                    ),
            ),
          ),
        ],
      ),
    );

  Widget _buildBalanceSummary() => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Available Balance',
            style: GoogleFonts.poppins(fontSize: 14, color: Colors.white70),
          ),
          const SizedBox(height: 8),
          Text(
            '\$${_totalAvailable.toStringAsFixed(2)}',
            style: GoogleFonts.poppins(
              fontSize: 32,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Profits',
                    style: GoogleFonts.poppins(fontSize: 12, color: Colors.white70),
                  ),
                  Text(
                    '\$${_availableProfits.toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Commission',
                    style: GoogleFonts.poppins(fontSize: 12, color: Colors.white70),
                  ),
                  Text(
                    '\$${_availableCommission.toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Pending',
                    style: GoogleFonts.poppins(fontSize: 12, color: Colors.white70),
                  ),
                  Text(
                    '\$${_pendingWithdrawals.toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.yellow[200],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );

  Widget _buildWithdrawalTypeSelection() => Row(
      children: [
        Expanded(
          child: _buildTypeCard('Profits', 'profits'),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildTypeCard('Commission', 'commission'),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildTypeCard('Both', 'both'),
        ),
      ],
    );

  Widget _buildTypeCard(String label, String type) {
    final isSelected = _withdrawalType == type;
    return GestureDetector(
      onTap: () => setState(() => _withdrawalType = type),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primaryColor : Colors.grey[100],
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? AppColors.primaryColor : Colors.transparent,
            width: 2,
          ),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: GoogleFonts.poppins(
            fontWeight: FontWeight.w600,
            color: isSelected ? Colors.white : Colors.black,
          ),
        ),
      ),
    );
  }

  Widget _buildWithdrawalHistory() {
    if (_withdrawalHistory.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.history, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              'No withdrawal history',
              style: GoogleFonts.poppins(fontSize: 16, color: Colors.grey),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _withdrawalHistory.length,
      itemBuilder: (context, index) {
        final withdrawal = _withdrawalHistory[index];
        return _buildWithdrawalHistoryCard(withdrawal);
      },
    );
  }

  Widget _buildWithdrawalHistoryCard(Map<String, dynamic> withdrawal) {
    final status = withdrawal['status'] as String?;
    final statusColor = status == 'completed'
        ? Colors.green
        : status == 'pending'
            ? Colors.orange
            : Colors.red;

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
                      '\$${withdrawal['total_amount']}',
                      style: GoogleFonts.poppins(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      withdrawal['withdrawal_type'] ?? 'Unknown',
                      style: GoogleFonts.poppins(
                        fontSize: 12,
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    status ?? 'Unknown',
                    style: GoogleFonts.poppins(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Created: ${DateFormat('MMM dd, yyyy').format(DateTime.parse(withdrawal['created_at']))}',
                  style: GoogleFonts.poppins(fontSize: 11, color: Colors.grey[600]),
                ),
                Text(
                  'Net: \$${withdrawal['net_amount']}',
                  style: GoogleFonts.poppins(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: Colors.green,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  double _getAvailableForType() {
    switch (_withdrawalType) {
      case 'profits':
        return _availableProfits;
      case 'commission':
        return _availableCommission;
      case 'both':
        return _totalAvailable;
      default:
        return 0;
    }
  }

  double _calculateNetAmount() {
    final amount = double.tryParse(_amountController.text) ?? 0;
    return amount * 0.99; // 1% fee
  }
}
