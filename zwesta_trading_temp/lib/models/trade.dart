class Position {
  final int id;
  final String symbol;
  final double entryPrice;
  final double currentPrice;
  final double volume;
  final String type;
  final String status;

  Position({
    required this.id,
    required this.symbol,
    required this.entryPrice,
    required this.currentPrice,
    required this.volume,
    required this.type,
    required this.status,
  });

  double get currentProfit => (currentPrice - entryPrice) * volume;

  factory Position.fromJson(Map<String, dynamic> json) {
    return Position(
      id: json['id'] ?? 0,
      symbol: json['symbol'] ?? '',
      entryPrice: (json['entryPrice'] ?? json['entry_price'] ?? 0).toDouble(),
      currentPrice: (json['currentPrice'] ?? json['current_price'] ?? 0).toDouble(),
      volume: (json['volume'] ?? json['quantity'] ?? 0).toDouble(),
      type: json['type'] ?? json['direction'] ?? 'BUY',
      status: json['status'] ?? 'OPEN',
    );
  }
}

class Trade {
  final int id;
  final String symbol;
  final double entryPrice;
  final double? exitPrice;
  final double quantity;
  final String? openDate;
  final String? closedAt;
  final String type;

  Trade({
    required this.id,
    required this.symbol,
    required this.entryPrice,
    this.exitPrice,
    required this.quantity,
    this.openDate,
    this.closedAt,
    required this.type,
  });

  double get profitAmount => exitPrice != null ? ((exitPrice! - entryPrice) * quantity) : 0;
  double get profitPercent => exitPrice != null ? ((exitPrice! - entryPrice) / entryPrice) * 100 : 0;
  bool get isProfit => profitAmount > 0;

  factory Trade.fromJson(Map<String, dynamic> json) {
    return Trade(
      id: json['id'] ?? 0,
      symbol: json['symbol'] ?? '',
      entryPrice: (json['entryPrice'] ?? json['entry_price'] ?? 0).toDouble(),
      exitPrice: json['exitPrice'] != null ? (json['exitPrice']).toDouble() : null,
      quantity: (json['quantity'] ?? 0).toDouble(),
      openDate: json['openDate'] ?? json['open_date'],
      closedAt: json['closedAt'] ?? json['closed_at'] ?? json['close_date'],
      type: json['type'] ?? json['direction'] ?? 'BUY',
    );
  }
}
