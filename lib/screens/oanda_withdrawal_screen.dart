import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/oanda_trading_service.dart';
import '../services/auth_service.dart';
import '../services/notification_service.dart';

class OandaWithdrawalScreen extends StatefulWidget {
  const OandaWithdrawalScreen({Key? key}) : super(key: key);

  @override
  State<OandaWithdrawalScreen> createState() => _OandaWithdrawalScreenState();
}

class _OandaWithdrawalScreenState extends State<OandaWithdrawalScreen> {
  final _targetController = TextEditingController(text: '100');
  bool _autoClose = true;
  bool _checking = false;
  bool _loadingNotifs = false;
  Map<String, dynamic>? _lastCheckResult;
  List<dynamic> _notifications = [];

  @override
  void initState() {
    super.initState();
    _loadNotifications();
  }

  @override
  void dispose() {
    _targetController.dispose();
    super.dispose();
  }

  String get _userId => context.read<AuthService>().currentUser?.id ?? '';

  Future<void> _loadNotifications() async {
    if (_userId.isEmpty) return;
    setState(() => _loadingNotifs = true);
    try {
      final data = await OandaTradingService.getWithdrawalNotifications(_userId);
      if (mounted && data['success'] == true) {
        setState(() => _notifications = data['notifications'] ?? []);
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingNotifs = false);
  }

  Future<void> _runProfitCheck() async {
    final target = double.tryParse(_targetController.text) ?? 0;
    if (target <= 0) {
      _showSnack('Enter a valid profit target > \$0');
      return;
    }
    setState(() { _checking = true; _lastCheckResult = null; });

    final result = await OandaTradingService.profitCheck(
      targetProfit: target,
      userId: _userId,
      autoClose: _autoClose,
    );

    if (!mounted) return;
    setState(() { _checking = false; _lastCheckResult = result; });

    if (result['success'] == true && result['target_reached'] == true) {
      await OandaTradingService.createWithdrawalNotification(
        userId: _userId,
        realizedProfit: (result['current_pnl'] as num).toDouble(),
        positionsClosed: result['positions_closed'] ?? 0,
        balanceAvailable: (result['balance_after']?['available'] ?? 0).toDouble(),
      );
      NotificationService.showNotification(
        title: 'OANDA Profit Target Reached!',
        body: 'P&L: \$${(result['current_pnl'] as num).toStringAsFixed(2)} — '
            'Positions closed. Withdraw on OANDA now.',
        id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
      );
      _loadNotifications();
    }
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.grey[800]),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        title: Text('OANDA Withdrawals',
            style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 18)),
        actions: [
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
            _buildNotificationsSection(),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoBanner() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFF1B5E20), Color(0xFF004D40)]),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: Color(0xFF69F0AE), size: 28),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('How OANDA Withdrawals Work',
                    style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14)),
                const SizedBox(height: 4),
                Text(
                  '1. Set a profit target\n'
                  '2. System monitors & auto-closes trades when target is hit\n'
                  '3. You get notified to withdraw on OANDA\'s website/app\n'
                  '4. Mark as done once you\'ve withdrawn',
                  style: GoogleFonts.poppins(color: Colors.white60, fontSize: 11, height: 1.5),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProfitCheckCard() {
    return Container(
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
          Text('When open OANDA trades reach the target, they are auto-closed.',
              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          const SizedBox(height: 16),
          TextField(
            controller: _targetController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
            decoration: InputDecoration(
              labelText: 'Profit Target (\$)',
              labelStyle: GoogleFonts.poppins(color: Colors.white54),
              prefixIcon: const Icon(Icons.attach_money, color: Color(0xFF69F0AE)),
              filled: true,
              fillColor: Colors.white.withOpacity(0.06),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.white12),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Color(0xFF00E5FF), width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Switch(
                value: _autoClose,
                activeColor: const Color(0xFF69F0AE),
                onChanged: (v) => setState(() => _autoClose = v),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _autoClose
                      ? 'Auto-close trades when target is reached'
                      : 'Check only — don\'t close trades',
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
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.bolt),
              label: Text(_checking ? 'Checking...' : 'Check & Auto-Close',
                  style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF4CAF50),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: _checking ? null : _runProfitCheck,
            ),
          ),
        ],
      ),
    );
  }

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
        color: const Color(0xFF69F0AE), icon: Icons.check_circle,
        title: 'Target Reached!', subtitle: r['message'] ?? '',
        extra: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 10),
            _infoRow('P&L Realized', '\$${r['current_pnl']}'),
            _infoRow('Positions Closed', '${r['positions_closed']}'),
            if (r['balance_after'] != null) ...[
              _infoRow('Balance', '\$${r['balance_after']['balance']}'),
              _infoRow('Available', '\$${r['balance_after']['available']}'),
            ],
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.open_in_browser, color: Colors.orangeAccent, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text('Now go to oanda.com or the OANDA app to withdraw your funds.',
                        style: GoogleFonts.poppins(color: Colors.orangeAccent, fontSize: 12, fontWeight: FontWeight.w500)),
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
          _infoRow('Current P&L', '\$${r['current_pnl']}'),
          _infoRow('Target', '\$${r['target_profit']}'),
          _infoRow('Open Positions', '${r['positions_checked']}'),
        ],
      ),
    );
  }

  Widget _resultBox({required Color color, required IconData icon,
      required String title, required String subtitle, Widget? extra}) {
    return Container(
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
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          Text(value, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildNotificationsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const Icon(Icons.notifications_active, color: Color(0xFFFFD600), size: 20),
          const SizedBox(width: 8),
          Text('Withdrawal Notifications',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 4),
        Text('Profits realized — withdraw from OANDA when ready.',
            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
        const SizedBox(height: 12),
        if (_loadingNotifs)
          const Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50)))
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
          ...List<Widget>.from(_notifications.map((n) => _buildNotifCard(n))),
      ],
    );
  }

  Widget _buildNotifCard(dynamic n) {
    final isPending = n['status'] == 'pending';
    final profit = (n['realized_profit'] as num?)?.toDouble() ?? 0;
    final available = (n['balance_available'] as num?)?.toDouble() ?? 0;
    final date = n['created_at'] ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isPending ? Colors.orange.withOpacity(0.08) : const Color(0xFF69F0AE).withOpacity(0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isPending ? Colors.orange.withOpacity(0.3) : const Color(0xFF69F0AE).withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(isPending ? Icons.pending_actions : Icons.check_circle,
                color: isPending ? Colors.orangeAccent : const Color(0xFF69F0AE), size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(isPending ? 'Withdrawal Ready' : 'Withdrawn',
                  style: GoogleFonts.poppins(
                    color: isPending ? Colors.orangeAccent : const Color(0xFF69F0AE),
                    fontSize: 14, fontWeight: FontWeight.w600)),
            ),
            Text(date.length > 10 ? date.substring(0, 10) : date,
                style: GoogleFonts.poppins(color: Colors.white30, fontSize: 10)),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            _miniStat('Profit', '\$${profit.toStringAsFixed(2)}', const Color(0xFF69F0AE)),
            const SizedBox(width: 16),
            _miniStat('Positions', '${n['positions_closed'] ?? 0}', const Color(0xFF00E5FF)),
            const SizedBox(width: 16),
            _miniStat('Available', '\$${available.toStringAsFixed(2)}', const Color(0xFFFFD600)),
          ]),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white30, fontSize: 9)),
        Text(value, style: GoogleFonts.poppins(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }
}
