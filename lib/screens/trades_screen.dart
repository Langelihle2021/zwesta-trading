import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import '../services/trading_service.dart';
import '../models/trade.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../widgets/custom_widgets.dart';
import 'broker_integration_screen.dart';

class TradesScreen extends StatefulWidget {
  const TradesScreen({Key? key}) : super(key: key);

  @override
  State<TradesScreen> createState() => _TradesScreenState();
}

class _TradesScreenState extends State<TradesScreen> {
  int _selectedTab = 0; // 0: all, 1: open, 2: closed

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: CustomAppBar(
        title: 'Trades',
        showBackButton: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _showOpenTradeDialog(context),
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0A0E21), Color(0xFF1A237E), Color(0xFF512DA8)],
          ),
        ),
        child: _buildTradesContent(),
      ),
    );
  }

  Widget _buildTradesContent() {
    return Consumer<TradingService>(
      builder: (context, tradingService, _) {
        return SafeArea(
          child: Column(
          children: [
            // Connected broker banner
            FutureBuilder<SharedPreferences>(
              future: SharedPreferences.getInstance(),
              builder: (ctx, snap) {
                if (!snap.hasData) return const SizedBox.shrink();
                final prefs = snap.data!;
                final broker = prefs.getString('broker');
                final connected = prefs.getBool('broker_connected') == true;
                return GestureDetector(
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BrokerIntegrationScreen())),
                  child: Container(
                    margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: connected ? Colors.green.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: connected ? Colors.green.withOpacity(0.3) : Colors.orange.withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        Icon(connected ? Icons.link : Icons.link_off, color: connected ? Colors.green : Colors.orange, size: 18),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            connected ? 'Connected to ${broker ?? "Broker"}' : 'No broker connected',
                            style: GoogleFonts.poppins(color: connected ? Colors.green : Colors.orange, fontSize: 12, fontWeight: FontWeight.w500),
                          ),
                        ),
                        Text('Manage', style: GoogleFonts.poppins(color: AppColors.primaryColor, fontSize: 11, fontWeight: FontWeight.w600)),
                        const SizedBox(width: 4),
                        const Icon(Icons.chevron_right, color: AppColors.primaryColor, size: 16),
                      ],
                    ),
                  ),
                );
              },
            ),

            // Tab Selector
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(
                children: [
                  _buildTabButton(
                    context,
                    'All',
                    0,
                    '${tradingService.trades.length}',
                  ),
                  const SizedBox(width: AppSpacing.md),
                  _buildTabButton(
                    context,
                    'Open',
                    1,
                    '${tradingService.activeTrades.length}',
                  ),
                  const SizedBox(width: AppSpacing.md),
                  _buildTabButton(
                    context,
                    'Closed',
                    2,
                    '${tradingService.closedTrades.length}',
                  ),
                ],
              ),
            ),

            // Trades List
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async {
                  await tradingService.fetchTrades();
                },
                child: _buildTradesList(context, tradingService),
              ),
            ),
          ],
        ),
        );
      },
    );
  }

  Widget _buildTabButton(BuildContext context, String label, int index, String count) {
    final isSelected = _selectedTab == index;
    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedTab = index;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primaryColor : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? AppColors.primaryColor : AppColors.veryLightGrey,
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: isSelected ? Colors.white : AppColors.darkGrey,
              ),
            ),
            Text(
              count,
              style: TextStyle(
                fontSize: 12,
                color: isSelected ? Colors.white70 : AppColors.grey,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTradesList(BuildContext context, TradingService tradingService) {
    List<Trade> trades;

    switch (_selectedTab) {
      case 1:
        trades = tradingService.activeTrades;
        break;
      case 2:
        trades = tradingService.closedTrades;
        break;
      default:
        trades = tradingService.trades;
    }

    if (trades.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.trending_up,
              size: 64,
              color: AppColors.lightGrey,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              _selectedTab == 1 ? 'No open trades' : 'No ${_selectedTab == 2 ? 'closed' : ''} trades',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              _selectedTab == 1
                  ? 'Tap + to open a new trade'
                  : 'You haven\'t closed any trades yet',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: trades.length,
      itemBuilder: (context, index) {
        final trade = trades[index];
        return TradeCard(
          symbol: trade.symbol,
          type: trade.type.toString().split('.').last,
          quantity: trade.quantity,
          entryPrice: trade.entryPrice,
          currentPrice: trade.currentPrice ?? trade.entryPrice,
          profit: trade.profit ?? 0,
          profitPercentage: trade.profitPercentage ?? 0,
          onTap: () {
            tradingService.selectTrade(trade);
            _showTradeDetailsDialog(context, trade, tradingService);
          },
        );
      },
    );
  }

  /// Fetch trading symbols from the backend API
  Future<List<Map<String, String>>> _fetchTradingSymbolsForDialog() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/commodities/list'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final commodities = data['commodities'] as Map;
        
        List<Map<String, String>> symbols = [];
        
        commodities.forEach((category, items) {
          if (items is List) {
            for (var item in items) {
              if (item is Map) {
                final symbol = item['symbol'] ?? '';
                final name = item['name'] ?? '';
                if (symbol.isNotEmpty && name.isNotEmpty) {
                  symbols.add({
                    'symbol': symbol,
                    'name': name,
                  });
                }
              }
            }
          }
        });
        
        return symbols;
      }
    } catch (e) {
      print('Error fetching trading symbols: $e');
    }
    
    // Fallback to minimal list if API fails
    return [
      {'symbol': 'EURUSD', 'name': 'EUR/USD'},
      {'symbol': 'GBPUSD', 'name': 'GBP/USD'},
      {'symbol': 'XPTUSD', 'name': 'Platinum'},
      {'symbol': 'OILK', 'name': 'Crude Oil'},
    ];
  }

  void _showOpenTradeDialog(BuildContext context) {
    final quantityController = TextEditingController();
    final entryPriceController = TextEditingController();
    final takeProfitController = TextEditingController();
    final stopLossController = TextEditingController();
    String selectedType = 'buy';
    String selectedSymbol = 'EURUSD';

    // Initialize with empty list, will be populated from API
    List<Map<String, String>> tradingSymbols = [];

    // Fetch trading symbols from backend API
    _fetchTradingSymbolsForDialog().then((symbols) {
      // This is used in the showDialog below
      tradingSymbols = symbols;
    });

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Open New Trade'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                value: selectedType,
                decoration: const InputDecoration(labelText: 'Trade Type'),
                items: const [
                  DropdownMenuItem(value: 'buy', child: Text('Buy')),
                  DropdownMenuItem(value: 'sell', child: Text('Sell')),
                ],
                onChanged: (value) {
                  selectedType = value ?? 'buy';
                },
              ),
              const SizedBox(height: AppSpacing.md),
              DropdownButtonFormField<String>(
                value: selectedSymbol,
                decoration: const InputDecoration(labelText: 'Select Symbol/Commodity'),
                items: tradingSymbols.map((item) {
                  return DropdownMenuItem(
                    value: item['symbol'],
                    child: Text(item['name'] ?? ''),
                  );
                }).toList(),
                onChanged: (value) {
                  selectedSymbol = value ?? 'EURUSD';
                },
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: quantityController,
                decoration: const InputDecoration(labelText: 'Quantity'),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: entryPriceController,
                decoration: const InputDecoration(labelText: 'Entry Price'),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: takeProfitController,
                decoration: const InputDecoration(labelText: 'Take Profit (Optional)'),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: stopLossController,
                decoration: const InputDecoration(labelText: 'Stop Loss (Optional)'),
                keyboardType: TextInputType.number,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              _submitOpenTrade(
                context,
                selectedSymbol,
                selectedType,
                double.tryParse(quantityController.text) ?? 0,
                double.tryParse(entryPriceController.text) ?? 0,
                double.tryParse(takeProfitController.text),
                double.tryParse(stopLossController.text),
              );
            },
            child: const Text('Open Trade'),
          ),
        ],
      ),
    );
  }

  void _submitOpenTrade(
    BuildContext context,
    String symbol,
    String type,
    double quantity,
    double entryPrice,
    double? takeProfit,
    double? stopLoss,
  ) async {
    final tradingService = context.read<TradingService>();

    bool success = await tradingService.openTrade(
      symbol,
      type == 'buy' ? TradeType.buy : TradeType.sell,
      quantity,
      entryPrice,
      takeProfit,
      stopLoss,
    );

    if (mounted) {
      Navigator.pop(context);
      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Trade opened successfully')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(tradingService.errorMessage ?? 'Error opening trade')),
        );
      }
    }
  }

  void _showTradeDetailsDialog(BuildContext context, Trade trade, TradingService tradingService) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('${trade.symbol} Details'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildDetailRow('Symbol', trade.symbol),
              _buildDetailRow('Type', trade.type.toString().split('.').last.toUpperCase()),
              _buildDetailRow('Quantity', '${trade.quantity.toStringAsFixed(0)} units'),
              _buildDetailRow('Entry Price', trade.entryPrice.toStringAsFixed(4)),
              _buildDetailRow(
                'Current Price',
                (trade.currentPrice ?? trade.entryPrice).toStringAsFixed(4),
              ),
              if (trade.takeProfit != null)
                _buildDetailRow('Take Profit', trade.takeProfit!.toStringAsFixed(4)),
              if (trade.stopLoss != null)
                _buildDetailRow('Stop Loss', trade.stopLoss!.toStringAsFixed(4)),
              _buildDetailRow(
                'Status',
                trade.status.toString().split('.').last.toUpperCase(),
              ),
              _buildDetailRow(
                'Profit/Loss',
                '${(trade.profit ?? 0) >= 0 ? '+' : ''}${(trade.profit ?? 0).toStringAsFixed(2)}',
              ),
              _buildDetailRow(
                'Profit %',
                '${(trade.profitPercentage ?? 0) >= 0 ? '+' : ''}${(trade.profitPercentage ?? 0).toStringAsFixed(2)}%',
              ),
            ],
          ),
        ),
        actions: [
          if (trade.status == TradeStatus.open)
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                _showClosePriceDialog(context, trade, tradingService);
              },
              child: const Text('Close Trade'),
            ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showClosePriceDialog(BuildContext context, Trade trade, TradingService tradingService) {
    final closingPriceController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Close Trade'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Symbol: ${trade.symbol}'),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: closingPriceController,
              decoration: const InputDecoration(labelText: 'Closing Price'),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              final closingPrice = double.tryParse(closingPriceController.text) ?? 0;
              bool success = await tradingService.closeTrade(trade.id, closingPrice);

              if (mounted) {
                Navigator.pop(context);
                if (success) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Trade closed successfully')),
                  );
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(tradingService.errorMessage ?? 'Error closing trade'),
                    ),
                  );
                }
              }
            },
            child: const Text('Close Trade'),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(value),
        ],
      ),
    );
  }
}
