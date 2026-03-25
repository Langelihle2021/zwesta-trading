import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:fl_chart/fl_chart.dart';
import '../l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import 'dart:math';
import 'package:http/http.dart' as http;
import '../services/auth_service.dart';
import '../services/trading_service.dart';
import '../services/bot_service.dart';

import '../providers/fallback_status_provider.dart';
import '../utils/environment_config.dart';
import 'trades_screen.dart';
import 'trade_analysis_screen.dart';
import 'account_management_screen.dart';
import 'bot_dashboard_screen.dart';
import 'bot_configuration_screen.dart';
import 'broker_integration_screen.dart';
import 'financials_screen.dart';
import 'rentals_and_features_screen.dart';
import 'multi_account_management_screen.dart';
import 'consolidated_reports_screen.dart';
import 'referral_dashboard_screen.dart';
import 'admin_dashboard_screen.dart';
import 'commission_config_screen.dart';
import 'multi_broker_management_screen.dart';
import 'enhanced_dashboard_screen.dart';
import 'commission_dashboard_screen.dart';
import 'broker_analytics_dashboard.dart';
import 'oanda_withdrawal_screen.dart';
import 'fxcm_withdrawal_screen.dart';
import 'binance_withdrawal_screen.dart';
import 'admin_withdrawal_verification_screen.dart';
import 'user_wallet_screen.dart';
import 'unified_broker_dashboard_screen.dart';
import 'crypto_strategies_screen.dart';
import '../widgets/logo_widget.dart';

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
  String? _lastRefreshError;

  // Broker account balances
  List<Map<String, dynamic>> _brokerAccounts = [];
  bool _brokerBalancesLoading = false;
  double _totalBrokerBalance = 0;

  // Balance tracking for increases/decreases
  // _sessionStartBalances is set ONCE on first fetch and never updated,
  // so balanceChange = currentBalance - sessionStart = total change this session.
  Map<String, double> _sessionStartBalances = {};
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
          Map<String, double> newChanges = {};
          for (var account in (data['accounts'] ?? [])) {
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

  /// Fetch real bots from BotService and filter out demo bots
  Future<void> _fetchRealBots() async {
    try {
      final botService = context.read<BotService>();
      
      // Fetch bots from backend via BotService
      await botService.fetchActiveBots();
      
      if (mounted) {
        setState(() {
          // Filter out demo bots (botId starts with 'DemoBot_' or 'demo')
          _realBotsList = botService.activeBots
              .where((bot) {
                final botId = (bot['botId'] ?? '').toString().toLowerCase();
                return !botId.startsWith('demobot_') && !botId.startsWith('demo_');
              })
              .toList();
          
          print('✅ Loaded ${_realBotsList.length} real bots (filtered demo bots)');
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
          _lastRefreshError = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _refreshFailureCount++;
          _lastRefreshError = e.toString();
        });
      }
    }
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
        return const BotDashboardScreen();
      default:
        return _buildDashboardTab();
    }
  }

  // ────── HELPER METHODS ──────

  /// Build the connected broker account card showing balance and withdrawals
  Widget _buildConnectedBrokerCard() {
    // Find the first connected broker account (e.g., Exness)
    final connected = _brokerAccounts.firstWhere(
      (a) => a['connected'] == true,
      orElse: () => <String, dynamic>{},
    );
    
    if (connected.isEmpty) {
      return const SizedBox.shrink();
    }
    
    final broker = connected['broker'] ?? 'Broker';
    final accountId = connected['accountId']?.toString() ?? '';
    final accountNum = connected['accountNumber']?.toString() ?? accountId;
    final balance = (connected['balance'] as num?)?.toDouble() ?? 0.0;
    final equity = (connected['equity'] as num?)?.toDouble() ?? 0.0;
    final currency = connected['currency'] ?? 'USD';
    final key = '${broker}_${accountNum}';
    final balanceChange = _balanceChanges[key] ?? 0.0;
    final isIncreasing = balanceChange >= 0;
    
    // Get recent withdrawals for this account
    final accountWithdrawals = _recentWithdrawals
        .where((w) => w['broker']?.toString() == broker && w['accountNumber']?.toString() == accountNum)
        .toList();
    final totalWithdrawn = accountWithdrawals.fold<double>(0, (sum, w) => sum + ((w['amount'] as num?)?.toDouble() ?? 0));
    
    return _glassCard(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          isIncreasing ? const Color(0xFF1B5E20).withOpacity(0.3) : const Color(0xFF4A235A).withOpacity(0.3),
          Colors.transparent,
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with broker icon
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
            ],
          ),
          const SizedBox(height: 18),
          
          // Balance and Equity
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Balance', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                  Text(
                    '$currency ${balance.toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('Equity', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                  Text(
                    '$currency ${equity.toStringAsFixed(2)}',
                    style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Balance Change Indicator
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
                      '$currency ${balanceChange.abs().toStringAsFixed(2)}',
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
          
          // Withdrawals Section
          if (accountWithdrawals.isNotEmpty) ...[
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Recent Withdrawals', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w500)),
                Text(
                  'Total: $currency ${totalWithdrawn.toStringAsFixed(2)}',
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
                            '$currency ${amount.toStringAsFixed(2)}',
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
            }).toList(),
          ],
        ],
      ),
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
    final activeBots = _realBotsList.where((bot) => bot['enabled'] == true || bot['status'] == 'Active').toList();
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
              Text('${activeBots.length} active',
                  style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 13, fontWeight: FontWeight.w500)),
            ],
          ),
          const SizedBox(height: 14),
          ...activeBots.take(5).map((bot) {
            final botId = bot['botId']?.toString() ?? 'Unknown Bot';
            final strategy = bot['strategy']?.toString() ?? 'Unknown';
            final profit = (double.tryParse(bot['totalProfit']?.toString() ?? '0') ?? 0);
            final isProfitable = profit > 0;
            final status = bot['status']?.toString() ?? 'running';
            
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
                              Text(botId, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                              Text(strategy, style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11)),
                            ],
                          ),
                        ),
                        Text(
                          '\$${profit.toStringAsFixed(2)}',
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
                            builder: (context, botService, _) {
                              return InkWell(
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
                              );
                            },
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
                                          final token = prefs.getString('authToken') ?? '';
                                          
                                          final response = await http.post(
                                            Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/delete'),
                                            headers: {
                                              'Content-Type': 'application/json',
                                              'Authorization': 'Bearer $token',
                                            },
                                            body: jsonEncode({'botId': botId}),
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
          }).toList(),
        ],
      ),
    );
  }

  // ── GLASS CARD HELPER ──
  Widget _glassCard({required Widget child, LinearGradient? gradient}) {
    return Container(
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
  }

  /// Build the dashboard tab - Modern premium layout
  Widget _buildDashboardTab() {
    return Container(
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
  }

  // ── PREMIUM WELCOME CARD ──
  Widget _buildPremiumWelcomeCard() {
    return Consumer<AuthService>(
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
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: const LinearGradient(
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
              // ── Total Portfolio Balance ──
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'TOTAL PORTFOLIO BALANCE',
                      style: GoogleFonts.poppins(color: Colors.white54, fontSize: 10, fontWeight: FontWeight.w500, letterSpacing: 1.2),
                    ),
                    const SizedBox(height: 4),
                    _brokerBalancesLoading && _totalBrokerBalance == 0
                        ? Row(
                            children: [
                              SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 1.5, color: Color(0xFF00E5FF))),
                              const SizedBox(width: 10),
                              Text('Loading...', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 14)),
                            ],
                          )
                        : Text(
                            '\$${_totalBrokerBalance.toStringAsFixed(2)}',
                            style: GoogleFonts.poppins(
                              color: Colors.white,
                              fontSize: 28,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                    if (_brokerAccounts.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          '${_brokerAccounts.where((a) => a['connected'] == true).length} connected account${_brokerAccounts.where((a) => a['connected'] == true).length == 1 ? '' : 's'}',
                          style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ── BROKER ACCOUNTS CARD ──
  Widget _buildBrokerAccountsCard() {
    if (_brokerBalancesLoading && _brokerAccounts.isEmpty) {
      return _glassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Broker Accounts', style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00E5FF))),
          ],
        ),
      );
    }

    if (_brokerAccounts.isEmpty) {
      return const SizedBox.shrink();
    }

    return _glassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Broker Accounts', style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600)),
              Text('\$${_totalBrokerBalance.toStringAsFixed(2)}',
                style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ..._brokerAccounts.map((account) {
            final broker = account['broker']?.toString() ?? 'Unknown';
            final accountNum = account['accountNumber']?.toString() ?? '';
            final balance = (account['balance'] as num?)?.toDouble() ?? 0;
            final equity = (account['equity'] as num?)?.toDouble() ?? 0;
            final mode = account['mode']?.toString() ?? '';
            final connected = account['connected'] == true;
            final error = account['error']?.toString();

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
                      color: connected
                          ? const Color(0xFF69F0AE).withOpacity(0.15)
                          : const Color(0xFFFF8A80).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      connected ? Icons.account_balance_wallet : Icons.error_outline,
                      color: connected ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('$broker  ($mode)',
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
                        Text('Account: $accountNum',
                          style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10)),
                        if (!connected && error != null)
                          Text(error, style: GoogleFonts.poppins(color: const Color(0xFFFF8A80), fontSize: 10)),
                      ],
                    ),
                  ),
                  if (connected)
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('\$${balance.toStringAsFixed(2)}',
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
                        ),
                        Text('Equity: \$${equity.toStringAsFixed(2)}',
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
    final activeBots = _realBotsList.where((bot) => bot['enabled'] == true || bot['status'] == 'Active').length;
    final totalTrades = _realBotsList.fold<int>(
      0, (sum, bot) => sum + (int.tryParse(bot['totalTrades']?.toString() ?? '0') ?? 0),
    );
    final totalProfit = _realBotsList.fold<double>(
      0, (sum, bot) => sum + (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0),
    );

    return Row(
      children: [
        Expanded(child: _buildStatPill(Icons.smart_toy, '$activeBots', 'Active Bots', const Color(0xFF7C4DFF))),
        const SizedBox(width: 10),
        Expanded(child: _buildStatPill(Icons.swap_horiz, '$totalTrades', 'Trades', const Color(0xFF00E5FF))),
        const SizedBox(width: 10),
        Expanded(
          child: _buildStatPill(
            totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
            '\$${totalProfit.toStringAsFixed(0)}',
            'Profit',
            totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
          ),
        ),
      ],
    );
  }

  Widget _buildStatPill(IconData icon, String value, String label, Color color) {
    return _glassCard(
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
            style: GoogleFonts.poppins(
              color: Colors.white,
              fontSize: 20,
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
  }

  // ── PROFIT OVERVIEW ──
  Widget _buildProfitOverviewCard() {
    final totalProfit = _realBotsList.fold<double>(
      0, (sum, bot) => sum + (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0),
    );
    final winningBots = _realBotsList.where((bot) => (double.tryParse(bot['profit']?.toString() ?? '0') ?? 0) > 0).length;
    final totalBots = _realBotsList.length;
    final winRate = totalBots > 0 ? (winningBots / totalBots * 100) : 0.0;

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
              '\$${totalProfit.toStringAsFixed(2)}',
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
    final symbolProfits = <String, double>{};
    for (final bot in _realBotsList) {
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
                  final pct = (pair.value / total * 100);
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

  Widget _chartLegendItem(Color color, String label, int count) {
    return Row(
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 8),
        Text('$label ($count)', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12)),
      ],
    );
  }

  // ── PROFIT TREND LINE CHART ──
  Widget _buildProfitLineChart() {
    // Gather profit per bot as data points
    final profitPoints = <FlSpot>[];
    double cumulative = 0;
    for (int i = 0; i < _realBotsList.length; i++) {
      final profit = double.tryParse(_realBotsList[i]['profit']?.toString() ?? '0') ?? 0;
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
            'Across ${_realBotsList.length} bot(s)',
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
                      FlLine(color: Colors.white10, strokeWidth: 1),
                ),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 50,
                      getTitlesWidget: (value, meta) => Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: Text(
                          '\$${value.toStringAsFixed(0)}',
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
                        if (idx >= 0 && idx < _realBotsList.length) {
                          final botId = (_realBotsList[idx]['botId'] ?? '').toString();
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
                          const Color(0xFF00E5FF).withOpacity(0.0),
                        ],
                      ),
                    ),
                  ),
                ],
                lineTouchData: LineTouchData(
                  touchTooltipData: LineTouchTooltipData(
                    getTooltipItems: (touchedSpots) {
                      return touchedSpots.map((spot) {
                        return LineTooltipItem(
                          '\$${spot.y.toStringAsFixed(2)}',
                          GoogleFonts.poppins(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        );
                      }).toList();
                    },
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
  Widget _buildTradeAnalysisPreview() {
    return GestureDetector(
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
  }

  // ── TOP PAIRS ──
  Widget _buildTopPairsCard() {
    final symbolProfits = <String, double>{};
    for (final bot in _realBotsList) {
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
                      '\$${pair.value.toStringAsFixed(2)}',
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
    final allTrades = <Map<String, dynamic>>[];
    for (final bot in _realBotsList) {
      final trades = bot['tradeHistory'] ?? [];
      if (trades is List) {
        allTrades.addAll(trades.cast<Map<String, dynamic>>());
      }
    }
    allTrades.sort((a, b) {
      final timeA = DateTime.tryParse(a['time']?.toString() ?? '') ?? DateTime.now();
      final timeB = DateTime.tryParse(b['time']?.toString() ?? '') ?? DateTime.now();
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
          if (allTrades.isEmpty)
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
            ...allTrades.take(5).map((trade) {
              final profit = double.tryParse(trade['profit']?.toString() ?? '0') ?? 0;
              final direction = trade['direction']?.toString() ?? 'BUY';

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
                            '${trade['symbol'] ?? 'EURUSD'}',
                            style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                          ),
                          Text(
                            '$direction  |  ${trade['time']?.toString().split('.')[0] ?? 'N/A'}',
                            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      '${profit >= 0 ? "+" : ""}\$${profit.toStringAsFixed(2)}',
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
        'route': '/bot-configuration',
        'screen': const BotConfigurationScreen(),
      },
      {
        'label': 'Bot\nMonitor',
        'icon': Icons.trending_up,
        'color': const Color(0xFFFFB74D),
        'route': '/bot-dashboard',
        'screen': const BotDashboardScreen(),
      },
      {
        'label': 'Trade\nAnalysis',
        'icon': Icons.bar_chart,
        'color': const Color(0xFF00E5FF),
        'route': '/trade-analysis',
        'screen': const TradeAnalysisScreen(),
      },
      {
        'label': 'Broker\nSetup',
        'icon': Icons.settings,
        'color': const Color(0xFF7C4DFF),
        'route': '/broker-integration',
        'screen': const BrokerIntegrationScreen(),
      },
      {
        'label': 'Bot\nManager',
        'icon': Icons.cloud,
        'color': const Color(0xFFB388FF),
        'route': '/multi-broker-management',
        'screen': const MultiBrokerManagementScreen(),
      },
      {
        'label': 'Financials',
        'icon': Icons.attach_money,
        'color': const Color(0xFFFF6E40),
        'route': '/financials',
        'screen': null,
      },
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Quick Actions',
          style: GoogleFonts.poppins(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 14),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.0,
          ),
          itemCount: actions.length,
          itemBuilder: (context, index) {
            final action = actions[index];
            final label = action['label'] as String;
            final icon = action['icon'] as IconData;
            final color = action['color'] as Color;
            final screen = action['screen'] as Widget?;
            final route = action['route'] as String;

            return InkWell(
              onTap: () {
                if (screen != null) {
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => screen),
                  );
                } else if (route == '/financials') {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Go to Accounts tab to manage financial reports', 
                        style: GoogleFonts.poppins(color: Colors.white)),
                      backgroundColor: const Color(0xFFFF6E40),
                      duration: const Duration(seconds: 3),
                    ),
                  );
                }
              },
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

  BottomNavigationBar _buildBottomNavigationBar(AppLocalizations loc) {
    return BottomNavigationBar(
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
      ],
      onTap: (index) {
        setState(() {
          _selectedIndex = index;
        });
      },
    );
  }

  Widget _buildDrawerMenu(AppLocalizations loc) {
    return Drawer(
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
}
