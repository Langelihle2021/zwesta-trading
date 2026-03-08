import 'package:intl/intl.dart';
import '../models/trade.dart';

class PDFService {
  static Future<void> generateTradeReport({
    required List<Trade> trades,
    required String accountNumber,
    required double totalBalance,
    required double totalProfit,
    required int winningTrades,
  }) async {
    final dateFormat = DateFormat('dd/MM/yyyy HH:mm');
    final currencyFormat = NumberFormat.currency(symbol: '\$');

    // Calculate statistics
    final closedTrades = trades.where((t) => t.status == TradeStatus.closed).toList();
    final activeTrades = trades.where((t) => t.status == TradeStatus.open).toList();
    final winRate = closedTrades.isEmpty
        ? 0.0
        : (winningTrades / closedTrades.length) * 100;

    // Group trades by symbol
    final Map<String, List<Trade>> tradesBySymbol = {};
    for (var trade in trades) {
      if (!tradesBySymbol.containsKey(trade.symbol)) {
        tradesBySymbol[trade.symbol] = [];
      }
      tradesBySymbol[trade.symbol]!.add(trade);
    }

    // Generate HTML report
    final html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zwesta Trading Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1a3a9d;
            text-align: center;
            margin-bottom: 10px;
        }
        h2 {
            color: #333;
            border-bottom: 2px solid #1a3a9d;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-box {
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #1a3a9d;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #1a3a9d;
            margin-top: 5px;
        }
        .positive {
            color: #28a745;
        }
        .negative {
            color: #dc3545;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th {
            background-color: #f0f0f0;
            padding: 12px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #1a3a9d;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f9f9f9;
        }
        .text-right {
            text-align: right;
        }
        .text-center {
            text-align: center;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #999;
            font-size: 12px;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }
        @media print {
            body {
                margin: 0;
                background-color: white;
            }
            .container {
                box-shadow: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>ZWESTA TRADING</h1>
        <p style="text-align: center; color: #666; margin-bottom: 30px;">
            Trading Report | Generated: ${dateFormat.format(DateTime.now())}
        </p>

        <h2>Account Summary</h2>
        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Account Number</div>
                <div class="stat-value">$accountNumber</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Current Balance</div>
                <div class="stat-value">${currencyFormat.format(totalBalance)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total Profit/Loss</div>
                <div class="stat-value ${totalProfit >= 0 ? 'positive' : 'negative'}">${currencyFormat.format(totalProfit)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value positive">${winRate.toStringAsFixed(1)}% ($winningTrades/${closedTrades.length})</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Open Trades</div>
                <div class="stat-value">${activeTrades.length}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Closed Trades</div>
                <div class="stat-value">${closedTrades.length}</div>
            </div>
        </div>

        <h2>Trading Pairs Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th class="text-center">Trades</th>
                    <th class="text-center">Wins</th>
                    <th class="text-right">Total Profit</th>
                    <th class="text-right">P/L %</th>
                </tr>
            </thead>
            <tbody>
                ${tradesBySymbol.entries.map((entry) {
                  final symbol = entry.key;
                  final symbolTrades = entry.value;
                  final totalProfit = symbolTrades.fold<double>(0.0, (sum, trade) => sum + (trade.profit ?? 0));
                  final winCount = symbolTrades.where((t) => (t.profit ?? 0) > 0).length;
                  final avgEntry = symbolTrades.fold<double>(0.0, (sum, trade) => sum + trade.entryPrice) / symbolTrades.length;
                  final profitPercent = avgEntry == 0 ? 0 : (totalProfit / avgEntry) * 100;
                  final profitClass = totalProfit >= 0 ? 'positive' : 'negative';
                  
                  return '''
                <tr>
                    <td><strong>$symbol</strong></td>
                    <td class="text-center">${symbolTrades.length}</td>
                    <td class="text-center">$winCount</td>
                    <td class="text-right $profitClass"><strong>${currencyFormat.format(totalProfit)}</strong></td>
                    <td class="text-right $profitClass"><strong>${profitPercent.toStringAsFixed(1)}%</strong></td>
                </tr>
                  ''';
                }).join('')}
            </tbody>
        </table>

        <h2>Recent Trades (Last 10)</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th class="text-right">Entry</th>
                    <th class="text-center">Qty</th>
                    <th class="text-right">Profit</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${trades.take(10).map((trade) {
                  final profitClass = (trade.profit ?? 0) >= 0 ? 'positive' : 'negative';
                  return '''
                <tr>
                    <td>${trade.symbol}</td>
                    <td>${trade.type.toString().split('.').last.toUpperCase()}</td>
                    <td class="text-right">${trade.entryPrice.toStringAsFixed(4)}</td>
                    <td class="text-center">${trade.quantity.toInt()}</td>
                    <td class="text-right $profitClass"><strong>${currencyFormat.format(trade.profit ?? 0)}</strong></td>
                    <td>${trade.status.toString().split('.').last}</td>
                </tr>
                  ''';
                }).join('')}
            </tbody>
        </table>

        <div class="footer">
            <p>Zwesta Trading System - Confidential Report</p>
            <p>Generated at ${dateFormat.format(DateTime.now())}</p>
        </div>
    </div>

    <script>
        // Add print functionality
        window.addEventListener('load', function() {
            console.log('Report loaded. Use Ctrl+P or Cmd+P to print as PDF');
        });
    </script>
</body>
</html>
    ''';

    // Note: For APK builds, use PdfExportService instead for proper PDF export
    // Web-only functionality removed for mobile compatibility
  }
}

