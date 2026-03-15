import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/trading_service.dart';
import '../services/bot_service.dart';
import '../utils/constants.dart';

class TradeAnalysisScreen extends StatefulWidget {
  const TradeAnalysisScreen({Key? key}) : super(key: key);

  @override
  State<TradeAnalysisScreen> createState() => _TradeAnalysisScreenState();
}

class _TradeAnalysisScreenState extends State<TradeAnalysisScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  String _selectedPeriod = '7D';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E21),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Text(
          'Trade Analysis',
          style: GoogleFonts.poppins(
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: const Color(0xFF00E5FF),
          indicatorWeight: 3,
          labelColor: const Color(0xFF00E5FF),
          unselectedLabelColor: Colors.white54,
          labelStyle: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13),
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Performance'),
            Tab(text: 'Risk'),
          ],
        ),
      ),
      body: Consumer2<TradingService, BotService>(
        builder: (context, tradingService, botService, _) {
          final trades = tradingService.trades;
          final closedTrades = tradingService.closedTrades;
          final activeBots = botService.activeBots;

          // Calculate metrics
          final totalTrades = trades.length;
          final closedCount = closedTrades.length;
          final winCount = closedTrades.where((t) => (t.profit ?? 0) > 0).length;
          final lossCount = closedTrades.where((t) => (t.profit ?? 0) < 0).length;
          final winRate = closedCount > 0 ? (winCount / closedCount * 100) : 0.0;

          final totalProfit = closedTrades.fold<double>(0, (s, t) => s + (t.profit ?? 0));
          final avgProfit = closedCount > 0 ? totalProfit / closedCount : 0.0;

          final grossProfit = closedTrades
              .where((t) => (t.profit ?? 0) > 0)
              .fold<double>(0, (s, t) => s + (t.profit ?? 0));
          final grossLoss = closedTrades
              .where((t) => (t.profit ?? 0) < 0)
              .fold<double>(0, (s, t) => s + (t.profit ?? 0).abs());
          final profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? double.infinity : 0.0;

          final bestTrade = closedTrades.isNotEmpty
              ? closedTrades.reduce((a, b) => (a.profit ?? 0) > (b.profit ?? 0) ? a : b)
              : null;
          final worstTrade = closedTrades.isNotEmpty
              ? closedTrades.reduce((a, b) => (a.profit ?? 0) < (b.profit ?? 0) ? a : b)
              : null;

          // Calculate max drawdown
          double maxDrawdown = 0;
          double peak = 0;
          double runningPnL = 0;
          for (final t in closedTrades) {
            runningPnL += (t.profit ?? 0);
            if (runningPnL > peak) peak = runningPnL;
            final dd = peak - runningPnL;
            if (dd > maxDrawdown) maxDrawdown = dd;
          }

          // Symbol breakdown
          final symbolMap = <String, _SymbolStats>{};
          for (final t in closedTrades) {
            final sym = t.symbol;
            symbolMap.putIfAbsent(sym, () => _SymbolStats(sym));
            symbolMap[sym]!.addTrade(t.profit ?? 0);
          }
          final symbolList = symbolMap.values.toList()
            ..sort((a, b) => b.totalProfit.compareTo(a.totalProfit));

          // Consecutive wins/losses
          int maxConsecWins = 0, maxConsecLosses = 0;
          int curWins = 0, curLosses = 0;
          for (final t in closedTrades) {
            if ((t.profit ?? 0) > 0) {
              curWins++;
              curLosses = 0;
              if (curWins > maxConsecWins) maxConsecWins = curWins;
            } else {
              curLosses++;
              curWins = 0;
              if (curLosses > maxConsecLosses) maxConsecLosses = curLosses;
            }
          }

          return TabBarView(
            controller: _tabController,
            children: [
              // Overview Tab
              _buildOverviewTab(
                totalTrades: totalTrades,
                closedCount: closedCount,
                winCount: winCount,
                lossCount: lossCount,
                winRate: winRate,
                totalProfit: totalProfit,
                avgProfit: avgProfit,
                profitFactor: profitFactor,
                activeBots: activeBots.length,
                openTrades: tradingService.activeTrades.length,
              ),
              // Performance Tab
              _buildPerformanceTab(
                symbolList: symbolList,
                bestTrade: bestTrade,
                worstTrade: worstTrade,
                grossProfit: grossProfit,
                grossLoss: grossLoss,
                maxConsecWins: maxConsecWins,
                maxConsecLosses: maxConsecLosses,
              ),
              // Risk Tab
              _buildRiskTab(
                maxDrawdown: maxDrawdown,
                profitFactor: profitFactor,
                winRate: winRate,
                totalProfit: totalProfit,
                closedCount: closedCount,
                avgProfit: avgProfit,
              ),
            ],
          );
        },
      ),
    );
  }

  // ── OVERVIEW TAB ──
  Widget _buildOverviewTab({
    required int totalTrades,
    required int closedCount,
    required int winCount,
    required int lossCount,
    required double winRate,
    required double totalProfit,
    required double avgProfit,
    required double profitFactor,
    required int activeBots,
    required int openTrades,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Quick Stats Row
          Row(
            children: [
              Expanded(child: _glassMetric('Total Trades', '$totalTrades', Icons.swap_horiz, const Color(0xFF00E5FF))),
              const SizedBox(width: 12),
              Expanded(child: _glassMetric('Open', '$openTrades', Icons.radio_button_checked, Colors.orangeAccent)),
              const SizedBox(width: 12),
              Expanded(child: _glassMetric('Active Bots', '$activeBots', Icons.smart_toy, const Color(0xFF7C4DFF))),
            ],
          ),
          const SizedBox(height: 16),

          // Profit Card
          _buildGlassCard(
            child: Column(
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        gradient: totalProfit >= 0
                            ? const LinearGradient(colors: [Color(0xFF00C853), Color(0xFF69F0AE)])
                            : const LinearGradient(colors: [Color(0xFFFF1744), Color(0xFFFF8A80)]),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        totalProfit >= 0 ? Icons.trending_up : Icons.trending_down,
                        color: Colors.white,
                        size: 28,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Net Profit/Loss', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 13)),
                          Text(
                            '\$${totalProfit.toStringAsFixed(2)}',
                            style: GoogleFonts.poppins(
                              fontSize: 28,
                              fontWeight: FontWeight.bold,
                              color: totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    _miniStat('Avg/Trade', '\$${avgProfit.toStringAsFixed(2)}', avgProfit >= 0 ? Colors.greenAccent : Colors.redAccent),
                    _miniStat('Profit Factor', profitFactor == double.infinity ? '∞' : profitFactor.toStringAsFixed(2),
                        profitFactor >= 1 ? Colors.greenAccent : Colors.redAccent),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Win/Loss Visual
          _buildGlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Win Rate Analysis', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 16),
                // Win rate bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SizedBox(
                    height: 32,
                    child: Row(
                      children: [
                        if (winCount > 0)
                          Flexible(
                            flex: winCount,
                            child: Container(
                              color: const Color(0xFF00C853),
                              alignment: Alignment.center,
                              child: Text('$winCount W', style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                            ),
                          ),
                        if (lossCount > 0)
                          Flexible(
                            flex: lossCount,
                            child: Container(
                              color: const Color(0xFFFF1744),
                              alignment: Alignment.center,
                              child: Text('$lossCount L', style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
                            ),
                          ),
                        if (winCount == 0 && lossCount == 0)
                          Expanded(
                            child: Container(
                              color: Colors.white12,
                              alignment: Alignment.center,
                              child: Text('No closed trades', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    '${winRate.toStringAsFixed(1)}% Win Rate',
                    style: GoogleFonts.poppins(
                      color: const Color(0xFF00E5FF),
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Period selector
          const SizedBox(height: 16),
          _buildPeriodSelector(),
        ],
      ),
    );
  }

  // ── PERFORMANCE TAB ──
  Widget _buildPerformanceTab({
    required List<_SymbolStats> symbolList,
    required dynamic bestTrade,
    required dynamic worstTrade,
    required double grossProfit,
    required double grossLoss,
    required int maxConsecWins,
    required int maxConsecLosses,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Best/Worst cards
          Row(
            children: [
              Expanded(
                child: _buildGlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.emoji_events, color: Color(0xFFFFD600), size: 20),
                          const SizedBox(width: 8),
                          Text('Best Trade', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        bestTrade != null ? '\$${(bestTrade.profit ?? 0).toStringAsFixed(2)}' : '--',
                        style: GoogleFonts.poppins(
                          color: const Color(0xFF69F0AE),
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (bestTrade != null)
                        Text(bestTrade.symbol, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildGlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.warning_amber, color: Color(0xFFFF8A80), size: 20),
                          const SizedBox(width: 8),
                          Text('Worst Trade', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 12)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        worstTrade != null ? '\$${(worstTrade.profit ?? 0).toStringAsFixed(2)}' : '--',
                        style: GoogleFonts.poppins(
                          color: const Color(0xFFFF8A80),
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (worstTrade != null)
                        Text(worstTrade.symbol, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Gross / Streaks row
          Row(
            children: [
              Expanded(child: _glassMetric('Gross Profit', '\$${grossProfit.toStringAsFixed(0)}', Icons.arrow_upward, const Color(0xFF69F0AE))),
              const SizedBox(width: 12),
              Expanded(child: _glassMetric('Gross Loss', '\$${grossLoss.toStringAsFixed(0)}', Icons.arrow_downward, const Color(0xFFFF8A80))),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _glassMetric('Best Streak', '$maxConsecWins wins', Icons.local_fire_department, Colors.orangeAccent)),
              const SizedBox(width: 12),
              Expanded(child: _glassMetric('Worst Streak', '$maxConsecLosses losses', Icons.thermostat, Colors.redAccent)),
            ],
          ),
          const SizedBox(height: 20),

          // Symbol Breakdown
          _buildGlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Performance by Symbol', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 16),
                if (symbolList.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text('No data yet', style: GoogleFonts.poppins(color: Colors.white38)),
                    ),
                  )
                else
                  ...symbolList.take(8).map((s) => _buildSymbolRow(s)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSymbolRow(_SymbolStats s) {
    final maxVal = 1.0;
    final normalized = s.totalProfit.abs().clamp(0.0, 1000.0) / 1000.0;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(s.symbol, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: normalized.clamp(0.0, 1.0),
                    backgroundColor: Colors.white10,
                    valueColor: AlwaysStoppedAnimation(
                      s.totalProfit >= 0 ? const Color(0xFF00C853) : const Color(0xFFFF1744),
                    ),
                    minHeight: 8,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${s.tradeCount} trades  |  ${s.winRate.toStringAsFixed(0)}% WR',
                  style: GoogleFonts.poppins(color: Colors.white38, fontSize: 10),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Text(
            '\$${s.totalProfit.toStringAsFixed(2)}',
            style: GoogleFonts.poppins(
              color: s.totalProfit >= 0 ? const Color(0xFF69F0AE) : const Color(0xFFFF8A80),
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }

  // ── RISK TAB ──
  Widget _buildRiskTab({
    required double maxDrawdown,
    required double profitFactor,
    required double winRate,
    required double totalProfit,
    required int closedCount,
    required double avgProfit,
  }) {
    final riskScore = _calculateRiskScore(winRate, profitFactor, maxDrawdown);
    final riskLevel = riskScore >= 70 ? 'Low' : riskScore >= 40 ? 'Medium' : 'High';
    final riskColor = riskScore >= 70 ? const Color(0xFF69F0AE) : riskScore >= 40 ? Colors.orangeAccent : const Color(0xFFFF8A80);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          // Risk Score Ring
          _buildGlassCard(
            child: Column(
              children: [
                Text('Risk Score', style: GoogleFonts.poppins(color: Colors.white60, fontSize: 14)),
                const SizedBox(height: 16),
                SizedBox(
                  width: 140,
                  height: 140,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox(
                        width: 140,
                        height: 140,
                        child: CircularProgressIndicator(
                          value: riskScore / 100,
                          strokeWidth: 10,
                          backgroundColor: Colors.white10,
                          valueColor: AlwaysStoppedAnimation(riskColor),
                        ),
                      ),
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            '${riskScore.toInt()}',
                            style: GoogleFonts.poppins(
                              color: riskColor,
                              fontSize: 36,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(riskLevel, style: GoogleFonts.poppins(color: riskColor, fontSize: 14)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'Based on win rate, profit factor, and drawdown',
                  style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Risk metrics
          _buildGlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Risk Metrics', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 16),
                _riskRow('Max Drawdown', '\$${maxDrawdown.toStringAsFixed(2)}', maxDrawdown <= 100 ? Colors.greenAccent : Colors.redAccent),
                _riskRow('Profit Factor', profitFactor == double.infinity ? '∞' : profitFactor.toStringAsFixed(2),
                    profitFactor >= 1.5 ? Colors.greenAccent : profitFactor >= 1 ? Colors.orangeAccent : Colors.redAccent),
                _riskRow('Win Rate', '${winRate.toStringAsFixed(1)}%',
                    winRate >= 55 ? Colors.greenAccent : winRate >= 45 ? Colors.orangeAccent : Colors.redAccent),
                _riskRow('Avg Trade', '\$${avgProfit.toStringAsFixed(2)}', avgProfit >= 0 ? Colors.greenAccent : Colors.redAccent),
                _riskRow('Total Closed', '$closedCount trades', const Color(0xFF00E5FF)),
                _riskRow('Net Result', '\$${totalProfit.toStringAsFixed(2)}', totalProfit >= 0 ? Colors.greenAccent : Colors.redAccent),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Risk recommendations
          _buildGlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.lightbulb_outline, color: const Color(0xFFFFD600), size: 20),
                    const SizedBox(width: 8),
                    Text('Recommendations', style: GoogleFonts.poppins(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600)),
                  ],
                ),
                const SizedBox(height: 12),
                if (winRate < 50) _recTile('Improve win rate - consider tighter entry criteria', Icons.gpp_good),
                if (maxDrawdown > 200) _recTile('High drawdown detected - reduce position sizes', Icons.shield),
                if (profitFactor < 1.2 && profitFactor != 0) _recTile('Low profit factor - cut losses faster', Icons.speed),
                if (closedCount < 10) _recTile('More data needed for reliable analysis (min 10 trades)', Icons.data_usage),
                if (winRate >= 50 && profitFactor >= 1.5 && maxDrawdown <= 200)
                  _recTile('Your strategy is performing well! Keep it consistent.', Icons.check_circle),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _recTile(String text, IconData icon) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: const Color(0xFF00E5FF), size: 18),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13))),
        ],
      ),
    );
  }

  double _calculateRiskScore(double winRate, double pf, double maxDD) {
    double score = 0;
    score += (winRate / 100) * 40; // 40 points for win rate
    if (pf != double.infinity) {
      score += (pf.clamp(0, 3) / 3) * 30; // 30 points for profit factor
    } else {
      score += 30;
    }
    score += ((1000 - maxDD.clamp(0, 1000)) / 1000) * 30; // 30 points for low drawdown
    return score.clamp(0, 100);
  }

  Widget _riskRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.poppins(color: Colors.white60, fontSize: 13)),
          Text(value, style: GoogleFonts.poppins(color: color, fontWeight: FontWeight.w600, fontSize: 14)),
        ],
      ),
    );
  }

  // ── SHARED WIDGETS ──

  Widget _buildPeriodSelector() {
    final periods = ['1D', '7D', '30D', '90D', 'ALL'];
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: periods.map((p) {
        final isSelected = p == _selectedPeriod;
        return GestureDetector(
          onTap: () => setState(() => _selectedPeriod = p),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: 4),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: isSelected ? const Color(0xFF00E5FF) : Colors.white.withOpacity(0.05),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: isSelected ? const Color(0xFF00E5FF) : Colors.white12,
              ),
            ),
            child: Text(
              p,
              style: GoogleFonts.poppins(
                color: isSelected ? Colors.black : Colors.white54,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _glassMetric(String label, String value, IconData icon, Color color) {
    return _buildGlassCard(
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: GoogleFonts.poppins(color: Colors.white54, fontSize: 11),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _miniStat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
          const SizedBox(height: 4),
          Text(value, style: GoogleFonts.poppins(color: color, fontWeight: FontWeight.w600, fontSize: 15)),
        ],
      ),
    );
  }

  Widget _buildGlassCard({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      child: child,
    );
  }
}

class _SymbolStats {
  final String symbol;
  int tradeCount = 0;
  int wins = 0;
  double totalProfit = 0;

  _SymbolStats(this.symbol);

  void addTrade(double profit) {
    tradeCount++;
    totalProfit += profit;
    if (profit > 0) wins++;
  }

  double get winRate => tradeCount > 0 ? (wins / tradeCount * 100) : 0;
}
