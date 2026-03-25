import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/bot_service.dart';

class BotConfigurationScreen extends StatefulWidget {
  final String accountId;

  const BotConfigurationScreen({
    Key? key,
    required this.accountId,
  }) : super(key: key);

  @override
  State<BotConfigurationScreen> createState() => _BotConfigurationScreenState();
}

class _BotConfigurationScreenState extends State<BotConfigurationScreen> {
  late TextEditingController _riskAmountController;
  late TextEditingController _dailyLossController;
  late String _selectedRiskType;
  late List<String> _selectedPairs;
  late bool _enableScalping;
  late bool _enableEconomicEvents;

  final List<String> _availablePairs = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF',
    'AUDUSD', 'USDCAD', 'NZDUSD',
    'GOLD', 'WTI', 'NATGAS',
    'BTCUSD', 'ETHUSD', 'LTCUSD', 'XRPUSD'
  ];

  @override
  void initState() {
    super.initState();
    final botService = context.read<BotService>();
    botService.createConfig(widget.accountId);

    final config = botService.getConfig(widget.accountId)!;
    _riskAmountController = TextEditingController(text: config.riskAmount.toString());
    _dailyLossController = TextEditingController(text: config.maxDailyLossLimit.toString());
    _selectedRiskType = config.riskType;
    _selectedPairs = List.from(config.tradingPairs);
    _enableScalping = config.enableScalping;
    _enableEconomicEvents = config.enableEconomicEventTrading;
  }

  @override
  void dispose() {
    _riskAmountController.dispose();
    _dailyLossController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.grey.shade900,
        title: Row(
          children: [
            Image.asset(
              'assets/images/logo.jpeg',
              height: 32,
              width: 32,
              fit: BoxFit.contain,
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ZWESTA BOT CONFIG',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  'Configure your trading bot',
                  style: TextStyle(
                    color: Colors.cyan,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      body: Consumer<BotService>(
        builder: (context, botService, _) {
          final config = botService.getConfig(widget.accountId);
          if (config == null) {
            return const Center(child: CircularProgressIndicator());
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Bot Status Card
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Bot Status',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Bot Status',
                                style: TextStyle(color: Colors.grey),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                config.isEnabled ? 'ACTIVE' : 'INACTIVE',
                                style: TextStyle(
                                  color: config.isEnabled ? Colors.green : Colors.red,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          Switch(
                            value: config.isEnabled,
                            activeColor: Colors.green,
                            onChanged: (value) {
                              botService.toggleBot(widget.accountId, value);
                            },
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Risk Settings
              const Text(
                'Risk Management',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),

              // Risk Type Selector
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Risk Type',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: RadioListTile<String>(
                              title: const Text('\$ Fixed Amount', style: TextStyle(color: Colors.white, fontSize: 12)),
                              value: 'fixed',
                              groupValue: _selectedRiskType,
                              onChanged: (value) {
                                setState(() => _selectedRiskType = value!);
                              },
                              activeColor: Colors.cyan,
                              dense: true,
                            ),
                          ),
                          Expanded(
                            child: RadioListTile<String>(
                              title: const Text('% Percentage', style: TextStyle(color: Colors.white, fontSize: 12)),
                              value: 'percentage',
                              groupValue: _selectedRiskType,
                              onChanged: (value) {
                                setState(() => _selectedRiskType = value!);
                              },
                              activeColor: Colors.cyan,
                              dense: true,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Risk Amount
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _selectedRiskType == 'fixed'
                          ? 'Risk per Trade (\$)'
                          : 'Risk per Trade (%)',
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _riskAmountController,
                        style: const TextStyle(color: Colors.white),
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: InputDecoration(
                          hintText: _selectedRiskType == 'fixed' ? '\$10.00' : '2%',
                          hintStyle: const TextStyle(color: Colors.grey),
                          border: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan, width: 2),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Daily Loss Limit
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Max Daily Loss Limit (\$)',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _dailyLossController,
                        style: const TextStyle(color: Colors.white),
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: InputDecoration(
                          hintText: '\$100.00',
                          hintStyle: const TextStyle(color: Colors.grey),
                          border: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderSide: const BorderSide(color: Colors.cyan, width: 2),
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Bot stops trading for the day if loss limit is reached',
                        style: TextStyle(color: Colors.amber, fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Trading Pairs
              const Text(
                'Trading Pairs',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Select pairs to trade',
                        style: TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _availablePairs.map((pair) {
                          final isSelected = _selectedPairs.contains(pair);
                          return FilterChip(
                            label: Text(
                              pair,
                              style: TextStyle(
                                color: isSelected ? Colors.black : Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            backgroundColor: isSelected ? Colors.cyan : Colors.grey.shade700,
                            onSelected: (selected) {
                              setState(() {
                                if (selected) {
                                  _selectedPairs.add(pair);
                                } else {
                                  _selectedPairs.remove(pair);
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
              const SizedBox(height: 20),

              // Bot Strategies
              const Text(
                'Bot Strategies',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Card(
                color: Colors.grey.shade800,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      CheckboxListTile(
                        title: const Text(
                          'Scalping (Multiple trades daily)',
                          style: TextStyle(color: Colors.white),
                        ),
                        subtitle: const Text(
                          'Quick trades with small stops',
                          style: TextStyle(color: Colors.grey, fontSize: 11),
                        ),
                        value: _enableScalping,
                        onChanged: (value) {
                          setState(() => _enableScalping = value ?? true);
                        },
                        activeColor: Colors.cyan,
                      ),
                      const Divider(color: Colors.grey),
                      CheckboxListTile(
                        title: const Text(
                          'Economic Event Trading',
                          style: TextStyle(color: Colors.white),
                        ),
                        subtitle: const Text(
                          'Trade around economic news',
                          style: TextStyle(color: Colors.grey, fontSize: 11),
                        ),
                        value: _enableEconomicEvents,
                        onChanged: (value) {
                          setState(() => _enableEconomicEvents = value ?? true);
                        },
                        activeColor: Colors.cyan,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Save Button
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.cyan,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                onPressed: _saveConfiguration,
                child: const Text(
                  'Save Configuration',
                  style: TextStyle(
                    color: Colors.black,
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
              ),
              const SizedBox(height: 10),

              // Info Card
              Card(
                color: Colors.blue.shade900,
                child: const Padding(
                  padding: EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '💡 Billing Information',
                        style: TextStyle(
                          color: Colors.cyan,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        '• Monthly Fee: R1000',
                        style: TextStyle(color: Colors.white, fontSize: 12),
                      ),
                      Text(
                        '• Profit Commission: 15%',
                        style: TextStyle(color: Colors.white, fontSize: 12),
                      ),
                      Text(
                        '• Example: R1000 profit → R150 commission + R1000 fee',
                        style: TextStyle(color: Colors.amber, fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
            ],
          );
        },
      ),
    );
  }

  void _saveConfiguration() async {
    final botService = context.read<BotService>();

    try {
      final riskAmount = double.parse(_riskAmountController.text);
      final maxDailyLoss = double.parse(_dailyLossController.text);

      if (_selectedPairs.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please select at least one trading pair')),
        );
        return;
      }

      await botService.updateRiskSettings(
        widget.accountId,
        _selectedRiskType,
        riskAmount,
        maxDailyLoss,
      );

      await botService.updateTradingPairs(widget.accountId, _selectedPairs);

      await botService.updateBotStrategies(
        widget.accountId,
        _enableScalping,
        _enableEconomicEvents,
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Bot configuration saved successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pop(context);
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: Invalid input - $e')),
      );
    }
  }
}
