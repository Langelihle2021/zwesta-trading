import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/unified_broker_service.dart';
import '../widgets/logo_widget.dart';

class UnifiedBrokerDashboardScreen extends StatefulWidget {
  const UnifiedBrokerDashboardScreen({Key? key}) : super(key: key);

  @override
  State<UnifiedBrokerDashboardScreen> createState() => _UnifiedBrokerDashboardScreenState();
}

class _UnifiedBrokerDashboardScreenState extends State<UnifiedBrokerDashboardScreen> {
  bool _loading = true;
  bool _loadingPositions = false;
  bool _closingAll = false;
  Map<String, dynamic> _portfolio = {};
  Map<String, dynamic> _brokers = {};
  List<dynamic> _positions = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPortfolio();
  }

  Future<void> _loadPortfolio() async {
    setState(() { _loading = true; _error = null; });
    final data = await UnifiedBrokerService.getPortfolio();
    if (!mounted) return;
    if (data['success'] == true) {
      setState(() {
        _portfolio = data['portfolio'] ?? {};
        _brokers = Map<String, dynamic>.from(data['brokers'] ?? {});
        _loading = false;
      });
    } else {
      setState(() { _error = data['error'] ?? 'Failed to load'; _loading = false; });
    }
  }

  Future<void> _loadPositions() async {
    setState(() => _loadingPositions = true);
    final data = await UnifiedBrokerService.getAllPositions();
    if (!mounted) return;
    setState(() {
      _positions = data['positions'] ?? [];
      _loadingPositions = false;
    });
  }

  Future<void> _closeAll() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F3A),
        title: Text('Close ALL Positions?', style: GoogleFonts.poppins(color: Colors.redAccent, fontWeight: FontWeight.w600)),
        content: Text(
          'This will close ALL open positions across ALL brokers (Exness, OANDA, FXCM, Binance). This action cannot be undone.',
          style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Close All', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _closingAll = true);
    final result = await UnifiedBrokerService.closeAllPositions();
    if (!mounted) return;
    setState(() => _closingAll = false);

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(result['success'] == true
          ? 'Closed ${result['total_closed']} positions across all brokers'
          : 'Error: ${result['error']}'),
      backgroundColor: result['success'] == true ? Colors.green : Colors.red,
    ));

    _loadPortfolio();
    _loadPositions();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        title: Row(
          children: const [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Unified Portfolio'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () { _loadPortfolio(); _loadPositions(); }),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00E5FF)))
          : _error != null
              ? Center(child: Text(_error!, style: GoogleFonts.poppins(color: Colors.redAccent)))
              : RefreshIndicator(
                  onRefresh: () async { await _loadPortfolio(); await _loadPositions(); },
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildTotalCard(),
                        const SizedBox(height: 20),
                        _buildBrokerCards(),
                        const SizedBox(height: 20),
                        _buildPositionsSection(),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildTotalCard() {
    final bal = _portfolio['total_balance'] ?? 0;
    final avail = _portfolio['total_available'] ?? 0;
    final pnl = _portfolio['total_pnl'] ?? 0;
    final pos = _portfolio['total_positions'] ?? 0;
    final connected = _portfolio['connected_brokers'] ?? 0;
    final total = _portfolio['total_brokers'] ?? 0;
    final pnlPositive = (pnl as num) >= 0;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A237E), Color(0xFF0D47A1)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: const Color(0xFF1A237E).withOpacity(0.3), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Total Portfolio', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text('$connected/$total Brokers', style: GoogleFonts.poppins(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w500)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text('\$${_fmt(bal)}', style: GoogleFonts.poppins(color: Colors.white, fontSize: 32, fontWeight: FontWeight.w700)),
          const SizedBox(height: 14),
          Row(
            children: [
              _totalStat('Available', '\$${_fmt(avail)}', const Color(0xFF69F0AE)),
              const SizedBox(width: 24),
              _totalStat('P&L', '${pnlPositive ? '+' : ''}\$${_fmt(pnl)}', pnlPositive ? const Color(0xFF69F0AE) : Colors.redAccent),
              const SizedBox(width: 24),
              _totalStat('Positions', '$pos', const Color(0xFF00E5FF)),
            ],
          ),
          if (pos > 0) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                icon: _closingAll
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.redAccent))
                    : const Icon(Icons.close, color: Colors.redAccent, size: 18),
                label: Text(_closingAll ? 'Closing...' : 'Emergency Close All',
                    style: GoogleFonts.poppins(color: Colors.redAccent, fontWeight: FontWeight.w600, fontSize: 12)),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: Colors.redAccent),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: _closingAll ? null : _closeAll,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _totalStat(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
        Text(value, style: GoogleFonts.poppins(color: color, fontSize: 15, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _buildBrokerCards() {
    final brokerColors = {
      'IG': const Color(0xFFE53935),
      'OANDA': const Color(0xFF4CAF50),
      'FXCM': const Color(0xFF7C4DFF),
      'Binance': const Color(0xFFF0B90B),
    };
    final brokerIcons = {
      'IG': Icons.show_chart,
      'OANDA': Icons.trending_up,
      'FXCM': Icons.bar_chart,
      'Binance': Icons.currency_bitcoin,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Broker Breakdown', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        ..._brokers.entries.map((entry) {
          final name = entry.key;
          final data = Map<String, dynamic>.from(entry.value);
          final connected = data['connected'] == true;
          final color = brokerColors[name] ?? Colors.grey;
          final icon = brokerIcons[name] ?? Icons.business;

          return Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: connected ? color.withOpacity(0.08) : Colors.white.withOpacity(0.03),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: connected ? color.withOpacity(0.3) : Colors.white10),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: color.withOpacity(connected ? 0.2 : 0.05),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: connected ? color : Colors.white24, size: 24),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(name, style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: connected ? const Color(0xFF69F0AE).withOpacity(0.2) : Colors.redAccent.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(connected ? 'Connected' : 'Offline',
                                style: GoogleFonts.poppins(
                                  color: connected ? const Color(0xFF69F0AE) : Colors.redAccent,
                                  fontSize: 10, fontWeight: FontWeight.w600)),
                          ),
                        ],
                      ),
                      if (connected) ...[
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            _brokerStat('Balance', '\$${_fmt(data['balance'])}', Colors.white),
                            const SizedBox(width: 16),
                            _brokerStat('P&L', '${(data['pnl'] as num? ?? 0) >= 0 ? '+' : ''}\$${_fmt(data['pnl'])}',
                                (data['pnl'] as num? ?? 0) >= 0 ? const Color(0xFF69F0AE) : Colors.redAccent),
                            const SizedBox(width: 16),
                            _brokerStat('Pos', '${data['positions'] ?? 0}', const Color(0xFF00E5FF)),
                          ],
                        ),
                      ] else
                        Text(data['error'] ?? 'Not configured', style: GoogleFonts.poppins(color: Colors.white30, fontSize: 11)),
                    ],
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }

  Widget _brokerStat(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white30, fontSize: 9)),
        Text(value, style: GoogleFonts.poppins(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }

  Widget _buildPositionsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('All Open Positions', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
            TextButton.icon(
              onPressed: _loadingPositions ? null : _loadPositions,
              icon: _loadingPositions
                  ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00E5FF)))
                  : const Icon(Icons.download, color: Color(0xFF00E5FF), size: 16),
              label: Text(_loadingPositions ? 'Loading...' : 'Load Positions',
                  style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 12)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        if (_positions.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.04),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Column(children: [
              const Icon(Icons.inbox, color: Colors.white24, size: 36),
              const SizedBox(height: 8),
              Text('No positions loaded', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
              Text('Tap "Load Positions" to see all open trades.', style: GoogleFonts.poppins(color: Colors.white24, fontSize: 11)),
            ]),
          )
        else
          ...List<Widget>.from(_positions.map((p) => _buildPositionCard(p))),
      ],
    );
  }

  Widget _buildPositionCard(dynamic p) {
    final broker = p['broker'] ?? 'Unknown';
    final instrument = p['instrument'] ?? p['symbol'] ?? '';
    final direction = p['direction'] ?? p['side'] ?? '';
    final pnl = (p['unrealizedPL'] ?? p['pnl'] ?? 0).toDouble();
    final size = p['size'] ?? p['positionAmt'] ?? 0;
    final isBuy = direction.toString().toUpperCase() == 'BUY';
    final pnlPositive = pnl >= 0;

    final brokerColors = {
      'IG': const Color(0xFFE53935),
      'OANDA': const Color(0xFF4CAF50),
      'FXCM': const Color(0xFF7C4DFF),
      'Binance': const Color(0xFFF0B90B),
    };
    final color = brokerColors[broker] ?? Colors.grey;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
            decoration: BoxDecoration(
              color: color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(broker, style: GoogleFonts.poppins(color: color, fontSize: 9, fontWeight: FontWeight.w600)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(instrument, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
                Row(children: [
                  Icon(isBuy ? Icons.arrow_upward : Icons.arrow_downward,
                      color: isBuy ? const Color(0xFF69F0AE) : Colors.redAccent, size: 14),
                  const SizedBox(width: 4),
                  Text('$direction  |  Size: $size', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10)),
                ]),
              ],
            ),
          ),
          Text(
            '${pnlPositive ? '+' : ''}\$${pnl.toStringAsFixed(2)}',
            style: GoogleFonts.poppins(
              color: pnlPositive ? const Color(0xFF69F0AE) : Colors.redAccent,
              fontSize: 14, fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _fmt(dynamic value) {
    if (value == null) return '0.00';
    final num v = value is num ? value : double.tryParse(value.toString()) ?? 0;
    if (v.abs() >= 1000000) return '${(v / 1000000).toStringAsFixed(2)}M';
    if (v.abs() >= 1000) return '${(v / 1000).toStringAsFixed(2)}K';
    return v.toStringAsFixed(2);
  }
}
