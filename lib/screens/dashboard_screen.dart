import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../l10n/app_localizations.dart';
import '../models/trade.dart';
import '../providers/fallback_status_provider.dart';
import '../services/auth_service.dart';
import '../services/bot_service.dart';
import '../services/trading_service.dart';
import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';
import 'account_management_screen.dart';
import 'admin_dashboard_screen.dart';
import 'admin_withdrawal_verification_screen.dart';
import 'binance_withdrawal_screen.dart';
import 'bot_configuration_screen.dart';
import 'bot_dashboard_screen.dart';
import 'broker_analytics_dashboard.dart';
import 'broker_integration_screen.dart';
import 'commission_config_screen.dart';
import 'commission_dashboard_screen.dart';
import 'consolidated_reports_screen.dart';
import 'crypto_strategies_screen.dart';
import 'enhanced_dashboard_screen.dart';
import 'financials_screen.dart';
import 'fxcm_withdrawal_screen.dart';
import 'multi_account_management_screen.dart';
import 'multi_broker_management_screen.dart';
import 'oanda_withdrawal_screen.dart';
import 'referral_dashboard_screen.dart';
import 'rentals_and_features_screen.dart';
import 'trade_analysis_screen.dart';
import 'trades_screen.dart';
import 'unified_broker_dashboard_screen.dart';
import 'user_wallet_screen.dart';
import 'activity_log_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;
  List<dynamic> _realBotsList = [];
  Timer? _refreshTimer;
  int _refreshFailureCount = 0;

  /// Convert currency code to symbol (e.g., ZAR → R, USD → $, EUR → €)
  String _currencySymbol(String code) {
    const symbols = {
      'USD': r'$', 'EUR': '€', 'GBP': '£', 'ZAR': 'R',
      'JPY': '¥', 'CHF': 'CHF', 'AUD': r'A$', 'CAD': r'C$',
      'NZD': r'NZ$', 'SGD': r'S$', 'HKD': r'HK$', 'CNY': '¥',
      'INR': '₹', 'BRL': r'R$', 'KRW': '₩', 'TRY': '₺',
      'MXN': r'MX$', 'PLN': 'zł', 'SEK': 'kr', 'NOK': 'kr',
      'NGN': '₦', 'KES': 'KSh', 'GHS': 'GH₵', 'USDT': 'USDT',
    };
    return symbols[code.toUpperCase()] ?? code;
  }

  String _normalizeCurrency(dynamic value) {
    final currency = value?.toString().trim().toUpperCase();
    return currency == null || currency.isEmpty ? 'USD' : currency;
  }

  String _formatCurrencyAmount(double amount, String currency, {int decimals = 2}) {
    return '${_currencySymbol(currency)}${amount.toStringAsFixed(decimals)}';
  }

  String _accountCurrency(Map<String, dynamic> account) {
    return _normalizeCurrency(account['currency'] ?? account['account_currency']);
  }

  String _botCurrency(Map<String, dynamic> bot) {
    return _normalizeCurrency(bot['displayCurrency'] ?? bot['accountCurrency'] ?? bot['currency']);
  }

  Map<String, double> _aggregateAccountBalances(Iterable<Map<String, dynamic>> accounts) {
    final totals = <String, double>{};
    for (final account in accounts) {
      final currency = _accountCurrency(account);
      final amount = (account['balance'] as num?)?.toDouble() ?? 0.0;
      totals[currency] = (totals[currency] ?? 0.0) + amount;
    }
    return totals;
  }

  Map<String, double> _aggregateBotValues(String field) {
    final totals = <String, double>{};
    for (final bot in _realBotsList.cast<Map<String, dynamic>>()) {
      final currency = _botCurrency(bot);
      final amount = double.tryParse(bot[field]?.toString() ?? '0') ?? 0.0;
      totals[currency] = (totals[currency] ?? 0.0) + amount;
    }
    return totals;
  }

  String _normalizedModeValue(dynamic value, {bool defaultLive = false}) {
    final normalized = value?.toString().trim().toLowerCase() ?? '';
    if (normalized == 'live' || normalized == 'real') return 'live';
    if (normalized == 'demo' || normalized == 'trial') return 'demo';
    return defaultLive ? 'live' : 'demo';
  }

  String _accountMode(Map<String, dynamic> account) {
    return _normalizedModeValue(
      account['mode'],
      defaultLive: account['is_live'] == true,
    );
  }

  String _botMode(Map<String, dynamic> bot) {
    return _normalizedModeValue(
      bot['mode'],
      defaultLive: bot['is_live'] == true,
    );
  }

  String _modeLabel(String mode) => mode == 'live' ? 'Live' : 'Demo';

  Color _modeAccent(String mode) {
    return mode == 'live'
        ? const Color(0xFFFFB74D)
        : const Color(0xFF64B5F6);
  }

  List<Map<String, dynamic>> _filteredBrokerAccounts([String? mode]) {
    final selectedMode = mode ?? _balanceMode;
    return _brokerAccounts
        .where((account) => selectedMode == 'all' || _accountMode(account) == selectedMode)
        .cast<Map<String, dynamic>>()
        .toList();
  }

  List<Map<String, dynamic>> _filteredBots([String? mode]) {
    final selectedMode = mode ?? _balanceMode;
    return _realBotsList
        .where((bot) => selectedMode == 'all' || _botMode(Map<String, dynamic>.from(bot)) == selectedMode)
        .cast<Map<String, dynamic>>()
        .toList();
  }

  List<Map<String, dynamic>> _activeBotsFor([String? mode]) {
    return _filteredBots(mode)
        .where((bot) => bot['enabled'] == true || bot['status'] == 'Active')
        .cast<Map<String, dynamic>>()
        .toList();
  }

  Map<String, double> _aggregateBotValuesFor(String field, {String? mode}) {
    final totals = <String, double>{};
    for (final bot in _filteredBots(mode)) {
      final currency = _botCurrency(bot);
      final amount = double.tryParse(bot[field]?.toString() ?? '0') ?? 0.0;
      totals[currency] = (totals[currency] ?? 0.0) + amount;
    }
    return totals;
  }

  String _preferredProfitCurrency([String? mode]) {
    final selectedBots = _filteredBots(mode);
    if (selectedBots.isNotEmpty) {
      return _botCurrency(selectedBots.first);
    }

    final selectedAccounts = _filteredBrokerAccounts(mode);
    if (selectedAccounts.isNotEmpty) {
      return _accountCurrency(selectedAccounts.first);
    }

    if (mode != null && mode != 'all') {
      return _preferredProfitCurrency();
    }

    return 'USD';
  }

  Widget _buildModeSummaryTile({
    required String mode,
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
  }) {
    final accent = _modeAccent(mode);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: accent.withOpacity(0.22)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: accent.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: accent, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value,
                    style: GoogleFonts.poppins(
                      color: accent,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: GoogleFonts.poppins(color: Colors.white54, fontSize: 10),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatCurrencyBreakdown(Map<String, double> totals, {int decimals = 2}) {
    if (totals.isEmpty) {
      return _formatCurrencyAmount(0, _preferredProfitCurrency(), decimals: decimals);
    }
    final entries = totals.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return entries
        .map((entry) => _formatCurrencyAmount(entry.value, entry.key, decimals: decimals))
        .join(' • ');
  }

  // Broker account balances
  List<Map<String, dynamic>> _brokerAccounts = [];
  bool _brokerBalancesLoading = false;
  double _totalBrokerBalance = 0;

  // Demo/Live balance toggle
  String _balanceMode = 'all'; // 'all', 'live', 'demo'

  // Balance tracking for increases/decreases
  // _sessionStartBalances is set ONCE on first fetch and never updated,
  // so balanceChange = currentBalance - sessionStart = total change this session.
  final Map<String, double> _sessionStartBalances = {};
  Map<String, double> _balanceChanges = {};

  // Withdrawal data
  List<Map<String, dynamic>> _recentWithdrawals = [];
  bool _withdrawalsLoading = false;

  @override
  void initState() {
    super.initState();
    _fetchRealBots();
    _fetchBrokerBalances();
    _fetchRecentWithdrawals();
    _startAutoRefresh();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<String> _currentTradingMode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('trading_mode') ?? 'DEMO';
  }

  /// Fetch broker account balances from /api/accounts/balances
  Future<void> _fetchBrokerBalances() async {
    if (_brokerBalancesLoading) return;
    setState(() => _brokerBalancesLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      if (sessionToken == null || sessionToken.isEmpty) {
        throw Exception('No auth token');
      }

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/accounts/balances'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 20)); // Increased timeout to allow broker connections

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && mounted) {
          // Calculate balance changes vs session start (set once, never overwritten)
          final newChanges = <String, double>{};
          for (final account in (data['accounts'] ?? [])) {
            final key = '${account['broker']}_${account['accountNumber']}';
            final currentBalance = (account['balance'] as num?)?.toDouble() ?? 0;
            // Only record the starting balance the very first time we see this account
            _sessionStartBalances[key] ??= currentBalance;
            newChanges[key] = currentBalance - _sessionStartBalances[key]!;
          }
          
          setState(() {
            _brokerAccounts = List<Map<String, dynamic>>.from(data['accounts'] ?? []);
            _totalBrokerBalance = (data['totalBalance'] as num?)?.toDouble() ?? 0;
            _balanceChanges = newChanges;
          });
        }
      } else {
        throw Exception('API returned ${response.statusCode}');
      }
    } catch (e) {
      print('DEBUG: Broker balance fetch error: $e');
      rethrow; // Propagate error for retry logic
    } finally {
      if (mounted) setState(() => _brokerBalancesLoading = false);
    }
  }

  /// Fetch recent withdrawals
  Future<void> _fetchRecentWithdrawals() async {
    if (_withdrawalsLoading) return;
    setState(() => _withdrawalsLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      if (sessionToken == null || sessionToken.isEmpty) {
        throw Exception('No auth token');
      }

      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/withdrawals/recent'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && mounted) {
          setState(() {
            _recentWithdrawals = List<Map<String, dynamic>>.from(data['withdrawals'] ?? []);
          });
        }
      } else {
        throw Exception('API returned ${response.statusCode}');
      }
    } catch (e) {
      print('DEBUG: Withdrawal fetch error: $e');
      rethrow; // Propagate error for retry logic
    } finally {
      if (mounted) setState(() => _withdrawalsLoading = false);
    }
  }

  /// Fetch all bots so dashboard can separate live/demo locally.
  Future<void> _fetchRealBots() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      final userId = prefs.getString('user_id');
      if (sessionToken == null || sessionToken.isEmpty) {
        throw Exception('Session token missing. Please login again.');
      }

      var url = '${EnvironmentConfig.apiUrl}/api/bot/summary?mode=&include_history=true';
      if (userId != null && userId.isNotEmpty) {
        url += '&user_id=$userId';
      }

      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        throw Exception('API returned ${response.statusCode}');
      }

      final data = jsonDecode(response.body);
      if (data['success'] != true) {
        throw Exception(data['error'] ?? 'Failed to load bots');
      }

      if (mounted) {
        setState(() {
          _realBotsList = List<Map<String, dynamic>>.from(data['bots'] ?? []);
          print('✅ Loaded ${_realBotsList.length} bots from backend');
        });
      }
    } catch (e) {
      // Don't wipe existing bot data on refresh errors - preserve previous data
      print('⚠️ Bot refresh error (keeping previous data): $e');
      rethrow; // Propagate error for retry logic
    }
  }

  void _startAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshFailureCount = 0;
    
    // Initial refresh
    _performRefresh();
    
    // Subsequent refreshes with exponential backoff on error
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
      if (mounted) {
        _performRefresh();
      }
    });
  }
  
  Future<void> _performRefresh() async {
    try {
      await Future.wait<void>([
        _fetchRealBots(),
        _fetchBrokerBalances(),
        _fetchRecentWithdrawals(),
      ], eagerError: false);
      
      if (mounted) {
        setState(() {
          _refreshFailureCount = 0; // Reset on success
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _refreshFailureCount++;
        });
      }
    }
  }

  void _pushScreen(Widget screen) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => screen));
  }

  void _openFinancials() {
    final tradingService = context.read<TradingService>();
    if (tradingService.primaryAccount != null) {
      _pushScreen(FinancialsScreen(account: tradingService.primaryAccount!));
      return;
    }

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('No account available for financial reports')),
    );
  }

  void _openReferralDashboard() {
    final userId = context.read<AuthService>().currentUser?.id ?? '0';
    _pushScreen(ReferralDashboardScreen(userId: userId));
  }

  /// Get the current screen based on selected index
  Widget _getScreenForIndex(int index) {
    switch (index) {
      case 0:
        return _buildDashboardTab();
      case 1:
        return const TradesScreen();
      case 2:
        return const AccountManagementScreen();
      case 3:
        return const BotDashboardScreen(embedded: true);
      case 4:
        return _buildFeatureHubTab();
      default:
        return _buildDashboardTab();
    }
  }

  // ────── HELPER METHODS ──────

  /// Build the connected broker account card showing balance and withdrawals
  Widget _buildConnectedBrokerCard() {
    final connectedAccounts = _filteredBrokerAccounts()
        .where((account) => account['connected'] == true)
        .cast<Map<String, dynamic>>()
        .toList();

    if (connectedAccounts.isEmpty) {
      return const SizedBox.shrink();
    }
    return Column(
      children: [
        ...connectedAccounts.asMap().entries.map((entry) {
          final connected = entry.value;
          final broker = connected['broker'] ?? 'Broker';
          final accountId = connected['accountId']?.toString() ?? '';
          final accountNum = connected['accountNumber']?.toString() ?? accountId;
          final balance = (connected['balance'] as num?)?.toDouble() ?? 0.0;
          final equity = (connected['equity'] as num?)?.toDouble() ?? 0.0;
          final currency = connected['currency'] ?? 'USD';
          final mode = _accountMode(connected);
          final key = '${broker}_$accountNum';
          final balanceChange = _balanceChanges[key] ?? 0.0;
          final isIncreasing = balanceChange >= 0;
          final accountWithdrawals = _recentWithdrawals
              .where((w) => w['broker']?.toString() == broker && w['accountNumber']?.toString() == accountNum)
              .toList();
          final totalWithdrawn = accountWithdrawals.fold<double>(0, (sum, w) => sum + ((w['amount'] as num?)?.toDouble() ?? 0));

          return Padding(
            padding: EdgeInsets.only(bottom: entry.key == connectedAccounts.length - 1 ? 0 : 16),
            child: _glassCard(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  if (isIncreasing) const Color(0xFF1B5E20).withOpacity(0.3) else const Color(0xFF4A235A).withOpacity(0.3),
                  Colors.transparent,
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: const Color(0xFF00E5FF).withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.account_balance_wallet, color: Color(0xFF00E5FF), size: 28),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Connected to $broker',
                              style: GoogleFonts.poppins(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              'Account #$accountNum',
                              style: GoogleFonts.poppins(
                                color: Colors.white60,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: _modeAccent(mode).withOpacity(0.15),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          _modeLabel(mode),
                          style: GoogleFonts.poppins(
                            color: _modeAccent(mode),
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  // Grid of account metrics (2x3)
                  GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    childAspectRatio: 1.4,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    children: [
                      _buildMetricCard('Balance', '${_currencySymbol(currency)}${balance.toStringAsFixed(2)}', Colors.white, const Color(0xFF00E5FF)),
                      _buildMetricCard('Equity', '${_currencySymbol(currency)}${equity.toStringAsFixed(2)}', Colors.white, const Color(0xFF69F0AE)),
                      _buildMetricCard(
                        'Free Margin',
                        '${_currencySymbol(currency)}${((connected['free_margin'] as num?)?.toDouble() ?? 0.0).toStringAsFixed(2)}',
                        Colors.white,
                        const Color(0xFF81C784),
                      ),
                      _buildMetricCard(
                        'Margin Used',
                        '${_currencySymbol(currency)}${((connected['margin'] as num?)?.toDouble() ?? 0.0).toStringAsFixed(2)}',
                        Colors.white,
                        const Color(0xFFFFB74D),
                      ),
                      _buildMetricCard(
                        'Margin Level',
                        '${((connected['margin_level'] as num?)?.toDouble() ?? 0.0).toStringAsFixed(2)}%',
                        Colors.white,
                        const Color(0xFF64B5F6),
                      ),
                      _buildMetricCard(
                        'Total P/L',
                        '${_currencySymbol(currency)}${((connected['total_pl'] as num?)?.toDouble() ?? 0.0).toStringAsFixed(2)}',
                        ((connected['total_pl'] as num?)?.toDouble() ?? 0.0) >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                        ((connected['total_pl'] as num?)?.toDouble() ?? 0.0) >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: isIncreasing ? const Color(0xFF1B5E20).withOpacity(0.2) : const Color(0xFF4A235A).withOpacity(0.2),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          isIncreasing ? Icons.trending_up : Icons.trending_down,
                          color: isIncreasing ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              isIncreasing ? 'Balance Increase' : 'Balance Decrease',
                              style: GoogleFonts.poppins(color: Colors.white60, fontSize: 11),
                            ),
                            Text(
                              '${_currencySymbol(currency)}${balanceChange.abs().toStringAsFixed(2)}',
                              style: GoogleFonts.poppins(
                                color: isIncreasing ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  if (accountWithdrawals.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Recent Withdrawals', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w500)),
                        Text(
                          'Total: ${_currencySymbol(currency)}${totalWithdrawn.toStringAsFixed(2)}',
                          style: GoogleFonts.poppins(color: const Color(0xFFFFB74D), fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ...accountWithdrawals.take(2).map((withdrawal) {
                      final amount = (withdrawal['amount'] as num?)?.toDouble() ?? 0;
                      final status = withdrawal['status']?.toString() ?? 'pending';
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '${_currencySymbol(currency)}${amount.toStringAsFixed(2)}',
                                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500),
                                  ),
                                  Text(
                                    'Status: $status',
                                    style: GoogleFonts.poppins(color: Colors.white54, fontSize: 10),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _getWithdrawalStatusColor(status).withOpacity(0.2),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                status.toUpperCase(),
                                style: GoogleFonts.poppins(
                                  color: _getWithdrawalStatusColor(status),
                                  fontSize: 9,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ],
              ),
            ),
          );
        }),
      ],
    );
  }

  /// Get withdrawal status color based on status string
  Color _getWithdrawalStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'approved':
        return const Color(0xFF69F0AE);
      case 'pending':
        return const Color(0xFFFFB74D);
      case 'failed':
      case 'rejected':
        return const Color(0xFFFF8A80);
      default:
        return Colors.white60;
    }
  }

  /// Build recent bots card showing active trading bots
  Widget _buildRecentBotsCard() {
    final activeBots = _activeBotsFor();
    final liveActiveBots = _activeBotsFor('live');
    final demoActiveBots = _activeBotsFor('demo');
    if (activeBots.isEmpty) {
      return _glassCard(
        child: Column(
          children: [
            Text('Active Bots',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
            const SizedBox(height: 20),
            const Icon(Icons.smart_toy, color: Colors.white24, size: 48),
            const SizedBox(height: 8),
            Text('No active bots', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
          ],
        ),
      );
    }

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Active Bots',
                  style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
              Text(_balanceMode == 'all' ? '${liveActiveBots.length} live • ${demoActiveBots.length} demo' : '${activeBots.length} active',
                  style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 13, fontWeight: FontWeight.w500)),
            ],
          ),
          const SizedBox(height: 14),
          if (_balanceMode == 'all') ...[
            Row(
              children: [
                Expanded(
                  child: _buildModeSummaryTile(
                    mode: 'live',
                    title: 'Live Bots',
                    value: '${liveActiveBots.length}',
                    subtitle: 'active in live trading',
                    icon: Icons.bolt,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _buildModeSummaryTile(
                    mode: 'demo',
                    title: 'Demo Bots',
                    value: '${demoActiveBots.length}',
                    subtitle: 'active in demo trading',
                    icon: Icons.smart_toy,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
          ],
          ...activeBots.take(5).map((bot) {
            final botId = bot['botId']?.toString() ?? 'Unknown Bot';
            final strategy = bot['strategy']?.toString() ?? 'Unknown';
            final profit = double.tryParse(bot['currentProfit']?.toString() ?? bot['totalProfit']?.toString() ?? '0') ?? 0;
            final isProfitable = profit > 0;
            final botMode = _botMode(bot);
            final botCurrency = _botCurrency(bot);
            
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  border: Border.all(color: Colors.white.withOpacity(0.1)),
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Bot info header
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: isProfitable ? const Color(0xFF69F0AE).withOpacity(0.15) : const Color(0xFFFF8A80).withOpacity(0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            Icons.smart_toy,
                            color: isProfitable ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                            size: 18,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Flexible(
                                    child: Text(botId, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: _modeAccent(botMode).withOpacity(0.15),
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: Text(
                                      _modeLabel(botMode),
                                      style: GoogleFonts.poppins(
                                        color: _modeAccent(botMode),
                                        fontSize: 10,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              Text(strategy, style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11)),
                            ],
                          ),
                        ),
                        Text(
                          '${_currencySymbol(botCurrency)}${profit.toStringAsFixed(2)}',
                          style: GoogleFonts.poppins(
                            color: isProfitable ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    // Action buttons row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        // Start button
                        Expanded(
                          child: Consumer<BotService>(
                            builder: (context, botService, _) => InkWell(
                                onTap: () async {
                                  try {
                                    await botService.startBotTrading(botId);
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text('Bot $botId started'), duration: const Duration(seconds: 2)),
                                    );
                                    _performRefresh();
                                  } catch (e) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                                    );
                                  }
                                },
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 8),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF69F0AE).withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(color: const Color(0xFF69F0AE).withOpacity(0.5)),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      const Icon(Icons.play_arrow, color: Color(0xFF69F0AE), size: 16),
                                      const SizedBox(width: 4),
                                      Text('Start', style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 12, fontWeight: FontWeight.w500)),
                                    ],
                                  ),
                                ),
                              ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        // Analytics button
                        Expanded(
                          child: InkWell(
                            onTap: () {
                              // Navigate to Bots tab for full analytics
                              Navigator.of(context).pushNamedAndRemoveUntil('/', (_) => false);
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: const Color(0xFF00E5FF).withOpacity(0.2),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: const Color(0xFF00E5FF).withOpacity(0.5)),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.bar_chart, color: Color(0xFF00E5FF), size: 16),
                                  const SizedBox(width: 4),
                                  Text('Analytics', style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 12, fontWeight: FontWeight.w500)),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        // Delete button
                        Expanded(
                          child: InkWell(
                            onTap: () {
                              showDialog(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  title: Text('Delete Bot?', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.bold)),
                                  backgroundColor: const Color(0xFF1A1F3A),
                                  content: Text('Are you sure you want to delete bot $botId?', style: GoogleFonts.poppins(color: Colors.white70)),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.pop(ctx),
                                      child: Text('Cancel', style: GoogleFonts.poppins(color: Colors.white54)),
                                    ),
                                    TextButton(
                                      onPressed: () async {
                                        Navigator.pop(ctx);
                                        try {
                                          // Call backend API to delete bot
                                          final prefs = await SharedPreferences.getInstance();
                                          final token = prefs.getString('auth_token') ?? '';
                                          final userId = prefs.getString('user_id');
                                          
                                          final response = await http.delete(
                                            Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/delete/$botId'),
                                            headers: {
                                              'Content-Type': 'application/json',
                                              'X-Session-Token': token,
                                            },
                                            body: jsonEncode({
                                              if (userId != null && userId.isNotEmpty) 'user_id': userId,
                                            }),
                                          );
                                          
                                          if (response.statusCode == 200) {
                                            _performRefresh();
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(content: Text('Bot $botId deleted'), duration: const Duration(seconds: 2)),
                                            );
                                          } else {
                                            throw 'Failed to delete bot';
                                          }
                                        } catch (e) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                                          );
                                        }
                                      },
                                      child: Text('Delete', style: GoogleFonts.poppins(color: const Color(0xFFFF8A80), fontWeight: FontWeight.bold)),
                                    ),
                                  ],
                                ),
                              );
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFF8A80).withOpacity(0.2),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: const Color(0xFFFF8A80).withOpacity(0.5)),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.delete, color: Color(0xFFFF8A80), size: 16),
                                  const SizedBox(width: 4),
                                  Text('Delete', style: GoogleFonts.poppins(color: const Color(0xFFFF8A80), fontSize: 12, fontWeight: FontWeight.w500)),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── GLASS CARD HELPER ──
  Widget _glassCard({required Widget child, LinearGradient? gradient}) => Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: gradient,
        color: gradient == null ? Colors.white.withOpacity(0.06) : null,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );

  /// Build the dashboard tab - Modern premium layout
  Widget _buildDashboardTab() => Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF0A0E21), Color(0xFF1A1F3A), Color(0xFF0A0E21)],
        ),
      ),
      child: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Error banner if refresh failures detected
            if (_refreshFailureCount > 0)
              Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFB74D).withOpacity(0.15),
                  border: Border.all(color: const Color(0xFFFFB74D).withOpacity(0.5)),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber, color: Color(0xFFFFB74D), size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Connection issues detected. Some data may be outdated.',
                        style: GoogleFonts.poppins(color: const Color(0xFFFFB74D), fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            _buildPremiumWelcomeCard(),
            const SizedBox(height: 16),
            _buildConnectedBrokerCard(),
            const SizedBox(height: 16),
            _buildBrokerAccountsCard(),
            const SizedBox(height: 20),
            _buildQuickStatsRow(),
            const SizedBox(height: 20),
            _buildProfitOverviewCard(),
            const SizedBox(height: 20),
            _buildPortfolioPieChart(),
            const SizedBox(height: 20),
            _buildWinLossDonutChart(),
            const SizedBox(height: 20),
            _buildProfitLineChart(),
            const SizedBox(height: 20),
            _buildTradeAnalysisPreview(),
            const SizedBox(height: 20),
            _buildTopPairsCard(),
            const SizedBox(height: 20),
            _buildRecentTradesCard(),
            const SizedBox(height: 24),
            _buildQuickActionsGrid(),
            const SizedBox(height: 20),
            _buildRecentBotsCard(),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );

  Widget _buildFeatureHubTab() => Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF0A0E21), Color(0xFF151A30), Color(0xFF0A0E21)],
        ),
      ),
      child: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _glassCard(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF1A237E), Color(0xFF283593), Color(0xFF006064)],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Feature Hub',
                    style: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Mobile now exposes the same major operating areas as the web flow: reports, commissions, wallet, broker tools, portfolio views, and automation controls.',
                    style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _buildFeatureSection(
              title: 'Reports & Money',
              subtitle: 'Reporting, earnings, wallet, and financial tracking',
              actions: [
                _FeatureAction('Reports', Icons.assessment, const Color(0xFFFF6E40), () => _pushScreen(const ConsolidatedReportsScreen())),
                _FeatureAction('Financials', Icons.attach_money, const Color(0xFF26C6DA), _openFinancials),
                _FeatureAction('Commissions', Icons.monetization_on, const Color(0xFF69F0AE), () => _pushScreen(const CommissionDashboardScreen())),
                _FeatureAction('Wallet', Icons.account_balance_wallet, const Color(0xFFF0B90B), () => _pushScreen(const UserWalletScreen())),
                _FeatureAction('Activity Log', Icons.history, const Color(0xFF8D6E63), () => _pushScreen(const ActivityLogScreen())),
                _FeatureAction('Referrals', Icons.group_add, const Color(0xFF66BB6A), _openReferralDashboard),
              ],
            ),
            const SizedBox(height: 16),
            _buildFeatureSection(
              title: 'Broker & Portfolio',
              subtitle: 'Connected accounts, analytics, portfolio, and broker operations',
              actions: [
                _FeatureAction('Portfolio', Icons.dashboard_customize, const Color(0xFF5C6BC0), () => _pushScreen(const UnifiedBrokerDashboardScreen())),
                _FeatureAction('Broker Setup', Icons.account_tree, const Color(0xFF7C4DFF), () => _pushScreen(const BrokerIntegrationScreen())),
                _FeatureAction('Multi-Broker', Icons.business_center, const Color(0xFFB388FF), () => _pushScreen(const MultiBrokerManagementScreen())),
                _FeatureAction('Accounts', Icons.people, const Color(0xFF00E5FF), () => _pushScreen(const MultiAccountManagementScreen())),
                _FeatureAction('Analytics', Icons.speed, const Color(0xFFFFD600), () => _pushScreen(const BrokerAnalyticsDashboard())),
              ],
            ),
            const SizedBox(height: 16),
            _buildFeatureSection(
              title: 'Automation & Trading',
              subtitle: 'Bot creation, monitoring, strategy tools, and analysis',
              actions: [
                _FeatureAction('Create Bot', Icons.add_circle, const Color(0xFF00C853), () => _pushScreen(const BotConfigurationScreen())),
                _FeatureAction('Bot Monitor', Icons.smart_toy_outlined, const Color(0xFFFFB74D), () => _pushScreen(const BotDashboardScreen())),
                _FeatureAction('Trade Analysis', Icons.analytics_outlined, const Color(0xFF00E5FF), () => _pushScreen(const TradeAnalysisScreen())),
                _FeatureAction('Crypto', Icons.currency_bitcoin, const Color(0xFFF3BA2F), () => _pushScreen(const CryptoStrategiesScreen())),
                _FeatureAction('Trading View', Icons.analytics, const Color(0xFF7C4DFF), () => _pushScreen(const EnhancedDashboardScreen())),
              ],
            ),
            const SizedBox(height: 16),
            _buildFeatureSection(
              title: 'Operations',
              subtitle: 'Features, payouts, and admin-facing operations screens',
              actions: [
                _FeatureAction('Rentals', Icons.card_giftcard, Colors.orangeAccent, () => _pushScreen(const RentalsAndFeaturesScreen())),
                _FeatureAction('OANDA Out', Icons.account_balance_wallet, const Color(0xFF4CAF50), () => _pushScreen(const OandaWithdrawalScreen())),
                _FeatureAction('FXCM Out', Icons.account_balance_wallet, const Color(0xFF7C4DFF), () => _pushScreen(const FxcmWithdrawalScreen())),
                _FeatureAction('Binance Out', Icons.currency_bitcoin, const Color(0xFFF0B90B), () => _pushScreen(const BinanceWithdrawalScreen())),
                _FeatureAction('Verify', Icons.admin_panel_settings, const Color(0xFFE74C3C), () => _pushScreen(const AdminWithdrawalVerificationScreen())),
              ],
            ),
          ],
        ),
      ),
    );

  Widget _buildFeatureSection({
    required String title,
    required String subtitle,
    required List<_FeatureAction> actions,
  }) => _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
          ),
          const SizedBox(height: 14),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.45,
            ),
            itemCount: actions.length,
            itemBuilder: (context, index) {
              final action = actions[index];
              return InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: action.onTap,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        action.color.withOpacity(0.22),
                        action.color.withOpacity(0.08),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: action.color.withOpacity(0.28)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        decoration: BoxDecoration(
                          color: action.color.withOpacity(0.18),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(action.icon, color: action.color, size: 22),
                      ),
                      Text(
                        action.label,
                        style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );

  // ── PREMIUM WELCOME CARD ──
  Widget _buildPremiumWelcomeCard() => Consumer<AuthService>(
      builder: (context, authService, _) {
        final name = authService.currentUser?.firstName ?? 'Trader';
        final hour = DateTime.now().hour;
        final greeting = hour < 12 ? 'Good Morning' : hour < 18 ? 'Good Afternoon' : 'Good Evening';
        
        return _glassCard(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF1A237E), Color(0xFF0D47A1), Color(0xFF01579B)],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 50,
                    height: 50,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)],
                      ),
                    ),
                    child: Center(
                      child: Text(
                        name[0].toUpperCase(),
                        style: GoogleFonts.poppins(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          greeting,
                          style: GoogleFonts.poppins(color: Colors.white60, fontSize: 13),
                        ),
                        Text(
                          name,
                          style: GoogleFonts.poppins(
                            color: Colors.white,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            shape: BoxShape.circle,
                            color: Color(0xFF69F0AE),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'Online',
                          style: GoogleFonts.poppins(color: Colors.white70, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              // ── Demo / Live Toggle ──
              Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    for (final mode in [{'key': 'all', 'label': 'All'}, {'key': 'live', 'label': 'Live'}, {'key': 'demo', 'label': 'Demo'}])
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setState(() => _balanceMode = mode['key']!),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            decoration: BoxDecoration(
                              color: _balanceMode == mode['key'] ? const Color(0xFF0066FF) : Colors.transparent,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Center(
                              child: Text(
                                mode['label']!,
                                style: GoogleFonts.poppins(
                                  color: _balanceMode == mode['key'] ? Colors.white : Colors.white54,
                                  fontSize: 12,
                                  fontWeight: _balanceMode == mode['key'] ? FontWeight.w600 : FontWeight.w400,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // ── Total Portfolio Balance ──
              Builder(
                builder: (context) {
                  final filtered = _filteredBrokerAccounts();
                  final liveAccounts = _filteredBrokerAccounts('live');
                  final demoAccounts = _filteredBrokerAccounts('demo');
                  final filteredTotals = _aggregateAccountBalances(filtered);
                  final connectedCount = filtered.where((a) => a['connected'] == true).length;

                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _balanceMode == 'all' ? 'TOTAL PORTFOLIO BALANCE' :
                          _balanceMode == 'live' ? 'LIVE BALANCE' : 'DEMO BALANCE',
                          style: GoogleFonts.poppins(color: Colors.white54, fontSize: 10, fontWeight: FontWeight.w500, letterSpacing: 1.2),
                        ),
                        const SizedBox(height: 4),
                        if (_brokerBalancesLoading && _totalBrokerBalance == 0) Row(
                                children: [
                                  const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 1.5, color: Color(0xFF00E5FF))),
                                  const SizedBox(width: 10),
                                  Text('Loading...', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 14)),
                                ],
                              ) else Text(
                                _formatCurrencyBreakdown(filteredTotals),
                                style: GoogleFonts.poppins(
                                  color: Colors.white,
                                  fontSize: 28,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                        if (connectedCount > 0)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              '$connectedCount ${_balanceMode == 'all' ? 'connected' : _balanceMode} account${connectedCount == 1 ? '' : 's'}',
                              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
                            ),
                          ),
                        if (_balanceMode == 'all') ...[
                          const SizedBox(height: 14),
                          Column(
                            children: [
                              _buildModeSummaryTile(
                                mode: 'live',
                                title: 'Live Balance',
                                value: _formatCurrencyBreakdown(_aggregateAccountBalances(liveAccounts)),
                                subtitle: '${liveAccounts.where((a) => a['connected'] == true).length} connected live account${liveAccounts.where((a) => a['connected'] == true).length == 1 ? '' : 's'}',
                                icon: Icons.trending_up,
                              ),
                              const SizedBox(height: 10),
                              _buildModeSummaryTile(
                                mode: 'demo',
                                title: 'Demo Balance',
                                value: _formatCurrencyBreakdown(_aggregateAccountBalances(demoAccounts)),
                                subtitle: '${demoAccounts.where((a) => a['connected'] == true).length} connected demo account${demoAccounts.where((a) => a['connected'] == true).length == 1 ? '' : 's'}',
                                icon: Icons.science,
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ],
          ),
        );
      },
    );

  // ── BROKER ACCOUNTS CARD ──
  Widget _buildBrokerAccountsCard() {
    final shownAccounts = _filteredBrokerAccounts();
    final liveAccounts = _filteredBrokerAccounts('live');
    final demoAccounts = _filteredBrokerAccounts('demo');

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Broker Accounts', style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 14),
          if (_balanceMode == 'all') ...[
            Column(
              children: [
                _buildModeSummaryTile(
                  mode: 'live',
                  title: 'Live Accounts',
                  value: _formatCurrencyBreakdown(_aggregateAccountBalances(liveAccounts)),
                  subtitle: '${liveAccounts.length} live account${liveAccounts.length == 1 ? '' : 's'} on dashboard',
                  icon: Icons.account_balance,
                ),
                const SizedBox(height: 10),
                _buildModeSummaryTile(
                  mode: 'demo',
                  title: 'Demo Accounts',
                  value: _formatCurrencyBreakdown(_aggregateAccountBalances(demoAccounts)),
                  subtitle: '${demoAccounts.length} demo account${demoAccounts.length == 1 ? '' : 's'} on dashboard',
                  icon: Icons.account_balance_wallet,
                ),
              ],
            ),
            const SizedBox(height: 14),
          ],
          ...shownAccounts.map((account) {
            final broker = account['broker']?.toString() ?? 'Unknown';
            final accountNum = account['accountNumber']?.toString() ?? '';
            final balance = (account['balance'] as num?)?.toDouble() ?? 0;
            final equity = (account['equity'] as num?)?.toDouble() ?? 0;
            final mode = _accountMode(account);
            final connected = account['connected'] == true;
            final error = account['error']?.toString();
            final warning = account['warning']?.toString();
            final acctCurrency = (account['currency'] as String? ?? 'USD').toUpperCase();
            final acctSymbol = acctCurrency == 'ZAR' ? 'R' : (acctCurrency == 'GBP' ? '£' : r'$');

            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.04),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Container(
                    width: 40, height: 40,
                    decoration: BoxDecoration(
                      color: (connected || balance > 0)
                          ? const Color(0xFF69F0AE).withOpacity(0.15)
                          : const Color(0xFFFF8A80).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      (connected || balance > 0) ? Icons.account_balance_wallet : Icons.error_outline,
                      color: (connected || balance > 0) ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text('$broker',
                                style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _modeAccent(mode).withOpacity(0.15),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                _modeLabel(mode),
                                style: GoogleFonts.poppins(
                                  color: _modeAccent(mode),
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        Text('Account: $accountNum',
                          style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10)),
                        if (!connected && balance == 0 && error != null)
                          Text(error, style: GoogleFonts.poppins(color: const Color(0xFFFF8A80), fontSize: 10)),
                        if (warning != null)
                          Text(warning, style: GoogleFonts.poppins(color: const Color(0xFFFFB74D), fontSize: 10)),
                      ],
                    ),
                  ),
                  if (balance > 0 || connected)
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('$acctSymbol${balance.toStringAsFixed(2)} $acctCurrency',
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                        ),
                        Text('Equity: $acctSymbol${equity.toStringAsFixed(2)}',
                          style: GoogleFonts.poppins(color: Colors.white54, fontSize: 10)),
                      ],
                    ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  // ── QUICK STATS ROW ──
  Widget _buildQuickStatsRow() {
    final selectedBots = _filteredBots();
    final activeBots = _activeBotsFor().length;
    final liveActiveBots = _activeBotsFor('live').length;
    final demoActiveBots = _activeBotsFor('demo').length;
    final totalTrades = selectedBots.fold<int>(
      0, (sum, bot) => sum + (int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0),
    );
    final totalProfitByCurrency = _aggregateBotValuesFor('profit');
    final totalProfit = totalProfitByCurrency.values.fold<double>(0, (sum, value) => sum + value);

    return Row(
      children: [
        Expanded(child: _buildStatPill(Icons.smart_toy, _balanceMode == 'all' ? 'Live $liveActiveBots / Demo $demoActiveBots' : '$activeBots', 'Active Bots', const Color(0xFF7C4DFF), valueFontSize: _balanceMode == 'all' ? 12 : 20)),
        const SizedBox(width: 10),
        Expanded(child: _buildStatPill(Icons.swap_horiz, '$totalTrades', 'Trades', const Color(0xFF00E5FF))),
        const SizedBox(width: 10),
        Expanded(
          child: _buildStatPill(
            totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
            _formatCurrencyBreakdown(totalProfitByCurrency, decimals: 0),
            'Profit',
            totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
          ),
        ),
      ],
    );
  }

  Widget _buildStatPill(IconData icon, String value, String label, Color color, {double valueFontSize = 20}) => _glassCard(
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(height: 10),
          Text(
            value,
            textAlign: TextAlign.center,
            maxLines: 2,
            style: GoogleFonts.poppins(
              color: Colors.white,
              fontSize: valueFontSize,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
          ),
        ],
      ),
    );

  // ── PROFIT OVERVIEW ──
  Widget _buildProfitOverviewCard() {
    final selectedBots = _filteredBots();
    final totalProfitByCurrency = _aggregateBotValuesFor('profit');
    final liveProfitByCurrency = _aggregateBotValuesFor('profit', mode: 'live');
    final demoProfitByCurrency = _aggregateBotValuesFor('profit', mode: 'demo');
    final totalProfit = totalProfitByCurrency.values.fold<double>(0, (sum, value) => sum + value);
    final winningBots = selectedBots.where((bot) => (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final totalBots = selectedBots.length;
    final winRate = totalBots > 0 ? (winningBots / totalBots * 100) : 0.0;
    final liveWinningBots = _filteredBots('live').where((bot) => (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final demoWinningBots = _filteredBots('demo').where((bot) => (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final liveBotsCount = _filteredBots('live').length;
    final demoBotsCount = _filteredBots('demo').length;

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Profit Overview',
                  style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: totalProfit >= 0
                      ? const Color(0xFF69F0AE).withOpacity(0.15)
                      : const Color(0xFFFF8A80).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  totalProfit >= 0 ? 'Profitable' : 'In Drawdown',
                  style: GoogleFonts.poppins(
                    color: totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Center(
            child: Text(
              _formatCurrencyBreakdown(totalProfitByCurrency),
              style: GoogleFonts.poppins(
                color: totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                fontSize: 36,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Center(
            child: Text('Total Net Return',
                style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
          ),
          if (_balanceMode == 'all') ...[
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(
                  child: _buildModeSummaryTile(
                    mode: 'live',
                    title: 'Live Profit',
                    value: _formatCurrencyBreakdown(liveProfitByCurrency),
                    subtitle: '${liveWinningBots}/${liveBotsCount} profitable live bots',
                    icon: Icons.show_chart,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _buildModeSummaryTile(
                    mode: 'demo',
                    title: 'Demo Profit',
                    value: _formatCurrencyBreakdown(demoProfitByCurrency),
                    subtitle: '${demoWinningBots}/${demoBotsCount} profitable demo bots',
                    icon: Icons.insights,
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 24),
          // Win Rate Bar
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: SizedBox(
              height: 10,
              child: LinearProgressIndicator(
                value: winRate / 100,
                backgroundColor: Colors.white10,
                valueColor: const AlwaysStoppedAnimation(Color(0xFF00E5FF)),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Win Rate: ${winRate.toStringAsFixed(1)}%',
                style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 13, fontWeight: FontWeight.w600),
              ),
              Text(
                '$winningBots / $totalBots bots profitable',
                style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ── PORTFOLIO DISTRIBUTION PIE CHART ──
  Widget _buildPortfolioPieChart() {
    final selectedBots = _filteredBots();
    final symbolProfits = <String, double>{};
    for (final bot in selectedBots) {
      final symbols = bot['symbol']?.toString() ?? 'EURUSD';
      final profit = (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0).abs();
      if (profit > 0) {
        symbolProfits[symbols] = (symbolProfits[symbols] ?? 0) + profit;
      }
    }

    if (symbolProfits.isEmpty) {
      return _glassCard(
        child: Column(
          children: [
            Text('Portfolio Distribution',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
            const SizedBox(height: 20),
            const Icon(Icons.pie_chart_outline, color: Colors.white24, size: 48),
            const SizedBox(height: 8),
            Text('No trading data yet', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
          ],
        ),
      );
    }

    final chartColors = [
      const Color(0xFF00E5FF),
      const Color(0xFF69F0AE),
      const Color(0xFFFFD600),
      const Color(0xFFFF8A80),
      const Color(0xFF7C4DFF),
      const Color(0xFFFF6E40),
      const Color(0xFF40C4FF),
      const Color(0xFFB388FF),
    ];

    final total = symbolProfits.values.fold<double>(0, (s, v) => s + v);
    final entries = symbolProfits.entries.toList()..sort((a, b) => b.value.compareTo(a.value));

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Portfolio Distribution',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: PieChart(
              PieChartData(
                sectionsSpace: 3,
                centerSpaceRadius: 45,
                sections: entries.asMap().entries.map((e) {
                  final i = e.key;
                  final pair = e.value;
                  final pct = pair.value / total * 100;
                  final color = chartColors[i % chartColors.length];
                  return PieChartSectionData(
                    value: pair.value,
                    color: color,
                    radius: 55,
                    title: '${pct.toStringAsFixed(0)}%',
                    titleStyle: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: entries.asMap().entries.map((e) {
              final i = e.key;
              final pair = e.value;
              final color = chartColors[i % chartColors.length];
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
                  const SizedBox(width: 6),
                  Text(pair.key, style: GoogleFonts.poppins(color: Colors.white70, fontSize: 11)),
                ],
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  // ── WIN / LOSS DONUT CHART ──
  Widget _buildWinLossDonutChart() {
    final winningBots = _realBotsList.where((b) => (double.tryParse(b['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final losingBots = _realBotsList.where((b) => (double.tryParse(b['profit']?.toString() ?? '0') ?? 0) < 0).length;
    final breakEven = _realBotsList.length - winningBots - losingBots;
    final total = _realBotsList.length;

    if (total == 0) {
      return _glassCard(
        child: Column(
          children: [
            Text('Win / Loss Ratio',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
            const SizedBox(height: 20),
            const Icon(Icons.donut_large, color: Colors.white24, size: 48),
            const SizedBox(height: 8),
            Text('No bots running', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
          ],
        ),
      );
    }

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Win / Loss Ratio',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 160,
                  child: PieChart(
                    PieChartData(
                      sectionsSpace: 2,
                      centerSpaceRadius: 35,
                      sections: [
                        if (winningBots > 0)
                          PieChartSectionData(
                            value: winningBots.toDouble(),
                            color: const Color(0xFF69F0AE),
                            radius: 40,
                            title: '$winningBots',
                            titleStyle: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                          ),
                        if (losingBots > 0)
                          PieChartSectionData(
                            value: losingBots.toDouble(),
                            color: const Color(0xFFFF8A80),
                            radius: 40,
                            title: '$losingBots',
                            titleStyle: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                          ),
                        if (breakEven > 0)
                          PieChartSectionData(
                            value: breakEven.toDouble(),
                            color: Colors.white30,
                            radius: 40,
                            title: '$breakEven',
                            titleStyle: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 20),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _chartLegendItem(const Color(0xFF69F0AE), 'Winning', winningBots),
                  const SizedBox(height: 10),
                  _chartLegendItem(const Color(0xFFFF8A80), 'Losing', losingBots),
                  const SizedBox(height: 10),
                  _chartLegendItem(Colors.white30, 'Break Even', breakEven),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chartLegendItem(Color color, String label, int count) => Row(
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 8),
        Text('$label ($count)', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12)),
      ],
    );

  /// Build individual metric card for account dashboard
  Widget _buildMetricCard(String label, String value, Color valueColor, Color accentColor) => Container(
      decoration: BoxDecoration(
        border: Border.all(color: accentColor.withOpacity(0.3), width: 1.5),
        borderRadius: BorderRadius.circular(12),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            accentColor.withOpacity(0.08),
            accentColor.withOpacity(0.02),
          ],
        ),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: GoogleFonts.poppins(
              color: Colors.white60,
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: GoogleFonts.poppins(
              color: valueColor,
              fontSize: 14,
              fontWeight: FontWeight.bold,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );

  // ── PROFIT TREND LINE CHART ──
  Widget _buildProfitLineChart() {
    final selectedBots = _filteredBots();
    final currency = _preferredProfitCurrency();
    // Gather profit per bot as data points
    final profitPoints = <FlSpot>[];
    double cumulative = 0;
    for (var i = 0; i < selectedBots.length; i++) {
      final profit = double.tryParse(selectedBots[i]['profit']?.toString() ?? '0') ?? 0;
      cumulative += profit;
      profitPoints.add(FlSpot(i.toDouble(), cumulative));
    }

    if (profitPoints.isEmpty) {
      return _glassCard(
        child: Column(
          children: [
            Text('Cumulative Profit Trend',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
            const SizedBox(height: 20),
            const Icon(Icons.show_chart, color: Colors.white24, size: 48),
            const SizedBox(height: 8),
            Text('No data yet', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
          ],
        ),
      );
    }

    final maxY = profitPoints.map((p) => p.y).reduce(max);
    final minY = profitPoints.map((p) => p.y).reduce(min);
    final range = (maxY - minY).abs();
    final padding = range > 0 ? range * 0.2 : 10.0;

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Cumulative Profit Trend',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(
            'Across ${selectedBots.length} bot(s)',
            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 200,
            child: LineChart(
              LineChartData(
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: range > 0 ? range / 4 : 5,
                  getDrawingHorizontalLine: (value) =>
                      const FlLine(color: Colors.white10, strokeWidth: 1),
                ),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 50,
                      getTitlesWidget: (value, meta) => Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: Text(
                          _formatCurrencyAmount(value, currency, decimals: 0),
                          style: GoogleFonts.poppins(color: Colors.white38, fontSize: 9),
                        ),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        final idx = value.toInt();
                        if (idx >= 0 && idx < selectedBots.length) {
                          final botId = (selectedBots[idx]['botId'] ?? '').toString();
                          return Padding(
                            padding: const EdgeInsets.only(top: 6),
                            child: Text(
                              botId.length > 5 ? botId.substring(0, 5) : botId,
                              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 8),
                            ),
                          );
                        }
                        return const SizedBox.shrink();
                      },
                    ),
                  ),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                borderData: FlBorderData(show: false),
                minY: minY - padding,
                maxY: maxY + padding,
                lineBarsData: [
                  LineChartBarData(
                    spots: profitPoints,
                    isCurved: true,
                    curveSmoothness: 0.3,
                    color: const Color(0xFF00E5FF),
                    barWidth: 3,
                    dotData: FlDotData(
                      show: true,
                      getDotPainter: (spot, percent, bar, index) =>
                          FlDotCirclePainter(
                        radius: 4,
                        color: spot.y >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                        strokeColor: Colors.white,
                        strokeWidth: 1.5,
                      ),
                    ),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          const Color(0xFF00E5FF).withOpacity(0.25),
                          const Color(0xFF00E5FF).withOpacity(0),
                        ],
                      ),
                    ),
                  ),
                ],
                lineTouchData: LineTouchData(
                  touchTooltipData: LineTouchTooltipData(
                    getTooltipItems: (touchedSpots) => touchedSpots.map((spot) => LineTooltipItem(
                          _formatCurrencyAmount(spot.y, currency),
                          GoogleFonts.poppins(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        )).toList(),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── TRADE ANALYSIS PREVIEW ──
  Widget _buildTradeAnalysisPreview() => GestureDetector(
      onTap: () {
        Navigator.push(context, MaterialPageRoute(builder: (_) => const TradeAnalysisScreen()));
      },
      child: _glassCard(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1B2838), Color(0xFF0D1B2A)],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)]),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.analytics_outlined, color: Colors.white, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'In-Depth Trade Analysis',
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Win rate, drawdown, risk score, symbol breakdown & more',
                    style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Color(0xFF00E5FF), size: 18),
          ],
        ),
      ),
    );

  // ── TOP PAIRS ──
  Widget _buildTopPairsCard() {
    final selectedBots = _filteredBots();
    final currency = _preferredProfitCurrency();
    final symbolProfits = <String, double>{};
    for (final bot in selectedBots) {
      final symbols = bot['symbol'] ?? 'EURUSD';
      final profit = double.tryParse(bot['profit']?.toString() ?? '0') ?? 0;
      symbolProfits[symbols] = (symbolProfits[symbols] ?? 0) + profit;
    }
    final topPairs = symbolProfits.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
    final pairColors = [
      const Color(0xFF00E5FF),
      const Color(0xFF69F0AE),
      const Color(0xFFFFD600),
      const Color(0xFFFF8A80),
      const Color(0xFF7C4DFF),
    ];

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Top Performing Pairs',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 16),
          if (topPairs.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    const Icon(Icons.bar_chart, color: Colors.white24, size: 40),
                    const SizedBox(height: 8),
                    Text('No trading data yet', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
                  ],
                ),
              ),
            )
          else
            ...topPairs.take(5).toList().asMap().entries.map((entry) {
              final i = entry.key;
              final pair = entry.value;
              final color = pairColors[i % pairColors.length];
              final maxVal = topPairs.first.value.abs();
              final barWidth = maxVal > 0 ? (pair.value.abs() / maxVal).clamp(0.05, 1.0) : 0.05;

              return Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: Row(
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: color.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Center(
                        child: Text(
                          '${i + 1}',
                          style: GoogleFonts.poppins(color: color, fontSize: 14, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(pair.key,
                              style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                          const SizedBox(height: 4),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: barWidth.toDouble(),
                              backgroundColor: Colors.white10,
                              valueColor: AlwaysStoppedAnimation(pair.value >= 0 ? color : const Color(0xFFFF8A80)),
                              minHeight: 6,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      _formatCurrencyAmount(pair.value, currency),
                      style: GoogleFonts.poppins(
                        color: pair.value >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  // ── RECENT TRADES ──
  Widget _buildRecentTradesCard() {
    final tradingService = context.watch<TradingService>();
    final accountCurrency = tradingService.accountCurrency;
    final recentTrades = [...tradingService.trades]
      ..sort((a, b) {
        final timeA = a.closedAt ?? a.openedAt;
        final timeB = b.closedAt ?? b.openedAt;
        return timeB.compareTo(timeA);
      });

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Recent Trades',
                  style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
              GestureDetector(
                onTap: () => setState(() => _selectedIndex = 1),
                child: Text('View All',
                    style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 12, fontWeight: FontWeight.w500)),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (recentTrades.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  children: [
                    const Icon(Icons.receipt_long, color: Colors.white24, size: 40),
                    const SizedBox(height: 8),
                    Text('No recent trades', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
                  ],
                ),
              ),
            )
          else
            ...recentTrades.take(5).map((trade) {
              final profit = trade.profit ?? 0;
              final direction = trade.type == TradeType.buy ? 'BUY' : 'SELL';
              final tradeTime = trade.closedAt ?? trade.openedAt;

              return Container(
                margin: const EdgeInsets.only(bottom: 10),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.04),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: direction == 'BUY'
                            ? const Color(0xFF69F0AE).withOpacity(0.15)
                            : const Color(0xFFFF8A80).withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        direction == 'BUY' ? Icons.arrow_upward : Icons.arrow_downward,
                        color: direction == 'BUY' ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                        size: 18,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            trade.symbol,
                            style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                          ),
                          Text(
                            '$direction  |  ${tradeTime.toLocal().toIso8601String().replaceFirst('T', ' ').split('.').first}',
                            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '${profit >= 0 ? "+" : ""}${_formatCurrencyAmount(profit, accountCurrency)}',
                      style: GoogleFonts.poppins(
                        color: profit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  // ── QUICK ACTIONS GRID ──
  Widget _buildQuickActionsGrid() {
    final actions = [
      {
        'label': 'Create\nBot',
        'icon': Icons.add_circle,
        'color': const Color(0xFF00C853),
        'onTap': () => _pushScreen(const BotConfigurationScreen()),
      },
      {
        'label': 'Bot\nMonitor',
        'icon': Icons.trending_up,
        'color': const Color(0xFFFFB74D),
        'onTap': () => _pushScreen(const BotDashboardScreen()),
      },
      {
        'label': 'Trade\nAnalysis',
        'icon': Icons.analytics_outlined,
        'color': const Color(0xFF00E5FF),
        'onTap': () => _pushScreen(const TradeAnalysisScreen()),
      },
      {
        'label': 'Broker\nSetup',
        'icon': Icons.account_tree,
        'color': const Color(0xFF7C4DFF),
        'onTap': () => _pushScreen(const BrokerIntegrationScreen()),
      },
      {
        'label': 'Multi\nBroker',
        'icon': Icons.business_center,
        'color': const Color(0xFFB388FF),
        'onTap': () => _pushScreen(const MultiBrokerManagementScreen()),
      },
      {
        'label': 'Reports',
        'icon': Icons.assessment,
        'color': const Color(0xFFFF6E40),
        'onTap': () => _pushScreen(const ConsolidatedReportsScreen()),
      },
      {
        'label': 'Financials',
        'icon': Icons.attach_money,
        'color': const Color(0xFF26C6DA),
        'onTap': _openFinancials,
      },
      {
        'label': 'Commissions',
        'icon': Icons.monetization_on,
        'color': const Color(0xFF69F0AE),
        'onTap': () => _pushScreen(const CommissionDashboardScreen()),
      },
      {
        'label': 'Wallet',
        'icon': Icons.account_balance_wallet,
        'color': const Color(0xFFF0B90B),
        'onTap': () => _pushScreen(const UserWalletScreen()),
      },
      {
        'label': 'Portfolio',
        'icon': Icons.dashboard_customize,
        'color': const Color(0xFF5C6BC0),
        'onTap': () => _pushScreen(const UnifiedBrokerDashboardScreen()),
      },
      {
        'label': 'Broker\nIntel',
        'icon': Icons.speed,
        'color': const Color(0xFFFFD600),
        'onTap': () => _pushScreen(const BrokerAnalyticsDashboard()),
      },
      {
        'label': 'Referrals',
        'icon': Icons.group_add,
        'color': const Color(0xFF66BB6A),
        'onTap': _openReferralDashboard,
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Mobile Command Center',
          style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 4),
        Text(
          'Reports, wallet, commissions, analytics, and trading controls are all available here on mobile.',
          style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
        ),
        const SizedBox(height: 14),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1,
          ),
          itemCount: actions.length,
          itemBuilder: (context, index) {
            final action = actions[index];
            final label = action['label']! as String;
            final icon = action['icon']! as IconData;
            final color = action['color']! as Color;
            final onTap = action['onTap']! as VoidCallback;

            return InkWell(
              onTap: onTap,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      color.withOpacity(0.25),
                      color.withOpacity(0.08),
                    ],
                  ),
                  border: Border.all(color: color.withOpacity(0.3)),
                  boxShadow: [
                    BoxShadow(
                      color: color.withOpacity(0.15),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: color.withOpacity(0.2),
                      ),
                      child: Icon(
                        icon,
                        color: color,
                        size: 28,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      label,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      drawer: _buildDrawerMenu(loc),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0E21),
        elevation: 0,
        title: Row(
          children: [
            const LogoWidget(size: 40, showText: false),
            const SizedBox(width: 12),
            Text(
              'ZWESTA',
              style: GoogleFonts.poppins(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.2,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white70),
            onPressed: _fetchRealBots,
            tooltip: loc.translate('refresh_bots'),
          ),
        ],
      ),
      body: Column(
        children: [
          Consumer<FallbackStatusProvider>(
            builder: (context, fallback, _) {
              if (fallback.usingFallback) {
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  color: Colors.amber.shade800.withOpacity(0.3),
                  child: Row(
                    children: [
                      const Icon(Icons.info_outline, color: Colors.amber, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          fallback.fallbackReason ?? 'Viewing cached data.',
                          style: GoogleFonts.poppins(color: Colors.amber.shade200, fontSize: 11),
                        ),
                      ),
                      GestureDetector(
                        onTap: () => fallback.clearFallback(),
                        child: const Icon(Icons.close, color: Colors.amber, size: 16),
                      ),
                    ],
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),
          Expanded(child: _getScreenForIndex(_selectedIndex)),
        ],
      ),
      bottomNavigationBar: _buildBottomNavigationBar(loc),
    );
  }

  BottomNavigationBar _buildBottomNavigationBar(AppLocalizations loc) => BottomNavigationBar(
      currentIndex: _selectedIndex,
      type: BottomNavigationBarType.fixed,
      backgroundColor: const Color(0xFF111633),
      selectedItemColor: const Color(0xFF00E5FF),
      unselectedItemColor: Colors.white38,
      selectedLabelStyle: GoogleFonts.poppins(fontSize: 11, fontWeight: FontWeight.w600),
      unselectedLabelStyle: GoogleFonts.poppins(fontSize: 10),
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: 'Dashboard'),
        BottomNavigationBarItem(icon: Icon(Icons.swap_horiz_rounded), label: 'Trades'),
        BottomNavigationBarItem(icon: Icon(Icons.account_circle_rounded), label: 'Accounts'),
        BottomNavigationBarItem(icon: Icon(Icons.smart_toy_outlined), label: 'Bots'),
        BottomNavigationBarItem(icon: Icon(Icons.widgets_rounded), label: 'Hub'),
      ],
      onTap: (index) {
        setState(() {
          _selectedIndex = index;
        });
      },
    );

  Widget _buildDrawerMenu(AppLocalizations loc) => Drawer(
      backgroundColor: const Color(0xFF111633),
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF1A237E), Color(0xFF0D47A1)],
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)]),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.auto_graph, color: Colors.white, size: 22),
                ),
                const SizedBox(height: 12),
                Text(
                  'ZWESTA TRADING',
                  style: GoogleFonts.poppins(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: 1),
                ),
                const SizedBox(height: 4),
                Text(
                  'Multi-Broker Auto-Trading System',
                  style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12),
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.dashboard_rounded, color: Color(0xFF00E5FF)),
            title: const Text('Dashboard', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 0);
            },
          ),
          ListTile(
            leading: const Icon(Icons.swap_horiz_rounded, color: Color(0xFF69F0AE)),
            title: const Text('Trades', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 1);
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_circle_rounded, color: Color(0xFFFFD600)),
            title: const Text('Accounts', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 2);
            },
          ),
          ListTile(
            leading: const Icon(Icons.smart_toy_outlined, color: Color(0xFF7C4DFF)),
            title: const Text('Bots', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 3);
            },
          ),
          ListTile(
            leading: const Icon(Icons.widgets_rounded, color: Color(0xFF00E5FF)),
            title: const Text('Feature Hub', style: TextStyle(color: Colors.white)),
            subtitle: const Text('All web-version modules in one place', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 4);
            },
          ),
          ListTile(
            leading: const Icon(Icons.add_circle_outline, color: Color(0xFF69F0AE)),
            title: const Text('Create New Bot', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Strategies, symbols & risk setup', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const BotConfigurationScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.insights, color: Color(0xFFFFD600)),
            title: const Text('Bot Monitor', style: TextStyle(color: Colors.white)),
            subtitle: const Text('View active bots & performance', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              setState(() => _selectedIndex = 3);
            },
          ),
          const Divider(color: Colors.white12),
          ListTile(
            leading: const Icon(Icons.card_giftcard, color: Colors.orangeAccent),
            title: const Text('Rentals & Features', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const RentalsAndFeaturesScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_tree, color: Color(0xFF00E5FF)),
            title: const Text('Broker Integration', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const BrokerIntegrationScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.people, color: Color(0xFF69F0AE)),
            title: const Text('Manage Accounts', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const MultiAccountManagementScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.assessment, color: Color(0xFFFFD600)),
            title: const Text('Consolidated Reports', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const ConsolidatedReportsScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.bar_chart, color: Color(0xFF00B0FF)),
            title: const Text('Financials', style: TextStyle(color: Colors.white)),
            onTap: () {
              Navigator.pop(context);
              final tradingService = context.read<TradingService>();
              if (tradingService.primaryAccount != null) {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => FinancialsScreen(
                      account: tradingService.primaryAccount!,
                    ),
                  ),
                );
              } else {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('No account available'),
                  ),
                );
              }
            },
          ),
          ListTile(
            leading: const Icon(Icons.monetization_on, color: Color(0xFF69F0AE)),
            title: const Text('Commissions', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Earnings, withdrawals & referral income', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const CommissionDashboardScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.speed, color: Color(0xFFFFD600)),
            title: const Text('Broker Analytics', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Connection health & performance', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const BrokerAnalyticsDashboard()));
            },
          ),
          // IG Markets integration removed
          ListTile(
            leading: const Icon(Icons.account_balance_wallet, color: Color(0xFF4CAF50)),
            title: const Text('OANDA Withdrawals', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Auto-close & withdraw profits', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const OandaWithdrawalScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet, color: Color(0xFF7C4DFF)),
            title: const Text('FXCM Withdrawals', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Auto-close & withdraw profits', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const FxcmWithdrawalScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.currency_bitcoin, color: Color(0xFFF0B90B)),
            title: const Text('Binance Withdrawals', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Crypto profits & USDT withdrawal', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const BinanceWithdrawalScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet, color: Color(0xFF9C27B0)),
            title: const Text('My Wallet', style: TextStyle(color: Colors.white)),
            subtitle: const Text('View earned balance & pending withdrawals', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const UserWalletScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.admin_panel_settings, color: Color(0xFFE74C3C)),
            title: const Text('Admin: Verify Withdrawals', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Verify Exness withdrawals & split commission', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const AdminWithdrawalVerificationScreen()));
            },
          ),
          const Divider(color: Colors.white12),
          ListTile(
            leading: const Icon(Icons.dashboard_customize, color: Color(0xFF00E5FF)),
            title: const Text('Unified Portfolio', style: TextStyle(color: Colors.white)),
            subtitle: const Text('All brokers in one view', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const UnifiedBrokerDashboardScreen()));
            },
          ),
          ListTile(
            leading: const Icon(Icons.smart_toy, color: Color(0xFFF0B90B)),
            title: const Text('Crypto Strategies', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Grid, DCA, Scalper & more', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(context, MaterialPageRoute(builder: (_) => const CryptoStrategiesScreen()));
            },
          ),
          const Divider(color: Colors.white12),
          ListTile(
            leading: const Icon(Icons.group_add, color: Color(0xFF69F0AE)),
            title: const Text('My Referrals', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Invite friends & earn 5%', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              final userId = context.read<AuthService>().currentUser?.id ?? '0';
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => ReferralDashboardScreen(userId: userId),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.admin_panel_settings, color: Color(0xFFFF8A80)),
            title: const Text('Admin Dashboard', style: TextStyle(color: Colors.white)),
            subtitle: const Text('View all users & earnings', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const AdminDashboardScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.tune, color: Color(0xFFFF6E40)),
            title: const Text('Commission Config', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Manage commission splits', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const CommissionConfigScreen(),
                ),
              );
            },
          ),
          const Divider(color: Colors.white12),
          ListTile(
            leading: const Icon(Icons.analytics_outlined, color: Color(0xFF00E5FF)),
            title: const Text('Trade Analysis', style: TextStyle(color: Colors.white)),
            subtitle: const Text('In-depth performance metrics', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const TradeAnalysisScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.analytics, color: Color(0xFF7C4DFF)),
            title: const Text('Trading Dashboard', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Your stats & performance', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const EnhancedDashboardScreen(),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.business, color: Color(0xFF00E5FF)),
            title: const Text('Multi-Broker Management', style: TextStyle(color: Colors.white)),
            subtitle: const Text('Add/remove broker credentials', style: TextStyle(color: Colors.white38, fontSize: 11)),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const MultiBrokerManagementScreen(),
                ),
              );
            },
          ),
          const Divider(color: Colors.white12),
          ListTile(
            leading: const Icon(Icons.logout, color: Color(0xFFFF8A80)),
            title: const Text('Logout', style: TextStyle(color: Color(0xFFFF8A80))),
            onTap: () {
              context.read<AuthService>().logout();
              Navigator.pop(context);
            },
          ),
        ],
      ),
    );
}

class _FeatureAction {
  const _FeatureAction(this.label, this.icon, this.color, this.onTap);

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
}
