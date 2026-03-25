import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/user_models.dart';
import '../services/credential_manager.dart';

class CredentialSetupScreen extends StatefulWidget {
  const CredentialSetupScreen({Key? key}) : super(key: key);

  @override
  State<CredentialSetupScreen> createState() => _CredentialSetupScreenState();
}

class _CredentialSetupScreenState extends State<CredentialSetupScreen> {
  final _firstNameController = TextEditingController();
  final _lastNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _accountNumberController = TextEditingController();
  final _apiKeyController = TextEditingController();

  String? _selectedBrokerId = 'xm_global';
  String? _selectedAccountType = 'DEMO';
  bool _agreeToTerms = false;
  bool _isLoading = false;
  String? _error;

  @override
  void dispose() {
    _firstNameController.dispose();
    _lastNameController.dispose();
    _emailController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _accountNumberController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  void _handleRegistration() async {
    if (_passwordController.text != _confirmPasswordController.text) {
      setState(() => _error = 'Passwords do not match');
      return;
    }

    if (!_agreeToTerms) {
      setState(() => _error = 'Please agree to terms');
      return;
    }

    setState(() => _isLoading = true);

    final brokerInfo = BrokerConfig.supportedBrokers
        .firstWhere((b) => b.id == _selectedBrokerId);
    final credentialManager =
        Provider.of<CredentialManager>(context, listen: false);

    final success = await credentialManager.registerUser(
      _firstNameController.text,
      _lastNameController.text,
      _emailController.text,
      _usernameController.text,
      _passwordController.text,
      brokerId: _selectedBrokerId!,
      brokerName: brokerInfo.name,
      accountNumber: _accountNumberController.text,
      apiKey: _apiKeyController.text,
      accountType: _selectedAccountType!,
    );

    if (success) {
      if (mounted) Navigator.pop(context);
    } else {
      setState(() => _error = 'Registration failed');
    }

    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset(
              'assets/images/logo.jpeg',
              width: 40,
              height: 40,
              fit: BoxFit.contain,
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ZWESTA',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Text(
                  'TRADING SYSTEM',
                  style: TextStyle(fontSize: 10, color: Colors.cyanAccent),
                ),
              ],
            ),
          ],
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Logo Section
            Center(
              child: Image.asset(
                'assets/images/logo.jpeg',
                width: 100,
                height: 100,
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'ZWESTA TRADING SYSTEM',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: Colors.cyan,
                  letterSpacing: 1,
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Join Zwesta Trader',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Create your trading account',
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),

            // Account Details Section
            const Text(
              'Account Details',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _firstNameController,
              decoration: InputDecoration(
                hintText: 'First Name',
                prefixIcon: const Icon(Icons.person),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _lastNameController,
              decoration: InputDecoration(
                hintText: 'Last Name',
                prefixIcon: const Icon(Icons.person),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _emailController,
              decoration: InputDecoration(
                hintText: 'Email',
                prefixIcon: const Icon(Icons.email),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _usernameController,
              decoration: InputDecoration(
                hintText: 'Username',
                prefixIcon: const Icon(Icons.person_outline),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 24),

            // Broker Selection
            const Text(
              'Broker Selection',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: _selectedBrokerId,
              items: BrokerConfig.supportedBrokers
                  .map((broker) => DropdownMenuItem(
                        value: broker.id,
                        child: Text(broker.name),
                      ))
                  .toList(),
              onChanged: (value) => setState(() => _selectedBrokerId = value),
              decoration: InputDecoration(
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 24),

            // Account Type
            const Text(
              'Account Type',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ChoiceChip(
                    label: const Text('DEMO'),
                    selected: _selectedAccountType == 'DEMO',
                    onSelected: (selected) =>
                        setState(() => _selectedAccountType = 'DEMO'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ChoiceChip(
                    label: const Text('LIVE'),
                    selected: _selectedAccountType == 'LIVE',
                    onSelected: (selected) =>
                        setState(() => _selectedAccountType = 'LIVE'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // MT5 Credentials
            const Text(
              'MT5 Credentials',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _accountNumberController,
              decoration: InputDecoration(
                hintText: 'MT5 Account Number',
                prefixIcon: const Icon(Icons.numbers),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _apiKeyController,
              decoration: InputDecoration(
                hintText: 'API Key / Token',
                prefixIcon: const Icon(Icons.vpn_key),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 24),

            // Password Section
            const Text(
              'Security',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              decoration: InputDecoration(
                hintText: 'Password',
                prefixIcon: const Icon(Icons.lock),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _confirmPasswordController,
              obscureText: true,
              decoration: InputDecoration(
                hintText: 'Confirm Password',
                prefixIcon: const Icon(Icons.lock),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 16),

            // Terms Checkbox
            Row(
              children: [
                Checkbox(
                  value: _agreeToTerms,
                  onChanged: (value) => setState(() => _agreeToTerms = value ?? false),
                ),
                Expanded(
                  child: const Text('I agree to Terms of Service'),
                ),
              ],
            ),

            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  _error!,
                  style: const TextStyle(color: Colors.red),
                ),
              ),

            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                onPressed: _isLoading ? null : _handleRegistration,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.cyan,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text(
                        'Create Account',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.black,
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
