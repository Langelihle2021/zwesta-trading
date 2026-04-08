import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/broker_connection_model.dart';
import '../services/broker_connection_service.dart';
import '../services/broker_credentials_service.dart';
import '../services/trading_service.dart';
import '../utils/constants.dart';
import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';
import 'bot_configuration_screen.dart';
import 'bot_dashboard_screen.dart';
import 'broker_analytics_dashboard.dart';
import 'consolidated_reports_screen.dart';
import 'dashboard_screen.dart';

class BrokerIntegrationScreen extends StatefulWidget {

  const BrokerIntegrationScreen({
    Key? key,
    this.onBackPressed,
  }) : super(key: key);
  final VoidCallback? onBackPressed;

  @override
  State<BrokerIntegrationScreen> createState() =>
      _BrokerIntegrationScreenState();
}

class _BrokerIntegrationScreenState extends State<BrokerIntegrationScreen> {
  late TextEditingController _serverController;
  late TextEditingController _accountController;
  late TextEditingController _passwordController;
  late TextEditingController _apiKeyController;
  late TextEditingController _usernameController;
  String _selectedBroker = 'Exness';
  bool _showSuccess = false;
  bool _isTestingConnection = false;
  bool _isConnected = false;
  bool _autoReconnectEnabled = false;
  bool _isLiveMode = false;  // DEMO by default
  DateTime? _lastConnectionTime;
  double _accountBalance = 0;
  String _accountCurrency = 'USD';  // Actual currency of the connected account (USD, ZAR, etc.)
  List<BrokerAccount> _savedAccounts = [];
  BrokerAccount? _activeAccount;

  // ✅ ONLY INTEGRATED BROKERS - These are fully working and tested
  final List<String> brokers = [
    'Exness',      // ✅ Primary MT5 path with crypto support
    'Binance',     // ✅ Primary crypto spot trading path
    'PXBT',        // ✅ Prime XBT crypto trading
    'OANDA',       // ✅ REST API forex trading
   // FXCM support available but requires separate API key
  ];

  final Map<String, String> brokerServers = {
    'Binance': 'spot',
    'OANDA': 'REST-API',
    'Pepperstone': 'Pepperstone MT5 Live',
    'FxOpen': 'FxOpen-MT5',
    'Exness': 'Exness-MT5Trial9',
    'Darwinex': 'Darwinex MT5',
    'IC Markets': 'ICMarkets-MT5',
    'IG Markets': 'REST-API',
    'FXM': 'FXM-Live',
    'AvaTrade': 'Ava-Real',
    'FP Markets': 'FPMarkets-Live',
    'Zulu Trade (SA)': 'ZuluTrade ZA',
    'Ovex (SA)': 'Ovex SA',
    'PXBT': 'PXBTTrading-1',
    'Prime XBT': 'PXBTTrading-1',
    'Trade Nations': 'TradeNations-MT5',
    'MetaQuotes': 'MetaQuotes-MT5',
  };

  @override
  void initState() {
    super.initState();
    _serverController = TextEditingController();
    _accountController = TextEditingController();
    _passwordController = TextEditingController();
    _apiKeyController = TextEditingController();
    _usernameController = TextEditingController();
    _loadSavedCredentials();
    _loadSavedAccounts();
  }

  bool get _isIgBroker => _selectedBroker.toLowerCase().contains('ig');
  bool get _isBinanceBroker => _selectedBroker.toLowerCase() == 'binance';
  bool get _isOandaBroker => _selectedBroker.toLowerCase() == 'oanda';
  bool get _isExnessBroker => _selectedBroker.toLowerCase() == 'exness';
  bool get _isPxbtBroker =>
      _selectedBroker.toLowerCase() == 'pxbt' ||
      _selectedBroker.toLowerCase() == 'prime xbt';
  bool get _isMt5Broker => !_isIgBroker && !_isBinanceBroker && !_isOandaBroker;

  String _defaultServerForSelectedBroker({bool? isLiveOverride}) {
    final isLive = isLiveOverride ?? _isLiveMode;
    if (_selectedBroker.toLowerCase() == 'exness') {
      return isLive ? 'Exness-MT5Real27' : 'Exness-MT5Trial9';
    }
    return brokerServers[_selectedBroker] ?? '';
  }

  void _loadSavedAccounts() async {
    final accounts = BrokerConnectionService.getSavedAccounts()
        .where((a) => !a.brokerName.toLowerCase().contains('xm'))
        .toList();
    setState(() => _savedAccounts = accounts);
  }

  void _loadSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    final savedBroker = prefs.getString('broker') ?? 'Exness';
    final normalizedSavedBroker =
        savedBroker.toLowerCase().contains('xm') ? 'Exness' : savedBroker;
    setState(() {
      _selectedBroker = normalizedSavedBroker;
      _accountController.text = prefs.getString('mt5_account') ?? '';
      _passwordController.text = prefs.getString('mt5_password') ?? '';
      _apiKeyController.text = prefs.getString('broker_api_key') ?? '';
      _usernameController.text = prefs.getString('broker_username') ?? '';
      _isConnected = prefs.getBool('broker_connected') ?? false;
      _accountBalance = prefs.getDouble('account_balance') ?? 0;
      _accountCurrency = prefs.getString('account_currency') ?? 'USD';
      _autoReconnectEnabled = prefs.getBool('auto_reconnect_enabled') ?? false;
      _isLiveMode = prefs.getBool('is_live_mode') ?? false;  // Load saved mode
      final savedServer = prefs.getString('mt5_server') ?? '';
      _serverController.text = savedServer.isNotEmpty
          ? savedServer
          : _defaultServerForSelectedBroker(isLiveOverride: _isLiveMode);
      final connectionTimeStr = prefs.getString('connection_time');
      if (connectionTimeStr != null) {
        _lastConnectionTime = DateTime.parse(connectionTimeStr);
      }
    });
  }

  void _saveCredentials() async {
    // Require test connection before saving
    if (!_isConnected) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('❌ Must test connection first (click "Test Connection" button)'),
          backgroundColor: Colors.orange,
          duration: Duration(seconds: 4),
        ),
      );
      return;
    }
    
    // Prevent double-save
    if (_showSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Already saved - please wait'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    final missingMt5 = _isMt5Broker && (_accountController.text.isEmpty || _passwordController.text.isEmpty);
    final missingIg = _isIgBroker && (_apiKeyController.text.isEmpty || _usernameController.text.isEmpty || _passwordController.text.isEmpty || _accountController.text.isEmpty);
    final missingBinance = _isBinanceBroker && (_apiKeyController.text.isEmpty || _passwordController.text.isEmpty);
    final missingOanda = _isOandaBroker && (_apiKeyController.text.isEmpty || _accountController.text.isEmpty);

    if (missingMt5 || missingIg || missingBinance || missingOanda) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all required broker fields')),
      );
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('broker', _selectedBroker);
    await prefs.setString('mt5_account', _accountController.text);
    await prefs.setString('mt5_password', _passwordController.text);
    await prefs.setString('mt5_server', _serverController.text);
    await prefs.setString('broker_api_key', _apiKeyController.text);
    await prefs.setString('broker_username', _usernameController.text);

    if (_isConnected) {
      await prefs.setBool('broker_connected', true);
      await prefs.setString('connection_time', DateTime.now().toIso8601String());
      await prefs.setDouble('account_balance', _accountBalance);
    }

    if (mounted) {
      // Save to backend via BrokerCredentialsService
      final brokerService = Provider.of<BrokerCredentialsService>(context, listen: false);
      final success = await brokerService.saveCredential(
        broker: _selectedBroker,
        accountNumber: _accountController.text,
        password: _passwordController.text,
        server: _serverController.text,
        isLive: _isLiveMode,
        apiKey: _apiKeyController.text.isNotEmpty ? _apiKeyController.text : null,
        apiSecret: _passwordController.text.isNotEmpty ? _passwordController.text : null,
        username: _usernameController.text.isNotEmpty ? _usernameController.text : null,
      );

      if (!success) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('❌ Failed to save credentials: ${brokerService.errorMessage}'),
              backgroundColor: Colors.red,
            ),
          );
        }
        return;
      }

      // Also sync with local trading service
      final tradingService = Provider.of<TradingService>(context, listen: false);
      await tradingService.syncBrokerAccount(
        brokerName: _selectedBroker,
        accountNumber: _accountController.text,
        server: _serverController.text,
      );
    }

    setState(() => _showSuccess = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _showSuccess = false);
    });
  }

  /// Check if Exness is available on the backend
  Future<Map<String, dynamic>> _checkExnessAvailability() async {
    try {
      final baseUrl = EnvironmentConfig.apiUrl;
      final response = await http.get(
        Uri.parse('$baseUrl/api/brokers/check-exness'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'available': data['available'] ?? false,
          'installed': data['installed'] ?? false,
          'version': data['version'] ?? 'Unknown',
          'error': data['error'],
        };
      } else {
        return {
          'available': false,
          'error': 'Failed to check Exness availability',
        };
      }
    } catch (e) {
      return {
        'available': false,
        'error': 'Error checking Exness: $e',
      };
    }
  }

  /// Check if PXBT MT5 is available on the backend
  Future<Map<String, dynamic>> _checkPxbtAvailability() async {
    try {
      final baseUrl = EnvironmentConfig.apiUrl;
      final response = await http.get(
        Uri.parse('$baseUrl/api/brokers/check-pxbt'),
      ).timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {
          'available': data['available'] ?? false,
          'installed': data['installed'] ?? false,
          'version': data['version'] ?? 'Unknown',
          'error': data['error'],
        };
      } else {
        return {
          'available': false,
          'error': 'Failed to check PXBT availability',
        };
      }
    } catch (e) {
      return {
        'available': false,
        'error': 'Error checking PXBT: $e',
      };
    }
  }

  void _testConnection() async {
    // Check Exness/PXBT availability first when selected
    if (_isExnessBroker) {
      setState(() => _isTestingConnection = true);
      
      final exnessCheck = await _checkExnessAvailability();
      
      // ✅ FIXED: Use proper comparison (was "!available == true" which is wrong)
      if (exnessCheck['available'] != true) {
        if (mounted) {
          setState(() => _isTestingConnection = false);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('❌ Exness MT5 not available: ${exnessCheck['error'] ?? "Unknown error"}'),
              backgroundColor: Colors.red,
              duration: const Duration(seconds: 5),
            ),
          );
        }
        return;
      }
    }

    if (_isPxbtBroker) {
      setState(() => _isTestingConnection = true);

      final pxbtCheck = await _checkPxbtAvailability();

      // ✅ FIXED: Use proper comparison (was "!available == true" which is wrong)
      if (pxbtCheck['available'] != true) {
        if (mounted) {
          setState(() => _isTestingConnection = false);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('❌ PXBT MT5 not available: ${pxbtCheck['error'] ?? "Unknown error"}'),
              backgroundColor: Colors.red,
              duration: const Duration(seconds: 5),
            ),
          );
        }
        return;
      }
    }

    final missingMt5 = (_isMt5Broker || _isExnessBroker) && (_accountController.text.isEmpty || _passwordController.text.isEmpty);
    final missingIg = _isIgBroker && (_apiKeyController.text.isEmpty || _usernameController.text.isEmpty || _passwordController.text.isEmpty || _accountController.text.isEmpty);
    final missingBinance = _isBinanceBroker && (_apiKeyController.text.isEmpty || _passwordController.text.isEmpty);
    final missingOanda = _isOandaBroker && (_apiKeyController.text.isEmpty || _accountController.text.isEmpty);

    if (missingMt5 || missingIg || missingBinance || missingOanda) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all required connection fields')),
      );
      return;
    }

    setState(() => _isTestingConnection = true);

    // Show loading message with context about MT5 connection delays
    if (_isExnessBroker) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('🔌 Testing Exness connection... (may take 30-60 seconds)'),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.blue.withOpacity(0.7),
        ),
      );
    }
    if (_isPxbtBroker) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('🔌 Testing PXBT connection... (may take 30-60 seconds)'),
          duration: const Duration(seconds: 3),
          backgroundColor: Colors.blue.withOpacity(0.7),
        ),
      );
    }

    try {
      final result = await BrokerConnectionService.testConnection(
        broker: _selectedBroker,
        accountNumber: _accountController.text,
        password: _isOandaBroker ? '' : _passwordController.text,
        server: _serverController.text,
        apiKey: (_isIgBroker || _isBinanceBroker || _isOandaBroker)
            ? (_apiKeyController.text.isEmpty ? null : _apiKeyController.text)
            : null,
        apiSecret: _isBinanceBroker ? _passwordController.text : null,
        username: _usernameController.text.isEmpty ? null : _usernameController.text,
        accountId: _accountController.text,
        market: _isBinanceBroker ? _serverController.text : null,
        isLive: _isLiveMode,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        // Backend returns: credential_id, broker, account_number, balance, currency, status, timestamp
        final credentialId = result['credential_id'] as String?;
        final balance = (result['balance'] ?? 10000.0).toDouble();
        final isDemo = !(result['is_live'] == true);
        final currency = (result['currency'] as String? ?? 'USD').toUpperCase();
        final currencySymbol = currency == 'ZAR' ? 'R' : (currency == 'GBP' ? '£' : (currency == 'EUR' ? '€' : r'$'));
        
        // Create BrokerAccount from backend response
        final account = BrokerAccount(
          id: credentialId ?? '${_selectedBroker}_${_accountController.text}',
          brokerName: _selectedBroker,
          accountNumber: _accountController.text,
          server: _serverController.text,
          isDemo: isDemo,
          accountBalance: balance,
          leverage: 100,
          spreadAverage: 1.5,
          createdAt: DateTime.now(),
          lastConnected: DateTime.now(),
          isActive: true,
          connectionStatus: 'CONNECTED',
        );

        setState(() {
          _isTestingConnection = false;
          _isConnected = true;
          _activeAccount = account;
          _lastConnectionTime = DateTime.now();
          _accountBalance = balance;
          _accountCurrency = currency;
        });

        final prefs = await SharedPreferences.getInstance();
        await prefs.setBool('broker_connected', true);
        await prefs.setString('connection_time', _lastConnectionTime!.toIso8601String());
        await prefs.setDouble('account_balance', _accountBalance);
        await prefs.setBool('is_live_mode', _isLiveMode);
        await prefs.setString('account_currency', currency);
        if (credentialId != null) {
          await prefs.setString('credential_id', credentialId);
          await prefs.setString('broker_name', _selectedBroker);
          await prefs.setString('account_number', _accountController.text);
        }

        if (mounted) {
          final tradingService = Provider.of<TradingService>(context, listen: false);
          await tradingService.syncBrokerAccount(
            brokerName: _selectedBroker,
            accountNumber: _accountController.text,
            server: _serverController.text,
          );
        }

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✓ Connected! Balance: $currencySymbol${balance.toStringAsFixed(2)} $currency'),
            backgroundColor: AppColors.successColor,
            duration: const Duration(seconds: 3),
          ),
        );
      } else {
        setState(() => _isTestingConnection = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✗ ${result['message'] ?? 'Connection failed'}'),
            backgroundColor: AppColors.dangerColor,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } catch (e) {
      setState(() => _isTestingConnection = false);
      print('DEBUG: Test connection error: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('✗ Error: $e'),
          backgroundColor: AppColors.dangerColor,
        ),
      );
    }
  }

  void _startAutoReconnect() async {
    if (_activeAccount == null) return;

    setState(() => _autoReconnectEnabled = true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_reconnect_enabled', true);

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('✓ Auto-reconnect enabled'),
        backgroundColor: AppColors.successColor,
      ),
    );
  }

  void _navigateToAnalytics() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => const BrokerAnalyticsDashboard(),
      ),
    );
  }

  @override
  void dispose() {
    _serverController.dispose();
    _accountController.dispose();
    _passwordController.dispose();
    _apiKeyController.dispose();
    _usernameController.dispose();
    BrokerConnectionService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Broker Integration'),
          ],
        ),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.dashboard_rounded),
            tooltip: 'Home',
            onPressed: () {
              Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(builder: (_) => const DashboardScreen()),
                (route) => route.isFirst,
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.assessment_outlined),
            tooltip: 'Reports',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const ConsolidatedReportsScreen()));
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back),
                    onPressed: widget.onBackPressed ?? () => Navigator.of(context).pop(),
                  ),
                  const Text(
                    'Broker Integration',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              if (_isConnected)
                ElevatedButton.icon(
                  onPressed: _navigateToAnalytics,
                  icon: const Icon(Icons.analytics),
                  label: const Text('Analytics'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primaryColor,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          if (_showSuccess) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.successColor,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.check_circle, color: Colors.white),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Broker credentials saved successfully!',
                      style: TextStyle(color: Colors.white),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            // ✅ Quick Action Buttons After Successful Connection
            Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    const Color(0xFF1A237E).withOpacity(0.5),
                    const Color(0xFF0D47A1).withOpacity(0.5),
                  ],
                ),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'What\'s Next?',
                    style: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Create Bot Button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (context) => const BotConfigurationScreen(),
                          ),
                        );
                      },
                      icon: const Icon(Icons.smart_toy),
                      label: const Text('Create Trading Bot'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF7C4DFF),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // View Active Bots Button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (context) => const BotDashboardScreen(),
                          ),
                        );
                      },
                      icon: const Icon(Icons.dashboard),
                      label: const Text('View Active Bots'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF00E5FF).withOpacity(0.2),
                        foregroundColor: const Color(0xFF00E5FF),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        side: const BorderSide(color: Color(0xFF00E5FF)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Go to Dashboard Button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (context) => const DashboardScreen(),
                          ),
                        );
                      },
                      icon: const Icon(Icons.home),
                      label: const Text('Go to Dashboard'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF69F0AE).withOpacity(0.15),
                        foregroundColor: const Color(0xFF69F0AE),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        side: const BorderSide(color: Color(0xFF69F0AE)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ] else
            const SizedBox(height: 20),
          Text(
            _isBinanceBroker
                ? 'Binance API Connection'
                : _isOandaBroker
                    ? 'OANDA API Connection'
                    : _isIgBroker
                        ? 'IG Markets API Connection'
                        : 'MT5 Broker Connection',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            _isBinanceBroker
                ? 'Connect your funded Binance account for crypto bot trading'
                : _isOandaBroker
                    ? 'Connect your OANDA account — trade Forex, Gold, Oil and Indices'
                    : _isIgBroker
                        ? 'Connect your IG Markets account with the official API credentials'
                        : 'Connect your MetaTrader 5 account for automated trading',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 24),
          Text(
            'Select Your Broker',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: DropdownButton<String>(
                value: _selectedBroker,
                isExpanded: true,
                underline: const SizedBox(),
                onChanged: (newValue) {
                  if (newValue != null) {
                    setState(() {
                      _selectedBroker = newValue;
                      _serverController.text = _defaultServerForSelectedBroker();
                    });
                  }
                },
                items: brokers.map((broker) => DropdownMenuItem<String>(
                    value: broker,
                    child: Text(broker),
                  )).toList(),
              ),
            ),
          ),
          const SizedBox(height: 24),
          if (_isMt5Broker) ...[
            Text(
              'MT5 Server',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _serverController,
              readOnly: true,
              decoration: InputDecoration(
                labelText: 'Server',
                border: const OutlineInputBorder(),
                prefixIcon: const Icon(Icons.storage),
                filled: true,
                fillColor: Colors.grey[900],
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'MT5 Account Number',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _accountController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Account Number (your MT5 account ID)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.account_circle),
                hintText: 'demo or 136372035',
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'MT5 Password',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'MT5 Password (your broker password)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock),
                hintText: 'demo123',
              ),
            ),
          ],
          if (_isIgBroker) ...[
            Text('IG API Key', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _apiKeyController,
              decoration: const InputDecoration(
                labelText: 'IG API Key',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.vpn_key),
              ),
            ),
            const SizedBox(height: 24),
            Text('IG Username', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _usernameController,
              decoration: const InputDecoration(
                labelText: 'IG Username',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.person),
              ),
            ),
            const SizedBox(height: 24),
            Text('IG Password', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'IG Password',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock),
              ),
            ),
            const SizedBox(height: 24),
            Text('IG Account ID', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _accountController,
              decoration: const InputDecoration(
                labelText: 'IG Account ID',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.account_circle),
                hintText: 'Demo account IDs usually start with D',
              ),
            ),
          ],
          if (_isOandaBroker) ...[
            Text('OANDA API Token', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _apiKeyController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'API Token (Bearer token from OANDA portal)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.vpn_key),
                hintText: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-yyyyyyyy',
              ),
            ),
            const SizedBox(height: 24),
            Text('OANDA Account ID', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _accountController,
              decoration: const InputDecoration(
                labelText: 'Account ID (e.g. 001-001-1234567-001)',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.account_circle),
                hintText: '001-001-1234567-001',
              ),
            ),
          ],
          if (_isBinanceBroker) ...[
            Text('Binance API Key', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _apiKeyController,
              decoration: const InputDecoration(
                labelText: 'Binance API Key',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.vpn_key),
              ),
            ),
            const SizedBox(height: 24),
            Text('Binance API Secret', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Binance API Secret',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock),
              ),
            ),
            const SizedBox(height: 24),
            Text('Trading Market', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: DropdownButton<String>(
                  value: _serverController.text.isEmpty ? 'spot' : _serverController.text,
                  isExpanded: true,
                  underline: const SizedBox(),
                  onChanged: (value) {
                    if (value != null) {
                      setState(() {
                        _serverController.text = value;
                        // Do not overwrite account — Binance has no account number
                      });
                    }
                  },
                  items: const [
                    DropdownMenuItem(value: 'spot', child: Text('Spot')),
                    DropdownMenuItem(value: 'futures', child: Text('Futures')),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 24),
          Text(
            'Account Mode',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  Expanded(
                    child: RadioListTile<bool>(
                      title: const Text('DEMO'),
                      subtitle: const Text('Paper trading'),
                      value: false,
                      groupValue: _isLiveMode,
                      onChanged: (value) {
                        if (value != null) {
                          setState(() {
                            _isLiveMode = value;
                            _serverController.text = _defaultServerForSelectedBroker();
                          });
                        }
                      },
                    ),
                  ),
                  Expanded(
                    child: RadioListTile<bool>(
                      title: const Text('LIVE'),
                      subtitle: const Text('Real trading'),
                      value: true,
                      groupValue: _isLiveMode,
                      onChanged: (value) {
                        if (value != null) {
                          setState(() {
                            _isLiveMode = value;
                            _serverController.text = _defaultServerForSelectedBroker();
                          });
                        }
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
          // Connection Status Card
          Container(
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF1A1F3A),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: _isConnected 
                  ? AppColors.successColor.withOpacity(0.3)
                  : Colors.orange.withOpacity(0.2),
              ),
              boxShadow: [
                BoxShadow(
                  color: (_isConnected ? AppColors.successColor : Colors.orange).withOpacity(0.15),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Status header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 14,
                          height: 14,
                          margin: const EdgeInsets.only(bottom: 2),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: _isConnected ? AppColors.successColor : Colors.orange,
                            boxShadow: [
                              BoxShadow(
                                color: (_isConnected ? AppColors.successColor : Colors.orange).withOpacity(0.5),
                                blurRadius: 8,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          _isConnected ? 'CONNECTED ✓' : 'Status: Not Connected',
                          style: GoogleFonts.poppins(
                            color: _isConnected ? AppColors.successColor : Colors.orange,
                            fontWeight: FontWeight.bold,
                            fontSize: 15,
                          ),
                        ),
                      ],
                    ),
                    if (_isConnected)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: _isLiveMode 
                            ? Colors.red.withOpacity(0.25)
                            : Colors.orange.withOpacity(0.25),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: _isLiveMode ? Colors.red : Colors.orange,
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              _isLiveMode ? Icons.warning : Icons.school,
                              color: _isLiveMode ? Colors.red : Colors.orange,
                              size: 16,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              _isLiveMode ? 'LIVE' : 'DEMO',
                              style: GoogleFonts.poppins(
                                color: _isLiveMode ? Colors.red : Colors.orange,
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
                if (_isConnected) ...[
                  const SizedBox(height: 14),
                  Text(
                    'Bot Status: READY',
                    style: GoogleFonts.poppins(
                      color: AppColors.successColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.successColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppColors.successColor.withOpacity(0.3),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Live Scalping Activity:',
                          style: GoogleFonts.poppins(
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 10),
                        _buildStatusInfoRow('Account', _accountController.text),
                        const SizedBox(height: 8),
                        _buildStatusInfoRow('Connection', _lastConnectionTime?.toString().split('.')[0] ?? 'N/A'),
                        const SizedBox(height: 8),
                        _buildStatusInfoRow('Balance', '${_accountCurrency == 'ZAR' ? 'R' : (_accountCurrency == 'GBP' ? '£' : r'$')}${_accountBalance.toStringAsFixed(2)} $_accountCurrency'),
                      ],
                    ),
                  ),
                ] else ...[
                  const SizedBox(height: 12),
                  Text(
                    'Click "Test Connection" to validate credentials',
                    style: GoogleFonts.poppins(
                      fontSize: 12,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ],
            ),
          ),
          // Auto-reconnect checkbox
          if (_isConnected)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: CheckboxListTile(
                title: Text(
                  'Enable Auto-Reconnect',
                  style: GoogleFonts.poppins(fontSize: 13),
                ),
                value: _autoReconnectEnabled,
                onChanged: (value) {
                  if (value == true) {
                    _startAutoReconnect();
                  }
                },
                contentPadding: EdgeInsets.zero,
              ),
            ),
          // Buttons
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _saveCredentials,
              icon: const Icon(Icons.save, size: 20, color: Colors.white),
              label: Text(
                'Save Credentials',
                style: GoogleFonts.poppins(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                  letterSpacing: 0.5,
                ),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryColor,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 4,
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _isTestingConnection ? null : _testConnection,
              icon: _isTestingConnection
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(Colors.white),
                      ),
                    )
                  : const Icon(Icons.cloud_sync, size: 20, color: Colors.white),
              label: Text(
                _isTestingConnection ? 'Testing Connection...' : 'Test Connection',
                style: GoogleFonts.poppins(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                  letterSpacing: 0.5,
                ),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: _isConnected ? AppColors.successColor : AppColors.primaryColor,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 4,
              ),
            ),
          ),
          if (_savedAccounts.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Saved Accounts',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
            ),
            const SizedBox(height: 12),
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _savedAccounts.length,
              itemBuilder: (context, index) {
                final account = _savedAccounts[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text('${account.brokerName} - ${account.accountNumber}'),
                    subtitle: Text('Server: ${account.server}'),
                    trailing: Chip(
                      label: Text(account.isDemo ? 'DEMO' : 'LIVE'),
                      backgroundColor: account.isDemo ? Colors.orange : Colors.green,
                    ),
                  ),
                );
              },
            ),
          ],
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border.all(color: Colors.white24),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isBinanceBroker
                      ? '📱 How to get your Binance API credentials:'
                      : _isOandaBroker
                          ? '📱 How to get your OANDA API credentials:'
                          : _isIgBroker
                              ? '📱 How to get your IG API credentials:'
                              : '📱 How to get your MT5 credentials:',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  _isBinanceBroker
                      ? '1. Open Binance and create an API key\n2. Enable trading permission for the key\n3. Copy the API key and secret\n4. Choose Spot or Futures\n5. Fund that Binance account before starting the bot'
                      : _isOandaBroker
                          ? '1. Go to oanda.com → My Account → Manage API Access\n2. Click "Generate" to create a Personal Access Token\n3. Copy the full token (shown once — save it!)\n4. Find your Account ID on the OANDA dashboard\n   (format: 001-001-XXXXXXX-001)\n5. Choose DEMO (fxpractice) or LIVE (fxtrade) mode'
                          : _isIgBroker
                              ? '1. Open the IG developer portal and create an API key\n2. Use your IG login username and password\n3. Copy the correct Account ID from IG\n4. Match DEMO/LIVE to the same IG environment\n5. Test connection before creating bots'
                              : '1. Open your MetaTrader 5 terminal\n2. Login with your broker account\n3. Your account number appears at the top\n4. Use your MT5 login password\n5. Server will auto-populate',
                  style: const TextStyle(fontSize: 12, color: Colors.white70),
                ),
                const SizedBox(height: 16),
                const Text(
                  '✓ Example Credentials:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.grey[800],
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: Colors.grey[700]!),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _isBinanceBroker
                            ? 'API Key: paste your Binance API key'
                            : (_isIgBroker ? 'API Key: paste your IG API key' : 'Account: demo or 136372035'),
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _isBinanceBroker
                            ? 'Secret: paste your Binance API secret'
                            : (_isIgBroker ? 'Account ID: D... or live account ID' : 'Password: demo123'),
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Navigation footer icons
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: Colors.white10)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                Tooltip(
                  message: 'Back to Previous Screen',
                  child: IconButton(
                    icon: const Icon(Icons.arrow_back, size: 24),
                    onPressed: widget.onBackPressed ?? () => Navigator.pop(context),
                    tooltip: 'Go Back',
                  ),
                ),
                Tooltip(
                  message: 'Refresh Connection Status',
                  child: IconButton(
                    icon: const Icon(Icons.refresh, size: 24),
                    onPressed: _isTestingConnection ? null : _testConnection,
                    tooltip: 'Refresh',
                  ),
                ),
                Tooltip(
                  message: 'Connection Settings',
                  child: IconButton(
                    icon: const Icon(Icons.settings, size: 24),
                    onPressed: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Settings: Auto-reconnect and account preferences')),
                      );
                    },
                    tooltip: 'Settings',
                  ),
                ),
                Tooltip(
                  message: 'View Connection History',
                  child: IconButton(
                    icon: const Icon(Icons.history, size: 24),
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('Connection History'),
                          content: SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('Last Connection: ${_lastConnectionTime?.toString() ?? "N/A"}'),
                                const SizedBox(height: 8),
                                Text('Status: ${_isConnected ? "Connected" : "Disconnected"}'),
                                const SizedBox(height: 8),
                                Text('Mode: ${_isLiveMode ? "LIVE 🔴" : "DEMO 🟠"}'),
                              ],
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('Close'),
                            ),
                          ],
                        ),
                      );
                    },
                    tooltip: 'History',
                  ),
                ),
                Tooltip(
                  message: 'Help & Documentation',
                  child: IconButton(
                    icon: const Icon(Icons.help_outline, size: 24),
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('Broker Integration Help'),
                          content: const SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('📱 Demo Mode (Orange): Training account for testing'),
                                SizedBox(height: 8),
                                Text('🔴 Live Mode (Red): Real money trading - USE WITH CAUTION'),
                                SizedBox(height: 12),
                                Text('✓ When Connected:'),
                                Text('  • Account is authenticated'),
                                Text('  • Bots can place real trades'),
                                Text('  • Balance is synchronized'),
                              ],
                            ),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('Close'),
                            ),
                          ],
                        ),
                      );
                    },
                    tooltip: 'Help',
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      ),
    );

  Widget _buildStatusInfoRow(String label, String value) => Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: GoogleFonts.poppins(
            color: Colors.white70,
            fontSize: 12,
          ),
        ),
        Text(
          value,
          style: GoogleFonts.poppins(
            color: Colors.white,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
}
