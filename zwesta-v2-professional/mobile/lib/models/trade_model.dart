class TradeModel {
  final String id;
  final String symbol;
  final String type; // BUY or SELL
  final double volume;
  final double entryPrice;
  final double currentPrice;
  final double pnl;
  final DateTime openedAt;
  final DateTime? closedAt;
  final String status; // open, closed, pending

  TradeModel({
    required this.id,
    required this.symbol,
    required this.type,
    required this.volume,
    required this.entryPrice,
    required this.currentPrice,
    required this.pnl,
    required this.openedAt,
    this.closedAt,
    required this.status,
  });

  factory TradeModel.fromJson(Map<String, dynamic> json) {
    return TradeModel(
      id: json['id'] ?? '',
      symbol: json['symbol'] ?? '',
      type: json['type'] ?? 'BUY',
      volume: (json['volume'] ?? 0).toDouble(),
      entryPrice: (json['entry_price'] ?? 0).toDouble(),
      currentPrice: (json['current_price'] ?? 0).toDouble(),
      pnl: (json['pnl'] ?? 0).toDouble(),
      openedAt: DateTime.parse(json['opened_at'] ?? DateTime.now().toIso8601String()),
      closedAt: json['closed_at'] != null ? DateTime.parse(json['closed_at']) : null,
      status: json['status'] ?? 'open',
    );
  }

  double get returnPercentage {
    if (entryPrice == 0) return 0;
    return ((currentPrice - entryPrice) / entryPrice) * 100;
  }

  bool get isProfit => pnl > 0;
}
