# Exness Backend Implementation Code

Add these routes to `multi_broker_backend_updated.py` to handle Exness trading operations.

## 1. Import MT5 Library (if not already imported)

```python
import MetaTrader5 as mt5
from typing import Optional, Dict, Any
```

## 2. Helper Functions

```python
def generate_session_token(account_id: str, length: int = 32) -> str:
    """Generate a secure session token for MT5 session management"""
    import secrets
    return secrets.token_urlsafe(length)

def validate_exness_server(server: str) -> bool:
    """Validate Exness server name"""
    valid_servers = ['Exness-MT5', 'Exness-MT5 Demo', 'Exness MT5']
    return server in valid_servers
```

## 3. Login Endpoint

```python
@app.route('/api/broker/exness/login', methods=['POST'])
def exness_login():
    """Authenticate with Exness MT5 account"""
    try:
        data = request.get_json()
        account_id = data.get('accountId')
        password = data.get('password')
        server = data.get('server', 'Exness-MT5')
        is_live = data.get('isLive', False)
        
        if not account_id or not password:
            return jsonify({'success': False, 'error': 'Missing accountId or password'}), 400
        
        if not validate_exness_server(server):
            return jsonify({'success': False, 'error': 'Invalid server name'}), 400
        
        # Attempt MT5 login
        if not mt5.initialize(login=int(account_id), password=password, server=server):
            error_msg = mt5.last_error()
            return jsonify({'success': False, 'error': f'MT5 login failed: {error_msg}'}), 401
        
        # Get account info to verify connection
        account_info = mt5.account_info()
        if not account_info:
            mt5.shutdown()
            return jsonify({'success': False, 'error': 'Failed to retrieve account info'}), 400
        
        # Generate session token
        session_token = generate_session_token(account_id)
        
        # Store session with connection details
        session_store[session_token] = {
            'account_id': account_id,
            'broker': 'exness',
            'account_type': 'LIVE' if is_live else 'DEMO',
            'server': server,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'connection': mt5,
        }
        
        logger.info(f"✅ Exness login successful for account {account_id}")
        
        return jsonify({
            'success': True,
            'sessionToken': session_token,
            'accountId': account_id,
            'accountType': 'DEMO' if not is_live else 'LIVE',
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Exness login error: {e}")
        try:
            mt5.shutdown()
        except:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/logout', methods=['POST'])
def exness_logout():
    """Logout and close Exness MT5 session"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if session:
            try:
                mt5.shutdown()
            except:
                pass
            del session_store[token]
        
        return jsonify({'success': True, 'message': 'Logged out successfully'}), 200
        
    except Exception as e:
        logger.error(f"Exness logout error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

## 4. Account Information Endpoint

```python
@app.route('/api/broker/exness/account', methods=['GET'])
def exness_account_info():
    """Get Exness account information"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        # Update last activity
        session['last_activity'] = datetime.now()
        
        # Get account information from MT5
        account_info = mt5.account_info()
        
        if not account_info:
            return jsonify({'error': 'Failed to retrieve account info'}), 400
        
        # Get symbols available on this account
        symbols = get_exness_available_symbols()
        
        # Calculate margin level
        margin_level = 0
        if account_info.margin_used > 0:
            margin_level = (account_info.equity / account_info.margin_used) * 100
        
        response_data = {
            'accountId': session['account_id'],
            'accountType': session.get('account_type', 'DEMO'),
            'balance': float(account_info.balance),
            'equity': float(account_info.equity),
            'margin': float(account_info.margin_used),
            'freeMargin': float(account_info.margin_free),
            'marginLevel': margin_level,
            'leverageMax': account_info.leverage,
            'symbols': symbols,
            'fetchedAt': datetime.now().isoformat(),
        }
        
        logger.info(f"📊 Retrieved account info for {session['account_id']}: Balance={response_data['balance']}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ Exness account info error: {e}")
        return jsonify({'error': str(e)}), 500
```

## 5. Place Trade Endpoint

```python
@app.route('/api/broker/exness/trade', methods=['POST'])
def exness_place_trade():
    """Place a trade on Exness MT5"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'success': False, 'error': 'Invalid session'}), 401
        
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side', 'BUY').upper()
        volume = float(data.get('volume', 0.01))
        stop_loss = data.get('stopLoss')
        take_profit = data.get('takeProfit')
        comment = data.get('comment', f'Zwesta Bot - {symbol}')
        
        if not symbol or side not in ['BUY', 'SELL']:
            return jsonify({'success': False, 'error': 'Invalid symbol or side'}), 400
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return jsonify({'success': False, 'error': f'Symbol {symbol} not found'}), 404
        
        # Prepare trade request
        trade_type = mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return jsonify({'success': False, 'error': 'Failed to get current price'}), 400
        
        price = tick.ask if side == 'BUY' else tick.bid
        
        # Build trade request
        request_dict = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': trade_type,
            'price': price,
            'comment': comment,
            'type_filling': mt5.ORDER_FILLING_IOC,
            'type_time': mt5.ORDER_TIME_GTC,
        }
        
        # Add SL and TP if provided
        if stop_loss:
            request_dict['sl'] = float(stop_loss)
        if take_profit:
            request_dict['tp'] = float(take_profit)
        
        # Send trade request
        result = mt5.order_send(request_dict)
        
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Trade failed: {result.comment if result else 'Unknown error'}"
            logger.error(f"❌ {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 400
        
        logger.info(f"✅ Trade executed: {side} {volume} {symbol} @ {price}")
        
        return jsonify({
            'success': True,
            'orderId': str(result.order),
            'orderComment': result.comment,
            'price': price,
            'volume': volume,
            'symbol': symbol,
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Exness trade error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

## 6. Get Open Orders Endpoint

```python
@app.route('/api/broker/exness/orders', methods=['GET'])
def exness_get_orders():
    """Get all open orders"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        # Get positions (open trades)
        positions = mt5.positions_get()
        
        if not positions:
            return jsonify({'orders': []}), 200
        
        orders = []
        for pos in positions:
            # Get current price for P&L calculation
            tick = mt5.symbol_info_tick(pos.symbol)
            if not tick:
                continue
            
            # Calculate current profit
            if pos.type == mt5.ORDER_TYPE_BUY:
                current_price = tick.bid
            else:
                current_price = tick.ask
            
            profit = (current_price - pos.price_open) * pos.volume
            if pos.type == mt5.ORDER_TYPE_SELL:
                profit = -profit
            
            orders.append({
                'orderId': str(pos.ticket),
                'symbol': pos.symbol,
                'side': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                'volume': pos.volume,
                'openPrice': pos.price_open,
                'stopLoss': pos.sl if pos.sl != 0 else None,
                'takeProfit': pos.tp if pos.tp != 0 else None,
                'commission': pos.commission,
                'currentProfit': profit,
                'status': 'OPEN',
                'openTime': datetime.fromtimestamp(pos.time).isoformat(),
            })
        
        return jsonify({'orders': orders}), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching orders: {e}")
        return jsonify({'error': str(e)}), 500
```

## 7. Close Order Endpoint

```python
@app.route('/api/broker/exness/orders/<order_id>/close', methods=['POST'])
def exness_close_order(order_id):
    """Close a specific order"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        order_id = int(order_id)
        
        # Get position info
        position = mt5.positions_get(ticket=order_id)
        if not position:
            return jsonify({'error': 'Position not found'}), 404
        
        position = position[0]
        
        # Get current price
        tick = mt5.symbol_info_tick(position.symbol)
        if not tick:
            return jsonify({'error': 'Failed to get current price'}), 400
        
        # Prepare close request
        close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        close_request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': position.symbol,
            'volume': position.volume,
            'type': close_type,
            'position': order_id,
            'price': close_price,
            'comment': f'Zwesta Close - Ticket {order_id}',
            'type_filling': mt5.ORDER_FILLING_IOC,
            'type_time': mt5.ORDER_TIME_GTC,
        }
        
        # Send close request
        result = mt5.order_send(close_request)
        
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Failed to close: {result.comment if result else 'Unknown error'}"
            return jsonify({'error': error_msg}), 400
        
        logger.info(f"✅ Position {order_id} closed successfully")
        
        return jsonify({
            'success': True,
            'closePrice': close_price,
            'orderId': str(result.order),
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error closing order: {e}")
        return jsonify({'error': str(e)}), 500
```

## 8. Update Order SL/TP Endpoint

```python
@app.route('/api/broker/exness/orders/<order_id>', methods=['PATCH'])
def exness_update_order(order_id):
    """Update stop loss and/or take profit"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        data = request.get_json()
        order_id = int(order_id)
        new_sl = data.get('stopLoss')
        new_tp = data.get('takeProfit')
        
        # Get position
        position = mt5.positions_get(ticket=order_id)
        if not position:
            return jsonify({'error': 'Position not found'}), 404
        
        position = position[0]
        
        # Prepare modify request
        modify_request = {
            'action': mt5.TRADE_ACTION_MODIFY,
            'position': order_id,
            'symbol': position.symbol,
        }
        
        if new_sl is not None:
            modify_request['sl'] = float(new_sl)
        if new_tp is not None:
            modify_request['tp'] = float(new_tp)
        
        # Send modify request
        result = mt5.order_send(modify_request)
        
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Failed to modify: {result.comment if result else 'Unknown error'}"
            return jsonify({'error': error_msg}), 400
        
        logger.info(f"✅ Position {order_id} modified successfully")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"❌ Error updating order: {e}")
        return jsonify({'error': str(e)}), 500
```

## 9. Get Available Symbols

```python
def get_exness_available_symbols() -> list:
    """Get list of available Exness symbols"""
    symbols = []
    
    # Try to get symbols from MT5
    all_symbols = mt5.symbols_get()
    
    if all_symbols and len(all_symbols) > 0:
        # Filter for common trading symbols
        symbol_names = [s.name for s in all_symbols if s.visible]
        return symbol_names[:50]  # Return top 50
    
    # Fallback to default symbols
    return [
        'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD',
        'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY',
        'XAUUSD', 'XAGUSD', 'COPPER',
        'CRUDE', 'BRENT', 'NG',
        'US100', 'US30', 'US500',
        'BTCUSD', 'ETHUSD', 'LTCUSD',
    ]
```

## 10. Get Symbol Data Endpoint

```python
@app.route('/api/broker/exness/symbols/<symbol>', methods=['GET'])
def exness_get_symbol_data(symbol):
    """Get symbol data (price, spread, etc.)"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        session = session_store.get(token)
        
        if not session:
            return jsonify({'error': 'Invalid session'}), 401
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return jsonify({'error': f'Symbol {symbol} not found'}), 404
        
        # Get tick (current price)
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return jsonify({'error': 'Failed to get price data'}), 400
        
        return jsonify({
            'symbol': symbol,
            'bid': float(tick.bid),
            'ask': float(tick.ask),
            'last': float(tick.last),
            'spread': float((tick.ask - tick.bid) / symbol_info.point),
            'time': datetime.fromtimestamp(tick.time).isoformat(),
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching symbol data: {e}")
        return jsonify({'error': str(e)}), 500
```

## Installation Requirements

Add to `requirements.txt`:

```
MetaTrader5>=5.0.45
```

Install with:

```bash
pip install MetaTrader5>=5.0.45
```

---

## Usage Example

```python
# In bot trading logic
from services.exness_trading_service import ExnessTradingService

service = ExnessTradingService(
    accountId='123456',
    password='your_password',
    server='Exness-MT5',
    isLive=False,  # Demo account
)

# Authenticate
if await service.authenticate():
    # Get account info
    account = await service.getAccountInfo()
    print(f"Balance: ${account.balance}")
    
    # Place a BUY order
    result = await service.buy(
        symbol='EURUSD',
        volume=0.1,
        stopLoss=1.0800,
        takeProfit=1.1000,
    )
    
    if result['success']:
        print(f"Order placed: {result['orderId']}")
```
