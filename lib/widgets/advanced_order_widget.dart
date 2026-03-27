import 'package:flutter/material.dart';
import '../services/advanced_order_service.dart';
import 'package:google_fonts/google_fonts.dart';

class AdvancedOrderWidget extends StatefulWidget {
  final String brokerName;
  final String accountId;
  final String sessionToken;
  final VoidCallback? onOrderPlaced;

  const AdvancedOrderWidget({
    Key? key,
    required this.brokerName,
    required this.accountId,
    required this.sessionToken,
    this.onOrderPlaced,
  }) : super(key: key);

  @override
  State<AdvancedOrderWidget> createState() => _AdvancedOrderWidgetState();
}

class _AdvancedOrderWidgetState extends State<AdvancedOrderWidget> {
  late TextEditingController _symbolController;
  late TextEditingController _quantityController;
  late TextEditingController _limitPriceController;
  late TextEditingController _stopPriceController;
  late TextEditingController _takeProfitController;
  late TextEditingController _stopLossController;
  late TextEditingController _trailingStopPipsController;

  OrderType _selectedOrderType = OrderType.market;
  OrderDirection _selectedDirection = OrderDirection.buy;
  bool _useTrailingStop = false;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _symbolController = TextEditingController();
    _quantityController = TextEditingController();
    _limitPriceController = TextEditingController();
    _stopPriceController = TextEditingController();
    _takeProfitController = TextEditingController();
    _stopLossController = TextEditingController();
    _trailingStopPipsController = TextEditingController();
  }

  @override
  void dispose() {
    _symbolController.dispose();
    _quantityController.dispose();
    _limitPriceController.dispose();
    _stopPriceController.dispose();
    _takeProfitController.dispose();
    _stopLossController.dispose();
    _trailingStopPipsController.dispose();
    super.dispose();
  }

  Future<void> _submitOrder() async {
    // Validate required fields
    if (_symbolController.text.isEmpty) {
      _showError('Please enter a symbol');
      return;
    }

    if (_quantityController.text.isEmpty) {
      _showError('Please enter quantity');
      return;
    }

    final quantity = double.tryParse(_quantityController.text);
    if (quantity == null || quantity <= 0) {
      _showError('Quantity must be a positive number');
      return;
    }

    // Parse optional fields
    final limitPrice = _limitPriceController.text.isNotEmpty
        ? double.tryParse(_limitPriceController.text)
        : null;
    final stopPrice = _stopPriceController.text.isNotEmpty
        ? double.tryParse(_stopPriceController.text)
        : null;
    final takeProfit = _takeProfitController.text.isNotEmpty
        ? double.tryParse(_takeProfitController.text)
        : null;
    final stopLoss = _stopLossController.text.isNotEmpty
        ? double.tryParse(_stopLossController.text)
        : null;
    final trailingStopPips = _trailingStopPipsController.text.isNotEmpty
        ? double.tryParse(_trailingStopPipsController.text)
        : null;

    // Create advanced order
    final order = AdvancedOrder(
      symbol: _symbolController.text.toUpperCase(),
      orderType: _selectedOrderType,
      direction: _selectedDirection,
      quantity: quantity,
      limitPrice: limitPrice,
      stopPrice: stopPrice,
      takeProfit: takeProfit,
      stopLoss: stopLoss,
      trailingStop: _useTrailingStop,
      trailingStopPips: trailingStopPips,
      brokerName: widget.brokerName,
      accountId: widget.accountId,
      sessionToken: widget.sessionToken,
    );

    // Validate order
    final validation = await AdvancedOrderService.validateOrder(order);
    if (validation['valid'] != true) {
      final warnings = List<String>.from(validation['warnings'] ?? []);
      _showError('Validation failed:\n${warnings.join("\n")}');
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      final result = await AdvancedOrderService.placeAdvancedOrder(order);

      if (!mounted) return;

      if (result['success'] == true) {
        _showSuccess(
          'Order placed successfully!\nOrder ID: ${result['order_id']}\nEntry Price: ${result['entry_price']}',
        );
        _clearForm();
        widget.onOrderPlaced?.call();
      } else {
        _showError('Order failed: ${result['error']}');
      }
    } catch (e) {
      _showError('Exception: $e');
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  void _clearForm() {
    _symbolController.clear();
    _quantityController.clear();
    _limitPriceController.clear();
    _stopPriceController.clear();
    _takeProfitController.clear();
    _stopLossController.clear();
    _trailingStopPipsController.clear();
    setState(() {
      _selectedOrderType = OrderType.market;
      _selectedDirection = OrderDirection.buy;
      _useTrailingStop = false;
    });
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 5),
      ),
    );
  }

  void _showSuccess(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.green,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '🚀 Advanced Order',
              style: GoogleFonts.poppins(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 16),

            // ==================== SYMBOL ====================
            Text('Trading Pair', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            TextField(
              controller: _symbolController,
              decoration: InputDecoration(
                labelText: 'Symbol (e.g., EURUSD, BTCUSDT)',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                prefixIcon: const Icon(Icons.trending_up),
              ),
            ),
            const SizedBox(height: 16),

            // ==================== DIRECTION ====================
            Text('Order Direction', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: SegmentedButton<OrderDirection>(
                    segments: const [
                      ButtonSegment(
                        value: OrderDirection.buy,
                        label: Text('BUY'),
                        icon: Icon(Icons.trending_up),
                      ),
                      ButtonSegment(
                        value: OrderDirection.sell,
                        label: Text('SELL'),
                        icon: Icon(Icons.trending_down),
                      ),
                    ],
                    selected: {_selectedDirection},
                    onSelectionChanged: (Set<OrderDirection> newSelection) {
                      setState(() => _selectedDirection = newSelection.first);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // ==================== QUANTITY ====================
            Text('Quantity', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            TextField(
              controller: _quantityController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                labelText: 'Order size',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
                prefixIcon: const Icon(Icons.functions),
              ),
            ),
            const SizedBox(height: 16),

            // ==================== ORDER TYPE ====================
            Text('Order Type', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: DropdownButton<OrderType>(
                  value: _selectedOrderType,
                  isExpanded: true,
                  underline: const SizedBox(),
                  onChanged: (OrderType? newValue) {
                    if (newValue != null) {
                      setState(() => _selectedOrderType = newValue);
                    }
                  },
                  items: const [
                    DropdownMenuItem(
                      value: OrderType.market,
                      child: Text('📊 Market - Execute immediately'),
                    ),
                    DropdownMenuItem(
                      value: OrderType.limit,
                      child: Text('📍 Limit - Execute at specific price'),
                    ),
                    DropdownMenuItem(
                      value: OrderType.stop,
                      child: Text('⏹️ Stop - Trigger at price level'),
                    ),
                    DropdownMenuItem(
                      value: OrderType.stopLimit,
                      child: Text('⏹️📍 Stop-Limit - Stop + Limit'),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // ==================== ORDER TYPE SPECIFIC FIELDS ====================
            if (_selectedOrderType == OrderType.limit ||
                _selectedOrderType == OrderType.stopLimit) ...[
              Text('Limit Price', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              TextField(
                controller: _limitPriceController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Price to execute at or better',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.price_check),
                ),
              ),
              const SizedBox(height: 16),
            ],
            if (_selectedOrderType == OrderType.stop ||
                _selectedOrderType == OrderType.stopLimit) ...[
              Text('Stop Price', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              TextField(
                controller: _stopPriceController,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Trigger price for order activation',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  prefixIcon: const Icon(Icons.stop_circle),
                ),
              ),
              const SizedBox(height: 16),
            ],

            // ==================== TAKE PROFIT & STOP LOSS ====================
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '🎯 Risk Management',
                    style: GoogleFonts.poppins(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Colors.white70,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text('Take Profit (Optional)',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _takeProfitController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Profit target price',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      prefixIcon: const Icon(Icons.trending_up),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text('Stop Loss (Optional)',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _stopLossController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Loss limit price',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                      prefixIcon: const Icon(Icons.trending_down),
                    ),
                  ),
                  const SizedBox(height: 12),
                  CheckboxListTile(
                    title: const Text('Use Trailing Stop'),
                    subtitle: const Text('Follow price movements'),
                    value: _useTrailingStop,
                    onChanged: (bool? value) {
                      setState(() => _useTrailingStop = value ?? false);
                    },
                  ),
                  if (_useTrailingStop) ...[
                    const SizedBox(height: 8),
                    Text('Trailing Stop Distance (pips)',
                        style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _trailingStopPipsController,
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        labelText: 'Distance in pips',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        prefixIcon: const Icon(Icons.straighten),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 24),

            // ==================== SUBMIT BUTTON ====================
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isSubmitting ? null : _submitOrder,
                icon: _isSubmitting
                    ? SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor:
                              AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Icon(Icons.check_circle),
                label: Text(_isSubmitting ? 'Submitting...' : 'Place Order'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00E5FF),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
