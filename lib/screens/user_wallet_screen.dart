import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';
import 'consolidated_reports_screen.dart';

class UserWalletScreen extends StatefulWidget {
  const UserWalletScreen({Key? key}) : super(key: key);

  @override
  State<UserWalletScreen> createState() => _UserWalletScreenState();
}

class _UserWalletScreenState extends State<UserWalletScreen> {
  double _walletBalance = 0;
  double _totalEarned = 0;
  double _totalWithdrawn = 0;
  bool _isLoading = true;
  String? _errorMessage;
  String? _successMessage;
  String _activeBrokerName = 'Exness';

  @override
  void initState() {
    super.initState();
    _fetchWalletData();
  }

  Future<void> _fetchWalletData() async {
    setState(() => _isLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('user_id');
      final sessionToken = prefs.getString('auth_token');
      _activeBrokerName = (prefs.getString('broker') ?? 'Exness').trim();

      if (userId == null || sessionToken == null) {
        throw Exception('User not authenticated');
      }

      // Fetch wallet balance
      final walletResponse = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/wallet/balance/$userId'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 10));

      if (walletResponse.statusCode == 200) {
        final data = jsonDecode(walletResponse.body);
        setState(() {
          _walletBalance = (data['balance'] as num?)?.toDouble() ?? 0;
        });
      }

      // Fetch earnings breakdown (broker-aware)
      final normalizedBroker = _activeBrokerName.toLowerCase();
      late http.Response earningsResponse;

      if (normalizedBroker == 'oanda') {
        final accountId = prefs.getString('account_number') ?? '';
        earningsResponse = await http
            .get(
              Uri.parse(
                '${EnvironmentConfig.apiUrl}/api/oanda/funds${accountId.isNotEmpty ? '?account_id=$accountId' : ''}',
              ),
              headers: {
                'Content-Type': 'application/json',
                'X-Session-Token': sessionToken,
              },
            )
            .timeout(const Duration(seconds: 10));

        if (earningsResponse.statusCode == 200) {
          final data = jsonDecode(earningsResponse.body);
          final funds = (data['funds'] as Map<String, dynamic>?) ?? const {};
          setState(() {
            _totalEarned = (funds['balance'] as num?)?.toDouble() ?? 0;
            _totalWithdrawn = 0;
            _isLoading = false;
          });
        } else {
          setState(() {
            _errorMessage = 'Could not load OANDA earnings breakdown';
            _isLoading = false;
          });
        }
      } else {
        earningsResponse = await http
            .get(
              Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/balance/$userId'),
              headers: {
                'Content-Type': 'application/json',
                'X-Session-Token': sessionToken,
              },
            )
            .timeout(const Duration(seconds: 10));

        if (earningsResponse.statusCode == 200) {
          final data = jsonDecode(earningsResponse.body);
          setState(() {
            _totalEarned = (data['total_available'] as num?)?.toDouble() ?? 0;
            _totalWithdrawn = (data['pending_withdrawals'] as num?)?.toDouble() ?? 0;
            _isLoading = false;
          });
        } else {
          setState(() {
            _errorMessage = 'Could not load broker earnings breakdown';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error loading wallet: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _requestWithdrawal() async {
    final amount = await _showWithdrawalAmountDialog();
    if (amount == null) {
      return;
    }

    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('user_id');
      final sessionToken = prefs.getString('auth_token') ?? '';

      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http
          .post(
            Uri.parse('${EnvironmentConfig.apiUrl}/api/withdrawal/request'),
            headers: {
              'Content-Type': 'application/json',
              'X-Session-Token': sessionToken,
            },
            body: jsonEncode({
              'user_id': userId,
              'amount': amount,
              'method': 'bank_transfer',
              'account_details': 'TBD',
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _successMessage =
              '✅ Withdrawal request submitted! Net: \$${data['net_amount']} (after ${data['fee']}% fee)';
        });
        await _fetchWalletData();
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? 'Withdrawal failed');
      }
    } catch (e) {
      setState(() => _errorMessage = 'Error: ${e.toString()}');
    }
  }

  Future<double?> _showWithdrawalAmountDialog() async {
    String? amountStr;
    return showDialog<double?>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Request Withdrawal'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Available Balance: \$${_walletBalance.toStringAsFixed(2)}'),
            const SizedBox(height: 12),
            TextField(
              decoration: const InputDecoration(
                hintText: 'Amount to withdraw',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.number,
              onChanged: (value) => amountStr = value,
            ),
            const SizedBox(height: 12),
            Text(
              'Note: 3% processing fee will be deducted',
              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final amount = double.tryParse(amountStr ?? '');
              if (amount == null || amount <= 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Invalid amount')),
                );
                return;
              }
              if (amount > _walletBalance) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                      content: Text('Amount exceeds available balance')),
                );
                return;
              }
              Navigator.pop(context, amount);
            },
            child: const Text('Request Withdrawal'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Row(
            children: [
              LogoWidget(size: 40, showText: false),
              SizedBox(width: 12),
              Expanded(
                child: Text('My Wallet & Earnings'),
              ),
            ],
          ),
          backgroundColor: Colors.grey[900],
          elevation: 0,
          actions: [
            IconButton(
              icon: const Icon(Icons.home_outlined),
              tooltip: 'Home',
              onPressed: () =>
                  Navigator.of(context).popUntil((route) => route.isFirst),
            ),
            IconButton(
              icon: const Icon(Icons.assessment_outlined),
              tooltip: 'Reports',
              onPressed: () {
                Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => const ConsolidatedReportsScreen()));
              },
            ),
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
              onPressed: _fetchWalletData,
            ),
          ],
        ),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                            color: Colors.white.withValues(alpha: 0.08)),
                      ),
                      child: const Text(
                        'Wallet, earnings, and reports now work together on mobile. Use the dashboard Hub for the full web-style module list.',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                    ),
                    // Error message
                    if (_errorMessage != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.2),
                          border: Border.all(color: Colors.red),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.error, color: Colors.red),
                            const SizedBox(width: 12),
                            Expanded(child: Text(_errorMessage!)),
                            IconButton(
                              icon: const Icon(Icons.close, size: 16),
                              onPressed: () =>
                                  setState(() => _errorMessage = null),
                            ),
                          ],
                        ),
                      ),

                    // Success message
                    if (_successMessage != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.green.withValues(alpha: 0.2),
                          border: Border.all(color: Colors.green),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.check_circle, color: Colors.green),
                            const SizedBox(width: 12),
                            Expanded(child: Text(_successMessage!)),
                            IconButton(
                              icon: const Icon(Icons.close, size: 16),
                              onPressed: () =>
                                  setState(() => _successMessage = null),
                            ),
                          ],
                        ),
                      ),

                    // Main wallet balance card
                    Card(
                      color: Colors.blue.withValues(alpha: 0.1),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Wallet Balance',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                Text(
                                  '\$${_walletBalance.toStringAsFixed(2)}',
                                  style: const TextStyle(
                                    fontSize: 36,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.blue,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 12,
                                    vertical: 6,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: const Text(
                                    'Available',
                                    style: TextStyle(
                                      color: Colors.blue,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),
                            Text(
                              'This balance is from your bot profits (after 30% commission).',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[300],
                              ),
                            ),
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                onPressed: _requestWithdrawal,
                                icon: const Icon(Icons.arrow_downward),
                                label: const Text('Request Withdrawal'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.blue,
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 12),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Earnings breakdown
                    Text(
                      'Earnings Breakdown',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: Card(
                            color: Colors.grey[850],
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Total Earned',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey[400],
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    '\$${_totalEarned.toStringAsFixed(2)}',
                                    style: const TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color:
                                          Colors.green.withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text(
                                      'After 30% split',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.green,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Card(
                            color: Colors.grey[850],
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Pending Withdrawals',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey[400],
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    '\$${_totalWithdrawn.toStringAsFixed(2)}',
                                    style: const TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.orange,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color:
                                          Colors.orange.withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text(
                                      'Awaiting admin',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.orange,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),

                    // How it works
                    Card(
                      color: Colors.grey[850],
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  Icons.info_outline,
                                  color: Colors.blue[300],
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  'How It Works',
                                  style: Theme.of(context).textTheme.bodyMedium,
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            _buildHowItWorksStep(
                              '1',
                              'Bot Trades',
                              'Your bot executes trades on $_activeBrokerName',
                              Colors.blue,
                            ),
                            const SizedBox(height: 8),
                            _buildHowItWorksStep(
                              '2',
                              'Profit Recorded',
                              '70% to your earnings, 30% to platform',
                              Colors.green,
                            ),
                            const SizedBox(height: 8),
                            _buildHowItWorksStep(
                              '3',
                              'You Request',
                              'Request withdrawal from your wallet',
                              Colors.orange,
                            ),
                            const SizedBox(height: 8),
                            _buildHowItWorksStep(
                              '4',
                              'Admin Verifies',
                              'Platform admin confirms with broker records',
                              Colors.purple,
                            ),
                            const SizedBox(height: 8),
                            _buildHowItWorksStep(
                              '5',
                              'Funds Transferred',
                              'Your earnings are sent to your account',
                              Colors.indigo,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
      );

  Widget _buildHowItWorksStep(
    String number,
    String title,
    String description,
    Color color,
  ) =>
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.2),
              border: Border.all(color: color),
            ),
            child: Center(
              child: Text(
                number,
                style: TextStyle(
                  color: color,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[400],
                  ),
                ),
              ],
            ),
          ),
        ],
      );
}
