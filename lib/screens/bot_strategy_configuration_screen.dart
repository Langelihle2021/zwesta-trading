import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../widgets/logo_widget.dart';

class BotStrategyConfigurationScreen extends StatefulWidget {
  const BotStrategyConfigurationScreen({Key? key}) : super(key: key);

  @override
  State<BotStrategyConfigurationScreen> createState() => _BotStrategyConfigurationScreenState();
}

class _BotStrategyConfigurationScreenState extends State<BotStrategyConfigurationScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _strategies = [];
  dynamic _selectedStrategy;
  bool _isLoading = true;

  final List<String> _strategyTypes = [
    'TREND_FOLLOW',
    'MEAN_REVERSION',
    'SCALPING',
    'ARBITRAGE',
    'GRID_TRADING',
    'DCA'
  ];

  final List<String> _riskLevels = ['LOW', 'MEDIUM', 'HIGH'];

  final List<String> _commonSymbols = [
    // Exness Standard account symbols (no 'm' suffix)
    'BTCUSD',   // Bitcoin
    'ETHUSD',   // Ethereum
    'EURUSD',   // Euro
    'USDJPY',   // Japanese Yen
    'XAUUSD',   // Gold
  ];

  @override
  void initState() {
    super.initState();
    _loadStrategies();
  }

  Future<void> _loadStrategies() async {
    try {
      setState(() => _isLoading = true);
      final response = await _apiService.get('/api/strategies');

      if (response['success'] == true) {
        setState(() {
          _strategies = response['strategies'] ?? [];
          _isLoading = false;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading strategies: $e'), duration: const Duration(seconds: 3)),
      );
      setState(() => _isLoading = false);
    }
  }

  Future<void> _createStrategy() async {
    final formKey = GlobalKey<FormState>();
    String? strategyName, description, strategyType, riskLevel;
    final selectedSymbols = <String>[];
    double? profitTarget, stopLoss;
    final parameters = <String, dynamic>{};

    await showDialog(
      context: context,
      builder: (context) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Create Bot Strategy',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Strategy Name',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      hintText: 'e.g., Quick Scalper, Gold Trend',
                    ),
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => strategyName = value,
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Description',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    maxLines: 2,
                    onSaved: (value) => description = value,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      labelText: 'Strategy Type',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _strategyTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                    onChanged: (value) => strategyType = value,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      labelText: 'Risk Level',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _riskLevels.map((l) => DropdownMenuItem(value: l, child: Text(l))).toList(),
                    onChanged: (value) => riskLevel = value,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                  const SizedBox(height: 15),
                  // Multi-select for symbols
                  const Text('Trading Symbols:', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Column(
                    children: _commonSymbols.map((symbol) => CheckboxListTile(
                        title: Text(symbol),
                        value: selectedSymbols.contains(symbol),
                        onChanged: (value) {
                          if (value ?? false) {
                            selectedSymbols.add(symbol);
                          } else {
                            selectedSymbols.remove(symbol);
                          }
                        },
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                      )).toList(),
                  ),
                  const SizedBox(height: 15),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          decoration: InputDecoration(
                            labelText: 'Profit Target %',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                          onSaved: (value) => profitTarget = double.tryParse(value ?? '0'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextFormField(
                          decoration: InputDecoration(
                            labelText: 'Stop Loss %',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                          onSaved: (value) => stopLoss = double.tryParse(value ?? '0'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton(
                        onPressed: () async {
                          if (selectedSymbols.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Please select at least one symbol'),
                                duration: Duration(seconds: 2),
                              ),
                            );
                            return;
                          }

                          if (formKey.currentState?.validate() ?? false) {
                            formKey.currentState?.save();
                            Navigator.pop(context);

                            try {
                              final response = await _apiService.post('/api/strategies/create', {
                                'strategy_name': strategyName,
                                'description': description,
                                'strategy_type': strategyType,
                                'risk_level': riskLevel,
                                'symbols': selectedSymbols,
                                'profit_target': profitTarget,
                                'stop_loss': stopLoss,
                                'parameters': parameters,
                              });

                              if (response['success'] == true) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(response['message']),
                                    duration: const Duration(seconds: 2),
                                  ),
                                );
                                _loadStrategies();
                              }
                            } catch (e) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                              );
                            }
                          }
                        },
                        child: const Text('Create Strategy'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _editStrategy(dynamic strategy) async {
    final formKey = GlobalKey<FormState>();
    late String strategyName;
    late String description;
    late String strategyType;
    late String riskLevel;
    late double profitTarget;
    late double stopLoss;
    var selectedSymbols = <String>[];

    // Pre-fill form with existing values
    strategyName = strategy['strategy_name'];
    description = strategy['description'] ?? '';
    strategyType = strategy['strategy_type'];
    riskLevel = strategy['risk_level'];
    profitTarget = (strategy['profit_target'] ?? 0).toDouble();
    stopLoss = (strategy['stop_loss'] ?? 0).toDouble();

    try {
      if (strategy['symbols'] is String) {
        selectedSymbols = List<String>.from(jsonDecode(strategy['symbols']));
      } else if (strategy['symbols'] is List) {
        selectedSymbols = List<String>.from(strategy['symbols']);
      }
    } catch (e) {
      selectedSymbols = [];
    }

    await showDialog(
      context: context,
      builder: (context) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Edit Bot Strategy',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    initialValue: strategyName,
                    decoration: InputDecoration(
                      labelText: 'Strategy Name',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    onChanged: (value) => strategyName = value,
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    initialValue: description,
                    decoration: InputDecoration(
                      labelText: 'Description',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    maxLines: 2,
                    onChanged: (value) => description = value,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    value: strategyType,
                    decoration: InputDecoration(
                      labelText: 'Strategy Type',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _strategyTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                    onChanged: (value) => strategyType = value!,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    value: riskLevel,
                    decoration: InputDecoration(
                      labelText: 'Risk Level',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _riskLevels.map((l) => DropdownMenuItem(value: l, child: Text(l))).toList(),
                    onChanged: (value) => riskLevel = value!,
                  ),
                  const SizedBox(height: 15),
                  const Text('Trading Symbols:', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Column(
                    children: _commonSymbols.map((symbol) => CheckboxListTile(
                        title: Text(symbol),
                        value: selectedSymbols.contains(symbol),
                        onChanged: (value) {
                          if (value ?? false) {
                            selectedSymbols.add(symbol);
                          } else {
                            selectedSymbols.remove(symbol);
                          }
                        },
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                      )).toList(),
                  ),
                  const SizedBox(height: 15),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          initialValue: profitTarget.toString(),
                          decoration: InputDecoration(
                            labelText: 'Profit Target %',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (value) => profitTarget = double.tryParse(value) ?? 0,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextFormField(
                          initialValue: stopLoss.toString(),
                          decoration: InputDecoration(
                            labelText: 'Stop Loss %',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (value) => stopLoss = double.tryParse(value) ?? 0,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Cancel'),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton(
                        onPressed: () async {
                          Navigator.pop(context);

                          try {
                            final response = await _apiService.put(
                              '/api/strategies/${strategy['strategy_id']}',
                              {
                                'strategy_name': strategyName,
                                'description': description,
                                'strategy_type': strategyType,
                                'risk_level': riskLevel,
                                'symbols': selectedSymbols,
                                'profit_target': profitTarget,
                                'stop_loss': stopLoss,
                              },
                            );

                            if (response['success'] == true) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(response['message']),
                                  duration: const Duration(seconds: 2),
                                ),
                              );
                              _loadStrategies();
                            }
                          } catch (e) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                            );
                          }
                        },
                        child: const Text('Update Strategy'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _deleteStrategy(String strategyId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Strategy'),
        content: const Text('Are you sure you want to delete this strategy?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm ?? false) {
      try {
        final response = await _apiService.delete('/api/strategies/$strategyId');
        if (response['success'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(response['message']), duration: const Duration(seconds: 2)),
          );
          _loadStrategies();
          setState(() => _selectedStrategy = null);
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Bot Strategy Configuration'),
          ],
        ),
        backgroundColor: Colors.deepPurple,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _strategies.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.psychology, size: 80, color: Colors.grey.shade300),
                      const SizedBox(height: 20),
                      Text(
                        'No strategies created yet',
                        style: TextStyle(fontSize: 16, color: Colors.grey.shade600),
                      ),
                      const SizedBox(height: 20),
                      ElevatedButton.icon(
                        onPressed: _createStrategy,
                        icon: const Icon(Icons.add),
                        label: const Text('Create Your First Strategy'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.deepPurple,
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                        ),
                      ),
                    ],
                  ),
                )
              : Column(
                  children: [
                    // Header with Add Button
                    Padding(
                      padding: const EdgeInsets.all(15),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Strategies (${_strategies.length})',
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                          ),
                          ElevatedButton.icon(
                            onPressed: _createStrategy,
                            icon: const Icon(Icons.add),
                            label: const Text('New Strategy'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.deepPurple,
                            ),
                          ),
                        ],
                      ),
                    ),
                    // Strategies Grid
                    Expanded(
                      child: GridView.builder(
                        padding: const EdgeInsets.all(15),
                        gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                          maxCrossAxisExtent: 400,
                          childAspectRatio: 1.2,
                          crossAxisSpacing: 15,
                          mainAxisSpacing: 15,
                        ),
                        itemCount: _strategies.length,
                        itemBuilder: (context, index) {
                          final strategy = _strategies[index];
                          var symbols = <String>[];
                          try {
                            if (strategy['symbols'] is String) {
                              symbols = List<String>.from(jsonDecode(strategy['symbols']));
                            } else if (strategy['symbols'] is List) {
                              symbols = List<String>.from(strategy['symbols']);
                            }
                          } catch (e) {
                            symbols = [];
                          }

                          return GestureDetector(
                            onTap: () => setState(() => _selectedStrategy = strategy),
                            child: Card(
                              elevation: _selectedStrategy == strategy ? 8 : 2,
                              color: _selectedStrategy == strategy ? Colors.deepPurple.withAlpha(50) : null,
                              child: Padding(
                                padding: const EdgeInsets.all(15),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Expanded(
                                          child: Text(
                                            strategy['strategy_name'],
                                            style: const TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                            ),
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                        PopupMenuButton(
                                          itemBuilder: (context) => [
                                            PopupMenuItem(
                                              child: const Text('Edit'),
                                              onTap: () => _editStrategy(strategy),
                                            ),
                                            PopupMenuItem(
                                              child: const Text('Delete', style: TextStyle(color: Colors.red)),
                                              onTap: () => _deleteStrategy(strategy['strategy_id']),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Row(
                                      children: [
                                        Chip(
                                          label: Text(strategy['strategy_type']),
                                          backgroundColor: Colors.blue.withAlpha(100),
                                          labelStyle: const TextStyle(fontSize: 12),
                                        ),
                                        const SizedBox(width: 5),
                                        Chip(
                                          label: Text(strategy['risk_level']),
                                          backgroundColor: strategy['risk_level'] == 'HIGH'
                                              ? Colors.red.withAlpha(100)
                                              : strategy['risk_level'] == 'MEDIUM'
                                                  ? Colors.orange.withAlpha(100)
                                                  : Colors.green.withAlpha(100),
                                          labelStyle: const TextStyle(fontSize: 12),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 10),
                                    Text(
                                      strategy['description'] ?? 'No description',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
                                    ),
                                    const SizedBox(height: 10),
                                    Text(
                                      'Symbols: ${symbols.join(", ")}',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                                    ),
                                    const Spacer(),
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Text(
                                          'TP: ${strategy['profit_target']}%',
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                        ),
                                        Text(
                                          'SL: ${strategy['stop_loss']}%',
                                          style: const TextStyle(
                                            fontSize: 12,
                                            fontWeight: FontWeight.bold,
                                            color: Colors.red,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
    );
}
