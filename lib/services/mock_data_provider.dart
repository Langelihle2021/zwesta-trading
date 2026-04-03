import '../models/account.dart';
import '../models/trade.dart';

/// Mock data provider for offline/testing mode
class MockDataProvider {
  /// Get mock trades for testing
  static List<Trade> getMockTrades() => [
        Trade(
          id: 'trade_001',
          symbol: 'EURUSD',
          type: TradeType.buy,
          quantity: 1,
          entryPrice: 1.0950,
          currentPrice: 1.1050,
          openedAt: DateTime.now().subtract(const Duration(days: 5)),
          closedAt: DateTime.now().subtract(const Duration(days: 2)),
          profit: 150,
          profitPercentage: 1.43,
          status: TradeStatus.closed,
        ),
        Trade(
          id: 'trade_002',
          symbol: 'GBPUSD',
          type: TradeType.sell,
          quantity: 0.5,
          entryPrice: 1.2680,
          currentPrice: 1.2550,
          openedAt: DateTime.now().subtract(const Duration(days: 3)),
          closedAt: DateTime.now().subtract(const Duration(hours: 12)),
          profit: 65,
          profitPercentage: 1.03,
          status: TradeStatus.closed,
        ),
      ];

  /// Get mock account data
  static Account getMockAccount() => Account(
        id: 'acc_001',
        accountNumber: 'ZWS-2024-001',
        balance: 75000,
        usedMargin: 15000,
        availableMargin: 60000,
        profit: 2500,
        currency: 'USD',
        status: 'active',
        createdAt: DateTime.now().subtract(const Duration(days: 180)),
        leverage: '1:100',
        broker: 'XM Trading',
        server: 'XM-Real',
      );

  /// Get mock accounts list
  static List<Account> getMockAccounts() => [
        getMockAccount(),
        Account(
          id: 'acc_002',
          accountNumber: 'ZWS-2024-002',
          balance: 50000,
          usedMargin: 8000,
          availableMargin: 42000,
          profit: 1200,
          currency: 'USD',
          status: 'active',
          createdAt: DateTime.now().subtract(const Duration(days: 120)),
          leverage: '1:50',
          broker: 'OctaFX',
          server: 'OctaFX-Live',
        ),
      ];

  /// Get summaries for dashboard
  static Map<String, dynamic> getMockDashboardData() {
    final trades = getMockTrades();
    final closedTrades =
        trades.where((t) => t.status == TradeStatus.closed).toList();
    final winningTrades =
        closedTrades.where((t) => t.profit != null && t.profit! > 0).toList();
    final losingTrades =
        closedTrades.where((t) => t.profit == null || t.profit! <= 0).toList();

    final totalProfit = winningTrades.fold<double>(
      0.0,
      (sum, t) => sum + (t.profit ?? 0),
    );
    final totalLoss = losingTrades.fold<double>(
      0.0,
      (sum, t) => sum + (t.profit ?? 0),
    );

    return {
      'totalBalance': 75000.0,
      'totalProfit': totalProfit + totalLoss,
      'openTrades': trades.where((t) => t.status == TradeStatus.open).length,
      'closedTrades': closedTrades.length,
      'winningTrades': winningTrades.length,
      'losingTrades': losingTrades.length,
      'winRate': closedTrades.isEmpty
          ? 0.0
          : ((winningTrades.length / closedTrades.length) * 100),
      'totalProfit': totalProfit,
      'totalLoss': totalLoss,
    };
  }
}
