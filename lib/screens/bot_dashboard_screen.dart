import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/currency_provider.dart';
import '../services/bot_service.dart';
import '../services/broker_credentials_service.dart';
import '../utils/environment_config.dart';
import '../widgets/account_display_widget.dart';
import '../widgets/logo_widget.dart';

import '../widgets/trading_mode_switcher.dart';
import 'bot_analytics_screen.dart';
import 'bot_configuration_screen.dart';
import 'consolidated_reports_screen.dart';
import 'dashboard_screen.dart';

class BotDashboardScreen extends StatefulWidget {
  const BotDashboardScreen({Key? key, this.embedded = false}) : super(key: key);

  final bool embedded;

  @override
  State<BotDashboardScreen> createState() => _BotDashboardScreenState();
}

class _BotDashboardScreenState extends State<BotDashboardScreen> {
  String _searchQuery = '';
  String _filterStatus = 'all'; // 'all', 'active', 'inactive'
  String _tradingMode = 'DEMO'; // Current trading mode: DEMO or LIVE
  bool _showAccountDetails = false; // Toggle to show account details

  @override
  void initState() {
    super.initState();
    _loadTradingMode();
  }

  Future<void> _loadTradingMode() async {
    final prefs = await SharedPreferences.getInstance();
    final mode = prefs.getString('trading_mode') ?? 'DEMO';
    setState(() => _tradingMode = mode);
    // Re-fetch bots with the correct mode
    if (mounted) {
      final botService = context.read<BotService>();
      botService.startPolling(tradingMode: mode);
      botService.fetchActiveBots(tradingMode: mode, force: true);
    }
  }

  void _onModeChanged(String newMode) {
    setState(() => _tradingMode = newMode);
    // Re-fetch bots filtered by the new mode
    final botService = context.read<BotService>();
    botService.startPolling(tradingMode: newMode);
    botService.fetchActiveBots(tradingMode: newMode, force: true);
  }

  @override
  void dispose() {
    context.read<BotService>().stopPolling();
    super.dispose();
  }

  String _currencySymbol(AppCurrency currency) {
    switch (currency) {
      case AppCurrency.usd:
        return r'$';
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

  String _normalizeCurrencyCode(dynamic value) {
    final currency = value?.toString().trim().toUpperCase();
    return currency == null || currency.isEmpty ? 'USD' : currency;
  }

  String _symbolForCode(String currencyCode) {
    switch (_normalizeCurrencyCode(currencyCode)) {
      case 'ZAR':
        return 'R';
      case 'GBP':
        return 'GBP';
      case 'USD':
      default:
        return r'$';
    }
  }

  String _formatAmount(
    CurrencyProvider currencyProvider,
    double amount, {
    int decimals = 2,
    String? currencyCode,
  }) {
    final symbol = _symbolForCode(currencyCode ?? _currencyCode(currencyProvider.currency));
    final absoluteAmount = amount.abs().toStringAsFixed(decimals);

    if (amount < 0) {
      return '-$symbol$absoluteAmount';
    }
    return '$symbol$absoluteAmount';
  }

  String _formatBotAggregate(CurrencyProvider currencyProvider, List<Map<String, dynamic>> bots, String field, {int decimals = 2}) {
    final totals = <String, double>{};
    for (final bot in bots) {
      final currency = _normalizeCurrencyCode(bot['displayCurrency'] ?? bot['accountCurrency'] ?? bot['currency']);
      final amount = double.tryParse(bot[field]?.toString() ?? '0') ?? 0.0;
      totals[currency] = (totals[currency] ?? 0.0) + amount;
    }
    if (totals.isEmpty) {
      return _formatAmount(currencyProvider, 0, decimals: decimals);
    }
    final entries = totals.entries.toList()..sort((a, b) => a.key.compareTo(b.key));
    return entries
        .map((entry) => _formatAmount(currencyProvider, entry.value, decimals: decimals, currencyCode: entry.key))
        .join(' • ');
  }

  @override
  Widget build(BuildContext context) {
    final content = Consumer2<BotService, CurrencyProvider>(
      builder: (context, botService, currencyProvider, _) {
        // Bots are already filtered by trading mode from the backend
        final allBots = List<Map<String, dynamic>>.from(botService.activeBots);

        // Apply search + status filter
        final bots = allBots.where((bot) {
          final botId = (bot['botId'] ?? '').toString().toLowerCase();
          final symbol = (bot['symbol'] ?? bot['symbols'] ?? '').toString().toLowerCase();
          final strategy = (bot['strategy'] ?? '').toString().toLowerCase();
          final matchesSearch = _searchQuery.isEmpty ||
              botId.contains(_searchQuery.toLowerCase()) ||
              symbol.contains(_searchQuery.toLowerCase()) ||
              strategy.contains(_searchQuery.toLowerCase());
          final isEnabled = bot['enabled'] == true || bot['status'] == 'Active';
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

        final activeBots = allBots.where((b) => b['enabled'] == true || b['status'] == 'Active').length;
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
                  onRefresh: () => botService.fetchActiveBots(tradingMode: _tradingMode, force: true),
                  color: const Color(0xFF00E5FF),
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [
                      // ⭐ TRADING MODE SWITCHER & ACCOUNT DISPLAY
                      Theme(
                        data: Theme.of(context).copyWith(
                          cardColor: Colors.white.withOpacity(0.06),
                          primaryColor: const Color(0xFF00E5FF),
                        ),
                        child: Column(
                          children: [
                            // Mode Switcher (Compact pill style)
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Account Mode',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                TradingModeSwitcher(
                                  currentMode: _tradingMode,
                                  onModeChanged: _onModeChanged,
                                  isCompact: true,
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),

                            // Account Details Toggle & Display
                            if (_showAccountDetails)
                              Container(
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(
                                  color: Colors.white.withOpacity(0.04),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: Colors.white.withOpacity(0.08),
                                  ),
                                ),
                                child: AccountDisplayWidget(
                                  tradingMode: _tradingMode,
                                  onRefresh: () {
                                    context.read<BotService>().fetchActiveBots(tradingMode: _tradingMode, force: true);
                                  },
                                ),
                              )
                            else
                              Center(
                                child: TextButton.icon(
                                  onPressed: () =>
                                      setState(() => _showAccountDetails = true),
                                  icon: const Icon(Icons.account_balance_wallet,
                                      size: 20, color: Color(0xFF00E5FF)),
                                  label: const Text(
                                    'Show Account Details',
                                    style: TextStyle(
                                      color: Color(0xFF00E5FF),
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ),
                            const SizedBox(height: 16),
                          ],
                        ),
                      ),


                      // Summary row
                      Row(
                        children: [
                          _summaryChip(Icons.smart_toy, '$activeBots Active', const Color(0xFF69F0AE)),
                          const SizedBox(width: 10),
                          _summaryChip(Icons.list_alt, '${allBots.length} Total', const Color(0xFF00E5FF)),
                          const SizedBox(width: 10),
                          _summaryChip(
                            totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
                            _formatBotAggregate(currencyProvider, allBots, 'profit'),
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
                              items: AppCurrency.values.map((currency) => DropdownMenuItem<AppCurrency>(
                                  value: currency,
                                  child: Text(_currencyCode(currency)),
                                )).toList(),
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

                      // ⭐ BINANCE QUICK BOT - One-Click Creation
                      GestureDetector(
                        onTap: () {
                          // Show presets dialog or create directly
                          _showBinanceQuickCreateDialog(context);
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF3BA2F).withOpacity(0.15),
                            border: Border.all(color: const Color(0xFFF3BA2F), width: 2),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Text('₿ ', style: TextStyle(fontSize: 22)),
                              const SizedBox(width: 8),
                              Text(
                                'Quick Binance Bot',
                                style: GoogleFonts.poppins(
                                  color: const Color(0xFFF3BA2F),
                                  fontWeight: FontWeight.w700,
                                  fontSize: 14,
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Icon(Icons.flash_on, color: Color(0xFFF3BA2F), size: 18),
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

    if (widget.embedded) {
      return content;
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        elevation: 0,
        title: const Row(
          children: [
            LogoWidget(size: 36, showText: false),
            SizedBox(width: 10),
            Text('Bot Monitor'),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Reports',
            icon: const Icon(Icons.assessment_outlined),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ConsolidatedReportsScreen()),
              );
            },
          ),
          IconButton(
            tooltip: 'Dashboard',
            icon: const Icon(Icons.dashboard_rounded),
            onPressed: () {
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const DashboardScreen()),
                (route) => route.isFirst,
              );
            },
          ),
        ],
      ),
      body: content,
    );
  }

  Widget _summaryChip(IconData icon, String label, Color color) => Expanded(
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

  Widget _emptyState() => Container(
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

  Widget _errorState(String error) => Container(
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
            onPressed: () => context.read<BotService>().fetchActiveBots(tradingMode: _tradingMode, force: true),
            child: Text('Retry', style: GoogleFonts.poppins(color: const Color(0xFF00E5FF))),
          ),
        ],
      ),
    );

  Widget _buildBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) => _buildUnifiedBotCard(bot, currencyProvider);

  Widget _buildUnifiedBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) {
    final botId = bot['botId'] ?? 'Unknown';
    final isEnabled = bot['enabled'] == true || bot['status'] == 'Active';
    final status = (bot['status'] ?? (isEnabled ? 'Active' : 'Inactive')).toString().toUpperCase();
    final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
    final totalTrades = int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0;
    final winRate = double.tryParse(bot['winRate']?.toString() ?? '0') ?? 0;
    final roi = double.tryParse(bot['roi']?.toString() ?? '0') ?? 0;
    final avgTrade = double.tryParse(bot['avgProfitPerTrade']?.toString() ?? '0') ?? 0;
    final maxDrawdown = double.tryParse(bot['maxDrawdown']?.toString() ?? '0') ?? 0;
    final todaysProfit = double.tryParse(bot['dailyProfit']?.toString() ?? '0') ?? 0;
    final accountBalance = double.tryParse(bot['accountBalance']?.toString() ?? '0') ?? 0;
    final accountEquity = double.tryParse(bot['accountEquity']?.toString() ?? '0') ?? 0;
    final openPositions = (bot['openPositionsPreview'] as List?) ?? (bot['openPositions'] as List?) ?? [];
    final openPositionsCount = int.tryParse(bot['openPositionsCount']?.toString() ?? '${openPositions.length}') ?? openPositions.length;
    final symbols = bot['symbol'] ?? bot['symbols'] ?? 'N/A';
    final strategy = bot['strategy'] ?? 'Auto';
    final brokerType = bot['broker_type'] ?? bot['broker'] ?? 'MT5';
    final displayCurrency = _normalizeCurrencyCode(bot['displayCurrency'] ?? bot['accountCurrency'] ?? bot['currency']);
    final symbolStr = symbols is List ? symbols.join(', ') : symbols.toString();
    final runtime = bot['runtimeFormatted'] ?? '--';
    final drawdownPauseUntilText = bot['drawdownPauseUntil']?.toString();
    final drawdownPauseUntil = drawdownPauseUntilText == null || drawdownPauseUntilText.isEmpty
      ? null
      : DateTime.tryParse(drawdownPauseUntilText);
    final isCoolingDown = drawdownPauseUntil != null && drawdownPauseUntil.isAfter(DateTime.now());
    final activeSymbolCooldowns = (bot['activeSymbolCooldowns'] as List?) ?? [];

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
                      'Cooling down until ${DateFormat('HH:mm').format(drawdownPauseUntil.toLocal())}',
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
                            color: brokerType.toString().toUpperCase().contains('BINANCE')
                              ? const Color(0xFFF7931A).withOpacity(0.2)
                              : const Color(0xFF2196F3).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(
                              color: brokerType.toString().toUpperCase().contains('BINANCE')
                                ? const Color(0xFFF7931A).withOpacity(0.5)
                                : const Color(0xFF2196F3).withOpacity(0.5),
                            ),
                          ),
                          child: Text(
                            brokerType.toString().toUpperCase().contains('BINANCE')
                              ? 'BINANCE'
                              : 'MT5',
                            style: GoogleFonts.poppins(
                              color: brokerType.toString().toUpperCase().contains('BINANCE')
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
              Text(_formatAmount(currencyProvider, todaysProfit, currencyCode: displayCurrency), style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontWeight: FontWeight.bold, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _botStat('Trades', '$totalTrades', const Color(0xFF00E5FF)),
              _botStat('Win Rate', '${winRate.toStringAsFixed(1)}%', const Color(0xFF69F0AE)),
              _botStat('Profit', _formatAmount(currencyProvider, profit, currencyCode: displayCurrency), profit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _botStat('ROI', '${roi.toStringAsFixed(1)}%', const Color(0xFFFFA726)),
              _botStat('Avg/Trade', _formatAmount(currencyProvider, avgTrade, decimals: 0, currencyCode: displayCurrency), const Color(0xFFAB47BC)),
              _botStat('Max Drawdown', _formatAmount(currencyProvider, maxDrawdown, decimals: 0, currencyCode: displayCurrency), const Color(0xFFFF8A80)),
            ],
          ),
          // Account Balance & Equity
          if (accountBalance > 0) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF00E5FF).withOpacity(0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF00E5FF).withOpacity(0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.account_balance_wallet, color: Color(0xFF00E5FF), size: 16),
                          const SizedBox(width: 8),
                          Text('Balance', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                        ],
                      ),
                      Flexible(
                        child: Text(
                          _formatAmount(currencyProvider, accountBalance, currencyCode: displayCurrency),
                          style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontWeight: FontWeight.w700, fontSize: 14),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  if (accountEquity > 0 && accountEquity != accountBalance) ...[
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.trending_up, color: Color(0xFF69F0AE), size: 16),
                            const SizedBox(width: 8),
                            Text('Equity', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                          ],
                        ),
                        Flexible(
                          child: Text(
                            _formatAmount(currencyProvider, accountEquity, currencyCode: displayCurrency),
                            style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
          // Open Positions
          if (openPositionsCount > 0) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                const Icon(Icons.candlestick_chart, color: Color(0xFFFFA726), size: 16),
                const SizedBox(width: 6),
                Text(
                  'Open Positions ($openPositionsCount)',
                  style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ...openPositions.take(5).map((pos) {
              final posSymbol = pos['symbol']?.toString() ?? '';
              final posType = pos['type']?.toString() ?? '';
              final posVolume = double.tryParse(pos['volume']?.toString() ?? '0') ?? 0;
              final posEntry = double.tryParse(pos['entryPrice']?.toString() ?? '0') ?? 0;
              final posCurrent = double.tryParse(pos['currentPrice']?.toString() ?? '0') ?? 0;
              final posProfit = double.tryParse(pos['profit']?.toString() ?? '0') ?? 0;
              final isBuy = posType.toUpperCase().contains('BUY');
              return Container(
                margin: const EdgeInsets.only(bottom: 4),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.04),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white.withOpacity(0.06)),
                ),
                child: Row(
                  children: [
                    Icon(
                      isBuy ? Icons.arrow_upward : Icons.arrow_downward,
                      color: isBuy ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                      size: 14,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      posSymbol,
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: (isBuy ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80)).withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        isBuy ? 'BUY' : 'SELL',
                        style: GoogleFonts.poppins(
                          color: isBuy ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const Spacer(),
                    Flexible(
                      child: Text(
                        '${posVolume.toStringAsFixed(2)} lots',
                        style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        '@ ${posEntry.toStringAsFixed(posEntry > 100 ? 2 : 5)}',
                        style: GoogleFonts.poppins(color: Colors.white70, fontSize: 11),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (posCurrent > 0 || posProfit != 0) ...[
                      const SizedBox(width: 6),
                      Text(
                        _formatAmount(currencyProvider, posProfit, currencyCode: displayCurrency),
                        style: GoogleFonts.poppins(
                          color: posProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
                if ((pos['profitProtectionArmed'] == true) || (pos['lockedProfitFloor'] != null) || (pos['breakEvenFloor'] != null)) ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      if (pos['profitProtectionBucket'] != null)
                        _buildProtectionChip(
                          'Protect ${pos['profitProtectionBucket']}',
                          const Color(0xFF26A69A),
                        ),
                      if ((double.tryParse(pos['lockedProfitFloor']?.toString() ?? '0') ?? 0) > 0)
                        _buildProtectionChip(
                          'Floor ${_formatAmount(currencyProvider, double.tryParse(pos['lockedProfitFloor']?.toString() ?? '0') ?? 0, currencyCode: displayCurrency)}',
                          const Color(0xFF26A69A),
                        ),
                      if ((double.tryParse(pos['breakEvenFloor']?.toString() ?? '0') ?? 0) > 0)
                        _buildProtectionChip(
                          'BE+ ${_formatAmount(currencyProvider, double.tryParse(pos['breakEvenFloor']?.toString() ?? '0') ?? 0, currencyCode: displayCurrency)}',
                          const Color(0xFF42A5F5),
                        ),
                    ],
                  ),
                ],
              );
            }),
            if (openPositionsCount > 5)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '+${openPositionsCount - 5} more positions',
                  style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
                ),
              ),
            if (activeSymbolCooldowns.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: activeSymbolCooldowns.take(3).map((cooldown) {
                  final cooldownUntil = DateTime.tryParse(cooldown['until']?.toString() ?? '');
                  final label = cooldownUntil == null
                      ? '${cooldown['symbol']} cooldown'
                      : '${cooldown['symbol']} until ${DateFormat('HH:mm').format(cooldownUntil.toLocal())}';
                  return _buildProtectionChip(label, const Color(0xFFFFA726));
                }).toList(),
              ),
            ],
          ],
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
                        final botService = context.read<BotService>();
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
              const SizedBox(width: 6),
              // Overflow menu for less-used actions (Delete)
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert, color: Colors.white54, size: 22),
                color: const Color(0xFF1A1F3A),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                onSelected: (value) async {
                  if (value == 'delete') {
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
                    final deleted = await botService.deleteBot(botId);
                    if (!mounted) return;
                    if (deleted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('$botId deleted'),
                          backgroundColor: Colors.red,
                          duration: const Duration(seconds: 2),
                        ),
                      );
                      setState(() {});
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(botService.errorMessage ?? 'Failed to delete $botId'),
                          backgroundColor: Colors.orange,
                          duration: const Duration(seconds: 3),
                        ),
                      );
                    }
                  }
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'delete',
                    child: Row(
                      children: [
                        const Icon(Icons.delete_outline, color: Colors.redAccent, size: 18),
                        const SizedBox(width: 8),
                        Text('Delete Bot', style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 13)),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildProtectionChip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: GoogleFonts.poppins(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _botStat(String label, String value, Color color) => Expanded(
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

  // IG Markets integration removed

  /// Quick broker button for dashboard quick actions
  Widget _quickBrokerButton({
    required String label,
    required Color color,
    required VoidCallback onTap,
    dynamic icon,
    String? description,
  }) => GestureDetector(
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

  /// Create bot for specific broker - with quick create option for Binance
  void _createBotForBroker(BuildContext context, String brokerName) async {
    if (brokerName == 'Binance') {
      // Show quick create dialog for Binance
      _showBinanceQuickCreateDialog(context);
    } else {
      // Standard bot creation flow
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => const BotConfigurationScreen(),
        ),
      );
    }
  }

  /// Show quick create dialog for Binance with preset options
  void _showBinanceQuickCreateDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A2E),
        title: Row(
          children: [
            const Text('₿ ', style: TextStyle(fontSize: 24, color: Color(0xFFF3BA2F))),
            Text('Quick Binance Bot', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w700)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Choose a trading preset to create your bot instantly:',
              style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13),
            ),
            const SizedBox(height: 20),
            _binancePresetOption(
              dialogContext,
              '🚀 Top Edge (6 pairs)',
              'Best win rates: BTC, ETH, SOL, XRP, BNB, LTC',
              'top_edge',
            ),
            const SizedBox(height: 10),
            _binancePresetOption(
              dialogContext,
              '⚖️  Balanced (6 pairs)',
              'Low-medium risk: BTC, ETH, LINK, ADA, DOGE, MATIC',
              'balanced',
            ),
            const SizedBox(height: 10),
            _binancePresetOption(
              dialogContext,
              '🔶 DeFi & L2 (6 pairs)',
              'High volatility: UNI, AAVE, APT, INJ, SUI, FTM',
              'defi',
            ),
            const SizedBox(height: 10),
            _binancePresetOption(
              dialogContext,
              '📈 Large Cap (6 pairs)',
              'Stable focus: BTC, ETH, BNB, SOL, ADA, XRP',
              'large_cap_only',
            ),
            const SizedBox(height: 20),
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
                // Show standard configuration screen
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const BotConfigurationScreen()),
                );
              },
              child: Text(
                'Custom Setup',
                style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Individual Binance preset option button
  Widget _binancePresetOption(BuildContext context, String title, String description, String preset) => InkWell(
      onTap: () => _quickCreateBinanceBot(context, preset),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFF3BA2F).withOpacity(0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: GoogleFonts.poppins(color: const Color(0xFFF3BA2F), fontWeight: FontWeight.w600, fontSize: 12)),
            const SizedBox(height: 4),
            Text(description, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 11)),
          ],
        ),
      ),
    );

  /// Quick create Binance bot with preset
  void _quickCreateBinanceBot(BuildContext context, String preset) async {
    Navigator.pop(context); // Close dialog
    
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      
      if (sessionToken == null || sessionToken.isEmpty) {
        _showErrorSnackbar('⚠️ Session expired. Please login again.');
        return;
      }
      
      final brokerService = BrokerCredentialsService();
      
      await brokerService.fetchCredentials();
      final credential = brokerService.activeCredential;
      
      if (credential == null) {
        _showErrorSnackbar('⚠️ Please setup Binance broker integration first');
        return;
      }
      
      if (credential.broker.toLowerCase() != 'binance') {
        _showErrorSnackbar('⚠️ This quick create only works with Binance broker');
        return;
      }
      
      // Verify credentialId exists
      if (credential.credentialId.isEmpty) {
        _showErrorSnackbar('⚠️ Invalid Binance credential');
        return;
      }
      
      // Show loading dialog
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF1A1A2E),
          content: Row(
            children: [
              const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.white60)),
              ),
              const SizedBox(width: 16),
              Text('Creating quick bot...', style: GoogleFonts.poppins(color: Colors.white70)),
            ],
          ),
        ),
      );
      
      // Call quick create endpoint
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/quick-create'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({
          'credentialId': credential.credentialId,
          'preset': preset,
        }),
      ).timeout(const Duration(seconds: 15));
      
      if (!mounted) return;
      Navigator.pop(context); // Close loading dialog
      
      if (response.statusCode == 201 || response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final botId = data['botId'] ?? 'Bot';
        final pairs = (data['pairs'] as List?)?.join(', ') ?? 'N/A';
        
        // Show success dialog
        showDialog(
          context: context,
          builder: (ctx) => AlertDialog(
            backgroundColor: const Color(0xFF1A1A2E),
            title: Row(
              children: [
                const Text('✅', style: TextStyle(fontSize: 24)),
                const SizedBox(width: 8),
                Expanded(child: Text('Bot Created', style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontWeight: FontWeight.w700))),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Your quick bot is ready!', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13)),
                const SizedBox(height: 12),
                _infoRow('Bot ID', botId, Colors.white60),
                const SizedBox(height: 8),
                _infoRow('Pairs', pairs, Colors.white60),
                const SizedBox(height: 8),
                _infoRow('Status', '🟢 Running', const Color(0xFF69F0AE)),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  // Refresh bot list
                  final botService = Provider.of<BotService>(context, listen: false);
                  botService.fetchActiveBots(tradingMode: _tradingMode);
                  setState(() {});
                },
                child: Text('Done', style: GoogleFonts.poppins(color: const Color(0xFF00E5FF))),
              ),
            ],
          ),
        );
      } else {
        final error = jsonDecode(response.body)['error'] ?? 'Failed to create bot';
        _showErrorSnackbar('❌ $error');
      }
    } catch (e) {
      _showErrorSnackbar('❌ Error: $e');
    }
  }

  /// Helper widget to display info rows
  Widget _infoRow(String label, String value, Color valueColor) => Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
        Text(value, style: GoogleFonts.poppins(color: valueColor, fontSize: 12, fontWeight: FontWeight.w600)),
      ],
    );

  /// Show error snackbar
  void _showErrorSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message, style: GoogleFonts.poppins(color: Colors.white)),
        backgroundColor: Colors.red.shade700,
        duration: const Duration(seconds: 3),
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

  Widget _buildNewestBotCard(Map<String, dynamic> bot, CurrencyProvider currencyProvider) => _buildUnifiedBotCard(bot, currencyProvider);

  Widget _buildStatCard(String value, String label, Color color) => Container(
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

  Widget _buildMiniBot(Map<String, dynamic> bot) {
    final botId = bot['botId'] ?? 'Unknown';
    final isEnabled = bot['enabled'] == true;
    final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
    final displayCurrency = _normalizeCurrencyCode(bot['displayCurrency'] ?? bot['accountCurrency'] ?? bot['currency']);

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
              '${_symbolForCode(displayCurrency)}${profit.toStringAsFixed(2)}',
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
