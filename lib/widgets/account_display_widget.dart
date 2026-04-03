import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../screens/account_detail_screen.dart';
import '../utils/environment_config.dart';

class AccountDisplayWidget extends StatefulWidget {

  const AccountDisplayWidget({
    required this.tradingMode, required this.onRefresh, Key? key,
  }) : super(key: key);
  final String tradingMode; // 'DEMO' or 'LIVE'
  final VoidCallback onRefresh;

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

  String _formatAmount(double amount) => '\$${amount.toStringAsFixed(2).replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',')}';

  @override
  Widget build(BuildContext context) => Column(
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
                  const SizedBox(
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

  Widget _buildAccountCard(Map<String, dynamic> account) {
    final broker = account['broker'] ?? 'Unknown';
    final accountNum = account['account_number'] ?? account['accountNumber'] ?? 'N/A';
    final balance = (account['balance'] is num) ? account['balance'].toDouble() : 0.0;
    final equity = (account['equity'] is num) ? account['equity'].toDouble() : 0.0;
    final marginFree = (account['marginFree'] is num) ? account['marginFree'].toDouble() : 0.0;
    final activeBots = account['active_bots'] ?? 0;
    final connected = account['connected'] ?? false;
    final dataSource = account['dataSource'] ?? 'unknown';
    final warning = account['warning'];

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => AccountDetailScreen(account: account),
          ),
        );
      },
      child: Card(
        margin: const EdgeInsets.only(bottom: 12),
        color: const Color(0xFF1A1E33),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(
            color: connected
                ? Colors.green.withOpacity(0.3)
                : Colors.orange.withOpacity(0.2),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Broker header row
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: connected ? Colors.green : Colors.orange,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            broker,
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Account #$accountNum',
                            style: const TextStyle(
                              fontSize: 11,
                              color: Colors.white54,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: widget.tradingMode == 'LIVE'
                              ? Colors.red.withOpacity(0.15)
                              : Colors.green.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          widget.tradingMode,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: widget.tradingMode == 'LIVE'
                                ? Colors.red.shade300
                                : Colors.green.shade300,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      const Icon(Icons.chevron_right,
                          color: Colors.white24, size: 20),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Balance / Equity / Margin row
              Row(
                children: [
                  _statBox('Balance', _formatAmount(balance), Colors.blue),
                  const SizedBox(width: 8),
                  _statBox('Equity', _formatAmount(equity), Colors.purple),
                  const SizedBox(width: 8),
                  _statBox('Free Margin', _formatAmount(marginFree), Colors.teal),
                ],
              ),
              const SizedBox(height: 8),

              // Bots + data source row
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(Icons.smart_toy, size: 14, color: Colors.orange.shade300),
                      const SizedBox(width: 4),
                      Text(
                        '$activeBots active bot${activeBots == 1 ? '' : 's'}',
                        style: TextStyle(
                            fontSize: 11, color: Colors.orange.shade300),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      if (dataSource == 'live')
                        Icon(Icons.wifi, size: 12, color: Colors.green.shade400)
                      else if (dataSource == 'cache_fresh')
                        Icon(Icons.cached, size: 12, color: Colors.blue.shade300)
                      else
                        Icon(Icons.wifi_off, size: 12, color: Colors.orange.shade300),
                      const SizedBox(width: 4),
                      Text(
                        dataSource == 'live'
                            ? 'Live data'
                            : dataSource.toString().contains('cache')
                                ? 'Cached'
                                : 'Offline',
                        style: const TextStyle(
                            fontSize: 10,
                            color: Colors.white30),
                      ),
                    ],
                  ),
                ],
              ),

              if (warning != null) ...[
                const SizedBox(height: 6),
                Text(warning,
                    style: TextStyle(fontSize: 10, color: Colors.orange.shade300)),
              ],

              // Tap hint
              const SizedBox(height: 6),
              const Center(
                child: Text(
                  'Tap for detailed financials',
                  style: TextStyle(fontSize: 10, color: Colors.white24),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _statBox(String label, String value, Color color) => Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: color.withOpacity(0.7),
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              value,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: color,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
}
