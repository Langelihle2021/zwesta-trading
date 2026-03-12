import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/auth_service.dart';
import '../utils/constants.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';

class MultiBrokerManagementScreen extends StatefulWidget {
  const MultiBrokerManagementScreen({Key? key}) : super(key: key);

  @override
  State<MultiBrokerManagementScreen> createState() =>
      _MultiBrokerManagementScreenState();
}

class _MultiBrokerManagementScreenState
    extends State<MultiBrokerManagementScreen> {
  List<Map<String, dynamic>> _brokers = [];
  bool _isLoading = true;
  bool _isAddingBroker = false;
  String? _errorMessage;
  
  // Form controllers
  late TextEditingController _brokerNameController;
  late TextEditingController _accountNumberController;
  late TextEditingController _passwordController;
  late TextEditingController _serverController;
  bool _isLiveBroker = false;

  @override
  void initState() {
    super.initState();
    _brokerNameController = TextEditingController();
    _accountNumberController = TextEditingController();
    _passwordController = TextEditingController();
    _serverController = TextEditingController(text: 'MetaQuotes-Demo');
    _loadBrokers();
  }

  @override
  void dispose() {
    _brokerNameController.dispose();
    _accountNumberController.dispose();
    _passwordController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _loadBrokers() async {
    final authService = context.read<AuthService>();
    if (authService.token == null) return;

    setState(() => _isLoading = true);

    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/brokers'),
        headers: {'X-Session-Token': authService.token!},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _brokers = List<Map<String, dynamic>>.from(data['brokers'] ?? []);
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Failed to load brokers';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _addBroker() async {
    final authService = context.read<AuthService>();
    if (authService.token == null) return;

    if (_brokerNameController.text.isEmpty ||
        _accountNumberController.text.isEmpty ||
        _passwordController.text.isEmpty) {
      setState(() => _errorMessage = 'All fields required');
      return;
    }

    setState(() => _isAddingBroker = true);

    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/brokers/add'),
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': authService.token!,
        },
        body: jsonEncode({
          'broker_name': _brokerNameController.text,
          'account_number': _accountNumberController.text,
          'password': _passwordController.text,
          'server': _serverController.text,
          'is_live': _isLiveBroker,
        }),
      );

      if (response.statusCode == 201) {
        _brokerNameController.clear();
        _accountNumberController.clear();
        _passwordController.clear();
        _serverController.text = 'MetaQuotes-Demo';
        _isLiveBroker = false;
        await _loadBrokers();
        setState(() => _isAddingBroker = false);
        // Show success
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('✅ Broker credential added')),
          );
        }
      } else {
        final data = jsonDecode(response.body);
        setState(() {
          _errorMessage = data['error'] ?? 'Failed to add broker';
          _isAddingBroker = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isAddingBroker = false;
      });
    }
  }

  Future<void> _removeBroker(String credentialId) async {
    final authService = context.read<AuthService>();
    if (authService.token == null) return;

    try {
      final response = await http.delete(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/brokers/$credentialId'),
        headers: {'X-Session-Token': authService.token!},
      );

      if (response.statusCode == 200) {
        await _loadBrokers();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('✅ Broker credential removed')),
          );
        }
      }
    } catch (e) {
      setState(() => _errorMessage = 'Error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Multi-Broker Management'),
        backgroundColor: Colors.blue[700],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Error message
                  if (_errorMessage != null)
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        color: Colors.red.withOpacity(0.1),
                        border: Border.all(color: Colors.red),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error, color: Colors.red),
                          const SizedBox(width: AppSpacing.md),
                          Expanded(
                            child: Text(
                              _errorMessage!,
                              style: const TextStyle(color: Colors.red),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, color: Colors.red),
                            onPressed: () =>
                                setState(() => _errorMessage = null),
                          ),
                        ],
                      ),
                    ),

                  const SizedBox(height: AppSpacing.lg),

                  // Add Broker Form
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    decoration: BoxDecoration(
                      color: Colors.blue[50],
                      border: Border.all(color: Colors.blue[200]!),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Add Broker Credential',
                          style: GoogleFonts.poppins(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Colors.blue[900],
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        TextField(
                          controller: _brokerNameController,
                          decoration: const InputDecoration(
                            labelText: 'Broker Name *',
                            hintText: 'e.g., MetaQuotes, FxOpen, etc.',
                            prefixIcon: Icon(Icons.business),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        TextField(
                          controller: _accountNumberController,
                          decoration: const InputDecoration(
                            labelText: 'Account Number *',
                            hintText: 'e.g., 104254514',
                            prefixIcon: Icon(Icons.numbers),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        TextField(
                          controller: _passwordController,
                          obscureText: true,
                          decoration: const InputDecoration(
                            labelText: 'Password *',
                            hintText: 'Your MT5 password',
                            prefixIcon: Icon(Icons.lock),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        TextField(
                          controller: _serverController,
                          decoration: const InputDecoration(
                            labelText: 'Server',
                            hintText: 'e.g., MetaQuotes-Demo',
                            prefixIcon: Icon(Icons.dns),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        Row(
                          children: [
                            Checkbox(
                              value: _isLiveBroker,
                              onChanged: (val) =>
                                  setState(() => _isLiveBroker = val ?? false),
                            ),
                            const Text('Live Account'),
                            const SizedBox(width: AppSpacing.lg),
                            const Icon(Icons.warning,
                                color: Colors.orange, size: 20),
                            const SizedBox(width: AppSpacing.sm),
                            const Text(
                              'Real money trading',
                              style: TextStyle(
                                color: Colors.orange,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.md),
                        ElevatedButton.icon(
                          onPressed: _isAddingBroker ? null : _addBroker,
                          icon: const Icon(Icons.add),
                          label: _isAddingBroker
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2),
                                )
                              : const Text('Add Broker'),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: AppSpacing.lg),

                  // Existing Brokers
                  Text(
                    'Your Brokers (${_brokers.length})',
                    style: GoogleFonts.poppins(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),

                  if (_brokers.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        children: [
                          Icon(Icons.cloud_off_outlined,
                              size: 48, color: Colors.grey[400]),
                          const SizedBox(height: AppSpacing.md),
                          Text(
                            'No broker credentials yet',
                            style: GoogleFonts.roboto(
                              color: Colors.grey[600],
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _brokers.length,
                      itemBuilder: (context, index) {
                        final broker = _brokers[index];
                        return Card(
                          margin: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: Colors.blue[700],
                              child: Icon(
                                broker['is_live'] ?? false
                                    ? Icons.warning
                                    : Icons.check_circle,
                                color: Colors.white,
                              ),
                            ),
                            title: Text(broker['broker_name'] ?? 'Unknown'),
                            subtitle: Text(
                              'Account: ${broker['account_number']} | ${broker['is_live'] ?? false ? '🔴 LIVE' : '🔵 DEMO'}',
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete,
                                  color: Colors.red),
                              onPressed: () {
                                showDialog(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: const Text('Remove Broker?'),
                                    content: Text(
                                        'Remove ${broker['broker_name']} (${broker['account_number']})?'),
                                    actions: [
                                      TextButton(
                                        onPressed: () =>
                                            Navigator.pop(ctx),
                                        child: const Text('Cancel'),
                                      ),
                                      TextButton(
                                        onPressed: () {
                                          Navigator.pop(ctx);
                                          _removeBroker(
                                              broker['credential_id']);
                                        },
                                        child: const Text('Remove',
                                            style: TextStyle(
                                                color: Colors.red)),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                          ),
                        );
                      },
                    ),
                ],
              ),
            ),
    );
  }
}
