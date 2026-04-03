import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';

class TradingBotsDashboardScreen extends StatefulWidget {
  const TradingBotsDashboardScreen({Key? key}) : super(key: key);

  @override
  State<TradingBotsDashboardScreen> createState() => _TradingBotsDashboardScreenState();
}

class _TradingBotsDashboardScreenState extends State<TradingBotsDashboardScreen> {
  bool _loading = true;
  List<Map<String, dynamic>> _botsSummary = [];
  Map<String, dynamic> _dashboardStats = {};
  String? _error;
  int _selectedBotIndex = -1;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    setState(() { _loading = true; _error = null; });
    
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('auth_token') ?? '';
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/dashboard/bots-summary'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          setState(() {
            _botsSummary = List<Map<String, dynamic>>.from(data['bots'] ?? []);
            _dashboardStats = {
              'totalBots': data['botsCount'] ?? 0,
              'botsRunning': data['botsRunning'] ?? 0,
              'totalBalance': data['totalBalance'] ?? 0.0,
              'totalProfit': data['totalProfit'] ?? 0.0,
            };
            _loading = false;
          });
        } else {
          setState(() { _error = data['error'] ?? 'Failed to load'; _loading = false; });
        }
      } else {
        setState(() { _error = 'Server error: ${response.statusCode}'; _loading = false; });
      }
    } catch (e) {
      setState(() { _error = 'Error: $e'; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111633),
        elevation: 0,
        title: Row(
          children: [
            const LogoWidget(size: 40, showText: false),
            const SizedBox(width: 12),
            Text('Trading Bots Dashboard', 
              style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 18)
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _loadDashboard,
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: _loading
        ? const Center(child: CircularProgressIndicator(valueColor: AlwaysStoppedAnimation<Color>(Colors.blueAccent)))
        : _error != null
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, size: 60, color: Colors.redAccent),
                  const SizedBox(height: 16),
                  Text(_error!, style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14)),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: _loadDashboard,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.blueAccent),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: _loadDashboard,
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Summary Cards
                    _buildSummaryCards(),
                    const SizedBox(height: 24),

                    // Bots List
                    Text('Trading Bots (${_botsSummary.length})',
                      style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)
                    ),
                    const SizedBox(height: 12),
                    
                    if (_botsSummary.isEmpty)
                      Center(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 40),
                          child: Text('No bots found', 
                            style: GoogleFonts.poppins(color: Colors.white70, fontSize: 14)
                          ),
                        ),
                      )
                    else
                      ListView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: _botsSummary.length,
                        itemBuilder: (context, index) => _buildBotCard(index),
                      ),
                  ],
                ),
              ),
            ),
    );

  Widget _buildSummaryCards() {
    final stats = _dashboardStats;
    final totalBalance = stats['totalBalance'] ?? 0.0;
    final totalProfit = stats['totalProfit'] ?? 0.0;
    final profitColor = totalProfit >= 0 ? Colors.greenAccent : Colors.redAccent;

    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _buildStatsCard(
                'Total Balance',
                '\$${totalBalance.toStringAsFixed(2)}',
                Icons.account_balance_wallet,
                Colors.blueAccent,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatsCard(
                'Total Profit',
                '\$${totalProfit.toStringAsFixed(2)}',
                Icons.trending_up,
                profitColor,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _buildStatsCard(
                'Bots Running',
                '${stats['botsRunning'] ?? 0}/${stats['totalBots'] ?? 0}',
                Icons.smart_toy,
                Colors.purpleAccent,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatsCard(
                'Active Trades',
                '${_botsSummary.fold<int>(0, (sum, bot) => sum + ((bot['trades'] ?? 0) as int))}',
                Icons.swap_horiz,
                Colors.orangeAccent,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildStatsCard(String title, String value, IconData icon, Color color) => Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF111633),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(title,
                  style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(value,
            style: GoogleFonts.poppins(color: color, fontWeight: FontWeight.w600, fontSize: 18),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );

  Widget _buildBotCard(int index) {
    final bot = _botsSummary[index];
    final isExpanded = _selectedBotIndex == index;
    final balance = bot['balance'] ?? 0.0;
    final profit = bot['profit'] ?? 0.0;
    final profitColor = profit >= 0 ? Colors.greenAccent : Colors.redAccent;
    final winRate = bot['winRate'] ?? 0.0;

    return GestureDetector(
      onTap: () => setState(() => _selectedBotIndex = isExpanded ? -1 : index),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF111633),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isExpanded ? Colors.blueAccent : Colors.white12,
            width: isExpanded ? 2 : 1,
          ),
        ),
        child: Column(
          children: [
            // Bot Header (Always Visible)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Container(
                                  width: 12,
                                  height: 12,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: bot['status'] == 'Running' 
                                      ? Colors.greenAccent 
                                      : Colors.redAccent,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    bot['botName'] ?? 'Unknown Bot',
                                    style: GoogleFonts.poppins(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 14,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    bot['broker']?['type'] ?? 'Unknown',
                                    style: GoogleFonts.poppins(
                                      color: Colors.blueAccent,
                                      fontSize: 11,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: Colors.purple.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    bot['tradingMode'] ?? 'interval',
                                    style: GoogleFonts.poppins(
                                      color: Colors.purpleAccent,
                                      fontSize: 11,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 16),
                      Icon(
                        isExpanded ? Icons.expand_less : Icons.expand_more,
                        color: Colors.white70,
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Quick Stats Row
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _buildQuickStat('Balance', '\$${balance.toStringAsFixed(2)}', Colors.blueAccent),
                      _buildQuickStat('Profit', '\$${profit.toStringAsFixed(2)}', profitColor),
                      _buildQuickStat('Trades', '${bot['trades'] ?? 0}', Colors.orange),
                      _buildQuickStat('Win Rate', '${winRate.toStringAsFixed(1)}%', winRate >= 50 ? Colors.green : Colors.red),
                    ],
                  ),
                ],
              ),
            ),

            // Expanded Details (Only when selected)
            if (isExpanded)
              _buildBotDetailedView(bot),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickStat(String label, String value, Color color) => Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(label,
          style: GoogleFonts.poppins(color: Colors.white70, fontSize: 10),
        ),
        const SizedBox(height: 4),
        Text(value,
          style: GoogleFonts.poppins(color: color, fontWeight: FontWeight.w600, fontSize: 12),
        ),
      ],
    );

  Widget _buildBotDetailedView(Map<String, dynamic> bot) => Container(
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: Colors.white12),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Performance Metrics
            Text('Performance Metrics',
              style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13),
            ),
            const SizedBox(height: 12),
            
            _buildDetailRow('Total Trades', '${bot['trades'] ?? 0}'),
            _buildDetailRow('Winning Trades', '${(bot['trades'] ?? 0) > 0 ? (bot['trades'] * (bot['winRate'] ?? 0) / 100).toStringAsFixed(0) : '0'}'),
            _buildDetailRow('Losing Trades', '${(bot['trades'] ?? 0) > 0 ? (bot['trades'] * (100 - (bot['winRate'] ?? 50)) / 100).toStringAsFixed(0) : '0'}'),
            _buildDetailRow('Win Rate', '${(bot['winRate'] ?? 0).toStringAsFixed(1)}%'),
            _buildDetailRow('Current Balance', '\$${(bot['balance'] ?? 0).toStringAsFixed(2)}'),
            _buildDetailRow('Total Profit', '\$${(bot['profit'] ?? 0).toStringAsFixed(2)}'),
            _buildDetailRow('Trading Symbol', bot['symbol'] ?? 'EURUSD'),
            
            const SizedBox(height: 16),
            
            // Action Buttons
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _showBotDetails(bot),
                    icon: const Icon(Icons.info_outline, size: 18),
                    label: const Text('Details'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blueAccent,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _showTradesHistory(bot),
                    icon: const Icon(Icons.history, size: 18),
                    label: const Text('Trades'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.orange,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => _showCommissions(bot),
                    icon: const Icon(Icons.attach_money, size: 18),
                    label: const Text('Commission'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.greenAccent,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );

  Widget _buildDetailRow(String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
            style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
          ),
          Text(value,
            style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 12),
          ),
        ],
      ),
    );

  void _showBotDetails(Map<String, dynamic> bot) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF111633),
        title: Text(bot['botName'] ?? 'Bot Details',
          style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _dialogDetailRow('Bot ID', bot['botId']),
              _dialogDetailRow('Status', bot['status']),
              _dialogDetailRow('Trading Mode', bot['tradingMode']),
              _dialogDetailRow('Created', bot['createdAt']),
              _dialogDetailRow('Broker', bot['broker']?['type'] ?? 'N/A'),
              _dialogDetailRow('Account #', bot['broker']?['accountNumber'] ?? 'N/A'),
              _dialogDetailRow('Current Balance', '\$${(bot['balance'] ?? 0).toStringAsFixed(2)}'),
              _dialogDetailRow('Total Profit', '\$${(bot['profit'] ?? 0).toStringAsFixed(2)}'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showTradesHistory(Map<String, dynamic> bot) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF111633),
        title: Text('${bot['botName']} - Trades',
          style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _dialogDetailRow('Total Trades', '${bot['trades'] ?? 0}'),
              _dialogDetailRow('Winning Trades', '${((bot['trades'] ?? 0) * (bot['winRate'] ?? 0) / 100).toStringAsFixed(0)}'),
              _dialogDetailRow('Losing Trades', '${((bot['trades'] ?? 0) * (100 - (bot['winRate'] ?? 50)) / 100).toStringAsFixed(0)}'),
              _dialogDetailRow('Win Rate', '${(bot['winRate'] ?? 0).toStringAsFixed(1)}%'),
              _dialogDetailRow('Total Profit', '\$${(bot['profit'] ?? 0).toStringAsFixed(2)}'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showCommissions(Map<String, dynamic> bot) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF111633),
        title: Text('${bot['botName']} - Commission',
          style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Commission earnings from this bot',
                style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
              ),
              const SizedBox(height: 16),
              _dialogDetailRow('Bot Name', bot['botName']),
              _dialogDetailRow('Broker', bot['broker']?['type'] ?? 'N/A'),
              _dialogDetailRow('Current Balance', '\$${(bot['balance'] ?? 0).toStringAsFixed(2)}'),
              _dialogDetailRow('Profit Generated', '\$${(bot['profit'] ?? 0).toStringAsFixed(2)}'),
              const SizedBox(height: 12),
              const Divider(color: Colors.white12),
              const SizedBox(height: 12),
              Text('Note: Commission data shows earnings from this bot. Withdrawals track fund transfers.',
                style: GoogleFonts.poppins(color: Colors.white70, fontSize: 11),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _dialogDetailRow(String label, String? value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
            style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
          ),
          Expanded(
            child: Text(value ?? 'N/A',
              textAlign: TextAlign.right,
              style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 12),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
}
