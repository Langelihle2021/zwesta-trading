class PositionModel {
  final String id;
  final String symbol;
  final String type; // BUY or SELL
  final double volume;
  final double entryPrice;
  final double currentPrice;
  final double stopLoss;
  final double takeProfit;
  final double currentPnL;
  final DateTime openedAt;
  final String status;

  PositionModel({
    required this.id,
    required this.symbol,
    required this.type,
    required this.volume,
    required this.entryPrice,
    required this.currentPrice,
    required this.stopLoss,
    required this.takeProfit,
    required this.currentPnL,
    required this.openedAt,
    required this.status,
  });

  factory PositionModel.fromJson(Map<String, dynamic> json) {
    return PositionModel(
      id: json['id'] ?? '',
      symbol: json['symbol'] ?? '',
      type: json['type'] ?? 'BUY',
      volume: (json['volume'] ?? 0).toDouble(),
      entryPrice: (json['entry_price'] ?? 0).toDouble(),
      currentPrice: (json['current_price'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      takeProfit: (json['take_profit'] ?? 0).toDouble(),
      currentPnL: (json['current_pnl'] ?? 0).toDouble(),
      openedAt: DateTime.parse(json['opened_at'] ?? DateTime.now().toIso8601String()),
      status: json['status'] ?? 'open',
    );
  }

  double get returnPercentage {
    if (entryPrice == 0) return 0;
    return ((currentPrice - entryPrice) / entryPrice) * 100;
  }

  bool get isProfit => currentPnL > 0;
}
