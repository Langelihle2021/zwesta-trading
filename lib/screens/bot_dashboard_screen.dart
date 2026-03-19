import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:async';
import 'package:intl/intl.dart';
import '../providers/currency_provider.dart';
import '../services/bot_service.dart';
import '../services/ig_trading_service.dart';
import '../widgets/logo_widget.dart';
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

  String _currencySymbol(AppCurrency currency) {
    switch (currency) {
      case AppCurrency.usd:
        return '\$';
      case AppCurrency.zar:
        return 'R';
      case AppCurrency.gbp:
        return 'GBP';
    }
  }

  String _currencyCode(AppCurrency currency) {
    switch (currency) {
      case AppCurrency.usd:
        return 'USD';
      case AppCurrency.zar:
        return 'ZAR';
      case AppCurrency.gbp:
        return 'GBP';
    }
  }

  String _formatAmount(
    CurrencyProvider currencyProvider,
    double amount, {
    int decimals = 2,
  }) {
    // Always display as USD - no currency conversion (backend enforces USD)
    const symbol = '\$';
    final absoluteAmount = amount.abs().toStringAsFixed(decimals);

    if (amount < 0) {
      return '-$symbol$absoluteAmount';
    }
    return '$symbol$absoluteAmount';
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<BotService, CurrencyProvider>(
      builder: (context, botService, currencyProvider, _) {
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
        final featuredBotIds = top5.map((bot) => (bot['botId'] ?? '').toString()).toSet();
        final remainingBots = bots.where((bot) => !featuredBotIds.contains((bot['botId'] ?? '').toString())).toList();

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
          child: allBots.isEmpty && botService.isLoading
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
                            _formatAmount(currencyProvider, totalProfit),
                            totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.06),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white.withOpacity(0.08)),
                          ),
                          child: DropdownButtonHideUnderline(
                            child: DropdownButton<AppCurrency>(
                              value: currencyProvider.currency,
                              dropdownColor: const Color(0xFF1A1F3A),
                              iconEnabledColor: const Color(0xFF00E5FF),
                              style: GoogleFonts.poppins(color: Colors.white, fontSize: 12),
                              items: AppCurrency.values.map((currency) {
                                return DropdownMenuItem<AppCurrency>(
                                  value: currency,
                                  child: Text(_currencyCode(currency)),
                                );
                              }).toList(),
                              onChanged: (value) {
                                if (value != null) {
                                  currencyProvider.setCurrency(value);
                                }
                              },
                            ),
                          ),
                        ),
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

                      // Top Newest Bots (full vertical cards - newest first)
                      if (top5.isNotEmpty) ...[
                        ...top5.map((bot) => _buildNewestBotCard(bot, currencyProvider)),
                        const SizedBox(height: 16),
                      ],

                      // Create bot button
                      GestureDetector(
                        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BotConfigurationScreen())),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)],
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                            ),
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFF00E5FF).withOpacity(0.3),
                                blurRadius: 16,
                                offset: const Offset(0, 6),
                              ),
                            ],
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.add_circle_outline, color: Colors.white, size: 22),
                              const SizedBox(width: 10),
                              Text('Create New Bot', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15, letterSpacing: 0.3)),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Quick Action Links for Popular Brokers
                      Text(
                        'Quick Create',
                        style: GoogleFonts.poppins(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white70),
                      ),
                      const SizedBox(height: 8),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            // Binance Quick Creator
                            _quickBrokerButton(
                              icon: '₿',
                              label: 'Binance',
                              color: const Color(0xFFF3BA2F),
                              onTap: () => _createBotForBroker(context, 'Binance'),
                              description: 'Crypto pairs',
                            ),
                            const SizedBox(width: 10),
                            // Forex Quick Creator
                            _quickBrokerButton(
                              icon: Icons.currency_exchange,
                              label: 'Forex',
                              color: const Color(0xFF4CAF50),
                              onTap: () => _createBotForBroker(context, 'Exness'),
                              description: 'USD, EUR...',
                            ),
                            const SizedBox(width: 10),
                            // Commodities Quick Creator
                            _quickBrokerButton(
                              icon: Icons.trending_up,
                              label: 'Commodities',
                              color: const Color(0xFFFF9800),
                              onTap: () => _createBotForBroker(context, 'Exness'),
                              description: 'Gold, Oil...',
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),

                      if (bots.isEmpty && !botService.isLoading)
                        _emptyState()
                      else if (botService.errorMessage != null && bots.isEmpty)
                        _errorState(botService.errorMessage!)
                      else
                        ...remainingBots.map((bot) => _buildBotCard(bot, currencyProvider)),
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

  Widget _buildBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) {
    return _buildUnifiedBotCard(bot, currencyProvider);
  }

  Widget _buildUnifiedBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) {
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
    final drawdownPauseUntilText = bot['drawdownPauseUntil']?.toString();
    final drawdownPauseUntil = drawdownPauseUntilText == null || drawdownPauseUntilText.isEmpty
      ? null
      : DateTime.tryParse(drawdownPauseUntilText);
    final isCoolingDown = drawdownPauseUntil != null && drawdownPauseUntil.isAfter(DateTime.now());

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
        boxShadow: [
          BoxShadow(
            color: isEnabled ? const Color(0xFF69F0AE).withOpacity(0.1) : Colors.black.withOpacity(0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isCoolingDown) ...[
            Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFFFA726).withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFFFA726).withOpacity(0.35)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.timer_outlined, color: Color(0xFFFFA726), size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Cooling down until ${DateFormat('HH:mm').format(drawdownPauseUntil!.toLocal())}',
                      style: GoogleFonts.poppins(
                        color: const Color(0xFFFFCC80),
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          // Header row
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(botId, style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(strategy, style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12)),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: brokerType.toString().contains('IG') 
                              ? const Color(0xFFE91E63).withOpacity(0.2)
                              : brokerType.toString().toUpperCase().contains('BINANCE')
                              ? const Color(0xFFF7931A).withOpacity(0.2)
                              : const Color(0xFF2196F3).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                              color: brokerType.toString().contains('IG')
                                ? const Color(0xFFE91E63).withOpacity(0.5)
                                : brokerType.toString().toUpperCase().contains('BINANCE')
                                ? const Color(0xFFF7931A).withOpacity(0.5)
                                : const Color(0xFF2196F3).withOpacity(0.5),
                            ),
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
                  color: isEnabled
                    ? const Color(0xFF69F0AE).withOpacity(0.2)
                    : Colors.grey.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isEnabled
                      ? const Color(0xFF69F0AE)
                      : Colors.grey,
                  ),
                ),
                child: Text(
                  status,
                  style: GoogleFonts.poppins(
                    color: isEnabled
                      ? const Color(0xFF69F0AE)
                      : Colors.grey,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.05),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            child: Text(symbolStr, style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500)),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text('Running for ', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
              Text(runtime, style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13)),
              const Spacer(),
              Text("Today's Profit ", style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
              Text(_formatAmount(currencyProvider, todaysProfit), style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _botStat('Trades', '$totalTrades', const Color(0xFF00E5FF)),
              _botStat('Win Rate', '${winRate.toStringAsFixed(1)}%', const Color(0xFF69F0AE)),
              _botStat('Profit', _formatAmount(currencyProvider, profit), profit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _botStat('ROI', '${roi.toStringAsFixed(1)}%', const Color(0xFFFFA726)),
              _botStat('Avg/Trade', _formatAmount(currencyProvider, avgTrade, decimals: 0), const Color(0xFFAB47BC)),
              _botStat('Max Drawdown', _formatAmount(currencyProvider, maxDrawdown, decimals: 0), const Color(0xFFFF8A80)),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: isEnabled 
                        ? [const Color(0xFFFFA726), const Color(0xFFFF7043)]
                        : [const Color(0xFF66BB6A), const Color(0xFF43A047)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: (isEnabled ? const Color(0xFFFFA726) : const Color(0xFF66BB6A)).withOpacity(0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () async {
                        final botService = BotService();
                        final result = isEnabled
                          ? await botService.stopBotTrading(botId)
                          : await botService.startBotTrading(botId);
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                          content: Text(result ? (isEnabled ? 'Bot stopped' : 'Bot started') : 'Action failed'),
                          backgroundColor: result ? Colors.green : Colors.red,
                          duration: const Duration(seconds: 2),
                        ));
                        setState(() {});
                      },
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(isEnabled ? Icons.pause_circle : Icons.play_circle, size: 18),
                            const SizedBox(width: 8),
                            Text(
                              isEnabled ? 'Stop' : 'Start',
                              style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF00E5FF), Color(0xFF00BCD4)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF00E5FF).withOpacity(0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () {
                        Navigator.push(context, MaterialPageRoute(
                          builder: (_) => BotAnalyticsScreen(bot: bot),
                        ));
                      },
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.analytics, size: 18),
                            const SizedBox(width: 8),
                            Text(
                              'Analytics',
                              style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFFF7043), Color(0xFFE64A19)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFFFF7043).withOpacity(0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () async {
                        final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: Text('Delete $botId?', style: const TextStyle(color: Colors.white)),
                            backgroundColor: const Color(0xFF0A0E21),
                            content: const Text(
                              'This action cannot be undone.',
                              style: TextStyle(color: Colors.white70),
                            ),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(ctx, false),
                                child: Text('Cancel', style: GoogleFonts.poppins(color: Colors.white70)),
                              ),
                              TextButton(
                                onPressed: () => Navigator.pop(ctx, true),
                                child: Text('Delete', style: GoogleFonts.poppins(color: Colors.red)),
                              ),
                            ],
                          ),
                        );
                        if (confirmed != true) return;
                        final botService = context.read<BotService>();
                        botService.removeBotLocally(botId);
                        if (!mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('✓ $botId deleted'),
                            backgroundColor: Colors.red,
                            duration: const Duration(seconds: 2),
                          ),
                        );
                        setState(() {});
                      },
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.delete_outline, size: 18),
                            const SizedBox(width: 8),
                            Text(
                              'Delete',
                              style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
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
                        ? 'IG Balance: ${_formatAmount(currencyProvider, ((data['balance'] ?? 0) as num).toDouble())}'
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
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: color.withOpacity(0.3)),
            ),
            child: Text(
              value,
              style: GoogleFonts.poppins(color: color, fontSize: 13, fontWeight: FontWeight.w600),
            ),
          ),
          const SizedBox(height: 4),
          Text(label, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 10)),
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

  /// Quick broker button for dashboard quick actions
  Widget _quickBrokerButton({
    required String label,
    required Color color,
    required VoidCallback onTap,
    dynamic icon,
    String? description,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.15),
          border: Border.all(color: color.withOpacity(0.5)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon is String)
              Text(
                icon,
                style: const TextStyle(fontSize: 24),
              )
            else if (icon is IconData)
              Icon(icon, color: color, size: 20),
            const SizedBox(height: 4),
            Text(
              label,
              style: GoogleFonts.poppins(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (description != null) ...[
              const SizedBox(height: 2),
              Text(
                description,
                style: GoogleFonts.poppins(
                  color: color.withOpacity(0.7),
                  fontSize: 9,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Create bot for specific broker
  void _createBotForBroker(BuildContext context, String brokerName) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const BotConfigurationScreen(),
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

  Widget _buildNewestBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) {
    return _buildUnifiedBotCard(bot, currencyProvider);
  }

  Widget _buildStatCard(String value, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            value,
            style: GoogleFonts.poppins(
              color: color,
              fontSize: 14,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: GoogleFonts.poppins(
              color: Colors.white60,
              fontSize: 10,
            ),
          ),
        ],
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
