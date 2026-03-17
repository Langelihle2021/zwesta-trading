# Exness Integration Guide

## Overview
Exness is configured as an **MT5 broker** in your system. The integration uses MetaTrader 5 protocol for trading operations.

## Current Setup Status

### ✅ Completed
- Exness added to broker registry (`broker_registry_service.dart`)
- UI support in `broker_integration_screen.dart` with server: `Exness-MT5`
- Backend broker type enum: `BrokerType.EXNESS`
- Credential capture: Account ID, Password, Server

### ❌ Needs Implementation

#### 1. **Exness Trading Service** (`exness_trading_service.dart`)
Create a new service handling:
- MT5 account connection
- Live price quotations via Exness API
- Order placement & management
- Account data retrieval (balance, equity, margin)
- Position monitoring

#### 2. **Backend Exness Handler** (`multi_broker_backend_updated.py`)
Add Exness-specific logic:
- Validate Exness MT5 credentials
- Route trading commands via WebAPI or cTrader
- Handle Exness symbol mapping
- Margin requirements specific to Exness (1:30 limit for retail)

#### 3. **Symbol Management**
- Map Exness symbols (e.g., EURUSD.a for spot)
- Handle Exness-specific asset classes
- Store available symbols per account type (DEMO/LIVE)

---

## Implementation Plan

### Phase 1: Flutter Service (`lib/services/exness_trading_service.dart`)

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/environment_config.dart';

class ExnessAccount {
  final String accountId;
  final String accountType; // DEMO or LIVE
  final double balance;
  final double equity;
  final double margin;
  final double freeMargin;
  final List<String> availableSymbols;
  
  ExnessAccount({
    required this.accountId,
    required this.accountType,
    required this.balance,
    required this.equity,
    required this.margin,
    required this.freeMargin,
    required this.availableSymbols,
  });
}

class ExnessTradingService {
  final String accountId;
  final String password;
  final String server;
  final bool isLive;
  
  String? _sessionToken;
  ExnessAccount? _account;
  
  ExnessTradingService({
    required this.accountId,
    required this.password,
    required this.server,
    required this.isLive,
  });
  
  /// Authenticate with Exness
  Future<bool> authenticate() async {
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'accountId': accountId,
          'password': password,
          'server': server,
          'isLive': isLive,
        }),
      ).timeout(Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _sessionToken = data['sessionToken'];
        return data['success'] ?? false;
      }
      return false;
    } catch (e) {
      print('❌ Exness authentication failed: $e');
      return false;
    }
  }
  
  /// Get account info
  Future<ExnessAccount?> getAccountInfo() async {
    if (_sessionToken == null) await authenticate();
    
    try {
      final response = await http.get(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/account'),
        headers: {'Authorization': 'Bearer $_sessionToken'},
      ).timeout(Duration(seconds: 10));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _account = ExnessAccount(
          accountId: data['accountId'],
          accountType: data['accountType'],
          balance: (data['balance'] as num).toDouble(),
          equity: (data['equity'] as num).toDouble(),
          margin: (data['margin'] as num).toDouble(),
          freeMargin: (data['freeMargin'] as num).toDouble(),
          availableSymbols: List<String>.from(data['symbols'] ?? []),
        );
        return _account;
      }
      return null;
    } catch (e) {
      print('❌ Failed to fetch Exness account info: $e');
      return null;
    }
  }
  
  /// Place a trade order
  Future<Map<String, dynamic>> placeOrder({
    required String symbol,
    required String side, // BUY or SELL
    required double volume,
    required double? slPrice,
    required double? tpPrice,
  }) async {
    if (_sessionToken == null) await authenticate();
    
    try {
      final response = await http.post(
        Uri.parse('${EnvironmentConfig.apiUrl}/api/broker/exness/trade'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_sessionToken',
        },
        body: jsonEncode({
          'symbol': symbol,
          'side': side,
          'volume': volume,
          'slPrice': slPrice,
          'tpPrice': tpPrice,
        }),
      ).timeout(Duration(seconds: 10));
      
      if (response.statusCode == 200 || response.statusCode == 201) {
        return {
          'success': true,
          'orderId': jsonDecode(response.body)['orderId'],
        };
      }
      return {
        'success': false,
        'error': jsonDecode(response.body)['error'] ?? 'Order placement failed',
      };
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
```

### Phase 2: Backend Handler (`multi_broker_backend_updated.py`)

Add these routes:

```python
@app.route('/api/broker/exness/login', methods=['POST'])
def exness_login():
    """Authenticate with Exness MT5"""
    try:
        data = request.get_json()
        account_id = data.get('accountId')
        password = data.get('password')
        server = data.get('server', 'Exness-MT5')
        is_live = data.get('isLive', False)
        
        # Validate credentials in database
        credentials = broker_credentials_service.get_credential_by_account(
            account_id, 'exness'
        )
        if not credentials:
            return jsonify({'success': False, 'error': 'Account not found'}), 400
        
        # Create MT5 connection
        broker_type = BrokerType.EXNESS
        connection = broker_manager.add_connection(
            account_id=account_id,
            broker_type=broker_type,
            credentials={
                'accountId': account_id,
                'password': password,
                'server': server,
            }
        )
        
        if not connection or not connection.connect():
            return jsonify({'success': False, 'error': 'Failed to connect'}), 400
        
        # Generate session token
        session_token = generate_session_token()
        session_store[session_token] = {
            'account_id': account_id,
            'broker': 'exness',
            'created_at': datetime.now(),
        }
        
        return jsonify({
            'success': True,
            'sessionToken': session_token,
            'accountType': 'LIVE' if is_live else 'DEMO',
        }), 200
        
    except Exception as e:
        logger.error(f"Exness login error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/account', methods=['GET'])
def exness_account_info():
    """Get Exness account information"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        account_id = session['account_id']
        connection = broker_manager.connections.get(account_id)
        
        if not connection:
            return jsonify({'error': 'No active connection'}), 400
        
        # Get account details from MT5
        account_info = {
            'accountId': account_id,
            'accountType': 'LIVE',  # or DEMO
            'balance': connection.get('balance', 0),
            'equity': connection.get('equity', 0),
            'margin': connection.get('usedMargin', 0),
            'freeMargin': connection.get('availableMargin', 0),
            'symbols': get_exness_symbols(),
        }
        
        return jsonify(account_info), 200
        
    except Exception as e:
        logger.error(f"Exness account info error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/broker/exness/trade', methods=['POST'])
def exness_place_trade():
    """Place a trade on Exness"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        data = request.get_json()
        account_id = session['account_id']
        connection = broker_manager.connections.get(account_id)
        
        if not connection:
            return jsonify({'error': 'No active connection'}), 400
        
        # Send trade command to MT5
        order_result = connection.send_trade_command({
            'symbol': data.get('symbol'),
            'side': data.get('side'),
            'volume': data.get('volume'),
            'slPrice': data.get('slPrice'),
            'tpPrice': data.get('tpPrice'),
        })
        
        if order_result.get('success'):
            return jsonify({
                'success': True,
                'orderId': order_result.get('orderId'),
            }), 201
        
        return jsonify({
            'success': False,
            'error': order_result.get('error', 'Trade failed'),
        }), 400
        
    except Exception as e:
        logger.error(f"Exness trade error: {e}")
        return jsonify({'error': str(e)}), 500


def get_exness_symbols():
    """Return list of tradable Exness symbols"""
    return [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD',
        'XAUUSD', 'CRUDE', 'NG', 'BTCUSD', 'ETHUSD',
        'US100', 'US30', 'US500', 'XAGUSD', 'COPPER',
    ]
```

### Phase 3: Credential Storage

Ensure `BrokerCredentialsService` stores Exness credentials:

```dart
// In broker_integration_screen.dart
if (_selectedBroker == 'Exness') {
  await BrokerCredentialsService.saveCredential(
    broker: 'exness',
    accountNumber: _accountController.text,
    password: _passwordController.text,
    server: _serverController.text,
  );
}
```

---

## Testing Checklist

- [ ] Exness credentials saved to database
- [ ] Authentication endpoint returns valid session token
- [ ] Account info endpoint fetches balance correctly
- [ ] Trade placement endpoint creates orders
- [ ] Symbol mapping displays Exness available pairs
- [ ] Polling updates position P&L
- [ ] Disconnection handling prevents stale sessions

---

## Exness-Specific Notes

### Leverage Limits (Regulatory)
- **Retail accounts**: Max 1:30 leverage
- **Professional accounts**: Max 1:infinity (unlimited)

### Symbol Conventions
- Spot forex: `EURUSD`, `GBPUSD`
- Metals: `XAUUSD` (gold), `XAGUSD` (silver)
- Crypto: `BTCUSD`, `ETHUSD`
- Indices: `US100` (Nasdaq), `US30` (DJIA)
- Energies: `CRUDE` (WTI oil)

### API Endpoints
- **Demo server**: `http://api.exness.demo:8080` (test)
- **Live server**: `https://api.exness.com` (production)

---

## Next Steps

1. **Create** `exness_trading_service.dart` with the service class above
2. **Implement** backend routes in `multi_broker_backend_updated.py`
3. **Update** `bot_configuration_screen.dart` to enable Exness bot creation
4. **Test** with demo account credentials
5. **Deploy** and monitor live account connections

Would you like me to implement any of these components?
