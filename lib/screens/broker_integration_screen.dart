import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:provider/provider.dart';
import '../utils/constants.dart';
import '../services/trading_service.dart';
import '../services/broker_connection_service.dart';
import '../services/connection_analytics_service.dart';
import '../models/broker_connection_model.dart';
import 'broker_analytics_dashboard.dart';

class BrokerIntegrationScreen extends StatefulWidget {
  final VoidCallback? onBackPressed;

  const BrokerIntegrationScreen({
    Key? key,
    this.onBackPressed,
  }) : super(key: key);

  @override
  State<BrokerIntegrationScreen> createState() =>
      _BrokerIntegrationScreenState();
}

class _BrokerIntegrationScreenState extends State<BrokerIntegrationScreen> {
  late TextEditingController _serverController;
  late TextEditingController _accountController;
  late TextEditingController _passwordController;
  String _selectedBroker = 'XM';
  bool _showSuccess = false;
  bool _isTestingConnection = false;
  bool _isConnected = false;
  bool _autoReconnectEnabled = false;
  bool _isLiveMode = false;  // DEMO by default
  DateTime? _lastConnectionTime;
  double _accountBalance = 0;
  List<BrokerAccount> _savedAccounts = [];
  BrokerAccount? _activeAccount;

  final List<String> brokers = [
    'XM',
    'Pepperstone',
    'FxOpen',
    'Exness',
    'Darwinex',
    'IC Markets',
    'IG',
    'FXM',
    'AvaTrade',
    'FP Markets',
    'Zulu Trade (SA)',
    'Ovex (SA)',
    'Prime XBT',
    'Trade Nations',
    'MetaQuotes',
  ];

  final Map<String, String> brokerServers = {
    'XM': 'XMGlobal-MT5',
    'Pepperstone': 'Pepperstone MT5 Live',
    'FxOpen': 'FxOpen-MT5',
    'Exness': 'Exness-MT5',
    'Darwinex': 'Darwinex MT5',
    'IC Markets': 'ICMarkets-MT5',
    'IG': 'IG-Live',
    'FXM': 'FXM-Live',
    'AvaTrade': 'Ava-Real',
    'FP Markets': 'FPMarkets-Live',
    'Zulu Trade (SA)': 'ZuluTrade ZA',
    'Ovex (SA)': 'Ovex SA',
    'Prime XBT': 'PrimeXBT-MT5',
    'Trade Nations': 'TradeNations-MT5',
    'MetaQuotes': 'MetaQuotes-MT5',
  };

  @override
  void initState() {
    super.initState();
    _serverController = TextEditingController();
    _accountController = TextEditingController();
    _passwordController = TextEditingController();
    _loadSavedCredentials();
    _loadSavedAccounts();
  }

  void _loadSavedAccounts() async {
    final accounts = BrokerConnectionService.getSavedAccounts();
    setState(() => _savedAccounts = accounts);
  }

  void _loadSavedCredentials() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _selectedBroker = prefs.getString('broker') ?? 'XM';
      _accountController.text = prefs.getString('mt5_account') ?? '';
      _passwordController.text = prefs.getString('mt5_password') ?? '';
      _serverController.text = brokerServers[_selectedBroker] ?? '';
      _isConnected = prefs.getBool('broker_connected') ?? false;
      _accountBalance = prefs.getDouble('account_balance') ?? 0;
      _autoReconnectEnabled = prefs.getBool('auto_reconnect_enabled') ?? false;
      _isLiveMode = prefs.getBool('is_live_mode') ?? false;  // Load saved mode
      final connectionTimeStr = prefs.getString('connection_time');
      if (connectionTimeStr != null) {
        _lastConnectionTime = DateTime.parse(connectionTimeStr);
      }
    });
  }

  void _saveCredentials() async {
    if (_accountController.text.isEmpty || _passwordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all fields')),
      );
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('broker', _selectedBroker);
    await prefs.setString('mt5_account', _accountController.text);
    await prefs.setString('mt5_password', _passwordController.text);
    await prefs.setString('mt5_server', _serverController.text);

    if (_isConnected) {
      await prefs.setBool('broker_connected', true);
      await prefs.setString('connection_time', DateTime.now().toIso8601String());
      await prefs.setDouble('account_balance', _accountBalance);
    }

    if (mounted) {
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

  void _testConnection() async {
    if (_accountController.text.isEmpty || _passwordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill account and password')),
      );
      return;
    }

    setState(() => _isTestingConnection = true);

    try {
      final result = await BrokerConnectionService.testConnection(
        broker: _selectedBroker,
        accountNumber: _accountController.text,
        password: _passwordController.text,
        server: _serverController.text,
        isLive: _isLiveMode,
      );

      if (!mounted) return;

      if (result['success'] == true) {
        // Backend returns: credential_id, broker, account_number, balance, status, timestamp
        final credentialId = result['credential_id'] as String?;
        final balance = (result['balance'] ?? 10000.0).toDouble();
        final isDemo = !(_passwordController.text.contains('live') || result['is_live'] == true);
        
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
        });

        final prefs = await SharedPreferences.getInstance();
        await prefs.setBool('broker_connected', true);
        await prefs.setString('connection_time', _lastConnectionTime!.toIso8601String());
        await prefs.setDouble('account_balance', _accountBalance);
        await prefs.setBool('is_live_mode', _isLiveMode);
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
            content: Text('✓ Connected! Balance: \$${balance.toStringAsFixed(2)}'),
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
    BrokerConnectionService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Broker Integration'),
        elevation: 0,
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
          if (_showSuccess)
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
                      'MT5 credentials saved successfully!',
                      style: TextStyle(color: Colors.white),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 20),
          Text(
            'MT5 Broker Connection',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Connect your MetaTrader 5 account for automated trading',
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
                onChanged: (String? newValue) {
                  if (newValue != null) {
                    setState(() {
                      _selectedBroker = newValue;
                      _serverController.text = brokerServers[newValue] ?? '';
                    });
                  }
                },
                items: brokers.map((String broker) {
                  return DropdownMenuItem<String>(
                    value: broker,
                    child: Text(broker),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 24),
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
            decoration: InputDecoration(
              labelText: 'Account Number (your MT5 account ID)',
              border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.account_circle),
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
            decoration: InputDecoration(
              labelText: 'MT5 Password (your broker password)',
              border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.lock),
              hintText: 'demo123',
            ),
          ),
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
                          setState(() => _isLiveMode = value);
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
                          setState(() => _isLiveMode = value);
                        }
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 32),
          Card(
            color: Colors.grey[900],
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _isConnected ? AppColors.successColor : Colors.orange,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _isConnected ? 'CONNECTED ✓' : 'Status: Not Connected',
                        style: TextStyle(
                          color: _isConnected ? AppColors.successColor : Colors.orange,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(width: 12),
                      if (_isConnected)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: _isLiveMode ? Colors.red : Colors.orange,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                _isLiveMode ? Icons.warning : Icons.school,
                                color: Colors.white,
                                size: 16,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                _isLiveMode ? 'LIVE' : 'DEMO',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                  if (_isConnected) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Bot Status: READY',
                      style: TextStyle(color: AppColors.successColor, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: AppColors.successColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Live Scalping Activity:',
                              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                          const SizedBox(height: 6),
                          Text('Connected Account: ${_accountController.text}',
                              style: const TextStyle(fontSize: 11, color: Colors.white70)),
                          const SizedBox(height: 6),
                          Text('Last Connection: ${_lastConnectionTime?.toString().split('.')[0] ?? 'N/A'}',
                              style: const TextStyle(fontSize: 11, color: Colors.white70)),
                          const SizedBox(height: 6),
                          Text('Account Balance: \$${_accountBalance.toStringAsFixed(2)}',
                              style: const TextStyle(fontSize: 11, color: Colors.white70)),
                        ],
                      ),
                    ),
                  ] else ...[
                    const SizedBox(height: 8),
                    const Text(
                      'Click "Test Connection" to validate credentials',
                      style: TextStyle(fontSize: 12, color: Colors.white70),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          if (_isConnected)
            Row(
              children: [
                Expanded(
                  child: CheckboxListTile(
                    title: const Text('Enable Auto-Reconnect', style: TextStyle(fontSize: 12)),
                    value: _autoReconnectEnabled,
                    onChanged: (bool? value) {
                      if (value == true) {
                        _startAutoReconnect();
                      }
                    },
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _saveCredentials,
              icon: const Icon(Icons.save),
              label: const Text('Save Credentials'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primaryColor,
                padding: const EdgeInsets.symmetric(vertical: 16),
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
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(Colors.white),
                      ),
                    )
                  : const Icon(Icons.cloud_sync),
              label: Text(_isTestingConnection ? 'Testing...' : 'Test Connection'),
              style: ElevatedButton.styleFrom(
                backgroundColor:
                    _isConnected ? AppColors.successColor : AppColors.primaryColor,
                padding: const EdgeInsets.symmetric(vertical: 16),
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
                const Text(
                  '📱 How to get your MT5 credentials:',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  '1. Open your MetaTrader 5 terminal\n'
                  '2. Login with your broker account\n'
                  '3. Your account number appears at the top\n'
                  '4. Use your MT5 login password\n'
                  '5. Server will auto-populate',
                  style: TextStyle(fontSize: 12, color: Colors.white70),
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
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Account: demo or 136372035',
                          style: TextStyle(fontFamily: 'monospace', fontSize: 11)),
                      SizedBox(height: 4),
                      Text('Password: demo123',
                          style: TextStyle(fontFamily: 'monospace', fontSize: 11)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Navigation footer icons
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
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
                          content: SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text('📱 Demo Mode (Orange): Training account for testing'),
                                const SizedBox(height: 8),
                                const Text('🔴 Live Mode (Red): Real money trading - USE WITH CAUTION'),
                                const SizedBox(height: 12),
                                const Text('✓ When Connected:'),
                                const Text('  • Account is authenticated'),
                                const Text('  • Bots can place real trades'),
                                const Text('  • Balance is synchronized'),
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
  }
}
