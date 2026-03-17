import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';
import '../widgets/logo_widget.dart';

class MultiAccountManagementScreen extends StatefulWidget {
  const MultiAccountManagementScreen({Key? key}) : super(key: key);

  @override
  State<MultiAccountManagementScreen> createState() =>
      _MultiAccountManagementScreenState();
}

class _MultiAccountManagementScreenState
    extends State<MultiAccountManagementScreen> {
  late String _apiUrl = EnvironmentConfig.apiUrl;

  List<Map<String, dynamic>> _accounts = [];
  List<Map<String, dynamic>> _availableBrokers = [];
  bool _isLoading = false;
  String? _errorMessage;

  // Form controllers
  late TextEditingController _accountIdController;
  late TextEditingController _accountNumberController;
  late TextEditingController _passwordController;
  late TextEditingController _serverController;

  String? _selectedBroker;

  @override
  void initState() {
    super.initState();
    _accountIdController = TextEditingController();
    _accountNumberController = TextEditingController();
    _passwordController = TextEditingController();
    _serverController = TextEditingController();

    _loadAccounts();
    _loadBrokers();
  }

  @override
  void dispose() {
    _accountIdController.dispose();
    _accountNumberController.dispose();
    _passwordController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _loadAccounts() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await http
          .get(Uri.parse('$_apiUrl/api/accounts/list'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _accounts = List<Map<String, dynamic>>.from(data['accounts'] ?? []);
        });
      } else {
        setState(() {
          _errorMessage = 'Failed to load accounts';
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _loadBrokers() async {
    try {
      final response = await http
          .get(Uri.parse('$_apiUrl/api/brokers/list'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _availableBrokers =
              List<Map<String, dynamic>>.from(data['brokers'] ?? []);
        });
      }
    } catch (e) {
      debugPrint('Error loading brokers: $e');
    }
  }

  Future<void> _addAccount() async {
    if (_accountIdController.text.isEmpty ||
        _selectedBroker == null ||
        _accountNumberController.text.isEmpty ||
        _passwordController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill all fields')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http.post(
        Uri.parse('$_apiUrl/api/accounts/add'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'accountId': _accountIdController.text,
          'brokerType': _selectedBroker,
          'credentials': {
            'account': int.tryParse(_accountNumberController.text),
            'password': _passwordController.text,
            'server': _serverController.text,
          }
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Account added successfully')),
          );
          _accountIdController.clear();
          _accountNumberController.clear();
          _passwordController.clear();
          _serverController.clear();
          setState(() {
            _selectedBroker = null;
          });
          _loadAccounts();
          Navigator.pop(context);
        } else {
          setState(() {
            _errorMessage = data['error'] ?? 'Failed to add account';
          });
        }
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _connectAccount(String accountId) async {
    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http
          .post(Uri.parse('$_apiUrl/api/accounts/connect/$accountId'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Connected to $accountId')),
        );
        _loadAccounts();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  void _showAddAccountDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Trading Account'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _accountIdController,
                decoration: const InputDecoration(
                  labelText: 'Account ID (nickname)',
                  hintText: 'e.g., My MT5 Account',
                ),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _selectedBroker,
                items: _availableBrokers
                    .map((b) => DropdownMenuItem<String>(
                          value: b['type'] as String,
                          child: Text(b['name'] as String),
                        ))
                    .toList(),
                onChanged: (value) => setState(() => _selectedBroker = value),
                decoration: const InputDecoration(labelText: 'Broker'),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _accountNumberController,
                decoration: const InputDecoration(
                  labelText: 'Account Number',
                  hintText: 'e.g., 136372035',
                ),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passwordController,
                decoration: const InputDecoration(
                  labelText: 'Password',
                ),
                obscureText: true,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _serverController,
                decoration: const InputDecoration(
                  labelText: 'Server',
                  hintText: 'e.g., MetaQuotes-Demo',
                ),
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
            onPressed: _addAccount,
            child: const Text('Add Account'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: const [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Multi-Account Management'),
          ],
        ),
        backgroundColor: Colors.grey[900],
        elevation: 0,
        centerTitle: false,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      backgroundColor: Colors.grey[850],
      body: _isLoading && _accounts.isEmpty
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF00E5FF)))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_errorMessage != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [Colors.red.withOpacity(0.2), Colors.red.withOpacity(0.1)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        border: Border.all(color: Colors.red.withOpacity(0.5)),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.red.withOpacity(0.15),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              _errorMessage!,
                              style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: 16),
                  Container(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF00E5FF), Color(0xFF7C4DFF)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(14),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xFF00E5FF).withOpacity(0.3),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: _showAddAccountDialog,
                        borderRadius: BorderRadius.circular(14),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.add_circle_outline, color: Colors.white, size: 22),
                              const SizedBox(width: 10),
                              const Text(
                                'Add Trading Account',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                  letterSpacing: 0.3,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  if (_accounts.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(40),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [Colors.grey[900]!.withOpacity(0.8), Colors.grey[800]!.withOpacity(0.6)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: Colors.white.withOpacity(0.1)),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.2),
                            blurRadius: 16,
                            offset: const Offset(0, 6),
                          ),
                        ],
                      ),
                      child: Column(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [Color(0xFF00E5FF).withOpacity(0.2), Color(0xFF7C4DFF).withOpacity(0.15)],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: Color(0xFF00E5FF).withOpacity(0.2),
                                  blurRadius: 20,
                                ),
                              ],
                            ),
                            child: Icon(
                              Icons.account_balance_wallet,
                              size: 56,
                              color: Color(0xFF00E5FF),
                            ),
                          ),
                          const SizedBox(height: 20),
                          Text(
                            'No accounts added yet',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              letterSpacing: 0.3,
                            ),
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'Add your first trading account to get started',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.white70,
                              height: 1.5,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    ..._accounts.map((account) => _buildAccountCard(account)),
                ],
              ),
            ),
    );
  }

  Widget _buildAccountCard(Map<String, dynamic> account) {
    final isConnected = account['connected'] ?? false;
    final info = account['info'];
    final statusColor = isConnected ? Colors.green : Colors.orange;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.grey[900]!.withOpacity(0.9),
            Colors.grey[800]!.withOpacity(0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: statusColor.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: statusColor.withOpacity(0.15),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [statusColor.withOpacity(0.25), statusColor.withOpacity(0.1)],
                              ),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Icon(
                              Icons.account_balance,
                              color: statusColor,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              account['accountId'] ?? 'Unknown',
                              style: const TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                                letterSpacing: 0.3,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Icon(Icons.category, color: statusColor.withOpacity(0.6), size: 14),
                          const SizedBox(width: 6),
                          Text(
                            'Broker: ${account['broker'] ?? 'N/A'}',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white70,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [statusColor.withOpacity(0.3), statusColor.withOpacity(0.15)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: statusColor.withOpacity(0.5)),
                    boxShadow: [
                      BoxShadow(
                        color: statusColor.withOpacity(0.2),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        isConnected ? Icons.check_circle : Icons.radio_button_unchecked,
                        color: statusColor,
                        size: 16,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        isConnected ? 'Connected' : 'Offline',
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (info != null) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  border: Border(
                    top: BorderSide(color: Colors.white.withOpacity(0.1)),
                    bottom: BorderSide(color: Colors.white.withOpacity(0.1)),
                  ),
                ),
                child: Column(
                  children: [
                    _buildInfoRow('Account #', info['accountNumber']?.toString(), Colors.cyan),
                    const SizedBox(height: 10),
                    _buildInfoRow('Balance', '\$${info['balance']?.toStringAsFixed(2)}', Colors.green),
                    const SizedBox(height: 10),
                    _buildInfoRow('Equity', '\$${info['equity']?.toStringAsFixed(2)}', Colors.blue),
                    const SizedBox(height: 10),
                    _buildInfoRow('Currency', info['currency'], Colors.purple),
                    const SizedBox(height: 10),
                    _buildInfoRow('Leverage', '1:${info['leverage']}', Colors.orange),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 14),
            Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: isConnected
                      ? [Colors.green.shade600.withOpacity(0.8), Colors.green.shade700]
                      : [Colors.blue.shade600, Colors.blue.shade700],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: (isConnected ? Colors.green : Colors.blue).withOpacity(0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: isConnected ? null : () => _connectAccount(account['accountId']),
                  borderRadius: BorderRadius.circular(12),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          isConnected ? Icons.check_circle : Icons.link,
                          size: 18,
                          color: Colors.white,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          isConnected ? 'Connected' : 'Connect Account',
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                            letterSpacing: 0.2,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String? value, Color accentColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Container(
              width: 3,
              height: 14,
              decoration: BoxDecoration(
                color: accentColor,
                borderRadius: BorderRadius.circular(1.5),
              ),
            ),
            const SizedBox(width: 10),
            Text(
              label,
              style: TextStyle(
                color: Colors.white70,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        Text(
          value ?? 'N/A',
          style: TextStyle(
            color: accentColor,
            fontWeight: FontWeight.bold,
            fontSize: 13,
            letterSpacing: 0.2,
          ),
        ),
      ],
    );
  }
}
