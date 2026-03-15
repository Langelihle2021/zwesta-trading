import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:async';
import '../services/bot_service.dart';
import 'bot_analytics_screen.dart';
import 'bot_configuration_screen.dart';

class BotDashboardScreen extends StatefulWidget {
  const BotDashboardScreen({Key? key}) : super(key: key);

  @override
  State<BotDashboardScreen> createState() => _BotDashboardScreenState();
}

class _BotDashboardScreenState extends State<BotDashboardScreen> {
  Timer? _refreshTimer;

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
        final bots = botService.activeBots.where((bot) {
          final id = (bot['botId'] ?? '').toString().toLowerCase();
          return !id.startsWith('demobot_') && !id.startsWith('demo_');
        }).toList();

        final activeBots = bots.where((b) => b['enabled'] == true).length;
        final totalProfit = bots.fold<double>(
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
                          _summaryChip(Icons.list_alt, '${bots.length} Total', const Color(0xFF00E5FF)),
                          const SizedBox(width: 10),
                          _summaryChip(
                            totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
                            '\$${totalProfit.toStringAsFixed(2)}',
                            totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),

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
    final status = bot['status'] ?? (isEnabled ? 'Active' : 'Inactive');
    final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
    final totalTrades = int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0;
    final winRate = double.tryParse(bot['winRate']?.toString() ?? '0') ?? 0;
    final symbols = bot['symbol'] ?? bot['symbols'] ?? 'N/A';
    final strategy = bot['strategy'] ?? 'Auto';
    final symbolStr = symbols is List ? (symbols as List).join(', ') : symbols.toString();

    return GestureDetector(
      onTap: () {
        Navigator.push(context, MaterialPageRoute(
          builder: (_) => BotAnalyticsScreen(bot: bot),
        ));
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.06),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white.withOpacity(0.08)),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.15), blurRadius: 10, offset: const Offset(0, 4))],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: isEnabled ? const Color(0xFF69F0AE).withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.smart_toy, color: isEnabled ? const Color(0xFF69F0AE) : Colors.grey, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(botId, style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      Text(strategy, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isEnabled ? const Color(0xFF69F0AE).withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    status,
                    style: GoogleFonts.poppins(
                      color: isEnabled ? const Color(0xFF69F0AE) : Colors.grey,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            // Symbols
            Row(
              children: [
                const Icon(Icons.currency_exchange, color: Color(0xFF00E5FF), size: 14),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(symbolStr, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12), overflow: TextOverflow.ellipsis),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Stats row
            Row(
              children: [
                _botStat('Profit', '\$${profit.toStringAsFixed(2)}', profit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80)),
                _botStat('Trades', '$totalTrades', const Color(0xFF00E5FF)),
                _botStat('Win Rate', '${winRate.toStringAsFixed(1)}%', const Color(0xFF7C4DFF)),
              ],
            ),
            const SizedBox(height: 10),
            // Tap to view hint
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text('Tap for details', style: GoogleFonts.poppins(color: Colors.white24, fontSize: 10)),
                const SizedBox(width: 4),
                const Icon(Icons.chevron_right, color: Colors.white24, size: 14),
              ],
            ),
          ],
        ),
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
}
