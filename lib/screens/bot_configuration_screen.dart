import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:provider/provider.dart';
import '../providers/currency_provider.dart';
import '../services/bot_service.dart';
import '../utils/environment_config.dart';
import '../services/broker_credentials_service.dart';
import '../services/commission_service.dart';
import '../services/fund_service.dart';
import '../widgets/logo_widget.dart';
import 'bot_dashboard_screen.dart';
import 'broker_integration_screen.dart';
import 'dashboard_screen.dart';

class BotConfigurationScreen extends StatefulWidget {
  const BotConfigurationScreen({Key? key}) : super(key: key);

  @override
  State<BotConfigurationScreen> createState() => _BotConfigurationScreenState();
}

class _BotConfigurationScreenState extends State<BotConfigurationScreen> {
  static const List<Map<String, String>> _binanceSymbols = [
    // --- Tier 1: Large Cap ---
    {'symbol': 'BTCUSDT',  'name': '₿ Bitcoin / Tether',     'category': 'Large Cap'},
    {'symbol': 'ETHUSDT',  'name': '◆ Ethereum / Tether',    'category': 'Large Cap'},
    {'symbol': 'BNBUSDT',  'name': '◈ BNB / Tether',         'category': 'Large Cap'},
    {'symbol': 'SOLUSDT',  'name': '◎ Solana / Tether',      'category': 'Large Cap'},
    {'symbol': 'XRPUSDT',  'name': '✕ XRP / Tether',         'category': 'Large Cap'},
    {'symbol': 'ADAUSDT',  'name': '◌ Cardano / Tether',     'category': 'Large Cap'},
    {'symbol': 'DOGEUSDT', 'name': '🐕 Dogecoin / Tether',   'category': 'Large Cap'},
    // --- Tier 2: High-Volume Altcoins ---
    {'symbol': 'AVAXUSDT', 'name': '▲ Avalanche / Tether',   'category': 'Altcoin'},
    {'symbol': 'MATICUSDT','name': '⬟ Polygon / Tether',     'category': 'Altcoin'},
    {'symbol': 'LINKUSDT', 'name': '⛓ Chainlink / Tether',   'category': 'Altcoin'},
    {'symbol': 'LTCUSDT',  'name': 'Ł Litecoin / Tether',    'category': 'Altcoin'},
    {'symbol': 'TRXUSDT',  'name': '△ TRON / Tether',        'category': 'Altcoin'},
    {'symbol': 'DOTUSDT',  'name': '● Polkadot / Tether',    'category': 'Altcoin'},
    {'symbol': 'ATOMUSDT', 'name': '⚛ Cosmos / Tether',      'category': 'Altcoin'},
    // --- Tier 3: DeFi & Layer-2 (high volatility) ---
    {'symbol': 'SHIBUSDT', 'name': '🦴 Shiba Inu / Tether',  'category': 'DeFi & L2'},
    {'symbol': 'UNIUSDT',  'name': '🦄 Uniswap / Tether',    'category': 'DeFi & L2'},
    {'symbol': 'NEARUSDT', 'name': '◎ NEAR Protocol / Tether','category': 'DeFi & L2'},
    {'symbol': 'ARBUSDT',  'name': '🔵 Arbitrum / Tether',   'category': 'DeFi & L2'},
    {'symbol': 'OPUSDT',   'name': '🔴 Optimism / Tether',   'category': 'DeFi & L2'},
    {'symbol': 'APTUSDT',  'name': '⚡ Aptos / Tether',       'category': 'DeFi & L2'},
    {'symbol': 'INJUSDT',  'name': '💉 Injective / Tether',  'category': 'DeFi & L2'},
    {'symbol': 'SUIUSDT',  'name': '💧 Sui / Tether',        'category': 'DeFi & L2'},
    {'symbol': 'FTMUSDT',  'name': '👻 Fantom / Tether',     'category': 'DeFi & L2'},
    {'symbol': 'AAVEUSDT', 'name': '👻 Aave / Tether',       'category': 'DeFi & L2'},
    // --- Tier 4: Gaming / Metaverse / Cross-chain ---
    {'symbol': 'SANDUSDT', 'name': '🏖 The Sandbox / Tether','category': 'Gaming'},
    {'symbol': 'MANAUSDT', 'name': '🌐 Decentraland / Tether','category': 'Gaming'},
    {'symbol': 'RUNEUSDT', 'name': '⚗️ THORChain / Tether',  'category': 'Gaming'},
    {'symbol': 'ALGOUSDT', 'name': '◈ Algorand / Tether',   'category': 'Gaming'},
  ];

  static const Map<String, Map<String, dynamic>> _binancePairAnalytics = {
    'BTCUSDT': {'edgePct': 6.8, 'winRate': 63.0, 'liquidityScore': 98.0, 'risk': 'Low', 'analysis': 'Momentum leader'},
    'ETHUSDT': {'edgePct': 6.2, 'winRate': 61.0, 'liquidityScore': 95.0, 'risk': 'Low', 'analysis': 'Trend continuation'},
    'BNBUSDT': {'edgePct': 5.3, 'winRate': 58.0, 'liquidityScore': 90.0, 'risk': 'Medium', 'analysis': 'Exchange beta'},
    'SOLUSDT': {'edgePct': 7.4, 'winRate': 59.0, 'liquidityScore': 88.0, 'risk': 'Medium', 'analysis': 'High momentum'},
    'XRPUSDT': {'edgePct': 5.6, 'winRate': 57.0, 'liquidityScore': 89.0, 'risk': 'Medium', 'analysis': 'Range breakout'},
    'ADAUSDT': {'edgePct': 5.1, 'winRate': 56.0, 'liquidityScore': 84.0, 'risk': 'Medium', 'analysis': 'Mean reversion'},
    'DOGEUSDT': {'edgePct': 6.5, 'winRate': 54.0, 'liquidityScore': 86.0, 'risk': 'High', 'analysis': 'Volatility spikes'},
    'AVAXUSDT': {'edgePct': 6.1, 'winRate': 55.0, 'liquidityScore': 80.0, 'risk': 'High', 'analysis': 'Momentum bursts'},
    'MATICUSDT': {'edgePct': 5.4, 'winRate': 55.0, 'liquidityScore': 79.0, 'risk': 'Medium', 'analysis': 'Swing setup'},
    'LINKUSDT': {'edgePct': 5.8, 'winRate': 57.0, 'liquidityScore': 82.0, 'risk': 'Medium', 'analysis': 'Trend strength'},
    'LTCUSDT': {'edgePct': 4.8, 'winRate': 54.0, 'liquidityScore': 76.0, 'risk': 'Medium', 'analysis': 'Lower beta'},
    'TRXUSDT': {'edgePct': 4.3, 'winRate': 56.0, 'liquidityScore': 74.0, 'risk': 'Low', 'analysis': 'Stable mover'},
    'DOTUSDT': {'edgePct': 5.0, 'winRate': 55.0, 'liquidityScore': 75.0, 'risk': 'Medium', 'analysis': 'Trend rebound'},
    'ATOMUSDT': {'edgePct': 5.2, 'winRate': 54.0, 'liquidityScore': 73.0, 'risk': 'Medium', 'analysis': 'Range expansion'},
    'SHIBUSDT': {'edgePct': 7.0, 'winRate': 51.0, 'liquidityScore': 78.0, 'risk': 'High', 'analysis': 'Speculative bursts'},
    'UNIUSDT': {'edgePct': 5.7, 'winRate': 55.0, 'liquidityScore': 70.0, 'risk': 'High', 'analysis': 'DeFi momentum'},
    'NEARUSDT': {'edgePct': 6.0, 'winRate': 54.0, 'liquidityScore': 72.0, 'risk': 'High', 'analysis': 'Trend acceleration'},
    'ARBUSDT': {'edgePct': 6.4, 'winRate': 53.0, 'liquidityScore': 74.0, 'risk': 'High', 'analysis': 'L2 impulse'},
    'OPUSDT': {'edgePct': 6.3, 'winRate': 53.0, 'liquidityScore': 73.0, 'risk': 'High', 'analysis': 'L2 breakout'},
    'APTUSDT': {'edgePct': 6.7, 'winRate': 52.0, 'liquidityScore': 71.0, 'risk': 'High', 'analysis': 'High beta alpha'},
    'INJUSDT': {'edgePct': 7.8, 'winRate': 56.0, 'liquidityScore': 69.0, 'risk': 'High', 'analysis': 'Strong trend alpha'},
    'SUIUSDT': {'edgePct': 6.9, 'winRate': 53.0, 'liquidityScore': 68.0, 'risk': 'High', 'analysis': 'Volatility trend'},
    'FTMUSDT': {'edgePct': 6.5, 'winRate': 52.0, 'liquidityScore': 66.0, 'risk': 'High', 'analysis': 'Fast movers'},
    'AAVEUSDT': {'edgePct': 5.9, 'winRate': 54.0, 'liquidityScore': 67.0, 'risk': 'High', 'analysis': 'DeFi trend'},
    'SANDUSDT': {'edgePct': 5.6, 'winRate': 52.0, 'liquidityScore': 63.0, 'risk': 'High', 'analysis': 'Narrative spikes'},
    'MANAUSDT': {'edgePct': 5.4, 'winRate': 51.0, 'liquidityScore': 62.0, 'risk': 'High', 'analysis': 'Event-driven'},
    'RUNEUSDT': {'edgePct': 6.1, 'winRate': 53.0, 'liquidityScore': 65.0, 'risk': 'High', 'analysis': 'Cross-chain momentum'},
    'ALGOUSDT': {'edgePct': 4.9, 'winRate': 53.0, 'liquidityScore': 61.0, 'risk': 'Medium', 'analysis': 'Range rotations'},
  };

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
  late TextEditingController _investmentAmountController;
  FundService _fundService = FundService();

  List<String> _allowedVolatility = ['Low', 'Medium'];
  
  // ========== NEW: Automated Risk Management Settings ==========
  double _riskPercent = 2.0;          // Risk per trade as %
  int _maxOpenTrades = 3;             // Max simultaneous trades
  double _maxDrawdownPercent = 20.0;  // Max allowed drawdown %

  String _selectedStrategy = 'Trend Following';
  List<String> _selectedSymbols = [];
  bool _isCreating = false;
  bool _isLoadingData = true;
  String? _successMessage;
  String? _errorMessage;
  
  // Auto-Withdrawal Settings
  String _withdrawalMode = 'fixed'; // 'fixed' or 'intelligent'
  double _targetProfit = 300; // For fixed mode
  double _minProfit = 50; // For intelligent mode
  double _maxProfit = 500; // For intelligent mode
  double _winRateMin = 60; // For intelligent mode
  bool _enableAutoWithdrawal = false;
  
  // Currency & Settings
  String _currencyChoice = 'USD'; // 'USD' or 'ZAR' (Rand)
  
  // Broker integration
  late BrokerCredentialsService _brokerService;
  late CommissionService _commissionService;
  
  Map<String, dynamic> commodityMarketData = {};
  List<Map<String, String>> tradingSymbols = [];  // Will be populated from API

    String get _activeBrokerName =>
      _brokerService.activeCredential?.broker.toLowerCase().trim() ?? '';

    bool get _isBinanceBroker => _activeBrokerName == 'binance';

    String get _symbolSectionTitle =>
      _isBinanceBroker ? 'Select Binance Pairs' : 'Select Trading Symbols';

    String get _symbolSelectionError => _isBinanceBroker
      ? 'Please select at least one Binance pair'
      : 'Please select at least one trading symbol';

  List<Map<String, dynamic>> get _rankedBinancePairs {
    final ranked = _binanceSymbols.map((item) {
      final symbol = item['symbol']!;
      final insight = _binancePairAnalytics[symbol] ?? const {};
      final edge = (insight['edgePct'] as num?)?.toDouble() ?? 0.0;
      final winRate = (insight['winRate'] as num?)?.toDouble() ?? 0.0;
      final liquidity = (insight['liquidityScore'] as num?)?.toDouble() ?? 50.0;
      final score = (edge * 0.45) + (winRate * 0.35) + ((liquidity / 100) * 20);

      return {
        'symbol': symbol,
        'name': item['name']!,
        'category': item['category']!,
        'edgePct': edge,
        'winRate': winRate,
        'liquidityScore': liquidity,
        'risk': insight['risk'] ?? 'Medium',
        'analysis': insight['analysis'] ?? 'General trend',
        'score': score,
      };
    }).toList();

    ranked.sort((a, b) => (b['score'] as double).compareTo(a['score'] as double));
    return ranked;
  }

  void _applyBinancePreset(String preset) {
    if (!_isBinanceBroker) {
      return;
    }

    final ranked = _rankedBinancePairs;
    List<String> symbols;

    switch (preset) {
      case 'top_edge':
        symbols = ranked.take(5).map((item) => item['symbol'] as String).toList();
        break;
      case 'high_liquidity':
        symbols = ranked
            .where((item) => (item['liquidityScore'] as double) >= 85)
            .take(6)
            .map((item) => item['symbol'] as String)
            .toList();
        break;
      case 'balanced':
        symbols = ranked
            .where((item) => (item['risk'] == 'Low' || item['risk'] == 'Medium'))
            .take(6)
            .map((item) => item['symbol'] as String)
            .toList();
        break;
      case 'defi':
        symbols = _binanceSymbols
            .where((item) => item['category'] == 'DeFi & L2')
            .take(6)
            .map((item) => item['symbol']!)
            .toList();
        break;
      case 'clear':
        symbols = [];
        break;
      default:
        symbols = _selectedSymbols;
    }

    setState(() {
      _selectedSymbols = symbols;
    });
  }

  String _currencyCode(AppCurrency currency) {
    switch (currency) {
      case AppCurrency.usd:
        return 'USD';
      case AppCurrency.zar:
        return 'ZAR';
      case AppCurrency.gbp:
        return 'GBP';
    }
  }

  Widget _binanceQuickActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    Color? color,
  }) {
    final chipColor = color ?? const Color(0xFFF0B90B);
    return ActionChip(
      avatar: Icon(icon, size: 16, color: chipColor),
      label: Text(label),
      backgroundColor: chipColor.withOpacity(0.15),
      side: BorderSide(color: chipColor.withOpacity(0.4)),
      onPressed: onTap,
    );
  }

  Widget _buildBinanceSetupInsights() {
    final topPairs = _rankedBinancePairs.take(3).toList();
    final selectedInsights = _selectedSymbols
        .map((s) => _binancePairAnalytics[s])
        .where((v) => v != null)
        .cast<Map<String, dynamic>>()
        .toList();

    final avgEdge = selectedInsights.isEmpty
        ? 0.0
        : selectedInsights
                .map((i) => (i['edgePct'] as num?)?.toDouble() ?? 0.0)
                .reduce((a, b) => a + b) /
            selectedInsights.length;
    final avgWinRate = selectedInsights.isEmpty
        ? 0.0
        : selectedInsights
                .map((i) => (i['winRate'] as num?)?.toDouble() ?? 0.0)
                .reduce((a, b) => a + b) /
            selectedInsights.length;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF0B90B).withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFF0B90B).withOpacity(0.45)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Binance Quick Actions',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _binanceQuickActionButton(
                icon: Icons.bolt,
                label: 'Top Edge',
                onTap: () => _applyBinancePreset('top_edge'),
              ),
              _binanceQuickActionButton(
                icon: Icons.water_drop,
                label: 'High Liquidity',
                onTap: () => _applyBinancePreset('high_liquidity'),
              ),
              _binanceQuickActionButton(
                icon: Icons.balance,
                label: 'Balanced 6',
                onTap: () => _applyBinancePreset('balanced'),
              ),
              _binanceQuickActionButton(
                icon: Icons.auto_graph,
                label: 'DeFi Aggressive',
                onTap: () => _applyBinancePreset('defi'),
                color: Colors.deepPurpleAccent,
              ),
              _binanceQuickActionButton(
                icon: Icons.clear,
                label: 'Clear',
                onTap: () => _applyBinancePreset('clear'),
                color: Colors.redAccent,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            selectedInsights.isEmpty
                ? 'Select pairs to see estimated performance profile.'
                : 'Selected basket est. edge ${avgEdge.toStringAsFixed(1)}% | est. win rate ${avgWinRate.toStringAsFixed(1)}%',
            style: TextStyle(color: Colors.grey[300], fontSize: 11),
          ),
          const SizedBox(height: 8),
          const Text(
            'Most Lucrative Pairs (Model Ranking)',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
          ...topPairs.asMap().entries.map((entry) {
            final rank = entry.key + 1;
            final pair = entry.value;
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '$rank. ${pair['symbol']}  | Edge ${((pair['edgePct'] as double)).toStringAsFixed(1)}% | Win ${((pair['winRate'] as double)).toStringAsFixed(0)}% | ${pair['analysis']}',
                style: TextStyle(color: Colors.grey[200], fontSize: 11),
              ),
            );
          }),
        ],
      ),
    );
  }

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
    _investmentAmountController = TextEditingController(text: '1000');
    
    // Initialize services
    _brokerService = BrokerCredentialsService();
    _commissionService = CommissionService();
    
    _initializeScreen();
    _commissionService.fetchCommissions();
    _loadRiskSettings();  // Load automation risk settings from API
  }

  Future<void> _initializeScreen() async {
    await _brokerService.fetchCredentials();
    if (!mounted) {
      return;
    }
    _fetchTradingData();
  }

  Future<void> _fetchTradingData() async {
    if (_isBinanceBroker) {
      setState(() {
        commodityMarketData = {};
        tradingSymbols = List<Map<String, String>>.from(_binanceSymbols);
        _selectedSymbols = _selectedSymbols
            .where((symbol) => _binanceSymbols.any((item) => item['symbol'] == symbol))
            .toList();
        _isLoadingData = false;
      });
      return;
    }

    await _fetchCommodityData();
  }

  Future<void> _fetchCommodityData() async {
    setState(() => _isLoadingData = true);
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
    _investmentAmountController.dispose();
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
      _showError(_symbolSelectionError);
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

      // 🔴 FIX: Null-safe credential verification
      final credential = _brokerService.activeCredential;
      if (credential == null) {
        throw Exception('Broker credential lost. Please setup broker integration again.');
      }

      print('🤖 Creating bot with broker credential: ${credential.credentialId}');
      print('   Broker: ${credential.broker}');
      print('   Account: ${credential.accountNumber}');

      // STEP 2: Create bot with credential_id
      final botPayload = {
        'botId': _botIdController.text,
        'credentialId': credential.credentialId, // ✅ Safe null-checked credential reference
        'symbols': _selectedSymbols,
        'strategy': _selectedStrategy,
        'riskPercent': _riskPercent,               // ✅ NEW: Automated risk %
        'maxOpenTrades': _maxOpenTrades,           // ✅ NEW: Max open trades
        'maxDrawdownPercent': _maxDrawdownPercent, // ✅ NEW: Max drawdown %
        'displayCurrency': _currencyCode(context.read<CurrencyProvider>().currency),
        'allowedVolatility': _allowedVolatility,
        'enabled': true,
        'autoWithdrawal': _enableAutoWithdrawal ? {
          'enabled': true,
          'withdrawalMode': _withdrawalMode,
          if (_withdrawalMode == 'fixed') 'targetProfit': _targetProfit,
          if (_withdrawalMode == 'intelligent') 'minProfit': _minProfit,
          if (_withdrawalMode == 'intelligent') 'maxProfit': _maxProfit,
          if (_withdrawalMode == 'intelligent') 'winRateMin': _winRateMin,
        } : {
          'enabled': false,
        },
      };
      
      final createResponse = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/bot/create'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken,
        },
        body: jsonEncode(botPayload),
      ).timeout(const Duration(seconds: 30));

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
      ).timeout(const Duration(seconds: 30));

      if (startResponse.statusCode == 200) {
        final data = jsonDecode(startResponse.body);
        print('✅ Bot started, trades placed: ${data['tradesPlaced']}');
        print('💰 Commission tracking enabled for this bot');

        // 🔴 FIX: Null-safe credential display in success message
        final credential = _brokerService.activeCredential;
        final brokerName = credential?.broker ?? 'Unknown';
        final accountNum = credential?.accountNumber ?? 'N/A';
        
        setState(() {
          _successMessage =
              'Bot created and started! 🎉\n'
              'Broker: $brokerName\n'
              'Account: $accountNum\n'
              '${_isBinanceBroker ? 'Pairs' : 'Symbols'}: ${_selectedSymbols.join(', ')}\n'
              'Trades placed: ${data['tradesPlaced']}\n\n'
              '💰 Commissions will be tracked on every trade.\n'
              '📊 Earnings appear in your Commission Dashboard.';
          _isCreating = false;
        });

        // Refresh commission data
        _commissionService.fetchCommissions();

        // Force-refresh bot list before navigating
        final botService = Provider.of<BotService>(context, listen: false);
        await botService.fetchActiveBots();

        // Show success snackbar immediately
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('✅ Bot "${_botIdController.text}" created and running! It will appear in the list below.'),
              backgroundColor: Colors.green,
              duration: const Duration(seconds: 2),
            ),
          );
        }

        // Navigate to dashboard immediately after refresh
        if (mounted) {
          Navigator.of(context).popUntil((route) => route.isFirst);
          Navigator.of(context).push(
            MaterialPageRoute(builder: (context) => const DashboardScreen()),
          );
        }
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

  void _showError(String message) {
    setState(() => _errorMessage = message);
  }

  // ========== AUTOMATED RISK MANAGEMENT METHODS ==========
  
  /// Load risk settings from backend API
  Future<void> _loadRiskSettings() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/risk-settings/get'),
        headers: {'Cookie': 'session=${await _getSessionId()}'},
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final settings = data['settings'] ?? {};
        setState(() {
          _riskPercent = (settings['risk_percent'] ?? 2.0).toDouble();
          _maxOpenTrades = (settings['max_open_trades'] ?? 3) as int;
          _maxDrawdownPercent = (settings['max_drawdown_percent'] ?? 20.0).toDouble();
        });
      }
    } catch (e) {
      print('Error loading risk settings: $e');
    }
  }

  /// Save risk settings to backend API
  Future<void> _saveRiskSettings() async {
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/risk-settings/save'),
        headers: {
          'Content-Type': 'application/json',
          'Cookie': 'session=${await _getSessionId()}',
        },
        body: jsonEncode({
          'risk_percent': _riskPercent,
          'max_open_trades': _maxOpenTrades,
          'max_drawdown_percent': _maxDrawdownPercent,
        }),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Risk settings saved! Bot will use automatic lot sizing.'),
            duration: Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('❌ Error saving risk settings: $e'),
          duration: const Duration(seconds: 3),
        ),
      );
    }
  }

  /// Get session ID from SharedPreferences
  Future<String> _getSessionId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('session_id') ?? '';
  }

  @override
  Widget build(BuildContext context) {
    final currencyProvider = context.watch<CurrencyProvider>();

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const LogoWidget(size: 40, showText: false),
            const SizedBox(width: 12),
            const Expanded(
              child: Text('Bot Configuration'),
            ),
          ],
        ),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<AppCurrency>(
                value: currencyProvider.currency,
                dropdownColor: Colors.grey[900],
                icon: const Icon(Icons.currency_exchange, color: Colors.white),
                style: const TextStyle(color: Colors.white),
                items: AppCurrency.values.map((currency) {
                  return DropdownMenuItem<AppCurrency>(
                    value: currency,
                    child: Text(_currencyCode(currency), style: const TextStyle(color: Colors.white)),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) {
                    currencyProvider.setCurrency(value);
                  }
                },
              ),
            ),
          ),
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
                    '$_symbolSectionTitle (${_selectedSymbols.length})',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  if (_brokerService.activeCredential != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Broker account: ${_brokerService.activeCredential!.broker} • ${_brokerService.activeCredential!.accountNumber}',
                      style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                    ),
                  ],
                  if (_isBinanceBroker) ...[
                    const SizedBox(height: 10),
                    _buildBinanceSetupInsights(),
                  ],
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
                                    final isBinanceSymbol = _isBinanceBroker;
                                  
                                  // Get market data for this symbol directly (API now uses correct keys)
                                  final marketData = commodityMarketData[symbolCode] ?? {};
                                  final binanceData = _binancePairAnalytics[symbolCode] ?? const {};
                                  final trend = marketData['trend'] ?? 'NEUTRAL';
                                    final isBullish = isBinanceSymbol ? true : trend == 'UP';
                                  final change = (marketData['change'] ?? 0).toDouble();
                                    final edgePct = (binanceData['edgePct'] as num?)?.toDouble() ?? 0.0;
                                    final winRate = (binanceData['winRate'] as num?)?.toDouble() ?? 0.0;
                                    final signal = isBinanceSymbol
                                      ? 'EDGE ${edgePct.toStringAsFixed(1)}%'
                                      : (marketData['signal'] ?? '🟡 NEUTRAL');
                                    final recommendation = isBinanceSymbol
                                      ? '${binanceData['analysis'] ?? 'Selected Binance pair will follow your strategy.'} | Est. win rate ${winRate.toStringAsFixed(0)}%'
                                      : (marketData['recommendation'] ?? 'No data available');
                                    final volatility = isBinanceSymbol
                                      ? '${binanceData['risk'] ?? 'Medium'} risk'
                                      : (marketData['volatility'] ?? 'Unknown');

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
                                                  isBinanceSymbol
                                                      ? '${edgePct.toStringAsFixed(1)}% edge • ${winRate.toStringAsFixed(0)}% win'
                                                      : '${change > 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
                                                  style: TextStyle(
                                                    color: isBinanceSymbol
                                                        ? Colors.orangeAccent
                                                        : change >= 0
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

                  // Currency Selection
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.1),
                      border: Border.all(color: Colors.blue.withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Transaction Currency',
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: Colors.blue[200],
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: ChoiceChip(
                                label: const Text('\$ USD'),
                                selected: _currencyChoice == 'USD',
                                onSelected: (_) => setState(() => _currencyChoice = 'USD'),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: ChoiceChip(
                                label: const Text('R ZAR (Rand)'),
                                selected: _currencyChoice == 'ZAR',
                                onSelected: (_) => setState(() => _currencyChoice = 'ZAR'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Settings Mode Selection
                  const SizedBox(height: 16),

                  // ========== AUTOMATED RISK MANAGEMENT SETTINGS ==========
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.green.withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(12),
                      color: Colors.green.withOpacity(0.05),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.security, color: Colors.green, size: 24),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Automated Risk Management',
                                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                      color: Colors.green,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Bot automatically calculates lot sizes, SL/TP levels, and enforces trading limits',
                                    style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Risk % Slider
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '💰 Risk Per Trade',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: Colors.green.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    '${_riskPercent.toStringAsFixed(2)}%',
                                    style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.green),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Slider(
                              value: _riskPercent,
                              min: 0.1,
                              max: 10.0,
                              divisions: 99,
                              onChanged: (value) => setState(() => _riskPercent = value),
                              label: '${_riskPercent.toStringAsFixed(2)}%',
                            ),
                            Text(
                              'Amount risked per trade relative to account balance. Conservative: 1-2%, Moderate: 2-3%, Aggressive: 3-5%',
                              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Max Open Trades Slider
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '📊 Max Open Trades',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    '$_maxOpenTrades trades',
                                    style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.blue),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Slider(
                              value: _maxOpenTrades.toDouble(),
                              min: 1,
                              max: 20,
                              divisions: 19,
                              onChanged: (value) => setState(() => _maxOpenTrades = value.toInt()),
                              label: '$_maxOpenTrades',
                            ),
                            Text(
                              'Limits total simultaneous positions. Lower = less risk, Higher = more diversification. Recommended: 2-3',
                              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Max Drawdown Slider
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '📉 Max Drawdown',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: Colors.purple.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    '${_maxDrawdownPercent.toStringAsFixed(1)}%',
                                    style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.purple),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Slider(
                              value: _maxDrawdownPercent,
                              min: 5,
                              max: 50,
                              divisions: 45,
                              onChanged: (value) => setState(() => _maxDrawdownPercent = value),
                              label: '${_maxDrawdownPercent.toStringAsFixed(1)}%',
                            ),
                            Text(
                              'Trading pauses when account loses this %. Allows system recovery before resuming. Recommended: 15-20%',
                              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        
                        // Save Settings Button
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveRiskSettings,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Risk Settings'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.blue.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: Colors.blue.withOpacity(0.3)),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.info, color: Colors.blue, size: 18),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  'These settings are used for automatic lot sizing. No manual position entry needed!',
                                  style: TextStyle(fontSize: 11, color: Colors.blue[200]),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  
                  // Auto-Withdrawal Settings
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.orange.withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(8),
                      color: Colors.orange.withOpacity(0.05),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.savings, color: Colors.orange, size: 24),
                            const SizedBox(width: 12),
                            Text(
                              'Auto-Withdrawal to USDT',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: Colors.orange,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        
                        // Enable/Disable Toggle
                        SwitchListTile(
                          value: _enableAutoWithdrawal,
                          onChanged: (value) {
                            setState(() => _enableAutoWithdrawal = value);
                          },
                          title: const Text('Enable Auto-Withdrawal'),
                          subtitle: Text(
                            _enableAutoWithdrawal
                                ? 'Profits will be withdrawn to your USDT wallet automatically'
                                : 'Disable to keep profits in trading account',
                            style: const TextStyle(fontSize: 12),
                          ),
                          contentPadding: EdgeInsets.zero,
                        ),
                        
                        if (_enableAutoWithdrawal) ...[
                          const SizedBox(height: 16),
                          Text(
                            'Choose Withdrawal Trigger Mode',
                            style: Theme.of(context).textTheme.bodyMedium,
                          ),
                          const SizedBox(height: 12),
                          
                          // Fixed Mode Option
                          Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: _withdrawalMode == 'fixed'
                                    ? Colors.green
                                    : Colors.grey.withOpacity(0.3),
                                width: 2,
                              ),
                              borderRadius: BorderRadius.circular(8),
                              color: _withdrawalMode == 'fixed'
                                  ? Colors.green.withOpacity(0.1)
                                  : Colors.transparent,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Radio<String>(
                                      value: 'fixed',
                                      groupValue: _withdrawalMode,
                                      onChanged: (value) {
                                        setState(() => _withdrawalMode = value ?? 'fixed');
                                      },
                                    ),
                                    const Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '💰 Fixed Mode',
                                            style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 14,
                                            ),
                                          ),
                                          SizedBox(height: 4),
                                          Text(
                                            'Withdraw when profit hits target amount',
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                                if (_withdrawalMode == 'fixed') ...[
                                  const SizedBox(height: 12),
                                  TextField(
                                    keyboardType: TextInputType.number,
                                    decoration: InputDecoration(
                                      labelText: 'Target Profit (\$)',
                                      hintText: '300',
                                      border: OutlineInputBorder(
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      prefixIcon: const Icon(Icons.attach_money),
                                    ),
                                    onChanged: (value) {
                                      setState(() {
                                        _targetProfit = double.tryParse(value) ?? 300;
                                      });
                                    },
                                  ),
                                ],
                              ],
                            ),
                          ),
                          
                          // Intelligent Mode Option
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: _withdrawalMode == 'intelligent'
                                    ? Colors.purple
                                    : Colors.grey.withOpacity(0.3),
                                width: 2,
                              ),
                              borderRadius: BorderRadius.circular(8),
                              color: _withdrawalMode == 'intelligent'
                                  ? Colors.purple.withOpacity(0.1)
                                  : Colors.transparent,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Radio<String>(
                                      value: 'intelligent',
                                      groupValue: _withdrawalMode,
                                      onChanged: (value) {
                                        setState(() => _withdrawalMode = value ?? 'fixed');
                                      },
                                    ),
                                    const Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '🧠 Intelligent Mode',
                                            style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              fontSize: 14,
                                            ),
                                          ),
                                          SizedBox(height: 4),
                                          Text(
                                            'Bot withdraws based on market conditions',
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                                if (_withdrawalMode == 'intelligent') ...[
                                  const SizedBox(height: 12),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: TextField(
                                          keyboardType: TextInputType.number,
                                          decoration: InputDecoration(
                                            labelText: 'Min (\$)',
                                            hintText: '50',
                                            border: OutlineInputBorder(
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                          ),
                                          onChanged: (value) {
                                            setState(() {
                                              _minProfit = double.tryParse(value) ?? 50;
                                            });
                                          },
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Expanded(
                                        child: TextField(
                                          keyboardType: TextInputType.number,
                                          decoration: InputDecoration(
                                            labelText: 'Max (\$)',
                                            hintText: '500',
                                            border: OutlineInputBorder(
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                          ),
                                          onChanged: (value) {
                                            setState(() {
                                              _maxProfit = double.tryParse(value) ?? 500;
                                            });
                                          },
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 12),
                                  TextField(
                                    keyboardType: TextInputType.number,
                                    decoration: InputDecoration(
                                      labelText: 'Min Win Rate (%)',
                                      hintText: '60',
                                      border: OutlineInputBorder(
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      helperText: 'Only withdraw when win rate ≥ this %',
                                    ),
                                    onChanged: (value) {
                                      setState(() {
                                        _winRateMin = double.tryParse(value) ?? 60;
                                      });
                                    },
                                  ),
                                ],
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.blue.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: Colors.blue.withOpacity(0.3)),
                            ),
                            child: const Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '📝 Next Step:',
                                  style: TextStyle(fontWeight: FontWeight.bold),
                                ),
                                SizedBox(height: 8),
                                Text(
                                  'After creating the bot, provide your USDT wallet address and choose your network (Polygon recommended)',
                                  style: TextStyle(fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
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
                // Commission Withdrawal Automation Button (auto-select XM Global)
                ElevatedButton.icon(
                  onPressed: () async {
                    final amount = await _showAmountInputDialog(context, title: 'Commission Withdrawal Amount');
                    if (amount != null) {
                      // Auto-select XM Global account for withdrawal
                      BrokerCredential? xmAccount;
                      try {
                        xmAccount = _brokerService.credentials.firstWhere(
                          (cred) => cred.broker.toLowerCase().contains('xm'),
                        );
                      } catch (_) {
                        xmAccount = null;
                      }
                      if (xmAccount == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('No XM Global account found for withdrawal.')),
                        );
                        return;
                      }
                      // Trigger fund transfer to XM account
                      final fromAccount = _brokerService.activeCredential?.accountNumber;
                      final toAccount = xmAccount.accountNumber;
                      final fundSuccess = await _fundService.transferFunds(fromAccount ?? '', toAccount, amount);
                      if (fundSuccess) {
                        final success = await _commissionService.requestWithdrawal(amount);
                        if (success) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Commission withdrawal sent to XM Global account!')),
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
