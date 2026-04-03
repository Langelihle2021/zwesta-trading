import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../services/unified_broker_service.dart';

class CryptoStrategiesScreen extends StatefulWidget {
  const CryptoStrategiesScreen({Key? key}) : super(key: key);

  @override
  State<CryptoStrategiesScreen> createState() => _CryptoStrategiesScreenState();
}

class _CryptoStrategiesScreenState extends State<CryptoStrategiesScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _loadingCatalog = true;
  bool _loadingActive = false;
  List<dynamic> _strategies = [];
  List<dynamic> _activeStrategies = [];

  static const _gold = Color(0xFFF0B90B);
  static const _bg = Color(0xFF0A0E21);

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadCatalog();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadCatalog() async {
    setState(() => _loadingCatalog = true);
    final data = await UnifiedBrokerService.getCryptoStrategies();
    if (!mounted) return;
    setState(() {
      _strategies = data['strategies'] ?? [];
      _loadingCatalog = false;
    });
  }

  Future<void> _loadActive() async {
    setState(() => _loadingActive = true);
    final userId = context.read<AuthService>().currentUser?.id ?? '0';
    final data = await UnifiedBrokerService.getActiveStrategies(userId);
    if (!mounted) return;
    setState(() {
      _activeStrategies = data['active_strategies'] ?? [];
      _loadingActive = false;
    });
  }

  Future<void> _activateStrategy(Map<String, dynamic> strategy) async {
    final params = Map<String, dynamic>.from(strategy['configurable_params'] ?? {});
    final pairController = TextEditingController(text: (strategy['supported_pairs'] as List?)?.first ?? 'BTCUSDT');
    final paramControllers = <String, TextEditingController>{};
    for (final key in params.keys) {
      paramControllers[key] = TextEditingController(text: params[key]['default'].toString());
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F3A),
        title: Text('Activate ${strategy['name']}',
            style: GoogleFonts.poppins(color: _gold, fontWeight: FontWeight.w600, fontSize: 16)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(strategy['description'] ?? '', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
              const SizedBox(height: 16),
              _dialogField('Trading Pair', pairController),
              const SizedBox(height: 8),
              ...paramControllers.entries.map((e) {
                final info = params[e.key];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _dialogField(
                    '${e.key.replaceAll('_', ' ')} (${info['type'] ?? 'text'})',
                    e.value,
                    hint: 'min: ${info['min']}, max: ${info['max']}',
                  ),
                );
              }),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _gold),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('Activate', style: TextStyle(color: Colors.black.withOpacity(0.87))),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final configParams = <String, dynamic>{};
    for (final e in paramControllers.entries) {
      configParams[e.key] = double.tryParse(e.value.text) ?? e.value.text;
    }

    final userId = context.read<AuthService>().currentUser?.id ?? '0';
    final result = await UnifiedBrokerService.activateStrategy(
      userId: userId,
      strategyId: strategy['id'],
      pair: pairController.text,
      params: configParams,
    );
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(result['success'] == true ? 'Strategy activated!' : 'Error: ${result['error']}'),
      backgroundColor: result['success'] == true ? Colors.green : Colors.red,
    ));

    if (result['success'] == true) {
      _tabController.animateTo(1);
      _loadActive();
    }
  }

  Future<void> _deactivate(String botId) async {
    final result = await UnifiedBrokerService.deactivateStrategy(botId);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(result['success'] == true ? 'Strategy deactivated' : 'Error: ${result['error']}'),
      backgroundColor: result['success'] == true ? Colors.green : Colors.red,
    ));
    if (result['success'] == true) _loadActive();
  }

  Widget _dialogField(String label, TextEditingController ctrl, {String? hint}) => TextField(
      controller: ctrl,
      style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: GoogleFonts.poppins(color: Colors.white38, fontSize: 12),
        hintText: hint,
        hintStyle: GoogleFonts.poppins(color: Colors.white24, fontSize: 11),
        filled: true,
        fillColor: Colors.white.withOpacity(0.06),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
    );

  @override
  Widget build(BuildContext context) => Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        title: Text('Crypto Bot Strategies', style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 18)),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: _gold,
          labelColor: _gold,
          unselectedLabelColor: Colors.white54,
          labelStyle: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13),
          onTap: (i) { if (i == 1 && _activeStrategies.isEmpty) _loadActive(); },
          tabs: const [Tab(text: 'Strategies'), Tab(text: 'Active Bots')],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [_buildCatalog(), _buildActive()],
      ),
    );

  Widget _buildCatalog() {
    if (_loadingCatalog) return const Center(child: CircularProgressIndicator(color: _gold));
    if (_strategies.isEmpty) {
      return Center(child: Text('No strategies available', style: GoogleFonts.poppins(color: Colors.white38)));
    }
    return RefreshIndicator(
      onRefresh: _loadCatalog,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _strategies.length,
        itemBuilder: (ctx, i) => _buildStrategyCard(_strategies[i]),
      ),
    );
  }

  Widget _buildStrategyCard(Map<String, dynamic> s) {
    final risk = s['risk_level'] ?? 'Medium';
    final riskColor = risk == 'Low' ? const Color(0xFF69F0AE) : risk == 'High' ? Colors.redAccent : _gold;
    final pairs = (s['supported_pairs'] as List?)?.join(', ') ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A1F3A), Color(0xFF111633)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _gold.withOpacity(0.15)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _gold.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.smart_toy, color: _gold, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s['name'] ?? '', style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                      Row(children: [
                        _chip(s['market_type'] ?? '', const Color(0xFF00E5FF)),
                        const SizedBox(width: 6),
                        _chip(risk, riskColor),
                      ]),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(s['description'] ?? '', style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12, height: 1.5)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6, runSpacing: 4,
              children: pairs.split(', ').map((p) => _chip(p, Colors.white24)).toList(),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: const Icon(Icons.play_arrow, size: 18),
                label: Text('Activate Strategy', style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _gold,
                  foregroundColor: Colors.black87,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () => _activateStrategy(s),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String text, Color color) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
      child: Text(text, style: GoogleFonts.poppins(color: color, fontSize: 10, fontWeight: FontWeight.w500)),
    );

  Widget _buildActive() {
    if (_loadingActive) return const Center(child: CircularProgressIndicator(color: _gold));
    if (_activeStrategies.isEmpty) {
      return Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.smart_toy_outlined, color: Colors.white24, size: 48),
          const SizedBox(height: 12),
          Text('No active strategies', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 14)),
          const SizedBox(height: 4),
          Text('Activate a strategy from the catalog.', style: GoogleFonts.poppins(color: Colors.white24, fontSize: 12)),
        ]),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadActive,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _activeStrategies.length,
        itemBuilder: (ctx, i) => _buildActiveCard(_activeStrategies[i]),
      ),
    );
  }

  Widget _buildActiveCard(Map<String, dynamic> a) {
    final profit = (a['total_profit'] ?? 0).toDouble();
    final profitPositive = profit >= 0;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _gold.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.smart_toy, color: _gold, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(a['strategy_id'] ?? '', style: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: const Color(0xFF69F0AE).withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
                child: Text('Active', style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 10, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _activeStat('Pair', a['pair'] ?? '', Colors.white),
              const SizedBox(width: 20),
              _activeStat('Trades', '${a['total_trades'] ?? 0}', const Color(0xFF00E5FF)),
              const SizedBox(width: 20),
              _activeStat('Profit', '${profitPositive ? '+' : ''}\$${profit.toStringAsFixed(2)}',
                  profitPositive ? const Color(0xFF69F0AE) : Colors.redAccent),
            ],
          ),
          const SizedBox(height: 8),
          Text('Started: ${a['created_at'] ?? 'N/A'}', style: GoogleFonts.poppins(color: Colors.white24, fontSize: 10)),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              icon: const Icon(Icons.stop, color: Colors.redAccent, size: 16),
              label: Text('Deactivate', style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.w600)),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Colors.redAccent),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () => _deactivate(a['bot_strategy_id']?.toString() ?? ''),
            ),
          ),
        ],
      ),
    );
  }

  Widget _activeStat(String label, String value, Color color) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white30, fontSize: 10)),
        Text(value, style: GoogleFonts.poppins(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
}
