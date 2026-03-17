import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../widgets/logo_widget.dart';

class SymbolManagementScreen extends StatefulWidget {
  const SymbolManagementScreen({Key? key}) : super(key: key);

  @override
  State<SymbolManagementScreen> createState() => _SymbolManagementScreenState();
}

class _SymbolManagementScreenState extends State<SymbolManagementScreen> {
  final ApiService _apiService = ApiService();
  List<dynamic> _symbols = [];
  List<dynamic> _filteredSymbols = [];
  String _selectedType = 'All';
  bool _isLoading = true;
  String _searchQuery = '';

  final List<String> _symbolTypes = [
    'All',
    'Forex',
    'Crypto',
    'Commodity',
    'Stock',
    'Index'
  ];

  final List<String> _brokers = ['Exness', 'IG', 'OANDA', 'FXCM', 'Binance'];

  @override
  void initState() {
    super.initState();
    _loadSymbols();
  }

  Future<void> _loadSymbols() async {
    try {
      setState(() => _isLoading = true);
      final response = await _apiService.get('/api/symbols');

      if (response['success'] == true) {
        setState(() {
          _symbols = response['symbols'] ?? [];
          _applyFilters();
          _isLoading = false;
        });
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading symbols: $e'), duration: const Duration(seconds: 3)),
      );
      setState(() => _isLoading = false);
    }
  }

  void _applyFilters() {
    _filteredSymbols = _symbols.where((symbol) {
      bool matchesType = _selectedType == 'All' || symbol['symbol_type'] == _selectedType;
      bool matchesSearch = _searchQuery.isEmpty ||
          symbol['symbol'].toString().toLowerCase().contains(_searchQuery.toLowerCase()) ||
          symbol['name'].toString().toLowerCase().contains(_searchQuery.toLowerCase());
      return matchesType && matchesSearch;
    }).toList();

    setState(() {});
  }

  Future<void> _addSymbol() async {
    final formKey = GlobalKey<FormState>();
    String? symbol, name, type, broker;
    double? minPrice, maxPrice;

    await showDialog(
      context: context,
      builder: (BuildContext context) => Dialog(
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
                    'Add New Symbol',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Symbol (e.g., EURUSD)',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => symbol = value?.toUpperCase(),
                  ),
                  const SizedBox(height: 15),
                  TextFormField(
                    decoration: InputDecoration(
                      labelText: 'Name (e.g., Euro/USD)',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    validator: (value) => value?.isEmpty ?? true ? 'Required' : null,
                    onSaved: (value) => name = value,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      labelText: 'Type',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _symbolTypes.skip(1).map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                    onChanged: (value) => type = value,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                  const SizedBox(height: 15),
                  DropdownButtonFormField<String>(
                    decoration: InputDecoration(
                      labelText: 'Broker',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    items: _brokers.map((b) => DropdownMenuItem(value: b, child: Text(b))).toList(),
                    onChanged: (value) => broker = value,
                    validator: (value) => value == null ? 'Required' : null,
                  ),
                  const SizedBox(height: 15),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          decoration: InputDecoration(
                            labelText: 'Min Price',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: TextInputType.number,
                          onSaved: (value) => minPrice = double.tryParse(value ?? '0'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextFormField(
                          decoration: InputDecoration(
                            labelText: 'Max Price',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          keyboardType: TextInputType.number,
                          onSaved: (value) => maxPrice = double.tryParse(value ?? '0'),
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
                          if (formKey.currentState?.validate() ?? false) {
                            formKey.currentState?.save();
                            Navigator.pop(context);

                            try {
                              final response = await _apiService.post('/api/symbols/add', {
                                'symbol': symbol,
                                'name': name,
                                'symbol_type': type,
                                'broker': broker,
                                'min_price': minPrice,
                                'max_price': maxPrice,
                              });

                              if (response['success'] == true) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text(response['message']), duration: const Duration(seconds: 2)),
                                );
                                _loadSymbols();
                              }
                            } catch (e) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
                              );
                            }
                          }
                        },
                        child: const Text('Add Symbol'),
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

  Future<void> _deleteSymbol(String symbolId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Symbol'),
        content: const Text('Are you sure you want to delete this symbol?'),
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
        final response = await _apiService.delete('/api/symbols/$symbolId');
        if (response['success'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(response['message']), duration: const Duration(seconds: 2)),
          );
          _loadSymbols();
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), duration: const Duration(seconds: 3)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: const [
            LogoWidget(size: 40, showText: false),
            SizedBox(width: 12),
            Text('Symbol Management'),
          ],
        ),
        backgroundColor: Colors.deepPurple,
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Filters
                Padding(
                  padding: const EdgeInsets.all(15),
                  child: Column(
                    children: [
                      // Search Bar
                      TextField(
                        decoration: InputDecoration(
                          hintText: 'Search symbols...',
                          prefixIcon: const Icon(Icons.search),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                        onChanged: (value) {
                          setState(() => _searchQuery = value);
                          _applyFilters();
                        },
                      ),
                      const SizedBox(height: 10),
                      // Type Filter
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: _symbolTypes.map((type) {
                            bool isSelected = _selectedType == type;
                            return Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 5),
                              child: FilterChip(
                                label: Text(type),
                                selected: isSelected,
                                backgroundColor: Colors.grey.shade200,
                                selectedColor: Colors.deepPurple,
                                labelStyle: TextStyle(
                                  color: isSelected ? Colors.white : Colors.black,
                                ),
                                onSelected: (selected) {
                                  setState(() => _selectedType = type);
                                  _applyFilters();
                                },
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ),
                // Symbols List
                Expanded(
                  child: _filteredSymbols.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.search_off, size: 60, color: Colors.grey.shade400),
                              const SizedBox(height: 10),
                              Text(
                                'No symbols found',
                                style: TextStyle(fontSize: 16, color: Colors.grey.shade600),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.all(10),
                          itemCount: _filteredSymbols.length,
                          itemBuilder: (context, index) {
                            final symbol = _filteredSymbols[index];
                            return Card(
                              margin: const EdgeInsets.symmetric(vertical: 5),
                              child: ListTile(
                                title: Text(
                                  symbol['symbol'] ?? 'Unknown',
                                  style: const TextStyle(fontWeight: FontWeight.bold),
                                ),
                                subtitle: Text(
                                  '${symbol['name'] ?? 'N/A'} • ${symbol['symbol_type'] ?? 'N/A'} • ${symbol['broker'] ?? 'N/A'}',
                                  style: TextStyle(color: Colors.grey.shade600),
                                ),
                                trailing: IconButton(
                                  icon: const Icon(Icons.delete, color: Colors.red),
                                  onPressed: () => _deleteSymbol(symbol['symbol_id']),
                                ),
                              ),
                            );
                          },
                        ),
                ),
              ],
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addSymbol,
        backgroundColor: Colors.deepPurple,
        child: const Icon(Icons.add),
      ),
    );
  }
}
