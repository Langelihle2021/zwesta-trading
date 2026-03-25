import 'package:flutter/material.dart';
import 'package:zwesta_trading/models/position_model.dart';
import 'package:zwesta_trading/theme/app_colors.dart';

class PositionsList extends StatelessWidget {
  final List<PositionModel> positions;
  final Function(String) onClose;

  const PositionsList({
    Key? key,
    required this.positions,
    required this.onClose,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    if (positions.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 32),
          child: Center(
            child: Text(
              'No open positions',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ),
      );
    }

    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: positions.length,
      itemBuilder: (context, index) {
        final position = positions[index];
        final isProfit = position.isProfit;

        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            contentPadding: const EdgeInsets.all(12),
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: isProfit
                    ? Colors.green.withOpacity(0.2)
                    : Colors.red.withOpacity(0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                position.type == 'BUY'
                    ? Icons.trending_up
                    : Icons.trending_down,
                color: isProfit ? Colors.green : Colors.red,
              ),
            ),
            title: Text(
              position.symbol,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            subtitle: Text(
              '${position.type} • ${position.volume.toStringAsFixed(2)} units',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            trailing: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '\$${position.currentPnL.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: isProfit ? Colors.green : Colors.red,
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Text(
                  '${position.returnPercentage.toStringAsFixed(2)}%',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: isProfit ? Colors.green : Colors.red,
                      ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
