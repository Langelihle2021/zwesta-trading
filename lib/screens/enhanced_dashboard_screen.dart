import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';

class EnhancedDashboardScreen extends StatefulWidget {
  const EnhancedDashboardScreen({Key? key}) : super(key: key);

  @override
  State<EnhancedDashboardScreen> createState() =>
      _EnhancedDashboardScreenState();
}

class _EnhancedDashboardScreenState extends State<EnhancedDashboardScreen> {
  Map<String, dynamic>? _dashboardData;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
    // Refresh every 10 seconds
    Future.delayed(const Duration(seconds: 10), _refreshDashboard);
  }

  Future<void> _loadDashboard() async {
    final authService = context.read<AuthService>();
    if (authService.token == null) return;

    setState(() => _isLoading = true);

    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/dashboard'),
        headers: {'X-Session-Token': authService.token!},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _dashboardData = data;
          _isLoading = false;
          _errorMessage = null;
        });
      } else {
        setState(() {
          _errorMessage = 'Failed to load dashboard';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _refreshDashboard() async {
    await _loadDashboard();
    if (mounted) {
      Future.delayed(const Duration(seconds: 10), _refreshDashboard);
    }
  }

  String _formatCurrency(dynamic value) {
    if (value == null) return r'$0.00';
    final num val = value is String ? double.parse(value) : value;
    return '\$${val.toStringAsFixed(2)}';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Trading Dashboard'),
        backgroundColor: Colors.blue[700],
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadDashboard,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _dashboardData == null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline,
                          size: 48, color: Colors.red[400]),
                      const SizedBox(height: AppSpacing.md),
                      Text(_errorMessage ?? 'Failed to load dashboard'),
                      const SizedBox(height: AppSpacing.md),
                      ElevatedButton(
                        onPressed: _loadDashboard,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadDashboard,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // User Info
                        _buildUserInfoCard(),
                        const SizedBox(height: AppSpacing.lg),

                        // Key Stats Grid
                        _buildStatsGrid(),
                        const SizedBox(height: AppSpacing.lg),

                        // Performance Card
                        _buildPerformanceCard(),
                        const SizedBox(height: AppSpacing.lg),

                        // Top Performers
                        _buildTopPerformersCard(),
                        const SizedBox(height: AppSpacing.lg),

                        // Commission Summary
                        _buildCommissionCard(),
                      ],
                    ),
                  ),
                ),
    );

  Widget _buildUserInfoCard() {
    final user = _dashboardData?['user'];
    return Card(
      elevation: 4,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.blue[700]!, Colors.blue[900]!],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 30,
                  backgroundColor: Colors.white.withOpacity(0.3),
                  child: Text(
                    (user?['name'] ?? 'U')[0].toUpperCase(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?['name'] ?? 'User',
                        style: GoogleFonts.poppins(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        user?['email'] ?? 'No email',
                        style: const TextStyle(
                          color: Colors.white70,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'User ID',
                      style: TextStyle(color: Colors.white70, fontSize: 12),
                    ),
                    Text(
                      user?['id']?.toString() ?? 'N/A',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Member Since',
                      style: TextStyle(color: Colors.white70, fontSize: 12),
                    ),
                    Text(
                      user?['created_at']?.toString().split('T')[0] ?? 'N/A',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsGrid() {
    final stats = _dashboardData?['stats'];
    return GridView.count(
      crossAxisCount: 2,
      childAspectRatio: 1.5,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: AppSpacing.md,
      crossAxisSpacing: AppSpacing.md,
      children: [
        _buildStatCard(
          title: 'Active Bots',
          value: '${stats?['active_bots'] ?? 0}',
          icon: Icons.smart_toy,
          color: Colors.green,
        ),
        _buildStatCard(
          title: 'Total Bots',
          value: '${stats?['total_bots'] ?? 0}',
          icon: Icons.computer,
          color: Colors.blue,
        ),
        _buildStatCard(
          title: 'Total Profit',
          value: _formatCurrency(stats?['total_profit']),
          icon: Icons.trending_up,
          color: Colors.orange,
        ),
        _buildStatCard(
          title: 'Total Trades',
          value: '${stats?['total_trades'] ?? 0}',
          icon: Icons.swap_horiz,
          color: Colors.purple,
        ),
        _buildStatCard(
          title: 'Win Rate',
          value: '${stats?['win_rate'] ?? 0}%',
          icon: Icons.percent,
          color: Colors.teal,
        ),
        _buildStatCard(
          title: 'Brokers',
          value: '${stats?['active_brokers'] ?? 0}',
          icon: Icons.business,
          color: Colors.indigo,
        ),
      ],
    );
  }

  Widget _buildStatCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
  }) => Card(
      elevation: 2,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [color.withOpacity(0.1), color.withOpacity(0.05)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: AppSpacing.sm),
            Text(
              value,
              style: GoogleFonts.poppins(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: color,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              title,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[600],
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );

  Widget _buildPerformanceCard() {
    final stats = _dashboardData?['stats'];
    final totalProfit = (stats?['total_profit'] ?? 0) as dynamic;
    final totalCommission =
        (stats?['total_commission_earned'] ?? 0) as dynamic;
    final totalTrades = stats?['total_trades'] ?? 0;
    final profitPerTrade = totalTrades > 0
        ? (totalProfit is String
                ? double.parse(totalProfit)
                : totalProfit as num) /
            totalTrades
        : 0;

    return Card(
      elevation: 2,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: Colors.amber[50],
          border: Border.all(color: Colors.amber[200]!),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.analytics, color: Colors.amber[700]),
                const SizedBox(width: AppSpacing.md),
                Text(
                  'Performance Overview',
                  style: GoogleFonts.poppins(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.amber[900],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            _buildPerformanceRow(
              'Total Profit:',
              _formatCurrency(totalProfit),
              Colors.green,
            ),
            const SizedBox(height: AppSpacing.sm),
            _buildPerformanceRow(
              'Commission Earned:',
              _formatCurrency(totalCommission),
              Colors.blue,
            ),
            const SizedBox(height: AppSpacing.sm),
            _buildPerformanceRow(
              'Avg Profit/Trade:',
              _formatCurrency(profitPerTrade),
              Colors.orange,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPerformanceRow(
    String label,
    String value,
    Color color,
  ) => Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 13)),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: color,
            fontSize: 13,
          ),
        ),
      ],
    );

  Widget _buildTopPerformersCard() {
    final topBots = _dashboardData?['top_performers'] as List? ?? [];
    return Card(
      elevation: 2,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: Colors.green[50],
          border: Border.all(color: Colors.green[200]!),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.star, color: Colors.green[700]),
                const SizedBox(width: AppSpacing.md),
                Text(
                  'Top Performers (${topBots.length})',
                  style: GoogleFonts.poppins(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.green[900],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (topBots.isEmpty)
              Text(
                'No bots yet',
                style: TextStyle(color: Colors.grey[600], fontSize: 12),
              )
            else
              ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: topBots.length,
                itemBuilder: (context, index) {
                  final bot = topBots[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                bot['name'] ?? 'Bot ${index + 1}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                              Text(
                                bot['strategy'] ?? 'N/A',
                                style: TextStyle(
                                  color: Colors.grey[600],
                                  fontSize: 10,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Text(
                          _formatCurrency(bot['total_profit']),
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.green,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildCommissionCard() => Card(
      elevation: 2,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: Colors.purple[50],
          border: Border.all(color: Colors.purple[200]!),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.monetization_on, color: Colors.purple[700]),
                const SizedBox(width: AppSpacing.md),
                Text(
                  'Commission Summary',
                  style: GoogleFonts.poppins(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.purple[900],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Total Commissions:',
                  style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                ),
                Text(
                  _formatCurrency(
                      _dashboardData?['stats']?['total_commission_earned']),
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.purple,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              '💡 Tip: Add referral codes to your friends to earn 15% commission on their trades!',
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey[600],
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      ),
    );
}
