import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
// import 'package:fl_chart/fl_chart.dart'; // Disabled for compatibility
import '../l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import 'dart:math';
import 'package:http/http.dart' as http;
import '../services/auth_service.dart';
import '../services/trading_service.dart';
import '../services/bot_service.dart';
import '../services/pdf_service.dart';
import '../services/ig_auto_connect_service.dart';
import '../providers/fallback_status_provider.dart';
import '../models/account.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../widgets/custom_widgets.dart';
import '../widgets/logo_widget.dart';
import '../widgets/bot_status_indicator.dart';
import 'trades_screen.dart';
import 'trade_analysis_screen.dart';
import 'account_management_screen.dart';
import 'bot_dashboard_screen.dart';
import 'bot_configuration_screen.dart';
import 'bot_analytics_screen.dart';
import 'broker_integration_screen.dart';
import 'financials_screen.dart';
import 'rentals_and_features_screen.dart';
import 'multi_account_management_screen.dart';
import 'consolidated_reports_screen.dart';
import 'referral_dashboard_screen.dart';
import 'admin_dashboard_screen.dart';
import 'multi_broker_management_screen.dart';
import 'enhanced_dashboard_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;
  List<dynamic> _realBotsList = [];
  bool _botsLoading = true;
  String? _botsError;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _fetchRealBots();
    _startAutoRefresh();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  /// Fetch real bots from BotService and filter out demo bots
  void _fetchRealBots() {
    setState(() {
      _botsLoading = true;
      _botsError = null;
    });

    try {
      final botService = context.read<BotService>();
      
      // Fetch bots from backend via BotService
      botService.fetchActiveBots().then((_) {
        if (mounted) {
          setState(() {
            // Filter out demo bots (botId starts with 'DemoBot_' or 'demo')
            _realBotsList = botService.activeBots
                .where((bot) {
                  final botId = (bot['botId'] ?? '').toString().toLowerCase();
                  return !botId.startsWith('demobot_') && !botId.startsWith('demo_');
                })
                .toList();
            
            _botsError = botService.errorMessage;
            _botsLoading = false;
            
            print('✅ Loaded ${_realBotsList.length} real bots (filtered demo bots)');
          });
        }
      }).catchError((e) {
        if (mounted) {
          setState(() {
            _botsError = 'Error fetching bots: $e';
            _realBotsList = [];
            _botsLoading = false;
          });
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _botsError = 'Error loading bots: $e';
          _realBotsList = [];
          _botsLoading = false;
        });
      }
    }
  }

  void _startAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
      if (mounted) {
        _fetchRealBots();
      }
    });
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
            _buildPremiumWelcomeCard(),
            const SizedBox(height: 20),
            _buildIGConnectionStatusCard(),
            const SizedBox(height: 20),
            _buildQuickStatsRow(),
            const SizedBox(height: 20),
            _buildProfitOverviewCard(),
            const SizedBox(height: 20),
            _buildTradeAnalysisPreview(),
            const SizedBox(height: 20),
            _buildTopPairsCard(),
            const SizedBox(height: 20),
            _buildRecentTradesCard(),
            const SizedBox(height: 20),
            _buildQuickActionsGrid(),
            const SizedBox(height: 16),
          ],
        ),
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
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.auto_graph, color: Color(0xFF00E5FF), size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Multi-Broker Automated Trading System',
                        style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
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

  // ── IG CONNECTION STATUS ──
  Widget _buildIGConnectionStatusCard() {
    return Consumer<IGAutoConnectService>(
      builder: (context, igService, _) {
        final isConnected = igService.isConnected;
        final isConnecting = igService.isConnecting;
        final hasError = igService.state == IGConnectionState.error;
        final info = igService.connectionInfo;

        Color statusColor;
        IconData statusIcon;
        String statusText;

        if (isConnected) {
          statusColor = const Color(0xFF69F0AE);
          statusIcon = Icons.check_circle;
          statusText = 'IG Connected';
        } else if (isConnecting) {
          statusColor = const Color(0xFFFFD600);
          statusIcon = Icons.sync;
          statusText = 'Connecting...';
        } else if (hasError) {
          statusColor = const Color(0xFFFF8A80);
          statusIcon = Icons.error_outline;
          statusText = igService.errorMessage ?? 'Connection Error';
        } else {
          statusColor = Colors.white38;
          statusIcon = Icons.cloud_off;
          statusText = 'IG Not Connected';
        }

        return _glassCard(
          child: Column(
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(statusIcon, color: statusColor, size: 24),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'IG Markets API',
                          style: GoogleFonts.poppins(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: statusColor,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                statusText,
                                style: GoogleFonts.poppins(color: statusColor, fontSize: 12),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  if (!isConnected && !isConnecting)
                    _buildConnectButton(context, igService),
                  if (isConnected)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: info?.isLive == true ? Colors.red.withOpacity(0.2) : Colors.orange.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        info?.isLive == true ? 'LIVE' : 'DEMO',
                        style: GoogleFonts.poppins(
                          color: info?.isLive == true ? Colors.redAccent : Colors.orangeAccent,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  if (isConnecting)
                    const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(Color(0xFFFFD600)),
                      ),
                    ),
                ],
              ),
              if (isConnected && info != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _igInfoItem('Account', info.accountId),
                      Container(width: 1, height: 30, color: Colors.white12),
                      _igInfoItem('Balance', '\$${info.balance.toStringAsFixed(2)}'),
                      Container(width: 1, height: 30, color: Colors.white12),
                      _igInfoItem('Currency', info.currency),
                    ],
                  ),
                ),
              ],
              if (hasError) ...[
                const SizedBox(height: 12),
                GestureDetector(
                  onTap: () => igService.autoConnect(),
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF00E5FF).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      'Tap to retry',
                      style: GoogleFonts.poppins(color: const Color(0xFF00E5FF), fontSize: 12),
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildConnectButton(BuildContext context, IGAutoConnectService igService) {
    return GestureDetector(
      onTap: () => _showIGQuickConnect(context, igService),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF00B0FF)]),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          'Connect',
          style: GoogleFonts.poppins(
            color: Colors.black,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  void _showIGQuickConnect(BuildContext context, IGAutoConnectService igService) {
    final apiKeyCtrl = TextEditingController();
    final usernameCtrl = TextEditingController();
    final passwordCtrl = TextEditingController();
    final accountIdCtrl = TextEditingController();
    bool isLive = false;
    bool saveForAutoConnect = true;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setSheetState) {
          return Container(
            padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
            decoration: const BoxDecoration(
              color: Color(0xFF1A1F3A),
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text('Connect to IG Markets',
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text('Enter your IG API credentials to connect automatically',
                      style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13)),
                  const SizedBox(height: 24),
                  _sheetTextField(apiKeyCtrl, 'API Key', Icons.key),
                  const SizedBox(height: 14),
                  _sheetTextField(usernameCtrl, 'IG Username', Icons.person),
                  const SizedBox(height: 14),
                  _sheetTextField(passwordCtrl, 'IG Password', Icons.lock, obscure: true),
                  const SizedBox(height: 14),
                  _sheetTextField(accountIdCtrl, 'Account ID', Icons.account_box),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => isLive = false),
                          child: Container(
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: !isLive ? const Color(0xFF00E5FF).withOpacity(0.15) : Colors.white.withOpacity(0.05),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: !isLive ? const Color(0xFF00E5FF) : Colors.white12),
                            ),
                            child: Column(
                              children: [
                                Icon(Icons.school, color: !isLive ? const Color(0xFF00E5FF) : Colors.white38, size: 20),
                                const SizedBox(height: 4),
                                Text('DEMO', style: GoogleFonts.poppins(
                                  color: !isLive ? const Color(0xFF00E5FF) : Colors.white38,
                                  fontSize: 12, fontWeight: FontWeight.w600,
                                )),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setSheetState(() => isLive = true),
                          child: Container(
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: isLive ? Colors.red.withOpacity(0.15) : Colors.white.withOpacity(0.05),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: isLive ? Colors.redAccent : Colors.white12),
                            ),
                            child: Column(
                              children: [
                                Icon(Icons.warning_amber, color: isLive ? Colors.redAccent : Colors.white38, size: 20),
                                const SizedBox(height: 4),
                                Text('LIVE', style: GoogleFonts.poppins(
                                  color: isLive ? Colors.redAccent : Colors.white38,
                                  fontSize: 12, fontWeight: FontWeight.w600,
                                )),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      SizedBox(
                        width: 24,
                        height: 24,
                        child: Checkbox(
                          value: saveForAutoConnect,
                          onChanged: (v) => setSheetState(() => saveForAutoConnect = v ?? true),
                          activeColor: const Color(0xFF00E5FF),
                          side: const BorderSide(color: Colors.white38),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text('Save for auto-connect on startup',
                          style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton(
                      onPressed: () async {
                        if (apiKeyCtrl.text.isEmpty || usernameCtrl.text.isEmpty || passwordCtrl.text.isEmpty || accountIdCtrl.text.isEmpty) {
                          ScaffoldMessenger.of(ctx).showSnackBar(
                            const SnackBar(content: Text('All fields are required')),
                          );
                          return;
                        }
                        if (saveForAutoConnect) {
                          await igService.saveCredentials(
                            apiKey: apiKeyCtrl.text,
                            username: usernameCtrl.text,
                            password: passwordCtrl.text,
                            accountId: accountIdCtrl.text,
                            isLive: isLive,
                          );
                        }
                        await igService.connect(
                          apiKey: apiKeyCtrl.text,
                          username: usernameCtrl.text,
                          password: passwordCtrl.text,
                          accountId: accountIdCtrl.text,
                          isLive: isLive,
                        );
                        if (ctx.mounted) Navigator.pop(ctx);
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF00E5FF),
                        foregroundColor: Colors.black,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      child: Text('Connect', style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 15)),
                    ),
                  ),
                ],
              ),
            ),
          );
        });
      },
    );
  }

  Widget _sheetTextField(TextEditingController ctrl, String hint, IconData icon, {bool obscure = false}) {
    return TextField(
      controller: ctrl,
      obscureText: obscure,
      style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GoogleFonts.poppins(color: Colors.white30, fontSize: 14),
        prefixIcon: Icon(icon, color: const Color(0xFF00E5FF), size: 20),
        filled: true,
        fillColor: Colors.white.withOpacity(0.06),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF00E5FF)),
        ),
      ),
    );
  }

  Widget _igInfoItem(String label, String value) {
    return Column(
      children: [
        Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10)),
        const SizedBox(height: 4),
        Text(value, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
      ],
    );
  }

  // ── QUICK STATS ROW ──
  Widget _buildQuickStatsRow() {
    final activeBots = _realBotsList.where((bot) => bot['enabled'] == true).length;
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

  // ── QUICK ACTIONS ──
  Widget _buildQuickActionsGrid() {
    final actions = [
      _QuickAction('Create Bot', Icons.add_circle_outline, const Color(0xFF69F0AE), () {
        Navigator.push(context, MaterialPageRoute(builder: (_) => const BotConfigurationScreen()));
      }),
      _QuickAction('Bot Monitor', Icons.insights, const Color(0xFFFFD600), () {
        setState(() => _selectedIndex = 3);
      }),
      _QuickAction('Trade Analysis', Icons.analytics_outlined, const Color(0xFF00E5FF), () {
        Navigator.push(context, MaterialPageRoute(builder: (_) => const TradeAnalysisScreen()));
      }),
      _QuickAction('Broker Setup', Icons.account_tree, const Color(0xFF7C4DFF), () {
        Navigator.push(context, MaterialPageRoute(builder: (_) => const BrokerIntegrationScreen()));
      }),
      _QuickAction('Bot Manager', Icons.smart_toy, const Color(0xFF7C4DFF), () {
        setState(() => _selectedIndex = 3);
      }),
      _QuickAction('Financials', Icons.bar_chart, const Color(0xFFFF8A80), () {
        final tradingService = context.read<TradingService>();
        if (tradingService.primaryAccount != null) {
          Navigator.push(context, MaterialPageRoute(
            builder: (_) => FinancialsScreen(account: tradingService.primaryAccount!),
          ));
        }
      }),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 12),
          child: Text('Quick Actions',
              style: GoogleFonts.poppins(color: Colors.white70, fontSize: 15, fontWeight: FontWeight.w600)),
        ),
        GridView.count(
          crossAxisCount: 3,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 1.1,
          children: actions.map((a) {
            return GestureDetector(
              onTap: a.onTap,
              child: _glassCard(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: a.color.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(a.icon, color: a.color, size: 24),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      a.label,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
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
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)]),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.auto_graph, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
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

class _QuickAction {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  _QuickAction(this.label, this.icon, this.color, this.onTap);
}


