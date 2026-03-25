import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:zwesta_trading/models/trade_model.dart';
import 'package:zwesta_trading/theme/app_colors.dart';

class ChartWidget extends StatelessWidget {
  final List<TradeModel> trades;

  const ChartWidget({
    Key? key,
    required this.trades,
  }) : super(key: key);

  List<FlSpot> _generatePnLSpots() {
    if (trades.isEmpty) return [];

    double runningTotal = 0;
    List<FlSpot> spots = [];

    for (int i = 0; i < trades.length; i++) {
      runningTotal += trades[i].pnl;
      spots.add(FlSpot(i.toDouble(), runningTotal));
    }

    return spots;
  }

  @override
  Widget build(BuildContext context) {
    final spots = _generatePnLSpots();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'P&L Trend',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            if (spots.isEmpty)
              SizedBox(
                height: 200,
                child: Center(
                  child: Text(
                    'No trades yet',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              )
            else
              SizedBox(
                height: 200,
                child: LineChart(
                  LineChartData(
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: false,
                      horizontalInterval: 100,
                      getDrawingHorizontalLine: (value) {
                        return FlLine(
                          color: Colors.grey[300],
                          strokeWidth: 1,
                        );
                      },
                    ),
                    titlesData: FlTitlesData(
                      show: true,
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 40,
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 30,
                        ),
                      ),
                    ),
                    lineBarsData: [
                      LineChartBarData(
                        spots: spots,
                        isCurved: true,
                        color: AppColors.primary,
                        barWidth: 3,
                        isStrokeCapRound: true,
                        dotData: FlDotData(show: false),
                        belowBarData: BarAreaData(
                          show: true,
                          color: AppColors.primary.withOpacity(0.2),
                        ),
                      ),
                    ],
                    borderData: FlBorderData(
                      show: true,
                      border: Border(
                        bottom: BorderSide(color: Colors.grey[300]!),
                        left: BorderSide(color: Colors.grey[300]!),
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
