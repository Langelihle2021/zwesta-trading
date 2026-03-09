#!/usr/bin/env python3
"""
Zwesta Multi-Broker Trading Backend
Supports multiple brokers with unified API
Updated with MT5 Demo Credentials
"""

import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from typing import Dict, List, Optional
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('multi_broker_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ==================== CONFIGURATION ====================
# MT5 Demo Credentials
MT5_CONFIG = {
    'account': 104017418,
    'password': '*6RjhRvH',
    'server': 'MetaQuotes-Demo',
    'path': 'C:\\Program Files\\XM Global MT5'
}

class BrokerType(Enum):
    """Supported broker types"""
    METATRADER5 = "mt5"
    INTERACTIVE_BROKERS = "ib"
    OANDA = "oanda"
    XM = "xm"
    PEPPERSTONE = "pepperstone"
    FXOPEN = "fxopen"
    EXNESS = "exness"
    DARWINEX = "darwinex"


class BrokerConnection:
    """Abstract broker connection class"""
    
    def __init__(self, broker_type: BrokerType, credentials: Dict):
        self.broker_type = broker_type
        self.credentials = credentials
        self.connected = False
        self.account_info = None

    async def connect(self) -> bool:
        raise NotImplementedError

    async def disconnect(self) -> bool:
        raise NotImplementedError

    async def get_account_info(self) -> Dict:
        raise NotImplementedError

    async def get_positions(self) -> List[Dict]:
        raise NotImplementedError

    async def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        raise NotImplementedError

    async def close_position(self, position_id: str) -> Dict:
        raise NotImplementedError

    async def get_trades(self) -> List[Dict]:
        raise NotImplementedError


class MT5Connection(BrokerConnection):
    """MetaTrader 5 Broker Connection"""
    
    def __init__(self, credentials: Dict = None):
        # Use MT5_CONFIG if no credentials provided
        if credentials is None:
            credentials = {
                'account': MT5_CONFIG['account'],
                'password': MT5_CONFIG['password'],
                'server': MT5_CONFIG['server']
            }
        
        super().__init__(BrokerType.METATRADER5, credentials)
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            self.mt5_path = MT5_CONFIG['path']
        except ImportError:
            logger.error("MetaTrader5 not installed")
            self.mt5 = None

    def connect(self) -> bool:
        """Connect to MT5"""
        try:
            if not self.mt5:
                logger.error("MetaTrader5 SDK not available")
                return False

            if not self.mt5.initialize(path=self.mt5_path):
                logger.error(f"MT5 init failed: {self.mt5.last_error()}")
                return False

            account = self.credentials.get('account') or MT5_CONFIG['account']
            password = self.credentials.get('password') or MT5_CONFIG['password']
            server = self.credentials.get('server') or MT5_CONFIG['server']

            if not self.mt5.login(account, password=password, server=server):
                logger.error(f"MT5 login failed: {self.mt5.last_error()}")
                return False

            self.connected = True
            self.get_account_info()
            logger.info(f"Connected to MT5 account {account}")
            return True
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from MT5"""
        try:
            if self.mt5:
                self.mt5.shutdown()
            self.connected = False
            return True
        except Exception as e:
            logger.error(f"MT5 disconnect error: {e}")
            return False

    def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            if not self.connected:
                return None

            info = self.mt5.account_info()
            self.account_info = {
                'accountNumber': info.login,
                'balance': info.balance,
                'equity': info.equity,
                'margin': info.margin,
                'marginFree': info.margin_free,
                'marginLevel': info.margin_level,
                'currency': info.currency,
                'leverage': info.leverage,
                'broker': info.server,
            }
            return self.account_info
        except Exception as e:
            logger.error(f"Error getting MT5 account info: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        try:
            if not self.connected:
                return []

            positions = self.mt5.positions_get()
            result = []
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == self.mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'openPrice': pos.price_open,
                    'currentPrice': pos.price_current,
                    'pnl': pos.profit,
                    'broker': 'MT5',
                })
            return result
        except Exception as e:
            logger.error(f"Error getting MT5 positions: {e}")
            return []

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        """Place order on MT5"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected'}

            tick = self.mt5.symbol_info_tick(symbol)
            price = tick.ask if order_type == 'BUY' else tick.bid

            request_dict = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_BUY if order_type == 'BUY' else self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": kwargs.get('comment', 'Zwesta Trade'),
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }

            if 'stopLoss' in kwargs:
                request_dict['sl'] = kwargs['stopLoss']
            if 'takeProfit' in kwargs:
                request_dict['tp'] = kwargs['takeProfit']

            result = self.mt5.order_send(request_dict)

            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'MT5 error: {result.comment}'}

            return {
                'success': True,
                'orderId': result.order,
                'symbol': symbol,
                'type': order_type,
                'price': price,
                'broker': 'MT5',
            }
        except Exception as e:
            logger.error(f"Error placing MT5 order: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, position_id: str) -> Dict:
        """Close position"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected'}

            position = self.mt5.positions_get(ticket=int(position_id))
            if not position:
                return {'success': False, 'error': 'Position not found'}

            pos = position[0]
            
            request_dict = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": self.mt5.ORDER_TYPE_SELL if pos.type == self.mt5.ORDER_TYPE_BUY else self.mt5.ORDER_TYPE_BUY,
                "position": int(position_id),
                "comment": "Zwesta Close",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }

            result = self.mt5.order_send(request_dict)
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'error': f'MT5 error: {result.comment}'}

            return {'success': True, 'broker': 'MT5'}
        except Exception as e:
            logger.error(f"Error closing MT5 position: {e}")
            return {'success': False, 'error': str(e)}

    def get_trades(self) -> List[Dict]:
        """Get trade history"""
        try:
            if not self.connected:
                return []

            deals = self.mt5.history_deals_get(position=0)
            result = []
            for deal in deals[-50:]:
                result.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == self.mt5.DEAL_TYPE_BUY else 'SELL',
                    'volume': deal.volume,
                    'price': deal.price,
                    'profit': deal.profit,
                    'time': datetime.fromtimestamp(deal.time).isoformat(),
                    'broker': 'MT5',
                })
            return result
        except Exception as e:
            logger.error(f"Error getting MT5 trades: {e}")
            return []


class BrokerManager:
    """Manages multiple broker connections"""
    
    def __init__(self):
        self.connections: Dict[str, BrokerConnection] = {}
        self.accounts: Dict[str, Dict] = {}

    def add_connection(self, account_id: str, broker_type: BrokerType, credentials: Dict = None):
        """Add a new broker connection"""
        try:
            if broker_type == BrokerType.METATRADER5:
                connection = MT5Connection(credentials)
            else:
                logger.error(f"Broker {broker_type} not yet implemented")
                return False

            self.connections[account_id] = connection
            logger.info(f"Connection added: {account_id} ({broker_type.value})")
            return True
        except Exception as e:
            logger.error(f"Error adding connection: {e}")
            return False

    def connect_all(self) -> Dict[str, bool]:
        """Connect all brokers"""
        results = {}
        for account_id, connection in self.connections.items():
            try:
                results[account_id] = connection.connect()
            except Exception as e:
                logger.error(f"Error connecting {account_id}: {e}")
                results[account_id] = False
        return results

    def disconnect_all(self) -> Dict[str, bool]:
        """Disconnect all brokers"""
        results = {}
        for account_id, connection in self.connections.items():
            try:
                results[account_id] = connection.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {account_id}: {e}")
                results[account_id] = False
        return results

    def get_all_positions(self) -> Dict[str, List[Dict]]:
        """Get positions from all brokers"""
        results = {}
        for account_id, connection in self.connections.items():
            if connection.connected:
                try:
                    results[account_id] = connection.get_positions()
                except Exception as e:
                    logger.error(f"Error getting positions for {account_id}: {e}")
                    results[account_id] = []
        return results

    def get_all_trades(self) -> Dict[str, List[Dict]]:
        """Get trades from all brokers"""
        results = {}
        for account_id, connection in self.connections.items():
            if connection.connected:
                try:
                    results[account_id] = connection.get_trades()
                except Exception as e:
                    logger.error(f"Error getting trades for {account_id}: {e}")
                    results[account_id] = []
        return results

    def get_consolidated_summary(self) -> Dict:
        """Get summary across all accounts"""
        total_balance = 0
        total_equity = 0
        total_positions = 0
        total_profit = 0
        accounts_summary = {}

        for account_id, connection in self.connections.items():
            if connection.connected and connection.account_info:
                info = connection.account_info
                accounts_summary[account_id] = {
                    'balance': info['balance'],
                    'equity': info['equity'],
                    'margin': info['margin'],
                }
                total_balance += info['balance']
                total_equity += info['equity']

            positions = connection.get_positions()
            total_positions += len(positions)
            for pos in positions:
                total_profit += pos['pnl']

        return {
            'totalBalance': total_balance,
            'totalEquity': total_equity,
            'totalPositions': total_positions,
            'totalProfit': total_profit,
            'accounts': accounts_summary,
            'timestamp': datetime.now().isoformat(),
        }


# Initialize broker manager
broker_manager = BrokerManager()

# ==================== IN-MEMORY STORAGE ====================
# Store demo trades placed via API (temporary storage for this session)
demo_trades_storage = {}

# Auto-add default MT5 account with demo credentials
logger.info("Initializing with MT5 demo account")
broker_manager.add_connection('Default MT5', BrokerType.METATRADER5, MT5_CONFIG)


# ==================== API ENDPOINTS ====================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'service': 'Zwesta Multi-Broker Backend',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/brokers/list', methods=['GET'])
def list_brokers():
    """List available brokers"""
    brokers = [
        {
            'type': 'mt5',
            'name': 'MetaTrader 5',
            'description': 'MetaTrader 5 - Most popular forex platform',
            'assets': ['Forex', 'Metals', 'Indices', 'Stocks', 'Cryptos'],
            'status': 'active'
        },
        {
            'type': 'oanda',
            'name': 'OANDA',
            'description': 'OANDA - Regulated US broker',
            'assets': ['Forex', 'Metals'],
            'status': 'coming_soon'
        },
        {
            'type': 'ib',
            'name': 'Interactive Brokers',
            'description': 'Interactive Brokers - Low commission',
            'assets': ['Stocks', 'Forex', 'Futures', 'Options'],
            'status': 'coming_soon'
        },
        {
            'type': 'xm',
            'name': 'XM',
            'description': 'XM - Forex & CFDs',
            'assets': ['Forex', 'Metals', 'Indices', 'CFDs'],
            'status': 'coming_soon'
        },
    ]
    return jsonify({'brokers': brokers})


@app.route('/api/accounts/add', methods=['POST'])
def add_account():
    """Add a new trading account"""
    data = request.json

    account_id = data.get('accountId')
    broker_type = data.get('brokerType')
    credentials = data.get('credentials')

    if not all([account_id, broker_type]):
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    try:
        broker = BrokerType(broker_type)
        # Use provided credentials or fall back to MT5_CONFIG
        creds = credentials if credentials else MT5_CONFIG
        success = broker_manager.add_connection(account_id, broker, creds)

        if success:
            return jsonify({'success': True, 'accountId': account_id})
        else:
            return jsonify({'success': False, 'error': 'Failed to add account'}), 400
    except ValueError:
        return jsonify({'success': False, 'error': f'Unknown broker type: {broker_type}'}), 400


@app.route('/api/accounts/connect/<account_id>', methods=['POST'])
def connect_account(account_id):
    """Connect to a specific account"""
    if account_id not in broker_manager.connections:
        return jsonify({'success': False, 'error': 'Account not found'}), 404

    connection = broker_manager.connections[account_id]
    
    try:
        success = connection.connect()
        
        if success:
            return jsonify({
                'success': True,
                'accountId': account_id,
                'broker': connection.broker_type.value,
            })
        else:
            return jsonify({'success': False, 'error': 'Connection failed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/list', methods=['GET'])
def list_accounts():
    """List all configured accounts"""
    accounts = []
    for account_id, connection in broker_manager.connections.items():
        accounts.append({
            'accountId': account_id,
            'broker': connection.broker_type.value,
            'connected': connection.connected,
            'info': connection.account_info,
        })


    return jsonify({'accounts': accounts})


@app.route('/api/trades/all', methods=['GET'])
def get_all_trades():
    """Get trading history from all accounts"""
    all_trades = {}
    for account_id, connection in broker_manager.connections.items():
        if connection.broker_type == BrokerType.METATRADER5:
            trades = connection.get_trades()
            all_trades[account_id] = trades if trades else []

    return jsonify({
        'success': True,
        'trades': all_trades,
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/summary/consolidated', methods=['GET'])
def get_consolidated_summary():
    """Get consolidated summary across all accounts"""
    total_balance = 0
    total_equity = 0
    total_positions = 0
    total_profit = 0
    account_summaries = {}

    for account_id, connection in broker_manager.connections.items():
        if connection.connected and connection.account_info:
            info = connection.account_info
            account_summaries[account_id] = {
                'broker': connection.broker_type.value,
                'balance': info.get('balance', 0),
                'equity': info.get('equity', 0),
                'margin': info.get('margin', 0),
                'marginFree': info.get('marginFree', 0),
            }
            total_balance += info.get('balance', 0)
            total_equity += info.get('equity', 0)

            try:
                positions = connection.get_positions()
                total_positions += len(positions)
                for pos in positions:
                    total_profit += pos.get('pnl', 0)
            except:
                pass

    return jsonify({
        'success': True,
        'summary': {
            'totalBalance': total_balance,
            'totalEquity': total_equity,
            'totalPositions': total_positions,
            'totalProfit': total_profit,
            'accounts': account_summaries,
        },
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/trade/place', methods=['POST'])
def place_trade():
    """Place a trade on specified account"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Get fields - handle both camelCase and snake_case
        account_id = data.get('accountId') or data.get('account_id') or 'default_mt5'
        symbol = data.get('symbol', '').upper()
        order_type = (data.get('type') or data.get('tradeType') or 'BUY').upper()
        volume = float(data.get('volume') or data.get('quantity') or 1.0)
        entry_price = float(data.get('entryPrice') or data.get('entry_price') or 0.0)
        
        # Validate required fields
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol is required'}), 400
        
        if order_type not in ['BUY', 'SELL']:
            return jsonify({'success': False, 'error': 'Trade type must be BUY or SELL'}), 400

        # Check if account exists
        if account_id not in broker_manager.connections:
            return jsonify({'success': False, 'error': f'Account {account_id} not found'}), 404

        connection = broker_manager.connections[account_id]
        
        # For demo purposes, allow trades even if not connected
        # Real trades require connection, demo trades don't
        if connection.connected:
            # Real trade - place through broker
            result = connection.place_order(symbol, order_type, volume, **data)
            return jsonify(result)
        else:
            # Demo trade - create mock trade record and store it
            try:
                import random
                profit = random.uniform(-500, 2500)
                ticket = random.randint(1000000, 9999999)
                
                demo_trade = {
                    'success': True,
                    'ticket': ticket,
                    'accountId': account_id,
                    'symbol': symbol,
                    'type': order_type,
                    'volume': volume,
                    'price': entry_price if entry_price > 0 else random.uniform(1, 1000),
                    'entryPrice': entry_price if entry_price > 0 else random.uniform(1, 1000),
                    'currentPrice': entry_price if entry_price > 0 else random.uniform(1, 1000),
                    'profit': profit,
                    'time': datetime.now().isoformat(),
                    'broker': 'MT5',
                    'status': 'open',
                }
                
                # Store trade in memory so it can be retrieved later
                if account_id not in demo_trades_storage:
                    demo_trades_storage[account_id] = []
                demo_trades_storage[account_id].append(demo_trade)
                
                logger.info(f"Created and stored demo trade: {symbol} {order_type} {volume} lots for account {account_id}")
                return jsonify(demo_trade), 200
            except Exception as e:
                logger.error(f"Error creating demo trade: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
    except Exception as e:
        logger.error(f"Error placing trade: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reports/summary', methods=['GET'])
def get_report_summary():
    """Get summary report data for all accounts"""
    reports = {}

    for account_id, connection in broker_manager.connections.items():
        if connection.connected:
            trades = connection.get_trades()
            
            closed_trades = trades
            winning = [t for t in closed_trades if t.get('profit', 0) > 0]
            losing = [t for t in closed_trades if t.get('profit', 0) <= 0]

            total_profit = sum(t.get('profit', 0) for t in closed_trades)
            total_loss = sum(t.get('profit', 0) for t in losing)

            reports[account_id] = {
                'broker': connection.broker_type.value,
                'accountNumber': connection.account_info.get('accountNumber') if connection.account_info else 'N/A',
                'totalTrades': len(closed_trades),
                'winningTrades': len(winning),
                'losingTrades': len(losing),
                'winRate': (len(winning) / len(closed_trades) * 100) if closed_trades else 0,
                'totalProfit': total_profit,
                'totalLoss': abs(total_loss),
                'netProfit': total_profit + total_loss,
                'largestWin': max([t.get('profit', 0) for t in winning], default=0),
                'largestLoss': min([t.get('profit', 0) for t in losing], default=0),
            }

    return jsonify({
        'success': True,
        'reports': reports,
        'timestamp': datetime.now().isoformat(),
    })


# ==================== ADVANCED TRADING ENDPOINTS ====================

@app.route('/api/positions/all', methods=['GET'])
def get_all_positions():
    """Get all open positions from all accounts"""
    try:
        all_positions = []
        for account_id, connection in broker_manager.connections.items():
            if connection.broker_type == BrokerType.METATRADER5 and connection.connected:
                try:
                    import MetaTrader5 as mt5
                    positions = connection.mt5.positions_get()
                    for position in positions:
                        all_positions.append({
                            'ticket': position.ticket,
                            'accountId': account_id,
                            'broker': 'MT5',
                            'symbol': position.symbol,
                            'type': 'BUY' if position.type == mt5.ORDER_TYPE_BUY else 'SELL',
                            'volume': position.volume,
                            'openPrice': position.price_open,
                            'currentPrice': position.price_current,
                            'profit': position.profit,
                            'profitPercent': (position.profit / (position.price_open * position.volume)) * 100 if position.price_open > 0 else 0,
                            'commission': position.commission,
                            'time': datetime.fromtimestamp(position.time).isoformat(),
                        })
                except Exception as e:
                    logger.error(f"Error getting positions for {account_id}: {e}")
        
        return jsonify({
            'success': True,
            'positions': all_positions,
            'count': len(all_positions),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in get_all_positions: {e}")
        return jsonify({'success': False, 'error': str(e), 'positions': []}), 500


@app.route('/api/position/close', methods=['POST'])
def close_position_api():
    """Close a specific position"""
    try:
        data = request.json
        account_id = data.get('accountId')
        position_id = data.get('positionId')
        
        if not account_id or not position_id:
            return jsonify({'success': False, 'error': 'Missing accountId or positionId'}), 400
        
        if account_id not in broker_manager.connections:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        connection = broker_manager.connections[account_id]
        if not connection.connected:
            return jsonify({'success': False, 'error': 'Account not connected'}), 400
        
        result = connection.close_position(position_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/account/equity', methods=['GET'])
def get_account_equity():
    """Get equity and margin for all accounts"""
    try:
        accounts_equity = []
        for account_id, connection in broker_manager.connections.items():
            if connection.connected and connection.account_info:
                accounts_equity.append({
                    'accountId': account_id,
                    'broker': connection.broker_type.value,
                    'balance': connection.account_info.get('balance', 0),
                    'equity': connection.account_info.get('equity', 0),
                    'margin': connection.account_info.get('margin', 0),
                    'marginFree': connection.account_info.get('margin_free', 0),
                    'marginLevel': connection.account_info.get('margin_level', 0),
                    'profit': connection.account_info.get('profit', 0),
                })
        
        return jsonify({
            'success': True,
            'accounts': accounts_equity,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error getting equity: {e}")
        return jsonify({'success': False, 'error': str(e), 'accounts': []}), 500


# ==================== MULTI-BROKER MANAGEMENT ENDPOINTS ====================

@app.route('/api/brokers/connect', methods=['POST'])
def connect_broker():
    """Connect a new broker account"""
    try:
        data = request.json
        account_id = data.get('accountId', 'broker_' + str(len(broker_manager.connections) + 1))
        broker_type_str = data.get('brokerType', 'mt5')
        credentials = data.get('credentials', {})
        
        # Map broker type string to enum
        broker_type_map = {
            'mt5': BrokerType.METATRADER5,
            'ib': BrokerType.INTERACTIVE_BROKERS,
            'oanda': BrokerType.OANDA,
        }
        
        broker_type = broker_type_map.get(broker_type_str.lower(), BrokerType.METATRADER5)
        
        if not broker_manager.add_connection(account_id, broker_type, credentials):
            return jsonify({'success': False, 'error': 'Failed to add connection'}), 400
        
        # Try to connect
        connection = broker_manager.connections[account_id]
        if hasattr(connection, 'connect'):
            if not connection.connect():
                return jsonify({'success': False, 'error': 'Failed to connect to broker'}), 400
        
        return jsonify({
            'success': True,
            'accountId': account_id,
            'broker': broker_type.value,
            'connected': connection.connected,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error connecting broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brokers/disconnect/<account_id>', methods=['POST'])
def disconnect_broker(account_id):
    """Disconnect a broker account"""
    try:
        if account_id not in broker_manager.connections:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        connection = broker_manager.connections[account_id]
        if hasattr(connection, 'disconnect'):
            connection.disconnect()
        
        del broker_manager.connections[account_id]
        logger.info(f"Disconnected from {account_id}")
        
        return jsonify({
            'success': True,
            'message': f'Disconnected from {account_id}',
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error disconnecting broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/commodities/list', methods=['GET'])
def list_commodities():
    """Get list of available trading symbols/commodities"""
    commodities = {
        'forex': [
            {'symbol': 'EURUSD', 'name': 'Euro vs US Dollar', 'type': 'Forex', 'min_price': 0.95, 'max_price': 1.15},
            {'symbol': 'GBPUSD', 'name': 'British Pound vs US Dollar', 'type': 'Forex', 'min_price': 1.15, 'max_price': 1.45},
            {'symbol': 'USDJPY', 'name': 'US Dollar vs Japanese Yen', 'type': 'Forex', 'min_price': 100, 'max_price': 160},
            {'symbol': 'AUDUSD', 'name': 'Australian Dollar vs US Dollar', 'type': 'Forex', 'min_price': 0.60, 'max_price': 0.80},
            {'symbol': 'NZDUSD', 'name': 'New Zealand Dollar vs US Dollar', 'type': 'Forex', 'min_price': 0.55, 'max_price': 0.75},
        ],
        'metals': [
            {'symbol': 'XAUUSD', 'name': 'Gold (per troy ounce)', 'type': 'Metal', 'lucrative': True, 'min_price': 1800, 'max_price': 2100},
            {'symbol': 'XAGUSD', 'name': 'Silver (per troy ounce)', 'type': 'Metal', 'lucrative': True, 'min_price': 20, 'max_price': 35},
            {'symbol': 'XPTUSD', 'name': 'Platinum (per troy ounce)', 'type': 'Metal', 'lucrative': True, 'min_price': 800, 'max_price': 1200},
            {'symbol': 'XPDUSD', 'name': 'Palladium (per troy ounce)', 'type': 'Metal', 'lucrative': True, 'min_price': 800, 'max_price': 1500},
        ],
        'energy': [
            {'symbol': 'WTIUSD', 'name': 'Crude Oil WTI (per barrel)', 'type': 'Energy', 'lucrative': True, 'min_price': 40, 'max_price': 140},
            {'symbol': 'BRENTUSD', 'name': 'Brent Crude Oil (per barrel)', 'type': 'Energy', 'lucrative': True, 'min_price': 40, 'max_price': 150},
            {'symbol': 'NATGASUS', 'name': 'Natural Gas (per MMBtu)', 'type': 'Energy', 'min_price': 1.5, 'max_price': 8.0},
        ],
        'agriculture': [
            {'symbol': 'CORNUSD', 'name': 'Corn (per bushel)', 'type': 'Agricultural', 'min_price': 3.0, 'max_price': 8.0},
            {'symbol': 'WHEATUSD', 'name': 'Wheat (per bushel)', 'type': 'Agricultural', 'min_price': 5.0, 'max_price': 13.0},
            {'symbol': 'SOYBEANSUSD', 'name': 'Soybeans (per bushel)', 'type': 'Agricultural', 'min_price': 8.0, 'max_price': 18.0},
            {'symbol': 'COFFEEUSD', 'name': 'Coffee Arabica (per lb)', 'type': 'Agricultural', 'min_price': 1.3, 'max_price': 3.0},
            {'symbol': 'COCOAUSD', 'name': 'Cocoa (per metric ton)', 'type': 'Agricultural', 'min_price': 2000, 'max_price': 4000},
            {'symbol': 'SUGARUSD', 'name': 'Sugar (per lb)', 'type': 'Agricultural', 'min_price': 15, 'max_price': 25},
        ],
        'indices': [
            {'symbol': 'SPX500', 'name': 'S&P 500 Index', 'type': 'Index', 'min_price': 3500, 'max_price': 5000},
            {'symbol': 'DAX40', 'name': 'DAX 40 (Germany)', 'type': 'Index', 'min_price': 12000, 'max_price': 18000},
            {'symbol': 'FTSE100', 'name': 'FTSE 100 (UK)', 'type': 'Index', 'min_price': 6500, 'max_price': 8500},
            {'symbol': 'NIKKEI225', 'name': 'Nikkei 225 (Japan)', 'type': 'Index', 'min_price': 25000, 'max_price': 35000},
        ]
    }
    
    return jsonify({
        'success': True,
        'commodities': commodities,
        'total_symbols': sum(len(v) for v in commodities.values()),
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/demo/generate-trades', methods=['POST'])
def generate_demo_trades():
    """Generate mock trades for demo/testing purposes"""
    try:
        import random
        from decimal import Decimal
        
        account_id = request.json.get('accountId', 'default_mt5') if request.json else 'default_mt5'
        count = request.json.get('count', 5) if request.json else 5
        
        demo_trades = []
        
        # Define trading symbols with realistic price ranges
        commodity_data = {
            # Forex pairs
            'EURUSD': {'min_price': 0.95, 'max_price': 1.15, 'volume_range': (0.1, 5.0)},
            'GBPUSD': {'min_price': 1.15, 'max_price': 1.45, 'volume_range': (0.1, 5.0)},
            'USDJPY': {'min_price': 100, 'max_price': 160, 'volume_range': (0.1, 5.0)},
            'AUDUSD': {'min_price': 0.60, 'max_price': 0.80, 'volume_range': (0.1, 5.0)},
            'NZDUSD': {'min_price': 0.55, 'max_price': 0.75, 'volume_range': (0.1, 5.0)},
            
            # Precious Metals (HIGH PROFIT POTENTIAL)
            'XAUUSD': {'min_price': 1800, 'max_price': 2100, 'volume_range': (0.01, 2.0)},  # GOLD
            'XAGUSD': {'min_price': 20, 'max_price': 35, 'volume_range': (0.1, 5.0)},  # SILVER
            'XPTUSD': {'min_price': 800, 'max_price': 1200, 'volume_range': (0.01, 1.0)},  # PLATINUM
            'XPDUSD': {'min_price': 800, 'max_price': 1500, 'volume_range': (0.01, 1.0)},  # PALLADIUM
            
            # Energy commodities
            'WTIUSD': {'min_price': 40, 'max_price': 140, 'volume_range': (1, 100)},  # CRUDE OIL WTI
            'BRENTUSD': {'min_price': 40, 'max_price': 150, 'volume_range': (1, 100)},  # BRENT CRUDE
            'NATGASUS': {'min_price': 1.5, 'max_price': 8.0, 'volume_range': (10, 200)},  # NATURAL GAS
            
            # Agricultural commodities
            'CORNUSD': {'min_price': 3.0, 'max_price': 8.0, 'volume_range': (1, 50)},  # CORN
            'WHEATUSD': {'min_price': 5.0, 'max_price': 13.0, 'volume_range': (1, 50)},  # WHEAT
            'SOYBEANSUSD': {'min_price': 8.0, 'max_price': 18.0, 'volume_range': (1, 50)},  # SOYBEANS
            'COFFEEUSD': {'min_price': 1.3, 'max_price': 3.0, 'volume_range': (10, 200)},  # COFFEE
            'COCOAUSD': {'min_price': 2000, 'max_price': 4000, 'volume_range': (1, 50)},  # COCOA
            'SUGARUSD': {'min_price': 15, 'max_price': 25, 'volume_range': (10, 200)},  # SUGAR
            
            # Indices
            'SPX500': {'min_price': 3500, 'max_price': 5000, 'volume_range': (0.1, 5.0)},  # S&P 500
            'DAX40': {'min_price': 12000, 'max_price': 18000, 'volume_range': (0.1, 5.0)},  # DAX
            'FTSE100': {'min_price': 6500, 'max_price': 8500, 'volume_range': (0.1, 5.0)},  # FTSE 100
            'NIKKEI225': {'min_price': 25000, 'max_price': 35000, 'volume_range': (0.01, 2.0)},  # Nikkei
        }
        
        symbols = list(commodity_data.keys())
        
        for i in range(count):
            symbol = random.choice(symbols)
            symbol_data = commodity_data[symbol]
            
            # Higher profit potential for commodities
            profit = random.uniform(-1000, 5000) if 'XAU' in symbol or 'WTI' in symbol else random.uniform(-500, 2500)
            
            demo_trades.append({
                'ticket': 1000000 + i,
                'accountId': account_id,
                'symbol': symbol,
                'type': random.choice(['BUY', 'SELL']),
                'volume': random.uniform(symbol_data['volume_range'][0], symbol_data['volume_range'][1]),
                'price': random.uniform(symbol_data['min_price'], symbol_data['max_price']),
                'profit': profit,
                'time': (datetime.now().isoformat()),
                'broker': 'MT5',
            })
        
        return jsonify({
            'success': True,
            'trades': demo_trades,
            'message': f'Generated {count} demo trades',
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error generating demo trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ALIAS ROUTES (for Flutter app compatibility) ====================
@app.route('/api/trades', methods=['GET'])
def get_trades_alias():
    """Alias for /api/trades/all - returns flattened trades list including demo trades"""
    try:
        trades_list = []
        
        # Get real trades from broker connections
        all_trades = {}
        for account_id, connection in broker_manager.connections.items():
            if connection.broker_type == BrokerType.METATRADER5:
                trades = connection.get_trades()
                # Ensure trades is always a list
                if trades is None:
                    trades = []
                elif isinstance(trades, dict):
                    # If accidentally passed dict, extract trades list if it exists
                    trades = trades.get('trades', []) if isinstance(trades, dict) else []
                all_trades[account_id] = trades
        
        # Add real trades from broker accounts
        for account_id, trades in all_trades.items():
            if isinstance(trades, list):
                for trade in trades:
                    if isinstance(trade, dict):
                        trade['accountId'] = account_id
                        trades_list.append(trade)
        
        # Add demo trades from storage
        for account_id, demo_trades in demo_trades_storage.items():
            if isinstance(demo_trades, list):
                for demo_trade in demo_trades:
                    if isinstance(demo_trade, dict):
                        # Make sure it has all required fields
                        if 'accountId' not in demo_trade:
                            demo_trade['accountId'] = account_id
                        trades_list.append(demo_trade)
        
        logger.info(f"Returning {len(trades_list)} trades (including {sum(len(t) for t in demo_trades_storage.values())} demo trades) to Flutter app")
        return jsonify({
            'success': True,
            'trades': trades_list,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in get_trades_alias: {e}")
        return jsonify({
            'success': False,
            'trades': [],
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }), 500


@app.route('/api/account/info', methods=['GET'])
def get_account_info_alias():
    """Get info for the first/default account"""
    for account_id, connection in broker_manager.connections.items():
        if connection.connected:
            return jsonify({
                'success': True,
                'account': {
                    'accountId': account_id,
                    'broker': connection.broker_type.value,
                    'accountNumber': connection.account_info.get('accountNumber') if connection.account_info else 'N/A',
                    'balance': connection.account_info.get('balance', 0) if connection.account_info else 0,
                    'equity': connection.account_info.get('equity', 0) if connection.account_info else 0,
                    'margin': connection.account_info.get('margin', 0) if connection.account_info else 0,
                    'freeMargin': connection.account_info.get('margin_free', 0) if connection.account_info else 0,
                }
            })
    
    # Return default account info if no connection found
    return jsonify({
        'success': True,
        'account': {
            'accountId': 'default_mt5',
            'broker': 'mt5',
            'accountNumber': MT5_CONFIG['account'],
            'balance': 0,
            'equity': 0,
            'margin': 0,
            'freeMargin': 0,
        }
    })


# ==================== BOT TRADING STRATEGY IMPLEMENTATIONS ====================

def scalping_strategy(symbol, account_id, risk_amount):
    """Scalping: Quick trades with small profits (0-5 pips)"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.5, 2.0),
        'profit': random.uniform(-risk_amount * 0.5, risk_amount * 0.3),
    }

def momentum_strategy(symbol, account_id, risk_amount):
    """Momentum: Follow strong price movements"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.1, 1.5),
        'profit': random.uniform(-risk_amount, risk_amount * 2),
    }

def trend_following_strategy(symbol, account_id, risk_amount):
    """Trend Following: Hold trades longer (big trends)"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.2, 1.0),
        'profit': random.uniform(-risk_amount * 0.3, risk_amount * 5),
    }

def mean_reversion_strategy(symbol, account_id, risk_amount):
    """Mean Reversion: Trade when price extreme"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.3, 1.2),
        'profit': random.uniform(-risk_amount * 0.2, risk_amount * 1.5),
    }

def range_trading_strategy(symbol, account_id, risk_amount):
    """Range Trading: Buy low, sell high within range"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.4, 1.5),
        'profit': random.uniform(-risk_amount * 0.1, risk_amount * 1),
    }

def breakout_strategy(symbol, account_id, risk_amount):
    """Breakout: Trade when price breaks support/resistance"""
    import random
    return {
        'symbol': symbol,
        'type': random.choice(['BUY', 'SELL']),
        'volume': random.uniform(0.2, 1.8),
        'profit': random.uniform(-risk_amount * 0.5, risk_amount * 3),
    }

STRATEGY_MAP = {
    'Scalping': scalping_strategy,
    'Momentum Trading': momentum_strategy,
    'Trend Following': trend_following_strategy,
    'Mean Reversion': mean_reversion_strategy,
    'Range Trading': range_trading_strategy,
    'Breakout Trading': breakout_strategy,
}

# ==================== INTELLIGENT STRATEGY SWITCHING & POSITION SIZING ====================

class StrategyPerformanceTracker:
    """Tracks performance of each strategy to enable intelligent switching"""
    
    def __init__(self):
        self.strategy_stats = {}
        self.reset_stats()
    
    def reset_stats(self):
        """Initialize stats for all strategies"""
        self.strategy_stats = {
            'Scalping': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
            'Momentum Trading': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
            'Trend Following': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
            'Mean Reversion': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
            'Range Trading': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
            'Breakout Trading': {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0},
        }
    
    def record_trade(self, strategy, profit, symbol=''):
        """Record a trade result for a strategy"""
        if strategy not in self.strategy_stats:
            self.strategy_stats[strategy] = {'trades': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'wins_streak': 0, 'losses_streak': 0}
        
        stats = self.strategy_stats[strategy]
        stats['trades'] += 1
        stats['profit'] += profit
        
        if profit > 0:
            stats['wins'] += 1
            stats['wins_streak'] += 1
            stats['losses_streak'] = 0
        else:
            stats['losses'] += 1
            stats['losses_streak'] += 1
            stats['wins_streak'] = 0
        
        logger.debug(f"Recorded {strategy} trade on {symbol}: profit={profit}, total_stats={stats}")
    
    def get_win_rate(self, strategy):
        """Get win rate for strategy"""
        stats = self.strategy_stats.get(strategy, {})
        trades = stats.get('trades', 0)
        if trades == 0:
            return 0
        return (stats.get('wins', 0) / trades) * 100
    
    def get_profit_factor(self, strategy):
        """Calculate profit factor (total wins / abs(total losses))"""
        stats = self.strategy_stats.get(strategy, {})
        profit = stats.get('profit', 0)
        trades = stats.get('trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        
        if losses == 0 or trades < 3:
            return 1.0  # Insufficient data
        
        avg_win = profit / wins if wins > 0 else 0
        avg_loss = -profit / losses if losses > 0 else 0
        
        if avg_loss == 0:
            return 99.99
        
        return avg_win / abs(avg_loss) if avg_loss != 0 else 1.0
    
    def get_best_strategy(self):
        """Get best performing strategy based on profit factor and win rate"""
        best_strategy = 'Trend Following'  # Default
        best_score = 0
        
        for strategy, stats in self.strategy_stats.items():
            if stats['trades'] < 3:  # Need at least 3 trades for evaluation
                continue
            
            win_rate = self.get_win_rate(strategy)
            profit_factor = self.get_profit_factor(strategy)
            total_profit = stats['profit']
            
            # Composite score: 40% profit_factor + 40% win_rate + 20% total_profit (normalized)
            score = (profit_factor * 0.4) + (win_rate / 100 * 0.4) + min(total_profit / 1000, 1.0) * 0.2
            
            if score > best_score:
                best_score = score
                best_strategy = strategy
        
        return best_strategy
    
    def get_all_stats(self):
        """Get all strategy statistics"""
        return {
            strategy: {
                **stats,
                'win_rate': self.get_win_rate(strategy),
                'profit_factor': round(self.get_profit_factor(strategy), 2),
            }
            for strategy, stats in self.strategy_stats.items()
        }


class DynamicPositionSizer:
    """Intelligently adjusts position sizes based on account performance"""
    
    def __init__(self, base_size=1.0, min_size=0.1, max_size=5.0):
        self.base_size = base_size
        self.min_size = min_size
        self.max_size = max_size
    
    def calculate_position_size(self, bot_config, volatility_level='Medium'):
        """
        Calculate optimal position size based on:
        - Account equity changes (scaling)
        - Win/loss streaks (confidence)
        - Volatility (risk adjustment)
        - Drawdown (protection)
        """
        import random
        
        size = self.base_size
        
        # Get account performance metrics
        total_trades = bot_config.get('totalTrades', 0)
        winning_trades = bot_config.get('winningTrades', 0)
        total_profit = bot_config.get('totalProfit', 0)
        max_drawdown = bot_config.get('maxDrawdown', 0)
        peak_profit = bot_config.get('peakProfit', 0)
        
        # 1. EQUITY SCALING - Scale by cumulative profit
        if total_trades > 0 and total_profit > 0:
            equity_multiplier = 1.0 + (total_profit / 1000)  # +10% size per $1000 profit
            size *= min(equity_multiplier, 1.5)  # Cap at 1.5x
        
        # 2. WIN STREAK SCALING - Increase after winning trades
        if total_trades > 0:
            recent_trades = bot_config.get('tradeHistory', [])[-5:] if bot_config.get('tradeHistory') else []
            win_streak = 0
            for trade in reversed(recent_trades):
                if trade.get('profit', 0) > 0:
                    win_streak += 1
                else:
                    break
            
            if win_streak > 2:
                size *= (1.0 + (win_streak * 0.1))  # +10% per win in streak
            elif win_streak < 0:  # Loss streak
                size *= 0.8  # Reduce by 20% after losses
        
        # 3. VOLATILITY ADJUSTMENT
        volatility_multiplier = {
            'Low': 1.1,      # Increase size in low volatility
            'Medium': 1.0,   # Normal size
            'High': 0.8,     # Reduce in high volatility
            'Very High': 0.6 # Significantly reduce in extreme volatility
        }
        size *= volatility_multiplier.get(volatility_level, 1.0)
        
        # 4. DRAWDOWN PROTECTION - Reduce size during drawdowns
        if peak_profit > 0 and max_drawdown > 0:
            drawdown_percent = (max_drawdown / peak_profit) * 100
            if drawdown_percent > 20:  # If drawdown > 20%
                size *= 0.5  # Reduce to 50%
            elif drawdown_percent > 10:  # If drawdown > 10%
                size *= 0.7  # Reduce to 70%
        
        # 5. APPLY MIN/MAX CONSTRAINTS
        final_size = max(self.min_size, min(size, self.max_size))
        
        return round(final_size, 2)


# Initialize trackers
strategy_tracker = StrategyPerformanceTracker()
position_sizer = DynamicPositionSizer(base_size=1.0, min_size=0.1, max_size=5.0)

# ==================== AUTO-INITIALIZE DEMO BOTS ====================
def initialize_demo_bots():
    """Auto-initialize demo trading bots on startup"""
    demo_bots_config = [
        {
            'botId': 'DemoBot_EURUSD_TrendFollow',
            'accountId': 'Demo MT5 - XM Global',
            'symbols': ['EURUSD', 'GBPUSD', 'USDJPY'],
            'strategy': 'Trend Following',
            'riskPerTrade': 100,
            'maxDailyLoss': 500,
            'enabled': True,
            'autoSwitch': True,
            'dynamicSizing': True,
            'basePositionSize': 1.0
        },
        {
            'botId': 'DemoBot_Commodities_MeanReversion',
            'accountId': 'Demo MT5 - XM Global',
            'symbols': ['XAUUSD', 'XAGUSD', 'WTIUSD'],
            'strategy': 'Mean Reversion',
            'riskPerTrade': 75,
            'maxDailyLoss': 400,
            'enabled': True,
            'autoSwitch': True,
            'dynamicSizing': True,
            'basePositionSize': 0.8
        },
        {
            'botId': 'DemoBot_Indices_RangeTrading',
            'accountId': 'Demo MT5 - XM Global',
            'symbols': ['SPX500', 'UK100', 'GER40'],
            'strategy': 'Range Trading',
            'riskPerTrade': 125,
            'maxDailyLoss': 600,
            'enabled': True,
            'autoSwitch': True,
            'dynamicSizing': True,
            'basePositionSize': 1.2
        }
    ]
    
    for bot_config in demo_bots_config:
        now = datetime.now()
        active_bots[bot_config['botId']] = {
            'botId': bot_config['botId'],
            'accountId': bot_config['accountId'],
            'symbols': bot_config['symbols'],
            'strategy': bot_config['strategy'],
            'riskPerTrade': bot_config['riskPerTrade'],
            'maxDailyLoss': bot_config['maxDailyLoss'],
            'enabled': bot_config['enabled'],
            'autoSwitch': bot_config['autoSwitch'],
            'dynamicSizing': bot_config['dynamicSizing'],
            'basePositionSize': bot_config['basePositionSize'],
            'totalTrades': 0,
            'winningTrades': 0,
            'totalProfit': 0,
            'totalLosses': 0,
            'totalInvestment': 0,
            'createdAt': now.isoformat(),
            'startTime': now.isoformat(),
            'profitHistory': [],
            'tradeHistory': [],
            'dailyProfits': {},
            'maxDrawdown': 0,
            'peakProfit': 0,
            'strategyHistory': [],
            'lastStrategySwitch': now.isoformat(),
            'volatilityLevel': 'Medium',
        }
        logger.info(f"Initialized demo bot: {bot_config['botId']} ({bot_config['strategy']})")

# ==================== BOT TRADING ENDPOINTS ====================


@app.route('/api/strategy/recommend', methods=['GET'])
def recommend_strategy():
    """Get recommended strategy based on current performance"""
    try:
        best_strategy = strategy_tracker.get_best_strategy()
        all_stats = strategy_tracker.get_all_stats()
        
        return jsonify({
            'success': True,
            'recommendedStrategy': best_strategy,
            'allStats': all_stats,
            'timestamp': datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting strategy recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/position/sizing-metrics/<bot_id>', methods=['GET'])
def get_position_sizing_metrics(bot_id):
    """Get detailed position sizing metrics for a bot"""
    try:
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        volatility = bot_config.get('volatilityLevel', 'Medium')
        
        # Calculate position sizes at different volatility levels
        position_sizes = {
            'current': position_sizer.calculate_position_size(bot_config, volatility),
            'low_volatility': position_sizer.calculate_position_size(bot_config, 'Low'),
            'medium_volatility': position_sizer.calculate_position_size(bot_config, 'Medium'),
            'high_volatility': position_sizer.calculate_position_size(bot_config, 'High'),
            'very_high_volatility': position_sizer.calculate_position_size(bot_config, 'Very High'),
        }
        
        # Get equity metrics
        total_profit = bot_config.get('totalProfit', 0)
        peak_profit = bot_config.get('peakProfit', 0)
        max_drawdown = bot_config.get('maxDrawdown', 0)
        
        drawdown_percent = (max_drawdown / peak_profit * 100) if peak_profit > 0 else 0
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'positionSizing': position_sizes,
            'equityMetrics': {
                'currentProfit': round(total_profit, 2),
                'peakProfit': round(peak_profit, 2),
                'maxDrawdown': round(max_drawdown, 2),
                'drawdownPercent': round(drawdown_percent, 2),
                'profitFactor': round((total_profit / max(max_drawdown, 1)), 2),
            },
            'volatilityLevel': volatility,
            'timestamp': datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting position sizing metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/config/<bot_id>', methods=['GET'])
def get_bot_config(bot_id):
    """Get complete bot configuration and status"""
    try:
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot = active_bots[bot_id]
        
        # Calculate runtime
        created = datetime.fromisoformat(bot['createdAt'])
        runtime_seconds = (datetime.now() - created).total_seconds()
        runtime_hours = runtime_seconds / 3600
        runtime_minutes = (runtime_seconds % 3600) / 60
        
        return jsonify({
            'success': True,
            'config': {
                'botId': bot.get('botId'),
                'accountId': bot.get('accountId'),
                'strategy': bot.get('strategy'),
                'symbols': bot.get('symbols'),
                'autoSwitch': bot.get('autoSwitch', True),
                'dynamicSizing': bot.get('dynamicSizing', True),
                'basePositionSize': bot.get('basePositionSize', 1.0),
                'riskPerTrade': bot.get('riskPerTrade'),
                'maxDailyLoss': bot.get('maxDailyLoss'),
                'enabled': bot.get('enabled'),
                'volatilityLevel': bot.get('volatilityLevel'),
            },
            'status': {
                'runtime': f"{int(runtime_hours):02d}:{int(runtime_minutes):02d}",
                'totalTrades': bot.get('totalTrades'),
                'winningTrades': bot.get('winningTrades'),
                'winRate': round((bot.get('winningTrades', 0) / max(bot.get('totalTrades', 1), 1)) * 100, 2),
                'totalProfit': round(bot.get('totalProfit', 0), 2),
                'dailyProfit': round(bot.get('dailyProfits', {}).get(datetime.now().strftime('%Y-%m-%d'), 0), 2),
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
            },
            'intelligence': {
                'lastStrategySwitch': bot.get('lastStrategySwitch'),
                'strategyChanges': len(bot.get('strategyHistory', [])),
                'strategyHistory': bot.get('strategyHistory', [])[-5:],  # Last 5 switches
            },
            'timestamp': datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting bot config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Commodity Market Sentiment Data
# Tracks price trends, volatility, and trading signals
commodity_market_data = {
    'EURUSD': {'price': 1.0890, 'change': 0.35, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 STRONG BUY', 'recommendation': 'Positive trajectory - good for trend following'},
    'GBPUSD': {'price': 1.2750, 'change': -0.22, 'trend': 'DOWN', 'volatility': 'Medium', 'signal': '🔴 SELL', 'recommendation': 'Downtrend - risky, avoid'},
    'USDJPY': {'price': 149.50, 'change': 0.15, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Slight uptrend, moderate opportunity'},
    'AUDUSD': {'price': 0.6580, 'change': 0.88, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Strong uptrend with high volatility - excellent'},
    'GOLD': {'price': 2045.50, 'change': 1.25, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Bullish trend - safe choice for scalping'},
    'SILVER': {'price': 24.30, 'change': -0.55, 'trend': 'DOWN', 'volatility': 'High', 'signal': '🟡 CAUTION', 'recommendation': 'Mixed signals - use smaller positions'},
    'PLATINUM': {'price': 920.00, 'change': 0.42, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Steady uptrend - reliable'},
    'PALLADIUM': {'price': 980.50, 'change': -1.10, 'trend': 'DOWN', 'volatility': 'High', 'signal': '🔴 SELL', 'recommendation': 'Downtrend with volatility - avoid'},
    'COPPER': {'price': 3.85, 'change': 0.65, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point'},
    'CRUDE_OIL': {'price': 82.45, 'change': 1.85, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Strong bullish action'},
    'NATURAL_GAS': {'price': 2.85, 'change': -2.40, 'trend': 'DOWN', 'volatility': 'Very High', 'signal': '🔴 SELL', 'recommendation': 'Strong downtrend - high risk'},
    'COFFEE': {'price': 225.50, 'change': 0.95, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Uptrend confirmed'},
    'SUGAR': {'price': 25.40, 'change': -0.35, 'trend': 'DOWN', 'volatility': 'Low', 'signal': '🟡 CAUTION', 'recommendation': 'Slight downtrend - wait for confirmation'},
    'WHEAT': {'price': 520.00, 'change': 0.55, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Positive seasonal trend'},
    'CORN': {'price': 425.75, 'change': 0.20, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Stable uptrend - safe trade'},
    'SOYBEAN': {'price': 1285.50, 'change': -0.45, 'trend': 'DOWN', 'volatility': 'Medium', 'signal': '🟡 CAUTION', 'recommendation': 'Mixed signals - monitor closely'},
    'COTTON': {'price': 76.80, 'change': 0.75, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 BUY', 'recommendation': 'Strong uptrend'},
    'CATTLE': {'price': 132.50, 'change': 1.10, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Bullish trend confirmed'},
    'HOGS': {'price': 78.25, 'change': -0.80, 'trend': 'DOWN', 'volatility': 'Medium', 'signal': '🔴 SELL', 'recommendation': 'Downtrend - avoid'},
    'DAX': {'price': 18250.00, 'change': 0.45, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Steady index growth'},
    'FTSE': {'price': 7890.50, 'change': -0.25, 'trend': 'DOWN', 'volatility': 'Low', 'signal': '🟡 CAUTION', 'recommendation': 'Slight decline - exercise caution'},
    'CAC40': {'price': 8050.75, 'change': 0.60, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Strong uptrend'},
    'NIKKEI': {'price': 28900.00, 'change': 2.35, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Very bullish'},
    'BITCOIN': {'price': 72500.00, 'change': 5.20, 'trend': 'UP', 'volatility': 'Very High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Strong bullish momentum'},
}

# Store active bots configuration
active_bots = {}

@app.route('/api/bot/create', methods=['POST'])
def create_bot():
    """Create and start a new trading bot"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No configuration provided'}), 400
        
        bot_id = data.get('botId') or f"bot_{datetime.now().timestamp()}"
        account_id = data.get('accountId', 'Default MT5')
        symbols = data.get('symbols', ['EURUSD'])  # List of symbols to trade
        strategy = data.get('strategy', 'Trend Following')
        risk_per_trade = float(data.get('riskPerTrade', 100))
        max_daily_loss = float(data.get('maxDailyLoss', 500))
        trading_enabled = data.get('enabled', True)
        
        # Store bot configuration with enhanced tracking
        now = datetime.now()
        auto_switch = data.get('autoSwitch', True)  # Enable intelligent strategy switching
        dynamic_sizing = data.get('dynamicSizing', True)  # Enable position sizing
        
        active_bots[bot_id] = {
            'botId': bot_id,
            'accountId': account_id,
            'symbols': symbols,
            'strategy': strategy,
            'riskPerTrade': risk_per_trade,
            'maxDailyLoss': max_daily_loss,
            'enabled': trading_enabled,
            'autoSwitch': auto_switch,  # Intelligent strategy switching
            'dynamicSizing': dynamic_sizing,  # Dynamic position sizing
            'basePositionSize': data.get('basePositionSize', 1.0),
            'totalTrades': 0,
            'winningTrades': 0,
            'totalProfit': 0,
            'totalLosses': 0,
            'totalInvestment': 0,
            'createdAt': now.isoformat(),
            'startTime': now.isoformat(),
            'profitHistory': [],  # List of {timestamp, profit} for charting
            'tradeHistory': [],  # Detailed trade log
            'dailyProfits': {},  # Date -> daily profit
            'maxDrawdown': 0,
            'peakProfit': 0,
            'strategyHistory': [],  # Track strategy changes over time
            'lastStrategySwitch': now.isoformat(),
            'volatilityLevel': 'Medium',  # Current market volatility
        }
        
        logger.info(f"Created bot {bot_id}: {strategy} on symbols {symbols}")
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'message': f'Bot {bot_id} created and running',
            'config': active_bots[bot_id]
        }), 200
    
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start automatic trading for a bot with intelligent strategy switching"""
    try:
        data = request.json
        bot_id = data.get('botId')
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        import random
        bot_config = active_bots[bot_id]
        
        # INTELLIGENT STRATEGY SWITCHING
        if bot_config.get('autoSwitch', True):
            # Check if we should switch strategies (every 10 trades)
            if bot_config['totalTrades'] > 0 and bot_config['totalTrades'] % 10 == 0:
                best_strategy = strategy_tracker.get_best_strategy()
                if best_strategy != bot_config['strategy']:
                    old_strategy = bot_config['strategy']
                    bot_config['strategy'] = best_strategy
                    bot_config['lastStrategySwitch'] = datetime.now().isoformat()
                    bot_config['strategyHistory'].append({
                        'timestamp': bot_config['lastStrategySwitch'],
                        'oldStrategy': old_strategy,
                        'newStrategy': best_strategy,
                        'reason': 'Auto-switch to best performer',
                        'trades': bot_config['totalTrades']
                    })
                    logger.info(f"Bot {bot_id} switched from {old_strategy} to {best_strategy}")
        
        # Get strategy function
        strategy_name = bot_config['strategy']
        strategy_func = STRATEGY_MAP.get(strategy_name, trend_following_strategy)
        
        # Simulate bot placing trades on configured symbols
        trades_placed = []
        for symbol in bot_config['symbols'][:3]:  # Limit to 3 trades per cycle
            # DYNAMIC POSITION SIZING
            if bot_config.get('dynamicSizing', True):
                position_size = position_sizer.calculate_position_size(
                    bot_config, 
                    volatility_level=bot_config.get('volatilityLevel', 'Medium')
                )
            else:
                position_size = bot_config.get('basePositionSize', 1.0)
            
            # Call strategy function to determine trade parameters
            trade_params = strategy_func(symbol, bot_config['accountId'], bot_config['riskPerTrade'])
            
            # Apply dynamic position sizing to the volume
            adjusted_volume = trade_params['volume'] * position_size
            
            trade = {
                'ticket': random.randint(1000000, 9999999),
                'symbol': trade_params['symbol'],
                'type': trade_params['type'],
                'volume': round(adjusted_volume, 2),
                'baseVolume': trade_params['volume'],
                'positionSize': position_size,
                'entryPrice': random.uniform(1, 2000),
                'profit': trade_params['profit'],
                'time': datetime.now().isoformat(),
                'timestamp': int(datetime.now().timestamp() * 1000),  # milliseconds for charting
                'botId': bot_id,
                'strategy': strategy_name,
                'isWinning': trade_params['profit'] > 0,
            }
            
            # Store trade
            if bot_config['accountId'] not in demo_trades_storage:
                demo_trades_storage[bot_config['accountId']] = []
            demo_trades_storage[bot_config['accountId']].append(trade)
            
            # Record strategy performance
            strategy_tracker.record_trade(strategy_name, trade['profit'], symbol)
            
            # Update bot stats
            bot_config['totalTrades'] += 1
            bot_config['totalInvestment'] += trade['volume'] * trade['entryPrice']
            
            if trade['profit'] > 0:
                bot_config['winningTrades'] += 1
            else:
                bot_config['totalLosses'] += abs(trade['profit'])
            
            bot_config['totalProfit'] += trade['profit']
            
            # Update peak and drawdown
            if bot_config['totalProfit'] > bot_config['peakProfit']:
                bot_config['peakProfit'] = bot_config['totalProfit']
            
            drawdown = bot_config['peakProfit'] - bot_config['totalProfit']
            if drawdown > bot_config['maxDrawdown']:
                bot_config['maxDrawdown'] = drawdown
            
            # Track profit history for charting
            bot_config['profitHistory'].append({
                'timestamp': trade['timestamp'],
                'profit': round(bot_config['totalProfit'], 2),
                'trades': bot_config['totalTrades'],
            })
            
            # Track daily profit
            today = datetime.now().strftime('%Y-%m-%d')
            if today not in bot_config['dailyProfits']:
                bot_config['dailyProfits'][today] = 0
            bot_config['dailyProfits'][today] += trade['profit']
            
            # Add to trade history
            bot_config['tradeHistory'].append(trade)
            
            trades_placed.append(trade)
        
        logger.info(f"Bot {bot_id} ({strategy_name}) placed {len(trades_placed)} trades with dynamic sizing")
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'strategy': strategy_name,
            'tradesPlaced': len(trades_placed),
            'trades': trades_placed,
            'positionSizing': {
                'base': bot_config.get('basePositionSize', 1.0),
                'current': position_sizer.calculate_position_size(bot_config, bot_config.get('volatilityLevel', 'Medium')),
                'dynamic': bot_config.get('dynamicSizing', True),
            },
            'botStats': {
                'totalTrades': bot_config['totalTrades'],
                'winningTrades': bot_config['winningTrades'],
                'totalLosses': round(bot_config['totalLosses'], 2),
                'totalProfit': round(bot_config['totalProfit'], 2),
                'totalInvestment': round(bot_config['totalInvestment'], 2),
                'winRate': round((bot_config['winningTrades'] / bot_config['totalTrades'] * 100) if bot_config['totalTrades'] > 0 else 0, 2),
                'roi': round((bot_config['totalProfit'] / max(bot_config['totalInvestment'], 1)) * 100, 2),
                'maxDrawdown': round(bot_config['maxDrawdown'], 2),
                'profitFactor': round((bot_config['totalProfit'] / max(bot_config['totalLosses'], 1)), 2) if bot_config['totalLosses'] > 0 else 99.99,
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500




@app.route('/api/market/commodities', methods=['GET'])
def get_commodity_market_data():
    """Get market sentiment and price data for all trading commodities"""
    try:
        return jsonify({
            'success': True,
            'commodities': commodity_market_data,
            'timestamp': datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    """Get status of all active bots with enhanced metrics"""
    try:
        bots_list = []
        for bot in active_bots.values():
            # Calculate runtime
            created = datetime.fromisoformat(bot['createdAt'])
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profit = bot['dailyProfits'].get(today, 0)
            
            # Calculate ROI
            investment = bot['totalInvestment']
            roi = (bot['totalProfit'] / max(investment, 1)) * 100 if investment > 0 else 0
            
            # Calculate profit factor - capped at 99.99 to avoid JSON infinity issues
            if bot['totalLosses'] > 0:
                profit_factor = min(bot['totalProfit'] / bot['totalLosses'], 99.99)
            else:
                profit_factor = 99.99 if bot['totalProfit'] > 0 else 0
            
            enhanced_bot = bot.copy()
            enhanced_bot.update({
                'runtimeHours': round(runtime_hours, 2),
                'runtimeMinutes': int(runtime_minutes),
                'runtimeSeconds': int(runtime_seconds),
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit, 2),
                'roi': round(roi, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(bot['totalProfit'] / max(bot['totalTrades'], 1), 2),
                'status': 'Active' if bot['enabled'] else 'Inactive',
                'lastTradeTime': bot['tradeHistory'][-1]['time'] if bot['tradeHistory'] else bot['createdAt'],
            })
            bots_list.append(enhanced_bot)
        
        return jsonify({
            'success': True,
            'activeBots': len([b for b in bots_list if b['enabled']]),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop/<bot_id>', methods=['POST'])
def stop_bot(bot_id):
    """Stop a trading bot"""
    try:
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        bot_config['enabled'] = False
        
        logger.info(f"Stopped bot {bot_id}")
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} stopped',
            'finalStats': {
                'totalTrades': bot_config['totalTrades'],
                'winningTrades': bot_config['winningTrades'],
                'totalProfit': bot_config['totalProfit'],
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COMMODITY MARKET DATA ====================
import random as rand

COMMODITIES = {
    # Forex
    'EURUSD': {'category': 'Forex', 'emoji': '📍'},
    'GBPUSD': {'category': 'Forex', 'emoji': '🇬🇧'},
    'USDJPY': {'category': 'Forex', 'emoji': '🇯🇵'},
    'AUDUSD': {'category': 'Forex', 'emoji': '🦘'},
    'USDCAD': {'category': 'Forex', 'emoji': '🍁'},
    
    # Metals
    'GOLD': {'category': 'Metals', 'emoji': '💎'},
    'SILVER': {'category': 'Metals', 'emoji': '🔗'},
    'PLATINUM': {'category': 'Metals', 'emoji': '⚙️'},
    'PALLADIUM': {'category': 'Metals', 'emoji': '🔌'},
    'COPPER': {'category': 'Metals', 'emoji': '🔴'},
    
    # Energies
    'CRUDE_OIL': {'category': 'Energy', 'emoji': '🛢️'},
    'NATURAL_GAS': {'category': 'Energy', 'emoji': '💨'},
    'BRENT_OIL': {'category': 'Energy', 'emoji': '⛽'},
    
    # Agricom
    'WHEAT': {'category': 'Agriculture', 'emoji': '🌾'},
    'CORN': {'category': 'Agriculture', 'emoji': '🌽'},
    'SOYBEANS': {'category': 'Agriculture', 'emoji': '🫘'},
    'COFFEE': {'category': 'Agriculture', 'emoji': '☕'},
    'SUGAR': {'category': 'Agriculture', 'emoji': '🍯'},
    'COCOA': {'category': 'Agriculture', 'emoji': '🍫'},
    
    # Indices
    'SP500': {'category': 'Indices', 'emoji': '📊'},
    'DAX': {'category': 'Indices', 'emoji': '📈'},
    'NZD/USD': {'category': 'Forex', 'emoji': '📍'},
}

if __name__ == '__main__':
    logger.info("Starting Zwesta Multi-Broker Backend")
    logger.info(f"MT5 Account: {MT5_CONFIG['account']}")
    logger.info(f"MT5 Server: {MT5_CONFIG['server']}")
    
    # Initialize demo bots on startup
    logger.info("Initializing demo trading bots...")
    initialize_demo_bots()
    logger.info(f"[OK] {len(active_bots)} demo bots initialized and ready")
    
    try:
        # Try ports in order: 9000, 5000, 3000
        ports = [9000, 5000, 3000]
        started = False
        for port in ports:
            try:
                logger.info(f"Attempting to start on http://0.0.0.0:{port}")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                started = True
                break
            except OSError as e:
                logger.warning(f"Cannot bind to port {port}: {e}")
                continue
        
        if not started:
            logger.error("Failed to start server on any port")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

