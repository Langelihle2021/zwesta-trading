import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

/// Model for real-time price data
class PriceUpdate {
  final String symbol;
  final double bid;
  final double ask;
  final double last;
  final DateTime timestamp;
  final double volume;
  final double high24h;
  final double low24h;
  final double change24hPercent;

  PriceUpdate({
    required this.symbol,
    required this.bid,
    required this.ask,
    required this.last,
    required this.timestamp,
    required this.volume,
    required this.high24h,
    required this.low24h,
    required this.change24hPercent,
  });

  factory PriceUpdate.fromJson(Map<String, dynamic> json) {
    return PriceUpdate(
      symbol: json['symbol'] ?? 'UNKNOWN',
      bid: (json['bid'] ?? 0).toDouble(),
      ask: (json['ask'] ?? 0).toDouble(),
      last: (json['last'] ?? json['price'] ?? 0).toDouble(),
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'])
          : DateTime.now(),
      volume: (json['volume'] ?? 0).toDouble(),
      high24h: (json['high24h'] ?? 0).toDouble(),
      low24h: (json['low24h'] ?? 0).toDouble(),
      change24hPercent: (json['change24h_percent'] ?? 0).toDouble(),
    );
  }

  double get spread => ask - bid;
  double get mid => (bid + ask) / 2;
  String get spreadPips => (spread * 10000).toStringAsFixed(2);
}

/// Type definition for price update callbacks
typedef PriceUpdateCallback = void Function(PriceUpdate);
typedef ConnectionStatusCallback = void Function(bool isConnected);

/// WebSocket service for real-time price updates
class RealtimePriceWebSocketService {
  static const String _wsBaseUrl = 'wss://api.zwesta-trader.com/ws'; // Update with your domain
  
  late WebSocketChannel? _channel;
  String? _connectionId;
  bool _isConnected = false;
  
  final Map<String, List<PriceUpdateCallback>> _priceCallbacks = {};
  final List<ConnectionStatusCallback> _statusCallbacks = [];
  
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const Duration _heartbeatInterval = Duration(seconds: 30);
  static const Duration _reconnectDelay = Duration(seconds: 5);

  // ==================== CONNECTION ====================

  /// Connect to websocket for real-time prices
  Future<bool> connect({
    required String brokerName,
    required String sessionToken,
  }) async {
    try {
      print('🔌 Connecting to real-time price WebSocket...');
      
      final wsUrl = '$_wsBaseUrl/prices?broker=$brokerName&token=$sessionToken';
      
      _channel = WebSocketChannel.connect(
        Uri.parse(wsUrl),
      );

      // Wait for initial connection
      await _channel!.ready.timeout(
        const Duration(seconds: 10),
        onTimeout: () {
          throw TimeoutException('WebSocket connection timeout');
        },
      );

      // Start listening to messages
      _startListening();
      
      // Start heartbeat to keep connection alive
      _startHeartbeat();
      
      _isConnected = true;
      _reconnectAttempts = 0;
      _notifyStatusChange(true);
      
      print('✅ Connected to real-time price WebSocket');
      return true;
    } catch (e) {
      print('❌ WebSocket connection failed: $e');
      _isConnected = false;
      _notifyStatusChange(false);
      _scheduleReconnect();
      return false;
    }
  }

  /// Disconnect from WebSocket
  Future<void> disconnect() async {
    try {
      _heartbeatTimer?.cancel();
      _reconnectTimer?.cancel();
      await _channel?.sink.close(status.goingAway);
      _channel = null;
      _isConnected = false;
      _notifyStatusChange(false);
      print('🔌 Disconnected from real-time price WebSocket');
    } catch (e) {
      print('⚠️ Error disconnecting: $e');
    }
  }

  // ==================== SUBSCRIPTIONS ====================

  /// Subscribe to price updates for a symbol
  void subscribeToSymbol(
    String symbol,
    PriceUpdateCallback callback,
  ) {
    if (!_priceCallbacks.containsKey(symbol)) {
      _priceCallbacks[symbol] = [];
    }
    _priceCallbacks[symbol]!.add(callback);

    // Send subscription message to server
    if (_isConnected && _channel != null) {
      _sendMessage({
        'action': 'subscribe',
        'symbol': symbol,
      });
    }
  }

  /// Unsubscribe from price updates for a symbol
  void unsubscribeFromSymbol(
    String symbol,
    PriceUpdateCallback callback,
  ) {
    if (_priceCallbacks.containsKey(symbol)) {
      _priceCallbacks[symbol]!.remove(callback);
      
      if (_priceCallbacks[symbol]!.isEmpty) {
        _priceCallbacks.remove(symbol);
        
        // Send unsubscribe message to server
        if (_isConnected && _channel != null) {
          _sendMessage({
            'action': 'unsubscribe',
            'symbol': symbol,
          });
        }
      }
    }
  }

  /// Subscribe to connection status changes
  void onConnectionStatusChanged(ConnectionStatusCallback callback) {
    _statusCallbacks.add(callback);
  }

  // ==================== SUBSCRIPTION BATCH ====================

  /// Subscribe to multiple symbols at once
  void subscribeToMultiple(
    List<String> symbols,
    PriceUpdateCallback callback,
  ) {
    for (final symbol in symbols) {
      subscribeToSymbol(symbol, callback);
    }
  }

  /// Unsubscribe from multiple symbols at once
  void unsubscribeFromMultiple(
    List<String> symbols,
    PriceUpdateCallback callback,
  ) {
    for (final symbol in symbols) {
      unsubscribeFromSymbol(symbol, callback);
    }
  }

  // ==================== INTERNAL ====================

  void _startListening() {
    _channel?.stream.listen(
      (message) {
        try {
          final data = jsonDecode(message) as Map<String, dynamic>;
          
          // Handle different message types
          if (data['type'] == 'price_update') {
            _handlePriceUpdate(data);
          } else if (data['type'] == 'connection_id') {
            _connectionId = data['connection_id'];
            print('🔑 WebSocket connection ID: $_connectionId');
          } else if (data['type'] == 'heartbeat_ack') {
            // Heartbeat acknowledged
            print('💓 Heartbeat acknowledged');
          } else if (data['type'] == 'error') {
            print('⚠️ WebSocket error: ${data['message']}');
          }
        } catch (e) {
          print('❌ Error handling WebSocket message: $e');
        }
      },
      onError: (error) {
        print('❌ WebSocket error: $error');
        _isConnected = false;
        _notifyStatusChange(false);
        _scheduleReconnect();
      },
      onDone: () {
        print('🔌 WebSocket connection closed');
        _isConnected = false;
        _notifyStatusChange(false);
        _scheduleReconnect();
      },
    );
  }

  void _handlePriceUpdate(Map<String, dynamic> data) {
    try {
      final priceUpdate = PriceUpdate.fromJson(data);
      
      // Notify all listeners for this symbol
      if (_priceCallbacks.containsKey(priceUpdate.symbol)) {
        for (final callback in _priceCallbacks[priceUpdate.symbol]!) {
          callback(priceUpdate);
        }
      }
    } catch (e) {
      print('❌ Error processing price update: $e');
    }
  }

  void _sendMessage(Map<String, dynamic> message) {
    try {
      if (_channel != null && _isConnected) {
        _channel!.sink.add(jsonEncode(message));
      }
    } catch (e) {
      print('❌ Error sending WebSocket message: $e');
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
      _sendMessage({
        'type': 'heartbeat',
      });
    });
  }

  void _notifyStatusChange(bool isConnected) {
    for (final callback in _statusCallbacks) {
      callback(isConnected);
    }
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      print('❌ Failed to reconnect after $_maxReconnectAttempts attempts');
      return;
    }

    _reconnectAttempts++;
    print('⏳ Reconnecting... (Attempt $_reconnectAttempts/$_maxReconnectAttempts)');
    
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(_reconnectDelay, () {
      // Note: You would need to pass the broker name and token here
      // For now, just attempt to connect with empty credentials
      // This is a simplified version - in production, store these credentials
    });
  }

  // ==================== GETTERS ====================

  bool get isConnected => _isConnected;
  int get activeSubscriptions => _priceCallbacks.length;

  /// Get list of currently subscribed symbols
  List<String> get subscribedSymbols => _priceCallbacks.keys.toList();

  /// Get number of listeners for a symbol
  int getListenerCountForSymbol(String symbol) {
    return _priceCallbacks[symbol]?.length ?? 0;
  }
}

/// Singleton instance
final realtimePriceWebSocketService = RealtimePriceWebSocketService();
