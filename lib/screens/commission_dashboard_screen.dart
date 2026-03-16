import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:fl_chart/fl_chart.dart';
import '../services/commission_service.dart';

class CommissionDashboardScreen extends StatefulWidget {
  const CommissionDashboardScreen({Key? key}) : super(key: key);

  @override
  State<CommissionDashboardScreen> createState() => _CommissionDashboardScreenState();
}

class _CommissionDashboardScreenState extends State<CommissionDashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CommissionService>().fetchCommissions();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        title: Text('Commissions', style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
        backgroundColor: const Color(0xFF111633),
        elevation: 0,
      ),
      body: Consumer<CommissionService>(
        builder: (context, service, _) {
          if (service.isLoading && service.commissions.isEmpty) {
            return const Center(child: CircularProgressIndicator(color: Color(0xFF00E5FF)));
          }

          final stats = service.stats;

          return RefreshIndicator(
            onRefresh: () => service.fetchCommissions(),
            color: const Color(0xFF00E5FF),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Stats cards
                if (stats != null) ...[
                  Row(
                    children: [
                      _statCard('Total Earned', '\$${stats.totalEarned.toStringAsFixed(2)}', const Color(0xFF69F0AE), Icons.attach_money),
                      const SizedBox(width: 12),
                      _statCard('Pending', '\$${stats.totalPending.toStringAsFixed(2)}', const Color(0xFFFFD600), Icons.hourglass_empty),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _statCard('Withdrawn', '\$${stats.totalWithdrawn.toStringAsFixed(2)}', const Color(0xFF00E5FF), Icons.account_balance_wallet),
                      const SizedBox(width: 12),
                      _statCard('Last 30 Days', '\$${service.last30DaysEarned.toStringAsFixed(2)}', const Color(0xFFFF6E40), Icons.calendar_today),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _statCard('Referrals', '${stats.referralCommissions}', const Color(0xFF7C4DFF), Icons.group),
                      const SizedBox(width: 12),
                      _statCard('Trades', '${stats.tradeCommissions}', const Color(0xFF40C4FF), Icons.swap_horiz),
                    ],
                  ),
                  const SizedBox(height: 20),
                ],

                // Top Earning Bots Pie Chart
                if (service.topEarningBots.isNotEmpty)
                  _buildTopBotsPieChart(service.topEarningBots),
                if (service.topEarningBots.isNotEmpty)
                  const SizedBox(height: 20),

                // Withdraw button
                if (stats != null && stats.totalPending > 0)
                  GestureDetector(
                    onTap: () => _showWithdrawDialog(service, stats.totalPending),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [Color(0xFF69F0AE), Color(0xFF00E5FF)]),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.account_balance_wallet, color: Colors.black, size: 20),
                          const SizedBox(width: 8),
                          Text('Request Withdrawal', style: GoogleFonts.poppins(color: Colors.black, fontWeight: FontWeight.w600, fontSize: 15)),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 20),

                // Section header
                Text('Commission History', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 12),

                if (service.commissions.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(40),
                    child: Column(
                      children: [
                        Icon(Icons.receipt_long, color: Colors.white.withOpacity(0.2), size: 48),
                        const SizedBox(height: 12),
                        Text('No commissions yet', style: GoogleFonts.poppins(color: Colors.white38)),
                      ],
                    ),
                  )
                else
                  ...service.commissions.map((c) => Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.06),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white.withOpacity(0.08)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: c.source == 'referral'
                                ? const Color(0xFF7C4DFF).withOpacity(0.15)
                                : const Color(0xFF69F0AE).withOpacity(0.15),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            c.source == 'referral' ? Icons.group : Icons.swap_horiz,
                            color: c.source == 'referral' ? const Color(0xFF7C4DFF) : const Color(0xFF69F0AE),
                            size: 18,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                c.source == 'referral' ? 'Referral Commission' : 'Trade Commission',
                                style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                              ),
                              Text(
                                'Bot: ${c.botId} • ${c.createdAt.toString().split(' ')[0]}',
                                style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '\$${c.amount.toStringAsFixed(2)}',
                              style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 14, fontWeight: FontWeight.bold),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: c.status == 'completed'
                                    ? const Color(0xFF69F0AE).withOpacity(0.15)
                                    : c.status == 'withdrawn'
                                        ? const Color(0xFF00E5FF).withOpacity(0.15)
                                        : const Color(0xFFFFD600).withOpacity(0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                c.status.toUpperCase(),
                                style: GoogleFonts.poppins(
                                  color: c.status == 'completed'
                                      ? const Color(0xFF69F0AE)
                                      : c.status == 'withdrawn'
                                          ? const Color(0xFF00E5FF)
                                          : const Color(0xFFFFD600),
                                  fontSize: 9,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  )),

                if (service.errorMessage != null)
                  Container(
                    margin: const EdgeInsets.only(top: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(service.errorMessage!, style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 12)),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _statCard(String label, String value, Color color, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.08)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 10),
            Text(value, style: GoogleFonts.poppins(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 2),
            Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBotsPieChart(List<Map<String, dynamic>> topBots) {
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

    final total = topBots.fold<double>(0, (s, b) => s + ((b['total_commission'] ?? 0) as num).toDouble());

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Top Earning Bots',
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 16),
          SizedBox(
            height: 180,
            child: PieChart(
              PieChartData(
                sectionsSpace: 3,
                centerSpaceRadius: 40,
                sections: topBots.asMap().entries.map((e) {
                  final i = e.key;
                  final bot = e.value;
                  final commission = ((bot['total_commission'] ?? 0) as num).toDouble();
                  final pct = total > 0 ? (commission / total * 100) : 0.0;
                  final color = chartColors[i % chartColors.length];
                  return PieChartSectionData(
                    value: commission,
                    color: color,
                    radius: 50,
                    title: '${pct.toStringAsFixed(0)}%',
                    titleStyle: GoogleFonts.poppins(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 14),
          ...topBots.asMap().entries.map((e) {
            final i = e.key;
            final bot = e.value;
            final color = chartColors[i % chartColors.length];
            final commission = ((bot['total_commission'] ?? 0) as num).toDouble();
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(bot['bot_id'] ?? 'Unknown', style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12)),
                  ),
                  Text('\$${commission.toStringAsFixed(2)}',
                      style: GoogleFonts.poppins(color: const Color(0xFF69F0AE), fontSize: 12, fontWeight: FontWeight.w600)),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  void _showWithdrawDialog(CommissionService service, double maxAmount) {
    final amountCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F3A),
        title: Text('Request Withdrawal', style: GoogleFonts.poppins(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Available: \$${maxAmount.toStringAsFixed(2)}', style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13)),
            const SizedBox(height: 12),
            TextField(
              controller: amountCtrl,
              keyboardType: TextInputType.number,
              style: GoogleFonts.poppins(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Amount',
                hintStyle: GoogleFonts.poppins(color: Colors.white30),
                prefixIcon: const Icon(Icons.attach_money, color: Color(0xFF00E5FF)),
                filled: true,
                fillColor: Colors.white.withOpacity(0.06),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel', style: GoogleFonts.poppins(color: Colors.white38)),
          ),
          ElevatedButton(
            onPressed: () async {
              final amount = double.tryParse(amountCtrl.text) ?? 0;
              if (amount <= 0 || amount > maxAmount) {
                ScaffoldMessenger.of(ctx).showSnackBar(const SnackBar(content: Text('Invalid amount')));
                return;
              }
              Navigator.pop(ctx);
              final ok = await service.requestWithdrawal(amount);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(ok ? 'Withdrawal requested!' : service.errorMessage ?? 'Failed')),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF00E5FF), foregroundColor: Colors.black),
            child: Text('Withdraw', style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
