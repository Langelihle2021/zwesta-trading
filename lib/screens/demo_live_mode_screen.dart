import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:logger/logger.dart';

import '../utils/environment_config.dart';

class DemoLiveModeScreen extends StatefulWidget {
  const DemoLiveModeScreen({super.key});

  @override
  _DemoLiveModeScreenState createState() => _DemoLiveModeScreenState();
}

class _DemoLiveModeScreenState extends State<DemoLiveModeScreen> {
  final Logger logger = Logger();
  
  bool isDemoMode = true;
  bool isLoading = false;
  String? selectedMode;
  
  // Live credentials
  final liveAccountController = TextEditingController();
  final livePasswordController = TextEditingController();
  final liveServerController = TextEditingController();
  
  // Pre-live checklist
  bool understoodRisks = false;
  bool completedDemoTrading = false;
  bool reviewedStrategy = false;
  bool hasBackupFunds = false;

  @override
  void initState() {
    super.initState();
    _loadCurrentMode();
  }

  Future<void> _loadCurrentMode() async {
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/trading-mode'),
        headers: {'Authorization': 'Bearer ${EnvironmentConfig.apiKey}'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          isDemoMode = data['mode'] == 'DEMO';
          selectedMode = isDemoMode ? 'DEMO' : 'LIVE';
        });
      }
    } catch (e) {
      logger.e('Error loading trading mode: $e');
      setState(() => selectedMode = 'DEMO');
    }
  }

  Future<void> _switchToDemo() async {
    setState(() => isLoading = true);
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/switch-mode'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${EnvironmentConfig.apiKey}',
        },
        body: jsonEncode({'mode': 'DEMO'}),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        setState(() {
          isDemoMode = true;
          selectedMode = 'DEMO';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Switched to DEMO Mode - Safe learning environment'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      logger.e('Error switching to demo: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> _switchToLive() async {
    if (!_validatePreLiveChecklist()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('⚠️ Please complete all pre-live requirements'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    if (liveAccountController.text.isEmpty ||
        livePasswordController.text.isEmpty ||
        liveServerController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('❌ Please fill in all live credentials'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    // Confirm before switching to live
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('⚠️ Switch to LIVE Trading?'),
        content: Text(
          'You are about to switch to LIVE trading with real money.\n\n'
          'Account: ${liveAccountController.text}\n'
          'Server: ${liveServerController.text}\n\n'
          'Are you absolutely sure?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Yes, Go LIVE',
              style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => isLoading = true);
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/user/switch-mode'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${EnvironmentConfig.apiKey}',
        },
        body: jsonEncode({
          'mode': 'LIVE',
          'account': liveAccountController.text,
          'server': liveServerController.text,
        }),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        setState(() {
          isDemoMode = false;
          selectedMode = 'LIVE';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Switched to LIVE Trading Mode - Real Money Active'),
            backgroundColor: Colors.red,
            duration: Duration(seconds: 3),
          ),
        );
        Navigator.pop(context); // Close dialog
      }
    } catch (e) {
      logger.e('Error switching to live: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => isLoading = false);
    }
  }

  bool _validatePreLiveChecklist() => understoodRisks && completedDemoTrading && reviewedStrategy && hasBackupFunds;

  @override
  Widget build(BuildContext context) => DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Trading Mode'),
          centerTitle: true,
          bottom: const TabBar(
            tabs: [
              Tab(text: '📚 Demo Mode (Learning)'),
              Tab(text: '💰 Live Mode (Real Money)'),
            ],
          ),
        ),
        body: isLoading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                children: [
                  // DEMO TAB
                  SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Demo Status Card
                        Card(
                          color: Colors.blue.shade50,
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  isDemoMode
                                      ? '✅ Currently in DEMO Mode'
                                      : '❌ Not in DEMO Mode',
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                    color: isDemoMode ? Colors.green : Colors.red,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Practice trading with virtual money. No real funds at risk.',
                                  style: TextStyle(color: Colors.grey.shade700),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                        
                        // Learning Benefits
                        const Text(
                          '🎓 Demo Mode Benefits',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        _buildBenefitItem(
                          '📊 Risk-Free Practice',
                          'Learn trading strategies without losing real money',
                        ),
                        _buildBenefitItem(
                          '🤖 Test Bots',
                          'Experiment with different trading bots and settings',
                        ),
                        _buildBenefitItem(
                          '📈 Understand Markets',
                          'Learn how price movements work and market behavior',
                        ),
                        _buildBenefitItem(
                          '✅ Build Confidence',
                          'Gain experience before committing real capital',
                        ),
                        const SizedBox(height: 24),

                        // Learning Resources
                        const Text(
                          '📚 Learning Resources',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        _buildResourceTile(
                          '1️⃣ Trading Basics',
                          'Learn forex, crypto, and commodity trading fundamentals',
                        ),
                        _buildResourceTile(
                          '2️⃣ Strategy Development',
                          'Develop and test your own trading strategies',
                        ),
                        _buildResourceTile(
                          '3️⃣ Risk Management',
                          'Master position sizing and stop-loss techniques',
                        ),
                        _buildResourceTile(
                          '4️⃣ Bot Configuration',
                          'Configure and optimize trading bots for your strategy',
                        ),
                        const SizedBox(height: 24),

                        // Switch to Live Button
                        if (!isDemoMode)
                          SizedBox(
                            width: double.infinity,
                            child: ElevatedButton.icon(
                              onPressed: _switchToDemo,
                              icon: const Icon(Icons.school),
                              label: const Text('Switch to Demo Mode'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.blue,
                                padding: const EdgeInsets.symmetric(vertical: 12),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),

                  // LIVE TAB
                  SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Live Status Card
                        Card(
                          color: isDemoMode ? Colors.red.shade50 : Colors.green.shade50,
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  isDemoMode
                                      ? '⏳ DEMO Mode Active'
                                      : '🔴 LIVE Trading Active',
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                    color: isDemoMode ? Colors.orange : Colors.red,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  isDemoMode
                                      ? 'Complete the pre-live requirements to enable live trading'
                                      : 'Real money trading is active. Trade carefully!',
                                  style: TextStyle(color: Colors.grey.shade700),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Pre-Live Checklist
                        const Text(
                          '✅ Pre-Live Requirements',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        _buildChecklistItem(
                          'I understand the risks of live trading',
                          understoodRisks,
                          (value) => setState(() => understoodRisks = value ?? false),
                        ),
                        _buildChecklistItem(
                          'I have completed demo trading practice',
                          completedDemoTrading,
                          (value) => setState(() => completedDemoTrading = value ?? false),
                        ),
                        _buildChecklistItem(
                          'I have reviewed and tested my strategy',
                          reviewedStrategy,
                          (value) => setState(() => reviewedStrategy = value ?? false),
                        ),
                        _buildChecklistItem(
                          'I have backup funds for emergencies',
                          hasBackupFunds,
                          (value) => setState(() => hasBackupFunds = value ?? false),
                        ),
                        const SizedBox(height: 24),

                        // Live Credentials
                        if (!isDemoMode)
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '🔐 Your Live Credentials',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: liveAccountController,
                                decoration: const InputDecoration(
                                  labelText: 'Account Number',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.account_circle),
                                ),
                                readOnly: true,
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: liveServerController,
                                decoration: const InputDecoration(
                                  labelText: 'Server',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.cloud),
                                ),
                                readOnly: true,
                              ),
                              const SizedBox(height: 24),
                              const Text(
                                '⚠️ Live Trading is Active!',
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.red,
                                ),
                              ),
                              const SizedBox(height: 8),
                              ElevatedButton.icon(
                                onPressed: _switchToDemo,
                                icon: const Icon(Icons.school),
                                label: const Text('Switch Back to Demo'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.orange,
                                  foregroundColor: Colors.white,
                                ),
                              ),
                            ],
                          )
                        else
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '🔐 Live Account Credentials',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: liveAccountController,
                                decoration: const InputDecoration(
                                  labelText: 'Account Number',
                                  hintText: 'e.g., 295619855',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.account_circle),
                                ),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: livePasswordController,
                                obscureText: true,
                                decoration: const InputDecoration(
                                  labelText: 'Password',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.lock),
                                ),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: liveServerController,
                                decoration: const InputDecoration(
                                  labelText: 'Server',
                                  hintText: 'e.g., Exness-Real',
                                  border: OutlineInputBorder(),
                                  prefixIcon: Icon(Icons.cloud),
                                ),
                              ),
                              const SizedBox(height: 24),
                              SizedBox(
                                width: double.infinity,
                                child: ElevatedButton.icon(
                                  onPressed: _validatePreLiveChecklist()
                                      ? _switchToLive
                                      : null,
                                  icon: const Icon(Icons.check_circle),
                                  label: const Text('Switch to Live Trading'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.red,
                                    padding: const EdgeInsets.symmetric(vertical: 12),
                                  ),
                                ),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
                ],
              ),
      ),
    );

  Widget _buildBenefitItem(String title, String description) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 40, child: Text(title.substring(0, 1))),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: TextStyle(color: Colors.grey.shade700, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );

  Widget _buildResourceTile(String title, String description) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: ListTile(
          title: Text(title),
          subtitle: Text(description),
          trailing: const Icon(Icons.arrow_forward_ios, size: 16),
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Resource coming soon!')),
            );
          },
        ),
      ),
    );

  Widget _buildChecklistItem(
    String label,
    bool value,
    Function(bool?) onChanged,
  ) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: CheckboxListTile(
        title: Text(label),
        value: value,
        onChanged: onChanged,
        activeColor: Colors.green,
      ),
    );

  @override
  void dispose() {
    liveAccountController.dispose();
    livePasswordController.dispose();
    liveServerController.dispose();
    super.dispose();
  }
}
