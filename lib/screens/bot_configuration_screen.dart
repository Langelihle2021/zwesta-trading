import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/environment_config.dart';
import '../services/broker_credentials_service.dart';
import '../services/commission_service.dart';
import '../services/fund_service.dart';
import 'bot_dashboard_screen.dart';
import 'broker_integration_screen.dart';

class BotConfigurationScreen extends StatefulWidget {
  const BotConfigurationScreen({Key? key}) : super(key: key);

  @override
  State<BotConfigurationScreen> createState() => _BotConfigurationScreenState();
}

class _BotConfigurationScreenState extends State<BotConfigurationScreen> {
    // Dialog to input account number
    Future<String?> _showAccountInputDialog(BuildContext context) async {
      String? account;
      await showDialog(
        context: context,
        builder: (context) {
          return AlertDialog(
            title: const Text('Enter Destination Account'),
            content: TextField(
              decoration: const InputDecoration(hintText: 'Account Number'),
              onChanged: (value) => account = value,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('OK'),
              ),
            ],
          );
        },
      );
      return account;
    }

    // Dialog to input amount
    Future<double?> _showAmountInputDialog(BuildContext context, {String title = 'Enter Amount'}) async {
      String? amountStr;
      await showDialog(
        context: context,
        builder: (context) {
          return AlertDialog(
            title: Text(title),
            content: TextField(
              decoration: const InputDecoration(hintText: 'Amount'),
              keyboardType: TextInputType.number,
              onChanged: (value) => amountStr = value,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('OK'),
              ),
            ],
          );
        },
      );
      if (amountStr == null) return null;
      final amount = double.tryParse(amountStr!);
      return amount;
    }
  late TextEditingController _botIdController;
  late TextEditingController _riskPerTradeController;
  late TextEditingController _maxDailyLossController;
  late TextEditingController _profitLockController;
  late TextEditingController _drawdownPauseController;
  FundService _fundService = FundService();

  List<String> _allowedVolatility = ['Low', 'Medium'];

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
  List<Map<String, String>> tradingSymbols = [];  // Will be populated from API

  final List<String> strategies = [
    'Trend Following',
    'Scalping',
    'Momentum Trading',
    'Mean Reversion',
    'Range Trading',
    'Breakout Trading',
  ];

  @override
  void initState() {
    super.initState();
    _botIdController = TextEditingController(
      text: 'bot_${DateTime.now().millisecondsSinceEpoch}',
    );
    _riskPerTradeController = TextEditingController(text: '100');
    _maxDailyLossController = TextEditingController(text: '500');
    _profitLockController = TextEditingController(text: '500');
    _drawdownPauseController = TextEditingController(text: '10');
    
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
        Uri.parse('${EnvironmentConfig.apiUrl}/api/commodities/list'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
                                                                                                                                                
        setState(() {
          // Get market data for signal display (flat dict: {EURUSD: {signal, trend, ...}, ...})
          final marketDataResponse = data['marketData'] ?? {};
          commodityMarketData = marketDataResponse.cast<String, dynamic>();
          
          // Get commodities list for symbol selection (nested by category)
          final commoditiesList = data['commodities'] as Map? ?? {};
          tradingSymbols = _buildSymbolsFromApiData(commoditiesList);
          _isLoadingData = false;
        });
      }
    } catch (e) {
      print('Error fetching commodity data: $e');
      // Use default market data if API fails
      setState(() => _isLoadingData = false);
    }
  }

  /// Convert API response format to UI format
  List<Map<String, String>> _buildSymbolsFromApiData(Map apiData) {
    List<Map<String, String>> symbols = [];
    
    final categoryEmojis = {
      'forex': '💱',
      'commodities': '⚡',
      'indices': '📊',
      'stocks': '📈',
    };
    
    apiData.forEach((category, items) {
      if (items is List) {
        String categoryName = category;
        // Convert snake_case to Title Case
        categoryName = category.split('_').map((w) => w[0].toUpperCase() + w.substring(1)).join(' ');
        
        final emoji = categoryEmojis[category] ?? '•';
        
        for (var item in items) {
          if (item is Map) {
            final symbol = item['symbol'] ?? '';
            final name = item['name'] ?? '';
            if (symbol.isNotEmpty && name.isNotEmpty) {
              symbols.add({
                'symbol': symbol,
                'name': '$emoji $name',
                'category': categoryName,
              });
            }
          }
        }
      }
    });
    
    return symbols;
  }

  @override
  void dispose() {
    _botIdController.dispose();
    _riskPerTradeController.dispose();
    _maxDailyLossController.dispose();
    _profitLockController.dispose();
    _drawdownPauseController.dispose();
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
          'profitLock': double.tryParse(_profitLockController.text) ?? 0.0,
          'drawdownPausePercent': double.tryParse(_drawdownPauseController.text) ?? 0.0,
          'allowedVolatility': _allowedVolatility,
          'enabled': true,
        }),
      ).timeout(const Duration(seconds: 10));

      if (createResponse.statusCode != 200 && createResponse.statusCode != 201) {
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

                  // Broker Information Section
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.green),
                      borderRadius: BorderRadius.circular(8),
                      color: Colors.green.withOpacity(0.05),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.account_balance, color: Colors.green, size: 24),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Connected Broker',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    _brokerService.activeCredential != null
                                        ? '${_brokerService.activeCredential!.broker} - Account #${_brokerService.activeCredential!.accountNumber}'
                                        : 'No broker connected',
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            ElevatedButton.icon(
                              onPressed: () {
                                Navigator.of(context).push(
                                  MaterialPageRoute(builder: (context) => const BrokerIntegrationScreen()),
                                ).then((_) {
                                  setState(() {
                                    _brokerService.fetchCredentials();
                                  });
                                });
                              },
                              icon: const Icon(Icons.edit, size: 18),
                              label: const Text('Change'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green.withOpacity(0.3),
                                foregroundColor: Colors.green,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        // Show list of saved credentials if multiple exist
                        if (_brokerService.credentials.length > 1)
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Divider(),
                              const SizedBox(height: 8),
                              const Text(
                                'Your Saved Credentials',
                                style: TextStyle(fontSize: 12, color: Colors.grey),
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: _brokerService.credentials.map((cred) {
                                  final isActive = cred.credentialId == _brokerService.activeCredential?.credentialId;
                                  return FilterChip(
                                    label: Text('${cred.broker} #${cred.accountNumber}'),
                                    selected: isActive,
                                    onSelected: (selected) {
                                      if (selected) {
                                        setState(() {
                                          _brokerService.setActiveCredential(cred);
                                        });
                                      }
                                    },
                                    backgroundColor: Colors.grey.withOpacity(0.2),
                                    selectedColor: Colors.green.withOpacity(0.3),
                                  );
                                }).toList(),
                              ),
                            ],
                          ),
                      ],
                    ),
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
                                  
                                  // Get market data for this symbol directly (API now uses correct keys)
                                  final marketData = commodityMarketData[symbolCode] ?? {};
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
                                          Flexible(
                                            child: Container(
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
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: TextStyle(
                                                  color: isBullish
                                                      ? Colors.green
                                                      : Colors.red,
                                                  fontSize: 11,
                                                  fontWeight: FontWeight.bold,
                                                ),
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      subtitle: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          SingleChildScrollView(
                                            scrollDirection: Axis.horizontal,
                                            child: Row(
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
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            '💡 $recommendation',
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
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
                      labelText: 'Risk Per Trade (4)',
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
                      labelText: 'Max Daily Loss (4)',
                      hintText: '500',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _profitLockController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Daily Profit Lock-In (4)',
                      hintText: '500',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _drawdownPauseController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Drawdown Pause (%)',
                      hintText: '10',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text('Allowed Volatility:', style: Theme.of(context).textTheme.bodyMedium),
                  Wrap(
                    spacing: 8,
                    children: ['Very Low', 'Low', 'Medium', 'High', 'Very High'].map((level) {
                      final selected = _allowedVolatility.contains(level);
                      return FilterChip(
                        label: Text(level),
                        selected: selected,
                        onSelected: (val) {
                          setState(() {
                            if (val) {
                              _allowedVolatility.add(level);
                            } else {
                              _allowedVolatility.remove(level);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // Create Bot Button
          Center(
            child: Column(
              children: [
                ElevatedButton.icon(
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
                const SizedBox(height: 16),
                // Fund Transfer Automation Button
                ElevatedButton.icon(
                  onPressed: () async {
                    final fromAccount = _brokerService.activeCredential?.accountNumber;
                    final toAccount = await _showAccountInputDialog(context);
                    final amount = await _showAmountInputDialog(context);
                    if (fromAccount != null && toAccount != null && amount != null) {
                      _triggerFundTransfer(fromAccount, toAccount, amount);
                    }
                  },
                  icon: const Icon(Icons.swap_horiz),
                  label: const Text('Automate Fund Transfer'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 32,
                      vertical: 16,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                // Commission Withdrawal Automation Button (auto-select IG/XM Global)
                ElevatedButton.icon(
                  onPressed: () async {
                    final amount = await _showAmountInputDialog(context, title: 'Commission Withdrawal Amount');
                    if (amount != null) {
                      // Auto-select IG or XM Global account
                      BrokerCredential? igXmAccount;
                      try {
                        igXmAccount = _brokerService.credentials.firstWhere(
                          (cred) => cred.broker.toLowerCase().contains('ig') || cred.broker.toLowerCase().contains('xm'),
                        );
                      } catch (_) {
                        igXmAccount = null;
                      }
                      if (igXmAccount == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('No IG or XM Global account found for withdrawal.')),
                        );
                        return;
                      }
                      // Optionally, trigger fund transfer to IG/XM account
                      final fromAccount = _brokerService.activeCredential?.accountNumber;
                      final toAccount = igXmAccount.accountNumber;
                      final fundSuccess = await _fundService.transferFunds(fromAccount ?? '', toAccount, amount);
                      if (fundSuccess) {
                        final success = await _commissionService.requestWithdrawal(amount);
                        if (success) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Commission withdrawal sent to IG/XM Global account!')),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(_commissionService.errorMessage ?? 'Withdrawal failed')),
                          );
                        }
                      } else {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(_fundService.errorMessage ?? 'Fund transfer to IG/XM failed')),
                        );
                      }
                    }
                  },
                  icon: const Icon(Icons.attach_money),
                  label: const Text('Automate Commission Withdrawal (IG/XM)'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 32,
                      vertical: 16,
                    ),
                  ),
                ),
              ],
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

  void _triggerFundTransfer(String fromAccount, String toAccount, double amount) async {
    bool success = await _fundService.transferFunds(fromAccount, toAccount, amount);
    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Funds transferred successfully!')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_fundService.errorMessage ?? 'Transfer failed')),
      );
    }
  }
}
