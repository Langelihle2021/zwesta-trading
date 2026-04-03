import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';

import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';
import 'consolidated_reports_screen.dart';

class AdminWithdrawalVerificationScreen extends StatefulWidget {
  const AdminWithdrawalVerificationScreen({Key? key}) : super(key: key);

  @override
  State<AdminWithdrawalVerificationScreen> createState() =>
      _AdminWithdrawalVerificationScreenState();
}

class _AdminWithdrawalVerificationScreenState
    extends State<AdminWithdrawalVerificationScreen> {
  List<Map<String, dynamic>> _pendingWithdrawals = [];
  final List<Map<String, dynamic>> _verifiedWithdrawals = [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _successMessage;
  String _selectedTab = 'pending';

  @override
  void initState() {
    super.initState();
    _fetchPendingWithdrawals();
  }

  Future<void> _fetchPendingWithdrawals() async {
    setState(() => _isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/admin/withdrawals/pending'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'your_admin_api_key', // TODO: Get from secure storage
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _pendingWithdrawals = List<Map<String, dynamic>>.from(data['withdrawals'] ?? []);
          _isLoading = false;
        });
      } else {
        throw Exception('Failed to fetch withdrawals: ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _verifyWithdrawal(String withdrawalId) async {
    final notes = await _showNotesDialog();
    if (notes == null) return; // User cancelled

    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/admin/withdrawal/exness/verify'),
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'your_admin_api_key',
        },
        body: jsonEncode({
          'withdrawal_id': withdrawalId,
          'notes': notes,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _successMessage =
              '✅ Verified! Dev earned \$${data['developer_commission']}, User wallet +\$${data['user_wallet_credit']}';
        });
        // Remove from pending list
        _pendingWithdrawals.removeWhere((w) => w['withdrawal_id'] == withdrawalId);
        _fetchPendingWithdrawals();
      } else {
        final error = jsonDecode(response.body);
        throw Exception(error['error'] ?? 'Verification failed');
      }
    } catch (e) {
      setState(() => _errorMessage = 'Error: ${e.toString()}');
    }
  }

  Future<String?> _showNotesDialog() async {
    String? notes;
    return showDialog<String?>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Verification Notes'),
        content: TextField(
          decoration: const InputDecoration(
            hintText: 'e.g., "Verified on Exness platform", "User confirmed withdrawal"',
            border: OutlineInputBorder(),
          ),
          maxLines: 3,
          onChanged: (value) => notes = value,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, notes ?? ''),
            child: const Text('Verify'),
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
              child: Text('Admin: Withdrawal Verification'),
            ),
          ],
        ),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.home_outlined),
            tooltip: 'Home',
            onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
          ),
          IconButton(
            icon: const Icon(Icons.assessment_outlined),
            tooltip: 'Reports',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const ConsolidatedReportsScreen()));
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Tab selector
          Container(
            color: Colors.grey[850],
            child: Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedTab = 'pending'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: _selectedTab == 'pending'
                                ? Colors.blue
                                : Colors.transparent,
                            width: 3,
                          ),
                        ),
                      ),
                      child: Text(
                        'Pending (${_pendingWithdrawals.length})',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _selectedTab == 'pending'
                              ? Colors.blue
                              : Colors.grey,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedTab = 'verified'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: _selectedTab == 'verified'
                                ? Colors.green
                                : Colors.transparent,
                            width: 3,
                          ),
                        ),
                      ),
                      child: Text(
                        'Verified',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _selectedTab == 'verified'
                              ? Colors.green
                              : Colors.grey,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          // Messages
          if (_errorMessage != null)
            Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withOpacity(0.2),
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
          if (_successMessage != null)
            Container(
              margin: const EdgeInsets.all(12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green.withOpacity(0.2),
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
          // Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _selectedTab == 'pending'
                    ? _buildPendingList()
                    : _buildVerifiedList(),
          ),
        ],
      ),
    );

  Widget _buildPendingList() {
    if (_pendingWithdrawals.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle, size: 48, color: Colors.grey),
            SizedBox(height: 12),
            Text('No pending withdrawals'),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _pendingWithdrawals.length,
      itemBuilder: (context, index) {
        final withdrawal = _pendingWithdrawals[index];
        final profit = withdrawal['profit_from_trades'] ?? 0.0;
        final userShare = profit * 0.70;
        final devShare = profit * 0.30;
        final createdAt = DateTime.parse(withdrawal['created_at'] ?? '');

        return Card(
          color: Colors.grey[850],
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
                          'Withdrawal ID: ${withdrawal['withdrawal_id']?.substring(0, 8) ?? 'N/A'}...',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.grey,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'User: ${withdrawal['user_id']?.substring(0, 8) ?? 'N/A'}...',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.orange.withOpacity(0.3),
                        border: Border.all(color: Colors.orange),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'PENDING',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.orange,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey[900],
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Profit Withdrawn',
                            style: TextStyle(color: Colors.grey[400]),
                          ),
                          Text(
                            '\$${profit.toStringAsFixed(2)}',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'User Gets (70%)',
                            style: TextStyle(color: Colors.grey[400]),
                          ),
                          Text(
                            '\$${userShare.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Colors.green,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Dev Commission (30%)',
                            style: TextStyle(color: Colors.grey[400]),
                          ),
                          Text(
                            '\$${devShare.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Colors.blue,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Requested: ${DateFormat('MMM d, yyyy HH:mm').format(createdAt)}',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[400],
                  ),
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: () =>
                      _verifyWithdrawal(withdrawal['withdrawal_id']),
                  icon: const Icon(Icons.verified_user),
                  label: const Text('Verify & Apply Commission Split'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    minimumSize: const Size(double.infinity, 40),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildVerifiedList() {
    if (_verifiedWithdrawals.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.history, size: 48, color: Colors.grey),
            SizedBox(height: 12),
            Text('No verified withdrawals yet'),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _verifiedWithdrawals.length,
      itemBuilder: (context, index) {
        final withdrawal = _verifiedWithdrawals[index];
        return Card(
          color: Colors.grey[850],
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: ListTile(
              leading: const Icon(Icons.check_circle, color: Colors.green),
              title: Text('ID: ${withdrawal['withdrawal_id']?.substring(0, 8) ?? 'N/A'}...'),
              subtitle: Text(
                '\$${withdrawal['profit_from_trades']?.toStringAsFixed(2) ?? '0.00'} profit',
              ),
              trailing: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.3),
                  border: Border.all(color: Colors.green),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'VERIFIED',
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.green,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
