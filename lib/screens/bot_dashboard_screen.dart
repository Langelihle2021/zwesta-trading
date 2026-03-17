import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:async';
import '../services/bot_service.dart';
import '../services/ig_trading_service.dart';
import 'bot_analytics_screen.dart';
import 'bot_configuration_screen.dart';

class BotDashboardScreen extends StatefulWidget {
  const BotDashboardScreen({Key? key}) : super(key: key);

  @override
  State<BotDashboardScreen> createState() => _BotDashboardScreenState();
}

class _BotDashboardScreenState extends State<BotDashboardScreen> {
  Timer? _refreshTimer;
  String _searchQuery = '';
  String _filterStatus = 'all'; // 'all', 'active', 'inactive'

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<BotService>().fetchActiveBots();
    });
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (mounted) context.read<BotService>().fetchActiveBots();
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<BotService>(
      builder: (context, botService, _) {
        // Filter out demo bots
        final allBots = botService.activeBots.where((bot) {
          final id = (bot['botId'] ?? '').toString().toLowerCase();
          return !id.startsWith('demobot_') && !id.startsWith('demo_');
        }).toList();

        // Apply search + status filter
        final bots = allBots.where((bot) {
          final botId = (bot['botId'] ?? '').toString().toLowerCase();
          final symbol = (bot['symbol'] ?? bot['symbols'] ?? '').toString().toLowerCase();
          final strategy = (bot['strategy'] ?? '').toString().toLowerCase();
          final matchesSearch = _searchQuery.isEmpty ||
              botId.contains(_searchQuery.toLowerCase()) ||
              symbol.contains(_searchQuery.toLowerCase()) ||
              strategy.contains(_searchQuery.toLowerCase());
          final isEnabled = bot['enabled'] == true;
          final matchesFilter = _filterStatus == 'all' ||
              (_filterStatus == 'active' && isEnabled) ||
              (_filterStatus == 'inactive' && !isEnabled);
          return matchesSearch && matchesFilter;
        }).toList();

        // Top 5 newest bots (by creation time or just last 5)
        final newestBots = List<Map<String, dynamic>>.from(allBots);
        newestBots.sort((a, b) {
          final aTime = a['createdAt']?.toString() ?? a['created_at']?.toString() ?? '';
          final bTime = b['createdAt']?.toString() ?? b['created_at']?.toString() ?? '';
          return bTime.compareTo(aTime);
        });
        final top5 = newestBots.take(5).toList();

        final activeBots = allBots.where((b) => b['enabled'] == true).length;
        final totalProfit = allBots.fold<double>(
          0, (sum, b) => sum + (double.tryParse(b['profit']?.toString() ?? '0') ?? 0),
        );

        return Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF0A0E21), Color(0xFF1A1F3A), Color(0xFF0A0E21)],
            ),
          ),
          child: botService.isLoading && bots.isEmpty
              ? const Center(child: CircularProgressIndicator(color: Color(0xFF00E5FF)))
              : RefreshIndicator(
                  onRefresh: () => botService.fetchActiveBots(),
                  color: const Color(0xFF00E5FF),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [
                      // Summary row
                      Row(
                        children: [
                          _summaryChip(Icons.smart_toy, '$activeBots Active', const Color(0xFF69F0AE)),
                          const SizedBox(width: 10),
                          _summaryChip(Icons.list_alt, '${allBots.length} Total', const Color(0xFF00E5FF)),
                          const SizedBox(width: 10),
                          _summaryChip(
                            totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
                            '\$${totalProfit.toStringAsFixed(2)}',
                            totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Search bar
                      Container(
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.06),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.white.withOpacity(0.08)),
                        ),
                        child: TextField(
                          onChanged: (v) => setState(() => _searchQuery = v),
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
                          decoration: InputDecoration(
                            hintText: 'Search bots by name, symbol, strategy...',
                            hintStyle: GoogleFonts.poppins(color: Colors.white24, fontSize: 13),
                            prefixIcon: const Icon(Icons.search, color: Color(0xFF00E5FF), size: 20),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Filter chips
                      Row(
                        children: [
                          _filterChip('All', 'all'),
                          const SizedBox(width: 8),
                          _filterChip('Active', 'active'),
                          const SizedBox(width: 8),
                          _filterChip('Inactive', 'inactive'),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Top 5 Newest Bots (horizontal scroll)
                      if (top5.isNotEmpty) ...[
                        Text('Newest Bots', style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 10),
                        SizedBox(
                          height: 100,
                          child: ListView.builder(
                            scrollDirection: Axis.horizontal,
                            itemCount: top5.length,
                            itemBuilder: (_, i) => _buildMiniBot(top5[i]),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Create bot button
                      GestureDetector(
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BotConfigurationScreen())),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)]),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.add_circle_outline, color: Colors.white, size: 20),
                              const SizedBox(width: 8),
                              Text('Create New Bot', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),

                      if (bots.isEmpty && !botService.isLoading)
                        _emptyState()
                      else if (botService.errorMessage != null && bots.isEmpty)
                        _errorState(botService.errorMessage!)
                      else
                        ...bots.map((bot) => _buildBotCard(bot)),
                    ],
                  ),
                ),
        );
      },
    );
  }

  Widget _summaryChip(IconData icon, String label, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.06),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white.withOpacity(0.08)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 6),
            Flexible(
              child: Text(label, style: GoogleFonts.poppins(color: color, fontSize: 12, fontWeight: FontWeight.w600), overflow: TextOverflow.ellipsis),
            ),
          ],
        ),
      ),
    );
  }

  Widget _emptyState() {
    return Container(
      padding: const EdgeInsets.all(40),
      child: Column(
        children: [
          Icon(Icons.smart_toy_outlined, color: Colors.white.withOpacity(0.2), size: 64),
          const SizedBox(height: 16),
          Text('No bots created yet', style: GoogleFonts.poppins(color: Colors.white54, fontSize: 16)),
          const SizedBox(height: 8),
          Text('Tap "Create New Bot" to get started', style: GoogleFonts.poppins(color: Colors.white30, fontSize: 13)),
        ],
      ),
    );
  }

  Widget _errorState(String error) {
    return Container(
      padding: const EdgeInsets.all(24),
      margin: const EdgeInsets.only(top: 12),
      decoration: BoxDecoration(
        color: Colors.red.withOpacity(0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.red.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          const Icon(Icons.error_outline, color: Colors.redAccent, size: 36),
          const SizedBox(height: 12),
          Text(error, style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 13), textAlign: TextAlign.center),
          const SizedBox(height: 12),
          TextButton(
            onPressed: () => context.read<BotService>().fetchActiveBots(),
            child: Text('Retry', style: GoogleFonts.poppins(color: const Color(0xFF00E5FF))),
          ),
        ],
      ),
    );
  }

  Widget _buildBotCard(Map<String, dynamic> bot) {
    final botId = bot['botId'] ?? 'Unknown';
    final isEnabled = bot['enabled'] == true;
    final status = (bot['status'] ?? (isEnabled ? 'Active' : 'Inactive')).toString().toUpperCase();
    final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
    final totalTrades = int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0;
    final winRate = double.tryParse(bot['winRate']?.toString() ?? '0') ?? 0;
    final roi = double.tryParse(bot['roi']?.toString() ?? '0') ?? 0;
    final avgTrade = double.tryParse(bot['avgProfitPerTrade']?.toString() ?? '0') ?? 0;
    final maxDrawdown = double.tryParse(bot['maxDrawdown']?.toString() ?? '0') ?? 0;
    final todaysProfit = double.tryParse(bot['dailyProfit']?.toString() ?? '0') ?? 0;
    final symbols = bot['symbol'] ?? bot['symbols'] ?? 'N/A';
    final strategy = bot['strategy'] ?? 'Auto';
    final brokerType = bot['broker_type'] ?? bot['broker'] ?? 'MT5';
    final symbolStr = symbols is List ? (symbols as List).join(', ') : symbols.toString();
    final runtime = bot['runtimeFormatted'] ?? '--';

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.grey.shade200),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.07), blurRadius: 10, offset: const Offset(0, 4))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(botId, style: GoogleFonts.poppins(color: Colors.black, fontSize: 17, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(strategy, style: GoogleFonts.poppins(color: Colors.grey.shade600, fontSize: 12)),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: brokerType.toString().contains('IG') 
                              ? const Color(0xFFE91E63).withOpacity(0.15)
                              : brokerType.toString().toUpperCase().contains('BINANCE')
                              ? const Color(0xFFF7931A).withOpacity(0.15)
                              : const Color(0xFF2196F3).withOpacity(0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            brokerType.toString().contains('IG') 
                              ? 'IG'
                              : brokerType.toString().toUpperCase().contains('BINANCE')
                              ? 'BINANCE'
                              : 'MT5',
                            style: GoogleFonts.poppins(
                              color: brokerType.toString().contains('IG')
                                ? const Color(0xFFE91E63)
                                : brokerType.toString().toUpperCase().contains('BINANCE')
                                ? const Color(0xFFF7931A)
                                : const Color(0xFF2196F3),
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: isEnabled ? const Color(0xFF69F0AE) : Colors.grey,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  status,
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Text(symbolStr, style: GoogleFonts.poppins(color: Colors.black87, fontSize: 13, fontWeight: FontWeight.w500)),
          const SizedBox(height: 10),
          Row(
            children: [
              Text('Running for ', style: GoogleFonts.poppins(color: Colors.grey.shade700, fontSize: 12)),
              Text(runtime, style: GoogleFonts.poppins(color: Colors.black, fontWeight: FontWeight.w600, fontSize: 13)),
              const Spacer(),
              Text("Today's Profit ", style: GoogleFonts.poppins(color: Colors.grey.shade700, fontSize: 12)),
              Text('\$${todaysProfit.toStringAsFixed(2)}', style: GoogleFonts.poppins(color: const Color(0xFF388E3C), fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _botStat('Trades', '$totalTrades', Colors.blue.shade700),
              _botStat('Win Rate', '${winRate.toStringAsFixed(1)}%', Colors.green.shade700),
              _botStat('Profit', '\$${profit.toStringAsFixed(2)}', profit >= 0 ? Colors.green.shade700 : Colors.red.shade700),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _botStat('ROI', '${roi.toStringAsFixed(1)}%', Colors.orange.shade700),
              _botStat('Avg/Trade', '\$${avgTrade.toStringAsFixed(0)}', Colors.indigo.shade700),
              _botStat('Max Drawdown', '\$${maxDrawdown.toStringAsFixed(0)}', Colors.red.shade700),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isEnabled ? Colors.orange.shade600 : Colors.green.shade600,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: Icon(isEnabled ? Icons.pause : Icons.play_arrow),
                  label: Text(isEnabled ? 'Stop' : 'Start'),
                  onPressed: () async {
                    final botService = BotService();
                    final result = isEnabled
                      ? await botService.stopBotTrading(botId)
                      : await botService.startBotTrading(botId);
                    if (!mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text(result ? (isEnabled ? 'Bot stopped' : 'Bot started') : 'Action failed'),
                      backgroundColor: result ? Colors.green : Colors.red,
                    ));
                    // Refresh bot list
                    setState(() {});
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue.shade600,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.bar_chart),
                  label: const Text('Analytics'),
                  onPressed: () {
                    Navigator.push(context, MaterialPageRoute(
                      builder: (_) => BotAnalyticsScreen(bot: bot),
                    ));
                  },
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red.shade400,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.delete),
                  label: const Text('Delete'),
                  onPressed: () {
                    // TODO: Implement delete logic
                  },
                ),
              ),
            ],
          ),
          // IG Quick Actions (only for IG bots)
          if (brokerType.toString().toUpperCase().contains('IG')) ...[            const SizedBox(height: 10),
            Row(
              children: [
                _igQuickBtn(Icons.account_balance_wallet, 'Balance', Colors.green, () async {
                  final data = await IGTradingService.getBalance();
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text(data['success'] == true
                        ? 'IG Balance: \$${(data['balance'] ?? 0).toStringAsFixed(2)}'
                        : 'Error: ${data['error']}'),
                    backgroundColor: Colors.grey[800],
                  ));
                }),
                const SizedBox(width: 8),
                _igQuickBtn(Icons.list_alt, 'Positions', Colors.orange, () async {
                  final data = await IGTradingService.getPositions();
                  if (!mounted) return;
                  final count = (data['positions'] as List?)?.length ?? 0;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text('$count open IG position(s)'),
                    backgroundColor: Colors.grey[800],
                  ));
                }),
                const SizedBox(width: 8),
                _igQuickBtn(Icons.close_fullscreen, 'Close All', Colors.red, () async {
                  final confirmed = await showDialog<bool>(
                    context: context,
                    builder: (ctx) => AlertDialog(
                      title: const Text('Close All IG Positions?'),
                      content: const Text('This will close all open positions on your IG account.'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                        TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Confirm', style: TextStyle(color: Colors.red))),
                      ],
                    ),
                  );
                  if (confirmed != true) return;
                  final data = await IGTradingService.closeAllPositions();
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text(data['success'] == true
                        ? 'Closed ${data['closed']}/${data['total']} positions'
                        : 'Error: ${data['error']}'),
                    backgroundColor: Colors.grey[800],
                  ));
                }),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _botStat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: GoogleFonts.poppins(color: color, fontSize: 15, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _igQuickBtn(IconData icon, String label, Color color, VoidCallback onTap) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: color.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Column(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(height: 2),
              Text(label, style: GoogleFonts.poppins(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterChip(String label, String value) {
    final isSelected = _filterStatus == value;
    return GestureDetector(
      onTap: () => setState(() => _filterStatus = value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF00E5FF).withOpacity(0.2) : Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: isSelected ? const Color(0xFF00E5FF) : Colors.white12),
        ),
        child: Text(
          label,
          style: GoogleFonts.poppins(
            color: isSelected ? const Color(0xFF00E5FF) : Colors.white38,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  Widget _buildMiniBot(Map<String, dynamic> bot) {
    final botId = bot['botId'] ?? 'Unknown';
    final isEnabled = bot['enabled'] == true;
    final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;

    return GestureDetector(
      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => BotAnalyticsScreen(bot: bot))),
      child: Container(
        width: 140,
        margin: const EdgeInsets.only(right: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: isEnabled
                ? [const Color(0xFF69F0AE).withOpacity(0.1), const Color(0xFF00E5FF).withOpacity(0.1)]
                : [Colors.grey.withOpacity(0.1), Colors.grey.withOpacity(0.05)],
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isEnabled ? const Color(0xFF69F0AE).withOpacity(0.3) : Colors.white12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Icon(Icons.smart_toy, color: isEnabled ? const Color(0xFF69F0AE) : Colors.grey, size: 16),
                const SizedBox(width: 6),
                Expanded(child: Text(botId, style: GoogleFonts.poppins(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600), overflow: TextOverflow.ellipsis)),
              ],
            ),
            Text(
              '\$${profit.toStringAsFixed(2)}',
              style: GoogleFonts.poppins(
                color: profit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                fontSize: 14,
                fontWeight: FontWeight.bold,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: isEnabled ? const Color(0xFF69F0AE).withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                isEnabled ? 'Active' : 'Inactive',
                style: GoogleFonts.poppins(color: isEnabled ? const Color(0xFF69F0AE) : Colors.grey, fontSize: 9, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
