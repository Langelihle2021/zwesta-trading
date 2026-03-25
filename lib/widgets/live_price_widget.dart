import 'package:flutter/material.dart';
import '../services/realtime_price_websocket_service.dart';
import 'package:google_fonts/google_fonts.dart';

class LivePriceWidget extends StatefulWidget {
  final List<String> symbols;
  final String brokerName;
  final String sessionToken;
  final bool autoConnect;

  const LivePriceWidget({
    Key? key,
    required this.symbols,
    required this.brokerName,
    required this.sessionToken,
    this.autoConnect = true,
  }) : super(key: key);

  @override
  State<LivePriceWidget> createState() => _LivePriceWidgetState();
}

class _LivePriceWidgetState extends State<LivePriceWidget> {
  final Map<String, PriceUpdate> _prices = {};
  bool _isConnected = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.autoConnect) {
      _connect();
    }
  }

  @override
  void didUpdateWidget(LivePriceWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.symbols != widget.symbols) {
      // Update subscriptions if symbols changed
      _updateSubscriptions();
    }
  }

  Future<void> _connect() async {
    try {
      final success = await realtimePriceWebSocketService.connect(
        brokerName: widget.brokerName,
        sessionToken: widget.sessionToken,
      );

      if (success) {
        // Subscribe to all symbols
        realtimePriceWebSocketService.subscribeToMultiple(
          widget.symbols,
          _onPriceUpdate,
        );

        // Listen to connection status
        realtimePriceWebSocketService.onConnectionStatusChanged(
          _onConnectionStatusChanged,
        );

        setState(() => _isConnected = true);
      } else {
        setState(() => _error = 'Failed to connect to real-time prices');
      }
    } catch (e) {
      setState(() => _error = 'Connection error: $e');
    }
  }

  void _onPriceUpdate(PriceUpdate priceUpdate) {
    if (mounted) {
      setState(() {
        _prices[priceUpdate.symbol] = priceUpdate;
      });
    }
  }

  void _onConnectionStatusChanged(bool isConnected) {
    if (mounted) {
      setState(() => _isConnected = isConnected);
    }
  }

  void _updateSubscriptions() {
    final currentlySubscribed =
        realtimePriceWebSocketService.subscribedSymbols;
    
    // Unsubscribe from symbols no longer needed
    for (final symbol in currentlySubscribed) {
      if (!widget.symbols.contains(symbol)) {
        realtimePriceWebSocketService.unsubscribeFromSymbol(
          symbol,
          _onPriceUpdate,
        );
      }
    }

    // Subscribe to new symbols
    for (final symbol in widget.symbols) {
      if (!currentlySubscribed.contains(symbol)) {
        realtimePriceWebSocketService.subscribeToSymbol(
          symbol,
          _onPriceUpdate,
        );
      }
    }
  }

  @override
  void dispose() {
    // Don't disconnect - keep listening
    // Just clean up if needed
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Center(
        child: Text(
          _error!,
          style: const TextStyle(color: Colors.red),
        ),
      );
    }

    if (_prices.isEmpty && !_isConnected) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(
              'Connecting to live prices...',
              style: GoogleFonts.poppins(color: Colors.white70),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Column(
        children: [
          // Connection Status
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _isConnected
                  ? Colors.green.withOpacity(0.1)
                  : Colors.orange.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _isConnected ? Colors.green : Colors.orange,
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _isConnected ? Colors.green : Colors.orange,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _isConnected
                        ? '✅ Live prices connected'
                        : '⏳ Connecting to live prices...',
                    style: TextStyle(
                      color: _isConnected ? Colors.green : Colors.orange,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Price Cards
          ..._prices.entries.map((entry) {
            final symbol = entry.key;
            final price = entry.value;
            final isPositive = price.change24hPercent >= 0;

            return Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1F3A),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withOpacity(0.1)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        symbol,
                        style: GoogleFonts.poppins(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: isPositive
                              ? Colors.green.withOpacity(0.2)
                              : Colors.red.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '${isPositive ? '+' : ''}${price.change24hPercent.toStringAsFixed(2)}%',
                          style: TextStyle(
                            color: isPositive ? Colors.green : Colors.red,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Prices
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Mid Price',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 11,
                            ),
                          ),
                          SizedBox(
                            height: 4,
                          ),
                          Text(
                            price.mid.toStringAsFixed(5),
                            style: const TextStyle(
                              color: Color(0xFF00E5FF),
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Bid',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 11,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            price.bid.toStringAsFixed(5),
                            style: const TextStyle(
                              color: Colors.green,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Ask',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 11,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            price.ask.toStringAsFixed(5),
                            style: const TextStyle(
                              color: Colors.red,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Spread',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.6),
                              fontSize: 11,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            price.spreadPips,
                            style: TextStyle(
                              color: Colors.orange,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Daily Stats
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.02),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        Column(
                          children: [
                            Text(
                              '24h High',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.5),
                                fontSize: 10,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              price.high24h.toStringAsFixed(5),
                              style: const TextStyle(
                                color: Colors.green,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        Column(
                          children: [
                            Text(
                              '24h Low',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.5),
                                fontSize: 10,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              price.low24h.toStringAsFixed(5),
                              style: const TextStyle(
                                color: Colors.red,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        Column(
                          children: [
                            Text(
                              'Volume',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.5),
                                fontSize: 10,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${(price.volume / 1000000).toStringAsFixed(2)}M',
                              style: const TextStyle(
                                color: Color(0xFF00E5FF),
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Updated: ${price.timestamp.toLocal().toString().split('.')[0]}',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ],
      ),
    );
  }
}
