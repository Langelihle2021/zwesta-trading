import 'package:flutter/material.dart';

class SimpleBotConfigurationScreen extends StatefulWidget {
  const SimpleBotConfigurationScreen({Key? key}) : super(key: key);

  @override
  State<SimpleBotConfigurationScreen> createState() =>
      _SimpleBotConfigurationScreenState();
}

class _SimpleBotConfigurationScreenState
    extends State<SimpleBotConfigurationScreen> {
  late TextEditingController _riskPerTradeController;
  late TextEditingController _maxDailyLossController;
  String _selectedRiskType = 'fixed';
  final List<String> _selectedPairs = [];
  final List<String> _selectedStrategies = [];

  final List<String> availablePairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];
  final List<String> availableStrategies = [
    'MA Crossover',
    'RSI',
    'MACD',
    'Bollinger Bands'
  ];

  @override
  void initState() {
    super.initState();
    _riskPerTradeController =
        TextEditingController(text: '100');
    _maxDailyLossController =
        TextEditingController(text: '500');
  }

  @override
  void dispose() {
    _riskPerTradeController.dispose();
    _maxDailyLossController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Text('Bot Configuration'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Risk Configuration
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Risk Configuration',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _riskPerTradeController,
                      decoration: const InputDecoration(
                        labelText: r'Risk Per Trade ($)',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _maxDailyLossController,
                      decoration: const InputDecoration(
                        labelText: r'Max Daily Loss ($)',
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 12),
                    DropdownButton<String>(
                      value: _selectedRiskType,
                      isExpanded: true,
                      items: ['fixed', 'percentage']
                          .map((type) => DropdownMenuItem(
                                value: type,
                                child: Text(type.toUpperCase()),
                              ))
                          .toList(),
                      onChanged: (value) {
                        setState(() => _selectedRiskType = value ?? 'fixed');
                      },
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Trading Pairs Selection
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Trading Pairs',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: availablePairs
                          .map(
                            (pair) => FilterChip(
                              label: Text(pair),
                              selected: _selectedPairs.contains(pair),
                              onSelected: (selected) {
                                setState(() {
                                  if (selected) {
                                    _selectedPairs.add(pair);
                                  } else {
                                    _selectedPairs.remove(pair);
                                  }
                                });
                              },
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Strategies Selection
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Trading Strategies',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      children: availableStrategies
                          .map(
                            (strategy) => FilterChip(
                              label: Text(strategy),
                              selected: _selectedStrategies.contains(strategy),
                              onSelected: (selected) {
                                setState(() {
                                  if (selected) {
                                    _selectedStrategies.add(strategy);
                                  } else {
                                    _selectedStrategies.remove(strategy);
                                  }
                                });
                              },
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Save Button
            ElevatedButton.icon(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Bot Configuration Saved!'),
                    duration: Duration(seconds: 2),
                  ),
                );
              },
              icon: const Icon(Icons.save),
              label: const Text('Save Configuration'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
}
