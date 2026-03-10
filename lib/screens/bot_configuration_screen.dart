import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/environment_config.dart';
import '../services/broker_credentials_service.dart';
import '../services/commission_service.dart';
import 'bot_dashboard_screen.dart';
import 'broker_integration_screen.dart';

class BotConfigurationScreen extends StatefulWidget {
  const BotConfigurationScreen({Key? key}) : super(key: key);

  @override
  State<BotConfigurationScreen> createState() => _BotConfigurationScreenState();
}

class _BotConfigurationScreenState extends State<BotConfigurationScreen> {
  late TextEditingController _botIdController;
  late TextEditingController _riskPerTradeController;
  late TextEditingController _maxDailyLossController;
  
  String _selectedStrategy = 'Trend Following';
  List<String> _selectedSymbols = [];
  bool _isCreating = false;
  bool _isLoadingData = true;
  String? _successMessage;
  String? _errorMessage;
  
  // NEW: Broker integration
  late BrokerCredentialsService _brokerService;
  late CommissionService _commissionService;
  
  Map<String, dynamic> commodityMarketData = {};

  final List<String> strategies = [
    'Trend Following',
    'Scalping',
    'Momentum Trading',
    'Mean Reversion',
    'Range Trading',
    'Breakout Trading',
  ];

  final List<Map<String, String>> tradingSymbols = [
    // Forex
    {'symbol': 'EURUSD', 'name': '💱 EURO/USD', 'category': 'Forex'},
    {'symbol': 'GBPUSD', 'name': '💷 GBP/USD', 'category': 'Forex'},
    {'symbol': 'USDJPY', 'name': '¥ USD/JPY', 'category': 'Forex'},
    {'symbol': 'AUDUSD', 'name': '🦘 AUD/USD', 'category': 'Forex'},
    {'symbol': 'NZDUSD', 'name': '🏔️ NZD/USD', 'category': 'Forex'},
    // Metals
    {'symbol': 'XAUUSD', 'name': '💎 GOLD - Per troy ounce', 'category': 'Metals'},
    {'symbol': 'XAGUSD', 'name': '⚪ SILVER - Per troy ounce', 'category': 'Metals'},
    {'symbol': 'XPTUSD', 'name': '💍 PLATINUM - Per troy ounce', 'category': 'Metals'},
    {'symbol': 'XPDUSD', 'name': '💎 PALLADIUM - Per troy ounce', 'category': 'Metals'},
    // Energy
    {'symbol': 'WTIUSD', 'name': '⚡ CRUDE OIL (WTI)', 'category': 'Energy'},
    {'symbol': 'BRENTUSD', 'name': '⚡ BRENT CRUDE', 'category': 'Energy'},
    {'symbol': 'NATGASUS', 'name': '🔥 NATURAL GAS', 'category': 'Energy'},
    // Agriculture
    {'symbol': 'CORNUSD', 'name': '🌽 CORN', 'category': 'Agriculture'},
    {'symbol': 'WHEATUSD', 'name': '🌾 WHEAT', 'category': 'Agriculture'},
    {'symbol': 'SOYBEANSUSD', 'name': '🫘 SOYBEANS', 'category': 'Agriculture'},
    {'symbol': 'COFFEEUSD', 'name': '☕ COFFEE', 'category': 'Agriculture'},
    {'symbol': 'COCOAUSD', 'name': '🍫 COCOA', 'category': 'Agriculture'},
    {'symbol': 'SUGARUSD', 'name': '🍬 SUGAR', 'category': 'Agriculture'},
    // Indices
    {'symbol': 'SPX500', 'name': '📈 S&P 500', 'category': 'Indices'},
    {'symbol': 'DAX40', 'name': '📊 DAX 40', 'category': 'Indices'},
    {'symbol': 'FTSE100', 'name': '📋 FTSE 100', 'category': 'Indices'},
    {'symbol': 'NIKKEI225', 'name': '🗾 NIKKEI 225', 'category': 'Indices'},
  ];

  @override
  void initState() {
    super.initState();
    _botIdController = TextEditingController(
      text: 'bot_${DateTime.now().millisecondsSinceEpoch}',
    );
    _riskPerTradeController = TextEditingController(text: '100');
    _maxDailyLossController = TextEditingController(text: '500');
    
    // Initialize services
    _brokerService = BrokerCredentialsService();
    _commissionService = CommissionService();
    
    _fetchCommodityData();
    _brokerService.fetchCredentials(); // Load broker credentials on startup
    _commissionService.fetchCommissions(); // Load commission data
  }

  Future<void> _fetchCommodityData() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/market/commodities'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final commodities = data['commodities'] as Map;
        
        setState(() {
          commodityMarketData = commodities.cast<String, dynamic>();
          _isLoadingData = false;
        });
      }
    } catch (e) {
      print('Error fetching commodity data: $e');
      // Use default market data if API fails
      setState(() => _isLoadingData = false);
    }
  }

  @override
  void dispose() {
    _botIdController.dispose();
    _riskPerTradeController.dispose();
    _maxDailyLossController.dispose();
    super.dispose();
  }

  Future<void> _createAndStartBot() async {
    // STEP 1: Check if broker is integrated
    if (!_brokerService.hasCredentials) {
      _showError('Please setup broker integration first!');
      
      // Show dialog with option to setup broker
      if (mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('⚠️ Broker Setup Required'),
            content: const Text(
              'You need to integrate your broker account before creating a bot. '
              'This ensures your bot can trade with verified credentials.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.pop(context);
                  // Navigate to broker integration screen
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => BrokerIntegrationScreen(
                        onBackPressed: () {
                          Navigator.pop(context);
                          // Refresh credentials after setup
                          _brokerService.fetchCredentials();
                        },
                      ),
                    ),
                  );
                },
                child: const Text('Setup Broker'),
              ),
            ],
          ),
        );
      }
      return;
    }

    if (_selectedSymbols.isEmpty) {
      _showError('Please select at least one trading symbol');
      return;
    }

    setState(() {
      _isCreating = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final sessionToken = prefs.getString('auth_token');
      
      if (sessionToken == null) {
        throw Exception('Session expired. Please login again.');
      }

      print('🤖 Creating bot with broker credential: ${_brokerService.activeCredential?.credentialId}');
      print('   Broker: ${_brokerService.activeCredential?.broker}');
      print('   Account: ${_brokerService.activeCredential?.accountNumber}');

      // STEP 2: Create bot with credential_id
      final createResponse = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/create'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({
          'botId': _botIdController.text,
          'credentialId': _brokerService.activeCredential!.credentialId, // ✅ Link to broker credential
          'symbols': _selectedSymbols,
          'strategy': _selectedStrategy,
          'riskPerTrade': double.parse(_riskPerTradeController.text),
          'maxDailyLoss': double.parse(_maxDailyLossController.text),
          'enabled': true,
        }),
      ).timeout(const Duration(seconds: 10));

      if (createResponse.statusCode != 200) {
        final errorData = jsonDecode(createResponse.body);
        throw Exception(errorData['error'] ?? 'Failed to create bot: ${createResponse.statusCode}');
      }

      print('✅ Bot created successfully');

      // STEP 3: Start bot
      final startResponse = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/start'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode({'botId': _botIdController.text}),
      ).timeout(const Duration(seconds: 10));

      if (startResponse.statusCode == 200) {
        final data = jsonDecode(startResponse.body);
        
        print('✅ Bot started, trades placed: ${data['tradesPlaced']}');
        print('💰 Commission tracking enabled for this bot');

        setState(() {
          _successMessage = 
            'Bot created and started! 🎉\n'
            'Broker: ${_brokerService.activeCredential?.broker}\n'
            'Account: ${_brokerService.activeCredential?.accountNumber}\n'
            'Trades placed: ${data['tradesPlaced']}\n\n'
            '💰 Commissions will be tracked on every trade.\n'
            '📊 Earnings appear in your Commission Dashboard.';
          _isCreating = false;
        });
        
        // Refresh commission data
        _commissionService.fetchCommissions();
        
        // Auto-navigate to dashboard after 3 seconds
        Future.delayed(const Duration(seconds: 3), () {
          if (mounted) {
            Navigator.of(context).pushAndRemoveUntil(
              MaterialPageRoute(builder: (context) => const BotDashboardScreen()),
              (route) => route.isFirst,
            );
          }
        });
      } else {
        final errorData = jsonDecode(startResponse.body);
        throw Exception(errorData['error'] ?? 'Failed to start bot: ${startResponse.statusCode}');
      }
    } catch (e) {
      _showError('Error: ${e.toString()}');
    } finally {
      setState(() => _isCreating = false);
    }
  }
      }
    } catch (e) {
      _showError('Error: ${e.toString()}');
    } finally {
      setState(() => _isCreating = false);
    }
  }

  void _resetForm() {
    _botIdController.text = 'bot_${DateTime.now().millisecondsSinceEpoch}';
    _riskPerTradeController.text = '100';
    _maxDailyLossController.text = '500';
    _selectedSymbols.clear();
    _selectedStrategy = 'Trend Following';
  }

  void _showError(String message) {
    setState(() => _errorMessage = message);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bot Configuration'),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
          TextButton.icon(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (context) => const BotDashboardScreen()),
              );
            },
            icon: const Icon(Icons.dashboard),
            label: const Text('Dashboard'),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Success Banner
            if (_successMessage != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.2),
                  border: Border.all(color: Colors.green),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle, color: Colors.green, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _successMessage!,
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 16),
                      onPressed: () =>
                          setState(() => _successMessage = null),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),

            // Error Banner
            if (_errorMessage != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.2),
                  border: Border.all(color: Colors.red),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error, color: Colors.red, size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 16),
                      onPressed: () =>
                          setState(() => _errorMessage = null),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 12),

          // Bot Rental Agreement Image
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.blue, width: 2),
              borderRadius: BorderRadius.circular(8),
              color: Colors.blue.withOpacity(0.05),
            ),
            child: Row(
              children: [
                Image.asset(
                  'assets/images/bot_rental.png',
                  height: 100,
                  width: 100,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      height: 100,
                      width: 100,
                      color: Colors.grey[800],
                      child: const Icon(Icons.image_not_supported, color: Colors.grey),
                    );
                  },
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Your Bot Rental Agreement',
                        style: TextStyle(  
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Configure your rental bot settings below',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[400],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Bot Configuration Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Bot Configuration',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),

                  // Bot ID and Strategy (Side by Side)
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _botIdController,
                          decoration: InputDecoration(
                            labelText: 'Bot ID',
                            hintText: 'bot_trend_1',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: _selectedStrategy,
                          decoration: InputDecoration(
                            labelText: 'Strategy',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                          items: strategies.map((strategy) {
                            return DropdownMenuItem(
                              value: strategy,
                              child: Text(strategy),
                            );
                          }).toList(),
                          onChanged: (value) {
                            if (value != null) {
                              setState(() => _selectedStrategy = value);
                            }
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Trading Symbols Selection
                  Text(
                    'Select Trading Symbols (${_selectedSymbols.length})',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 8),
                  Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.grey),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(8),
                      child: _isLoadingData
                          ? const Center(
                              child: CircularProgressIndicator(),
                            )
                          : SizedBox(
                              height: 350,
                              child: ListView.builder(
                                itemCount: tradingSymbols.length,
                                itemBuilder: (context, index) {
                                  final symbol = tradingSymbols[index];
                                  final symbolCode = symbol['symbol']!;
                                  
                                  // Map symbol code to commodity market data key
                                  String marketDataKey = symbolCode;
                                  if (symbolCode == 'XAUUSD') marketDataKey = 'GOLD';
                                  if (symbolCode == 'XAGUSD') marketDataKey = 'SILVER';
                                  if (symbolCode == 'XPTUSD') marketDataKey = 'PLATINUM';
                                  if (symbolCode == 'XPDUSD') marketDataKey = 'PALLADIUM';
                                  if (symbolCode == 'WTIUSD') marketDataKey = 'CRUDE_OIL';
                                  if (symbolCode == 'NATGASUS') marketDataKey = 'NATURAL_GAS';
                                  if (symbolCode == 'COFFEEUSD') marketDataKey = 'COFFEE';
                                  if (symbolCode == 'COCOAUSD') marketDataKey = 'COCOA';
                                  if (symbolCode == 'SUGARUSD') marketDataKey = 'SUGAR';
                                  if (symbolCode == 'WHEATUSD') marketDataKey = 'WHEAT';
                                  if (symbolCode == 'CORNUSD') marketDataKey = 'CORN';
                                  if (symbolCode == 'SOYBEANSUSD') marketDataKey = 'SOYBEAN';
                                  if (symbolCode == 'DAX40') marketDataKey = 'DAX';
                                  if (symbolCode == 'FTSE100') marketDataKey = 'FTSE';
                                  if (symbolCode == 'SPX500') marketDataKey = 'SPX500';
                                  if (symbolCode == 'NIKKEI225') marketDataKey = 'NIKKEI';
                                  
                                  final marketData = commodityMarketData[marketDataKey] ?? {};
                                  final trend = marketData['trend'] ?? 'NEUTRAL';
                                  final isBullish = trend == 'UP';
                                  final change = (marketData['change'] ?? 0).toDouble();
                                  final signal = marketData['signal'] ?? '🟡 NEUTRAL';
                                  final recommendation = marketData['recommendation'] ?? 'No data available';
                                  final volatility = marketData['volatility'] ?? 'Unknown';

                                  return Container(
                                    margin: const EdgeInsets.only(bottom: 8),
                                    decoration: BoxDecoration(
                                      border: Border.all(
                                        color: isBullish
                                            ? Colors.green.withOpacity(0.3)
                                            : Colors.red.withOpacity(0.3),
                                      ),
                                      borderRadius: BorderRadius.circular(8),
                                      color: isBullish
                                          ? Colors.green.withOpacity(0.05)
                                          : Colors.red.withOpacity(0.05),
                                    ),
                                    child: CheckboxListTile(
                                      value: _selectedSymbols.contains(symbolCode),
                                      onChanged: (value) {
                                        setState(() {
                                          if (value ?? false) {
                                            _selectedSymbols.add(symbolCode);
                                          } else {
                                            _selectedSymbols.remove(symbolCode);
                                          }
                                        });
                                      },
                                      title: Row(
                                        children: [
                                          Expanded(
                                            child: Text(symbol['name']!),
                                          ),
                                          Container(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 8,
                                              vertical: 4,
                                            ),
                                            decoration: BoxDecoration(
                                              color: isBullish
                                                  ? Colors.green.withOpacity(0.2)
                                                  : Colors.red.withOpacity(0.2),
                                              border: Border.all(
                                                color: isBullish
                                                    ? Colors.green
                                                    : Colors.red,
                                              ),
                                              borderRadius:
                                                  BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              signal,
                                              style: TextStyle(
                                                color: isBullish
                                                    ? Colors.green
                                                    : Colors.red,
                                                fontSize: 11,
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      subtitle: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Text(
                                                symbol['category']!,
                                                style: const TextStyle(fontSize: 11),
                                              ),
                                              const SizedBox(width: 8),
                                              Text(
                                                '${change > 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                                                style: TextStyle(
                                                  color: change >= 0
                                                      ? Colors.green
                                                      : Colors.red,
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 11,
                                                ),
                                              ),
                                              const SizedBox(width: 8),
                                              Container(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                      horizontal: 6,
                                                      vertical: 2,
                                                    ),
                                                decoration: BoxDecoration(
                                                  color: volatility == 'Low'
                                                      ? Colors.blue
                                                          .withOpacity(0.2)
                                                      : volatility == 'High'
                                                          ? Colors.orange
                                                              .withOpacity(0.2)
                                                          : Colors.grey
                                                              .withOpacity(0.2),
                                                  borderRadius:
                                                      BorderRadius.circular(3),
                                                ),
                                                child: Text(
                                                  volatility,
                                                  style: const TextStyle(
                                                    fontSize: 9,
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            '💡 $recommendation',
                                            style: TextStyle(
                                              fontSize: 10,
                                              color: Colors.grey[300],
                                              fontStyle: FontStyle.italic,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  );
                                },
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Risk Management
                  Text(
                    'Risk Management',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _riskPerTradeController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Risk Per Trade (\$)',
                      hintText: '100',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _maxDailyLossController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Max Daily Loss (\$)',
                      hintText: '500',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Create Bot Button
          Center(
            child: ElevatedButton.icon(
              onPressed: _isCreating ? null : _createAndStartBot,
              icon: _isCreating
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.play_circle),
              label: Text(_isCreating ? 'Creating Bot...' : 'Create & Start Bot'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                padding: const EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: 16,
                ),
              ),
            ),
          ),
        ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.grey[900],
        selectedItemColor: Colors.blue,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings),
            label: 'Config',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard),
            label: 'Dashboard',
          ),
        ],
        currentIndex: 1,
        onTap: (index) {
          if (index == 0) {
            Navigator.of(context).popUntil((route) => route.isFirst);
          } else if (index == 2) {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (context) => const BotDashboardScreen()),
            );
          }
        },
      ),
    );
  }
}
