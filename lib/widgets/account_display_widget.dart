import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import '../utils/environment_config.dart';

class AccountDisplayWidget extends StatefulWidget {
  final String tradingMode; // 'DEMO' or 'LIVE'
  final VoidCallback onRefresh;

  const AccountDisplayWidget({
    Key? key,
    required this.tradingMode,
    required this.onRefresh,
  }) : super(key: key);

  @override
  State<AccountDisplayWidget> createState() => _AccountDisplayWidgetState();
}

class _AccountDisplayWidgetState extends State<AccountDisplayWidget> {
  List<Map<String, dynamic>> _accounts = [];
  bool _isLoading = false;
  String? _errorMessage;
  DateTime? _lastSyncTime;

  @override
  void initState() {
    super.initState();
    _fetchAccounts();
  }

  @override
  void didUpdateWidget(AccountDisplayWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tradingMode != widget.tradingMode) {
      _fetchAccounts();
    }
  }

  Future<void> _fetchAccounts() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');

      if (sessionToken == null || userId == null) {
        setState(() {
          _errorMessage = 'Not authenticated';
          _isLoading = false;
        });
        return;
      }

      // Fetch balance data for the current mode
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/accounts/balances'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
          'X-User-ID': userId,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final allAccounts = List<Map<String, dynamic>>.from(data['accounts'] ?? []);

        // Filter accounts based on trading mode
        final isLive = widget.tradingMode == 'LIVE';
        final filteredAccounts = allAccounts
            .where((acc) => (acc['is_live'] ?? false) == isLive)
            .toList();

        setState(() {
          _accounts = filteredAccounts;
          _lastSyncTime = DateTime.now();
          _isLoading = false;
        });

        print('✅ Loaded ${filteredAccounts.length} ${widget.tradingMode} accounts');
      } else {
        setState(() {
          _errorMessage = 'Failed to load accounts: ${response.statusCode}';
          _isLoading = false;
        });
        print('❌ Error: ${response.statusCode}');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isLoading = false;
      });
      print('❌ Error loading accounts: $e');
    }
  }

  String _formatAmount(double amount) {
    return '\$${amount.toStringAsFixed(2).replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',')}';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with mode indicator and refresh button
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: widget.tradingMode == 'LIVE' ? Colors.red : Colors.green,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '${widget.tradingMode} Accounts (${_accounts.length})',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            Row(
              children: [
                if (_lastSyncTime != null)
                  Text(
                    'Last sync: ${_lastSyncTime!.toLocal().hour}:${_lastSyncTime!.toLocal().minute.toString().padLeft(2, '0')}',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                const SizedBox(width: 8),
                if (_isLoading)
                  SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  IconButton(
                    icon: const Icon(Icons.refresh, size: 20),
                    onPressed: _fetchAccounts,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                  ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 12),

        // Account list or empty state
        if (_errorMessage != null)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.red.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red.shade200),
            ),
            child: Row(
              children: [
                Icon(Icons.error_outline, color: Colors.red.shade700),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(color: Colors.red.shade700),
                  ),
                ),
              ],
            ),
          )
        else if (_accounts.isEmpty)
          Container(
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.account_balance_wallet,
                    size: 48,
                    color: Colors.grey.shade400,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'No ${widget.tradingMode} accounts connected',
                    style: TextStyle(color: Colors.grey.shade700),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Add a broker account to get started',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          )
        else
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _accounts.length,
            itemBuilder: (context, index) {
              final account = _accounts[index];
              return _buildAccountCard(account);
            },
          ),
      ],
    );
  }

  Widget _buildAccountCard(Map<String, dynamic> account) {
    final broker = account['broker'] ?? 'Unknown';
    final accountNum = account['account_number'] ?? 'N/A';
    final balance = account['balance'] ?? 0.0;
    final equity = account['equity'] ?? 0.0;
    final activeBots = account['active_bots'] ?? 0;
    final lastUpdate = account['last_update'];

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Broker and account info
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      broker,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Account #$accountNum',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade700,
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: widget.tradingMode == 'LIVE'
                        ? Colors.red.shade100
                        : Colors.green.shade100,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    widget.tradingMode,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: widget.tradingMode == 'LIVE'
                          ? Colors.red.shade700
                          : Colors.green.shade700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Balance and Equity
            Grid(
              children: [
                GridItem(
                  label: 'Balance',
                  value: _formatAmount(balance),
                  color: Colors.blue,
                ),
                GridItem(
                  label: 'Equity',
                  value: _formatAmount(equity),
                  color: Colors.purple,
                ),
                GridItem(
                  label: 'Active Bots',
                  value: activeBots.toString(),
                  color: Colors.orange,
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Last update info
            if (lastUpdate != null)
              Text(
                'Updated: $lastUpdate',
                style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
              ),
          ],
        ),
      ),
    );
  }
}

class Grid extends StatelessWidget {
  final List<GridItem> children;

  const Grid({Key? key, required this.children}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(
        children.length,
        (index) => Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: index < children.length - 1 ? 12 : 0),
            child: _buildStatBox(children[index]),
          ),
        ),
      ),
    );
  }

  Widget _buildStatBox(GridItem item) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: item.color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: item.color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.label,
            style: TextStyle(
              fontSize: 11,
              color: item.color,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            item.value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: item.color,
            ),
          ),
        ],
      ),
    );
  }
}

class GridItem {
  final String label;
  final String value;
  final Color color;

  GridItem({
    required this.label,
    required this.value,
    required this.color,
  });
}
