import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../services/binance_trading_service.dart';
import '../services/notification_service.dart';
import 'bot_dashboard_screen.dart';
import 'consolidated_reports_screen.dart';

class BinanceWithdrawalScreen extends StatefulWidget {
  const BinanceWithdrawalScreen({Key? key}) : super(key: key);

  @override
  State<BinanceWithdrawalScreen> createState() => _BinanceWithdrawalScreenState();
}

class _BinanceWithdrawalScreenState extends State<BinanceWithdrawalScreen> {
  final _targetController = TextEditingController(text: '100');
  final _walletController = TextEditingController();
  final _withdrawAmountController = TextEditingController();
  bool _autoClose = true;
  bool _checking = false;
  bool _withdrawing = false;
  bool _loadingNotifs = false;
  String _selectedNetwork = 'TRC20';
  Map<String, dynamic>? _lastCheckResult;
  List<dynamic> _notifications = [];

  final List<Map<String, String>> _networks = [
    {'value': 'TRC20', 'label': 'TRC20 (Tron)', 'fee': r'~$1'},
    {'value': 'BEP20', 'label': 'BEP20 (BSC)', 'fee': r'~$0.30'},
    {'value': 'ERC20', 'label': 'ERC20 (Ethereum)', 'fee': r'~$5-20'},
  ];

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  @override
  void dispose() {
    _targetController.dispose();
    _walletController.dispose();
    _withdrawAmountController.dispose();
    super.dispose();
  }

  String get _userId => context.read<AuthService>().currentUser?.id ?? '';

  Future<void> _loadNotifications() async {
    if (_userId.isEmpty) return;
    setState(() => _loadingNotifs = true);
    try {
      final data = await BinanceTradingService.getWithdrawalNotifications(_userId);
      if (mounted && data['success'] == true) {
        setState(() => _notifications = data['notifications'] ?? []);
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingNotifs = false);
  }

  Future<void> _runProfitCheck() async {
    final target = double.tryParse(_targetController.text) ?? 0;
    if (target <= 0) {
      _showSnack(r'Enter a valid profit target > $0');
      return;
    }
    setState(() { _checking = true; _lastCheckResult = null; });

    final result = await BinanceTradingService.profitCheck(
      targetProfit: target,
      userId: _userId,
      autoClose: _autoClose,
    );

    if (!mounted) return;
    setState(() { _checking = false; _lastCheckResult = result; });

    if (result['success'] == true && result['target_reached'] == true) {
      await BinanceTradingService.createWithdrawalNotification(
        userId: _userId,
        realizedProfit: (result['current_pnl'] as num).toDouble(),
        positionsClosed: result['positions_closed'] ?? 0,
        balanceAvailable: (result['balance_after']?['available'] ?? 0).toDouble(),
      );
      NotificationService.showNotification(
        title: 'Binance Profit Target Reached!',
        body: 'P&L: \$${(result['current_pnl'] as num).toStringAsFixed(2)} USDT — '
            'Positions closed. Withdraw USDT now.',
        id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
      );
      _loadNotifications();
    }
  }

  Future<void> _withdrawUsdt() async {
    final amount = double.tryParse(_withdrawAmountController.text) ?? 0;
    final address = _walletController.text.trim();

    if (amount <= 0) {
      _showSnack('Enter a valid amount > 0');
      return;
    }
    if (address.isEmpty) {
      _showSnack('Enter your USDT wallet address');
      return;
    }

    setState(() => _withdrawing = true);
    final result = await BinanceTradingService.withdrawUsdt(
      amount: amount,
      address: address,
      network: _selectedNetwork,
    );
    if (!mounted) return;
    setState(() => _withdrawing = false);

    if (result['success'] == true) {
      _showSnack('Withdrawal initiated! ${result['message'] ?? ''}');
      _withdrawAmountController.clear();
    } else {
      _showSnack('Error: ${result['error'] ?? 'Unknown'}');
    }
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.grey[800]),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        title: Text('Binance Withdrawals',
            style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 18)),
        actions: [
          IconButton(
            icon: const Icon(Icons.home_outlined),
            tooltip: 'Home',
            onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
          ),
          IconButton(
            icon: const Icon(Icons.smart_toy_outlined),
            tooltip: 'Bots',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const BotDashboardScreen()));
            },
          ),
          IconButton(
            icon: const Icon(Icons.assessment_outlined),
            tooltip: 'Reports',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const ConsolidatedReportsScreen()));
            },
          ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadNotifications),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildInfoBanner(),
            const SizedBox(height: 20),
            _buildProfitCheckCard(),
            if (_lastCheckResult != null) ...[
              const SizedBox(height: 16),
              _buildCheckResultCard(),
            ],
            const SizedBox(height: 24),
            _buildWithdrawCard(),
            const SizedBox(height: 24),
            _buildNotificationsSection(),
          ],
        ),
      ),
    );

  Widget _buildInfoBanner() => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFFF0B90B), Color(0xFFE8A90A)]),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Icon(Icons.currency_bitcoin, color: Colors.black87, size: 28),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('How Binance Crypto Withdrawals Work',
                    style: GoogleFonts.poppins(color: Colors.black87, fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                Text(
                  '1. Set a USDT profit target for your futures positions\n'
                  '2. System auto-closes trades when target is hit\n'
                  '3. Enter your USDT wallet address below\n'
                  '4. Withdraw profits directly in USDT (TRC20/BEP20)',
                  style: GoogleFonts.poppins(color: Colors.black54, fontSize: 11, height: 1.5),
                ),
              ],
            ),
          ),
        ],
      ),
    );

  Widget _buildProfitCheckCard() => Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Profit Target & Auto-Close',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text('When open Binance futures positions reach the target, they are auto-closed.',
              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          const SizedBox(height: 16),
          TextField(
            controller: _targetController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Profit Target (USDT)',
              labelStyle: GoogleFonts.poppins(color: Colors.white54),
              prefixIcon: const Icon(Icons.currency_bitcoin, color: Color(0xFFF0B90B)),
              filled: true,
              fillColor: Colors.white.withOpacity(0.06),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.white12),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Color(0xFFF0B90B), width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Switch(
                value: _autoClose,
                activeColor: const Color(0xFFF0B90B),
                onChanged: (v) => setState(() => _autoClose = v),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _autoClose
                      ? 'Auto-close positions when target is reached'
                      : 'Check only — don\'t close positions',
                  style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              icon: _checking
                  ? const SizedBox(width: 18, height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                  : const Icon(Icons.bolt, color: Colors.black87),
              label: Text(_checking ? 'Checking...' : 'Check & Auto-Close',
                  style: GoogleFonts.poppins(fontWeight: FontWeight.w600, color: Colors.black87)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFF0B90B),
                foregroundColor: Colors.black87,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _checking ? null : _runProfitCheck,
            ),
          ),
        ],
      ),
    );

  Widget _buildCheckResultCard() {
    final r = _lastCheckResult!;
    final success = r['success'] == true;
    final reached = r['target_reached'] == true;

    if (!success) {
      return _resultBox(color: Colors.red, icon: Icons.error_outline,
          title: 'Error', subtitle: r['error'] ?? 'Unknown error');
    }

    if (reached) {
      return _resultBox(
        color: const Color(0xFFF0B90B), icon: Icons.check_circle,
        title: 'Target Reached!', subtitle: r['message'] ?? '',
        extra: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 10),
            _infoRow('P&L Realized', '${r['current_pnl']} USDT'),
            _infoRow('Positions Closed', '${r['positions_closed']}'),
            if (r['balance_after'] != null) ...[
              _infoRow('Balance', '${r['balance_after']['balance']} USDT'),
              _infoRow('Available', '${r['balance_after']['available']} USDT'),
            ],
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF0B90B).withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.account_balance_wallet, color: Color(0xFFF0B90B), size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text('Use the withdrawal card below to send USDT to your wallet.',
                        style: GoogleFonts.poppins(color: const Color(0xFFF0B90B), fontSize: 12, fontWeight: FontWeight.w500)),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return _resultBox(
      color: const Color(0xFFFFD600), icon: Icons.hourglass_top,
      title: 'Not Yet Reached', subtitle: r['message'] ?? '',
      extra: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 10),
          _infoRow('Current P&L', '${r['current_pnl']} USDT'),
          _infoRow('Target', '${r['target_profit']} USDT'),
          _infoRow('Open Positions', '${r['positions_checked']}'),
        ],
      ),
    );
  }

  Widget _buildWithdrawCard() => Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFF0B90B).withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.send, color: Color(0xFFF0B90B), size: 22),
            const SizedBox(width: 10),
            Text('Withdraw USDT',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 4),
          Text('Send USDT directly to your crypto wallet.',
              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          const SizedBox(height: 16),

          // Network selector
          Text('Network', style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: _networks.map((n) => ChoiceChip(
              label: Text('${n['label']} ${n['fee']}',
                  style: GoogleFonts.poppins(
                    fontSize: 11,
                    color: _selectedNetwork == n['value'] ? Colors.black87 : Colors.white60,
                  )),
              selected: _selectedNetwork == n['value'],
              selectedColor: const Color(0xFFF0B90B),
              backgroundColor: Colors.white.withOpacity(0.08),
              onSelected: (v) {
                if (v) setState(() => _selectedNetwork = n['value']!);
              },
            )).toList(),
          ),
          const SizedBox(height: 16),

          // Wallet address
          TextField(
            controller: _walletController,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
            decoration: InputDecoration(
              labelText: 'USDT Wallet Address',
              labelStyle: GoogleFonts.poppins(color: Colors.white54),
              hintText: _selectedNetwork == 'TRC20' ? 'T...' : '0x...',
              hintStyle: GoogleFonts.poppins(color: Colors.white24),
              prefixIcon: const Icon(Icons.account_balance_wallet, color: Color(0xFFF0B90B)),
              filled: true,
              fillColor: Colors.white.withOpacity(0.06),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.white12),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Color(0xFFF0B90B), width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Amount
          TextField(
            controller: _withdrawAmountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Amount (USDT)',
              labelStyle: GoogleFonts.poppins(color: Colors.white54),
              prefixIcon: const Icon(Icons.attach_money, color: Color(0xFFF0B90B)),
              filled: true,
              fillColor: Colors.white.withOpacity(0.06),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.white12),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Color(0xFFF0B90B), width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 16),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              icon: _withdrawing
                  ? const SizedBox(width: 18, height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                  : const Icon(Icons.send, color: Colors.black87),
              label: Text(_withdrawing ? 'Sending...' : 'Withdraw USDT',
                  style: GoogleFonts.poppins(fontWeight: FontWeight.w600, color: Colors.black87)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFF0B90B),
                foregroundColor: Colors.black87,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _withdrawing ? null : _withdrawUsdt,
            ),
          ),
        ],
      ),
    );

  Widget _resultBox({required Color color, required IconData icon,
      required String title, required String subtitle, Widget? extra}) => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(width: 10),
            Text(title, style: GoogleFonts.poppins(color: color, fontSize: 16, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 6),
          Text(subtitle, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
          if (extra != null) extra,
        ],
      ),
    );

  Widget _infoRow(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          Text(value, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );

  Widget _buildNotificationsSection() => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const Icon(Icons.notifications_active, color: Color(0xFFF0B90B), size: 20),
          const SizedBox(width: 8),
          Text('Withdrawal Notifications',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 4),
        Text('Profits realized — withdraw USDT to your wallet.',
            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
        const SizedBox(height: 12),
        if (_loadingNotifs)
          const Center(child: CircularProgressIndicator(color: Color(0xFFF0B90B)))
        else if (_notifications.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.04),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(children: [
              const Icon(Icons.inbox, color: Colors.white24, size: 40),
              const SizedBox(height: 8),
              Text('No notifications yet',
                  style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
              Text('Run a profit check above to get started.',
                  style: GoogleFonts.poppins(color: Colors.white24, fontSize: 11)),
            ]),
          )
        else
          ...List<Widget>.from(_notifications.map(_buildNotifCard)),
      ],
    );

  Widget _buildNotifCard(dynamic n) {
    final isPending = n['status'] == 'pending';
    final profit = (n['realized_profit'] as num?)?.toDouble() ?? 0;
    final available = (n['balance_available'] as num?)?.toDouble() ?? 0;
    final date = n['created_at'] ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isPending ? const Color(0xFFF0B90B).withOpacity(0.08) : const Color(0xFF69F0AE).withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isPending ? const Color(0xFFF0B90B).withOpacity(0.3) : const Color(0xFF69F0AE).withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(isPending ? Icons.pending_actions : Icons.check_circle,
                color: isPending ? const Color(0xFFF0B90B) : const Color(0xFF69F0AE), size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(isPending ? 'Withdrawal Ready' : 'Withdrawn',
                  style: GoogleFonts.poppins(
                    color: isPending ? const Color(0xFFF0B90B) : const Color(0xFF69F0AE),
                    fontSize: 14, fontWeight: FontWeight.w600)),
            ),
            Text(date.length > 10 ? date.substring(0, 10) : date,
                style: GoogleFonts.poppins(color: Colors.white30, fontSize: 10)),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            _miniStat('Profit', '${profit.toStringAsFixed(2)} USDT', const Color(0xFFF0B90B)),
            const SizedBox(width: 16),
            _miniStat('Positions', '${n['positions_closed'] ?? 0}', const Color(0xFF00E5FF)),
            const SizedBox(width: 16),
            _miniStat('Available', '${available.toStringAsFixed(2)} USDT', const Color(0xFF69F0AE)),
          ]),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value, Color color) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white30, fontSize: 9)),
        Text(value, style: GoogleFonts.poppins(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
}
