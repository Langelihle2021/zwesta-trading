#!/usr/bin/env python3
"""
Zwesta Multi-Broker Trading Backend
Supports multiple brokers with unified API
Updated with MT5 Demo Credentials
"""

import os
import json
import time
import sqlite3
import uuid
import hashlib
import threading
from datetime import datetime, timedelta
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
# Environment Configuration (DEMO or LIVE)
ENVIRONMENT = os.getenv('TRADING_ENV', 'DEMO')  # Set TRADING_ENV=LIVE in production

# API Security Configuration
API_KEY = os.getenv('API_KEY', 'your_generated_api_key_here_change_in_production')

# MT5 Credentials - DEMO (default)
MT5_CONFIG = {
    'account': 104017418,
    'password': '*6RjhRvH',
    'server': 'MetaQuotes-Demo',
    'path': 'C:\\Program Files\\XM Global MT5'
}

# MT5 Credentials - LIVE (override with environment variables)
if ENVIRONMENT == 'LIVE':
    MT5_CONFIG = {
        'account': int(os.getenv('MT5_ACCOUNT', '0')),
        'password': os.getenv('MT5_PASSWORD', ''),
        'server': os.getenv('MT5_SERVER', ''),
        'path': os.getenv('MT5_PATH', 'C:\\Program Files\\XM Global MT5')
    }
    # Validate LIVE credentials
    if MT5_CONFIG['account'] == 0 or not MT5_CONFIG['password']:
        logger.error("[ALERT] LIVE MODE: Missing MT5 credentials in environment variables!")
        logger.error("Set: MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER")

# Withdrawal Configuration
WITHDRAWAL_CONFIG = {
    'min_amount': 10,
    'max_amount': 50000,
    'processing_fee_percent': 1.0,  # 1% fee
    'processing_days': 3,  # 2-3 business days
    'test_mode_max': 50,  # For testing with small amounts
}

logger.info(f"[INIT] Backend initialized in {ENVIRONMENT} mode")
if ENVIRONMENT == 'LIVE':
    logger.warning(f"[ALERT] LIVE TRADING MODE - Account: {MT5_CONFIG['account']}")
else:
    logger.info(f"[DEMO] DEMO MODE - Account: {MT5_CONFIG['account']}")

# ==================== API AUTHENTICATION ====================
def validate_api_key():
    """Validate API key from request headers"""
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not api_key:
        return False, "Missing API key in Authorization header"
    if api_key != API_KEY:
        return False, "Invalid API key"
    return True, "Valid"

def require_api_key(f):
    """Decorator to require API key authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        valid, message = validate_api_key()
        if not valid:
            return jsonify({'success': False, 'error': message}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_session(f):
    """Decorator to require valid session token and extract user_id"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get session token from header
        session_token = request.headers.get('X-Session-Token')
        if not session_token:
            return jsonify({'success': False, 'error': 'Missing session token in X-Session-Token header'}), 401
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Query user_sessions table
            cursor.execute('''
                SELECT user_id, expires_at, is_active 
                FROM user_sessions 
                WHERE token = ? AND is_active = 1
            ''', (session_token,))
            
            session = cursor.fetchone()
            conn.close()
            
            if not session:
                return jsonify({'success': False, 'error': 'Invalid or inactive session token'}), 401
            
            # Check expiration
            expires_at = datetime.fromisoformat(session['expires_at'])
            if expires_at < datetime.now():
                return jsonify({'success': False, 'error': 'Session token expired'}), 401
            
            # Attach user_id to request for use in the route handler
            request.user_id = session['user_id']
            return f(*args, **kwargs)
        
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return jsonify({'success': False, 'error': 'Session validation error'}), 500
    
    return decorated_function

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


# ==================== DATABASE SETUP ====================
DATABASE_PATH = 'zwesta_trading.db'

def init_database():
    """Initialize SQLite database with referral and commission tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            referrer_id TEXT,
            referral_code TEXT UNIQUE,
            created_at TEXT,
            total_commission REAL DEFAULT 0,
            FOREIGN KEY (referrer_id) REFERENCES users(user_id)
        )
    ''')
    
    # Commission tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commissions (
            commission_id TEXT PRIMARY KEY,
            earner_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            bot_id TEXT,
            profit_amount REAL,
            commission_rate REAL DEFAULT 0.05,
            commission_amount REAL,
            created_at TEXT,
            FOREIGN KEY (earner_id) REFERENCES users(user_id),
            FOREIGN KEY (client_id) REFERENCES users(user_id)
        )
    ''')
    
    # Referral tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            referral_id TEXT PRIMARY KEY,
            referrer_id TEXT NOT NULL,
            referred_user_id TEXT NOT NULL,
            created_at TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (referrer_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Withdrawals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            withdrawal_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT NOT NULL,
            account_details TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT,
            fee REAL DEFAULT 0,
            net_amount REAL,
            admin_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Bot monitoring table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_monitoring (
            monitoring_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            last_heartbeat TEXT,
            uptime_seconds INTEGER DEFAULT 0,
            health_check_count INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            last_error TEXT,
            last_error_time TEXT,
            auto_restart_count INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (bot_id) REFERENCES active_bots(botId)
        )
    ''')
    
    # Auto-withdrawal settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_withdrawal_settings (
            setting_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            target_profit REAL NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            withdrawal_method TEXT DEFAULT 'auto',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Auto-withdrawal history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_withdrawal_history (
            withdrawal_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            triggered_profit REAL NOT NULL,
            withdrawal_amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            net_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # User bots table - stores user-specific bots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_bots (
            bot_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            strategy TEXT,
            status TEXT DEFAULT 'active',
            enabled BOOLEAN DEFAULT 1,
            daily_profit REAL DEFAULT 0,
            total_profit REAL DEFAULT 0,
            broker_account_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Broker credentials table - stores user's broker connections
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broker_credentials (
            credential_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            broker_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            password TEXT NOT NULL,
            server TEXT,
            is_live BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # User sessions table - for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token TEXT UNIQUE,
            created_at TEXT,
            expires_at TEXT,
            ip_address TEXT,
            user_agent TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database on startup
init_database()


# ==================== REFERRAL SYSTEM ====================
class ReferralSystem:
    """Handles referral code generation, tracking, and commission calculation"""
    
    @staticmethod
    def generate_referral_code():
        """Generate unique 8-character referral code"""
        return uuid.uuid4().hex[:8].upper()
    
    @staticmethod
    def register_user(email: str, name: str, referral_code: Optional[str] = None) -> Dict:
        """Register new user with optional referrer"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            user_id = str(uuid.uuid4())
            new_referral_code = ReferralSystem.generate_referral_code()
            created_at = datetime.now().isoformat()
            
            # Check if referral code is valid
            referrer_id = None
            if referral_code:
                cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code.upper(),))
                referrer = cursor.fetchone()
                if referrer:
                    referrer_id = referrer['user_id']
                    logger.info(f"Valid referrer found: {referrer_id}")
            
            # Insert new user
            cursor.execute('''
                INSERT INTO users (user_id, email, name, referrer_id, referral_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, email, name, referrer_id, new_referral_code, created_at))
            
            # Create referral record if referrer exists
            if referrer_id:
                referral_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO referrals (referral_id, referrer_id, referred_user_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (referral_id, referrer_id, user_id, created_at))
                logger.info(f"Referral created: {referrer_id} -> {user_id}")
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'user_id': user_id,
                'referral_code': new_referral_code,
                'referrer_id': referrer_id,
                'message': 'User registered successfully'
            }
        except sqlite3.IntegrityError as e:
            logger.error(f"Email already exists: {e}")
            return {'success': False, 'error': 'Email already registered'}
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def add_commission(earner_id: str, client_id: str, profit_amount: float, bot_id: str) -> Dict:
        """Calculate and add commission for profit generated by referred client"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 5% commission to referrer from client profits
            commission_rate = 0.05
            commission_amount = profit_amount * commission_rate
            
            commission_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            
            # Record commission
            cursor.execute('''
                INSERT INTO commissions 
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at))
            
            # Update user total commission
            cursor.execute('''
                UPDATE users SET total_commission = total_commission + ? WHERE user_id = ?
            ''', (commission_amount, earner_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Commission added: {earner_id} earned ${commission_amount:.2f} from {client_id}")
            return {
                'success': True,
                'commission_id': commission_id,
                'commission_amount': commission_amount
            }
        except Exception as e:
            logger.error(f"Error adding commission: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_recruits(user_id: str) -> List[Dict]:
        """Get all users recruited by this user"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT u.user_id, u.email, u.name, u.created_at, u.total_commission
                FROM users u
                INNER JOIN referrals r ON u.user_id = r.referred_user_id
                WHERE r.referrer_id = ? AND r.status = 'active'
                ORDER BY r.created_at DESC
            ''', (user_id,))
            
            recruits = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return recruits
        except Exception as e:
            logger.error(f"Error getting recruits: {e}")
            return []
    
    @staticmethod
    def get_earning_recap(user_id: str) -> Dict:
        """Get commission earnings summary for user"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Total earnings from all recruits
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT client_id) as total_clients,
                    SUM(commission_amount) as total_earned,
                    COUNT(*) as total_transactions
                FROM commissions
                WHERE earner_id = ?
            ''', (user_id,))
            
            earnings = dict(cursor.fetchone())
            total_earned = earnings['total_earned'] or 0
            
            # Get total withdrawn
            cursor.execute('''
                SELECT SUM(amount) as total_withdrawn FROM withdrawals 
                WHERE user_id = ? AND status IN ('approved', 'pending', 'processing')
            ''', (user_id,))
            
            withdrawn = cursor.fetchone()
            total_withdrawn = withdrawn['total_withdrawn'] or 0
            available_balance = total_earned - total_withdrawn
            
            # Recent earnings
            cursor.execute('''
                SELECT c.commission_amount, c.created_at, u.name
                FROM commissions c
                LEFT JOIN users u ON c.client_id = u.user_id
                WHERE c.earner_id = ?
                ORDER BY c.created_at DESC
                LIMIT 10
            ''', (user_id,))
            
            recent = [dict(row) for row in cursor.fetchall()]
            
            # Get user details
            cursor.execute('SELECT referral_code, total_commission FROM users WHERE user_id = ?', (user_id,))
            user_data = cursor.fetchone()
            conn.close()
            
            if not user_data:
                return {}
            
            return {
                'referral_code': user_data['referral_code'],
                'total_commission': user_data['total_commission'],
                'total_clients': earnings['total_clients'] or 0,
                'total_earned': total_earned,
                'available_balance': available_balance,
                'total_withdrawn': total_withdrawn,
                'total_transactions': earnings['total_transactions'] or 0,
                'recent_earnings': recent
            }
        except Exception as e:
            logger.error(f"Error getting earning recap: {e}")
            return {}


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
@require_session
def create_bot():
    """Create and start a new trading bot for a user"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No configuration provided'}), 400
        
        user_id = data.get('user_id') or request.user_id  # Get from request body or session
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        bot_id = data.get('botId') or f"bot_{user_id}_{int(datetime.now().timestamp())}"
        account_id = data.get('accountId', 'Default MT5')
        symbols = data.get('symbols', ['EURUSD'])
        strategy = data.get('strategy', 'Trend Following')
        risk_per_trade = float(data.get('riskPerTrade', 100))
        max_daily_loss = float(data.get('maxDailyLoss', 500))
        trading_enabled = data.get('enabled', True)
        
        # Store bot in database
        created_at = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, created_at, created_at))
        
        conn.commit()
        conn.close()
        
        # Also store in active_bots for real-time trading
        now = datetime.now()
        active_bots[bot_id] = {
            'botId': bot_id,
            'user_id': user_id,
            'accountId': account_id,
            'symbols': symbols,
            'strategy': strategy,
            'riskPerTrade': risk_per_trade,
            'maxDailyLoss': max_daily_loss,
            'enabled': trading_enabled,
            'basePositionSize': data.get('basePositionSize', 1.0),
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
            'dailyProfit': 0,
            'maxDrawdown': 0,
            'peakProfit': 0,
        }
        
        logger.info(f"Created bot {bot_id} for user {user_id}: {strategy}")
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'user_id': user_id,
            'message': f'Bot {bot_id} created successfully',
            'config': active_bots[bot_id]
        }), 200
    
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/start', methods=['POST'])
@require_session
def start_bot():
    """Start automatic trading for a bot with intelligent strategy switching"""
    try:
        data = request.json
        bot_id = data.get('botId')
        user_id = data.get('user_id') or request.user_id  # Get from request or session
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot = active_bots[bot_id]
        if bot.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Also verify in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        conn.close()
        
        if not db_bot or db_bot['user_id'] != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
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
    """Get status of all active bots (supports user_id filter)"""
    try:
        user_id = request.args.get('user_id')
        
        bots_list = []
        for bot in active_bots.values():
            # Filter by user_id if provided
            if user_id and bot.get('user_id') != user_id:
                continue
            
            # Calculate runtime
            created = datetime.fromisoformat(bot['createdAt'])
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profit = bot['dailyProfits'].get(today, bot.get('dailyProfit', 0))
            
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
@require_session
def stop_bot(bot_id):
    """Stop a trading bot"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id  # Get from request or session
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot_config = active_bots[bot_id]
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Also verify in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        conn.close()
        
        if not db_bot or db_bot['user_id'] != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
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


@app.route('/api/bot/delete/<bot_id>', methods=['DELETE', 'POST'])
@require_session
def delete_bot(bot_id):
    """Delete a trading bot permanently"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id  # Get from request or session
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot_config = active_bots[bot_id]
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Also verify in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        
        if not db_bot or db_bot['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Delete from database
        cursor.execute('DELETE FROM user_bots WHERE bot_id = ?', (bot_id,))
        conn.commit()
        conn.close()
        
        bot_config = active_bots[bot_id]
        # Stop bot first if running
        if bot_config.get('enabled', False):
            bot_config['enabled'] = False
        
        # Remove bot from active_bots dictionary
        del active_bots[bot_id]
        
        logger.info(f"Deleted bot {bot_id}")
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} deleted successfully',
            'remainingBots': len(active_bots)
        }), 200
    
    except Exception as e:
        logger.error(f"Error deleting bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== BOT MONITORING SYSTEM ====================
@app.route('/api/bot/<bot_id>/health', methods=['GET'])
@require_api_key
def get_bot_health(bot_id):
    """Get bot health and monitoring status"""
    try:
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get monitoring data
        cursor.execute('''
            SELECT status, last_heartbeat, uptime_seconds, health_check_count, 
                   errors_count, last_error, auto_restart_count
            FROM bot_monitoring WHERE bot_id = ?
        ''', (bot_id,))
        
        monitoring = cursor.fetchone()
        conn.close()
        
        health_status = {
            'bot_id': bot_id,
            'is_running': bot_config.get('enabled', False),
            'strategy': bot_config.get('strategy', 'Unknown'),
            'daily_profit': bot_config.get('dailyProfit', 0),
            'total_profit': bot_config.get('totalProfit', 0),
            'status': dict(monitoring)['status'] if monitoring else 'unknown',
            'last_heartbeat': dict(monitoring)['last_heartbeat'] if monitoring else None,
            'uptime_seconds': dict(monitoring)['uptime_seconds'] if monitoring else 0,
            'health_checks': dict(monitoring)['health_check_count'] if monitoring else 0,
            'error_count': dict(monitoring)['errors_count'] if monitoring else 0,
            'last_error': dict(monitoring)['last_error'] if monitoring else None,
            'auto_restarts': dict(monitoring)['auto_restart_count'] if monitoring else 0,
        }
        
        return jsonify({
            'success': True,
            'health': health_status
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AUTO-WITHDRAWAL SYSTEM ====================
@app.route('/api/bot/<bot_id>/auto-withdrawal', methods=['POST'])
@require_api_key
def set_auto_withdrawal(bot_id):
    """Set profit target for automatic withdrawal"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        target_profit = data.get('target_profit')  # USD amount
        
        if not user_id or not target_profit:
            return jsonify({'success': False, 'error': 'user_id and target_profit required'}), 400
        
        if target_profit < 10:
            return jsonify({'success': False, 'error': 'Minimum profit target is $10'}), 400
        
        if target_profit > 50000:
            return jsonify({'success': False, 'error': 'Maximum profit target is $50,000'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        setting_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT OR REPLACE INTO auto_withdrawal_settings 
            (setting_id, bot_id, user_id, target_profit, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (setting_id, bot_id, user_id, target_profit, created_at, created_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Auto-withdrawal set for bot {bot_id}: ${target_profit} target")
        
        return jsonify({
            'success': True,
            'setting_id': setting_id,
            'bot_id': bot_id,
            'target_profit': target_profit,
            'message': f'Auto-withdrawal will trigger when bot reaches ${target_profit} profit'
        }), 200
    
    except Exception as e:
        logger.error(f"Error setting auto-withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/auto-withdrawal-status', methods=['GET'])
@require_api_key
def get_auto_withdrawal_status(bot_id):
    """Get auto-withdrawal settings and history for a bot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current settings
        cursor.execute('''
            SELECT setting_id, target_profit, is_active, created_at
            FROM auto_withdrawal_settings WHERE bot_id = ? AND is_active = 1
        ''', (bot_id,))
        
        settings = cursor.fetchone()
        
        # Get withdrawal history
        cursor.execute('''
            SELECT withdrawal_id, triggered_profit, withdrawal_amount, net_amount, 
                   status, created_at, completed_at
            FROM auto_withdrawal_history
            WHERE bot_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (bot_id,))
        
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'bot_id': bot_id,
            'current_setting': dict(settings) if settings else None,
            'history': history,
            'total_auto_withdrawals': len(history),
            'total_amount_withdrawn': sum([float(h['withdrawal_amount']) for h in history])
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting auto-withdrawal status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/disable-auto-withdrawal', methods=['POST'])
@require_api_key
def disable_auto_withdrawal(bot_id):
    """Disable auto-withdrawal for a bot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE auto_withdrawal_settings
            SET is_active = 0, updated_at = ?
            WHERE bot_id = ?
        ''', (datetime.now().isoformat(), bot_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Auto-withdrawal disabled for bot {bot_id}")
        
        return jsonify({
            'success': True,
            'message': f'Auto-withdrawal disabled for bot {bot_id}'
        }), 200
    
    except Exception as e:
        logger.error(f"Error disabling auto-withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== REFERRAL API ENDPOINTS ====================

@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Register new user with optional referral code"""
    try:
        data = request.get_json()
        email = data.get('email')
        name = data.get('name')
        referral_code = data.get('referral_code')  # Optional
        
        if not email or not name:
            return jsonify({'success': False, 'error': 'Email and name required'}), 400
        
        result = ReferralSystem.register_user(email, name, referral_code)
        return jsonify(result), 200 if result['success'] else 400
    
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/login', methods=['POST'])
def login_user():
    """Login user by email - creates session"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute('SELECT user_id, name, email, referral_code FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        user_id = user_dict['user_id']
        
        # Create session token
        session_id = str(uuid.uuid4())
        token = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (session_id, user_id, token, datetime.now().isoformat(), expires_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"User logged in: {email}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'name': user_dict['name'],
            'email': user_dict['email'],
            'referral_code': user_dict['referral_code'],
            'session_token': token,
            'message': 'Login successful'
        }), 200
    
    except Exception as e:
        logger.error(f"Error in login_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/profile/<user_id>', methods=['GET'])
@require_session
def get_user_profile(user_id):
    """Get user profile and their associated data"""
    # Verify user is accessing only their own profile
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user profiles'}), 403
    """Get user profile and their associated data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('''
            SELECT user_id, name, email, referral_code, total_commission, created_at
            FROM users WHERE user_id = ?
        ''', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        
        # Get user's bots
        cursor.execute('''
            SELECT bot_id, name, strategy, status, enabled, daily_profit, total_profit, created_at
            FROM user_bots WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        bots = [dict(row) for row in cursor.fetchall()]
        
        # Get user's broker credentials
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, is_live, is_active
            FROM broker_credentials WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        brokers = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': user_dict,
            'bots': bots,
            'total_bots': len(bots),
            'brokers': brokers,
            'total_brokers': len(brokers)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/broker-credentials', methods=['POST'])
@require_session
def add_broker_credentials(user_id):
    """Add broker credentials for a user"""
    # Verify user is adding credentials for themselves
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot add credentials for other users'}), 403
    """Add broker credentials for a user"""
    try:
        data = request.get_json()
        broker_name = data.get('broker_name')
        account_number = data.get('account_number')
        password = data.get('password')
        server = data.get('server')
        is_live = data.get('is_live', False)
        
        if not all([broker_name, account_number, password]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Insert broker credentials
        credential_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO broker_credentials 
            (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at, created_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Broker credentials added for user {user_id}: {broker_name}")
        
        return jsonify({
            'success': True,
            'credential_id': credential_id,
            'message': f'Broker credentials added for {broker_name}'
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding broker credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/broker-credentials', methods=['GET'])
@require_session
def get_broker_credentials(user_id):
    """Get all broker credentials for a user"""
    # Verify user is accessing only their own credentials
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user credentials'}), 403
    """Get all broker credentials for a user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live, is_active, created_at
            FROM broker_credentials WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        credentials = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'credentials': credentials,
            'total': len(credentials)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting broker credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/bots', methods=['GET'])
@require_session
def get_user_bots(user_id):
    """Get all bots for a specific user"""
    # Verify user is accessing only their own bots
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user bots'}), 403
    """Get all bots for a specific user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Get user's bots from database
        cursor.execute('''
            SELECT bot_id, name, strategy, status, enabled, daily_profit, total_profit, created_at
            FROM user_bots WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        bots = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Calculate totals
        total_daily = sum([float(bot.get('daily_profit', 0)) for bot in bots])
        total_profit = sum([float(bot.get('total_profit', 0)) for bot in bots])
        active_count = sum([1 for bot in bots if bot.get('enabled')])
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'bots': bots,
            'total_bots': len(bots),
            'active_bots': active_count,
            'total_daily_profit': total_daily,
            'total_profit': total_profit
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user bots: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/recruits', methods=['GET'])
def get_recruits(user_id):
    """Get all users recruited by this user"""
    try:
        recruits = ReferralSystem.get_recruits(user_id)
        
        return jsonify({
            'success': True,
            'recruits': recruits,
            'total_recruits': len(recruits)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting recruits: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/earnings', methods=['GET'])
def get_earnings(user_id):
    """Get commission earnings summary"""
    try:
        recap = ReferralSystem.get_earning_recap(user_id)
        
        return jsonify({
            'success': True,
            **recap
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting earnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/referral/validate/<referral_code>', methods=['GET'])
def validate_referral_code(referral_code):
    """Check if referral code is valid"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, name, email FROM users WHERE referral_code = ?
        ''', (referral_code.upper(),))
        
        referrer = cursor.fetchone()
        conn.close()
        
        if referrer:
            return jsonify({
                'success': True,
                'valid': True,
                'referrer_name': referrer['name'],
                'referrer_email': referrer['email']
            }), 200
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Referral code not found'
            }), 404
    
    except Exception as e:
        logger.error(f"Error validating referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/referral/link/<referral_code>', methods=['GET'])
def get_referral_link(referral_code):
    """Get shareable referral link"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, name FROM users WHERE referral_code = ?', (referral_code.upper(),))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            referral_link = f"https://yourapp.com/register?ref={referral_code.upper()}"
            return jsonify({
                'success': True,
                'referral_code': referral_code.upper(),
                'referral_link': referral_link,
                'referrer_name': user['name'],
                'message': f"Share this link to invite others: {referral_link}"
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Referral code not found'}), 404
    
    except Exception as e:
        logger.error(f"Error getting referral link: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/referral-code', methods=['GET'])
@require_api_key
def get_user_referral_code(user_id):
    """Get user's referral code and details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, name, referral_code, email, created_at FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        referral_link = f"https://zwesta.com/register?ref={user_dict['referral_code']}"
        
        # Get recruit count
        cursor.execute('SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?', (user_id,))
        recruit_data = cursor.fetchone()
        recruit_count = dict(recruit_data)['count'] if recruit_data else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user_id': user_dict['user_id'],
            'name': user_dict['name'],
            'email': user_dict['email'],
            'referral_code': user_dict['referral_code'],
            'referral_link': referral_link,
            'recruited_count': recruit_count,
            'created_at': user_dict['created_at']
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/regenerate-referral-code', methods=['POST'])
@require_api_key
def regenerate_referral_code(user_id):
    """Regenerate user's referral code"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Generate new referral code
        new_code = ReferralSystem.generate_referral_code()
        
        # Check if code already exists (very rare)
        while True:
            cursor.execute('SELECT referral_code FROM users WHERE referral_code = ?', (new_code,))
            if not cursor.fetchone():
                break
            new_code = ReferralSystem.generate_referral_code()
        
        # Update user's referral code
        cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (new_code, user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Regenerated referral code for user {user_id}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'new_referral_code': new_code,
            'referral_link': f"https://zwesta.com/register?ref={new_code}",
            'message': 'Referral code regenerated successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error regenerating referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/dashboard', methods=['GET'])
@require_api_key
def admin_dashboard():
    """Admin dashboard with all users, bots, and earnings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) as count FROM users')
        total_users = cursor.fetchone()['count'] or 0
        
        # Get total active bots
        total_bots = len([b for b in active_bots.values() if b.get('enabled', False)])
        
        # Get platform earnings (25% of all profits)
        cursor.execute('SELECT SUM(commission_amount * 5) as total_earned FROM commissions')
        platform_earnings_from_referrals = (cursor.fetchone()['total_earned'] or 0) / 5  # Divide back to get 25%
        
        # Calculate from actual bot profits
        total_profit = sum([b.get('totalProfit', 0) for b in active_bots.values()])
        platform_earnings = total_profit * 0.25  # 25% of all profits
        
        # Get all users with their bots
        cursor.execute('SELECT user_id, name, email FROM users ORDER BY created_at DESC LIMIT 100')
        users_list = [dict(row) for row in cursor.fetchall()]
        
        users_with_bots = []
        for user in users_list:
            # Find bots belonging to this user (simplified - would need more DB tracking)
            user_bots = [
                {
                    'botId': bot_id,
                    'strategy': bot_config.get('strategy', 'Unknown'),
                    'profit': bot_config.get('totalProfit', 0)
                }
                for bot_id, bot_config in active_bots.items()
            ]
            
            # Get user's commission info
            cursor.execute('''
                SELECT COUNT(DISTINCT client_id) as client_count, SUM(commission_amount) as total_commission
                FROM commissions WHERE earner_id = ?
            ''', (user['user_id'],))
            
            commission_data = dict(cursor.fetchone())
            
            users_with_bots.append({
                'user_id': user['user_id'],
                'name': user['name'],
                'email': user['email'],
                'bot_count': len(user_bots),
                'bots': user_bots[:5],  # First 5 bots
                'total_profit': sum([b.get('profit', 0) for b in user_bots]),
                'recruiter_count': commission_data.get('client_count', 0),
                'referral_earnings': commission_data.get('total_commission', 0)
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_users': total_users,
            'total_bots': total_bots,
            'total_profit': total_profit,
            'platform_earnings': platform_earnings,
            'referral_earnings': platform_earnings_from_referrals,
            'commission_rate_platform': 0.25,
            'commission_rate_referrer': 0.05,
            'users': users_with_bots
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting admin dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WITHDRAWAL SYSTEM ====================
@app.route('/api/withdrawal/request', methods=['POST'])
@require_api_key
def request_withdrawal():
    """Request a withdrawal of earned commissions"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        account_details = data.get('account_details')
        
        # Validate amount
        if amount < WITHDRAWAL_CONFIG['min_amount']:
            return jsonify({'success': False, 'error': f"Minimum withdrawal is ${WITHDRAWAL_CONFIG['min_amount']}"}), 400
        
        if amount > WITHDRAWAL_CONFIG['max_amount']:
            return jsonify({'success': False, 'error': f"Maximum withdrawal is ${WITHDRAWAL_CONFIG['max_amount']}"}), 400
        
        # Test mode: limit to $50 for testing
        if ENVIRONMENT == 'DEMO':
            if amount > WITHDRAWAL_CONFIG['test_mode_max']:
                return jsonify({'success': False, 'error': f"Test mode: maximum ${WITHDRAWAL_CONFIG['test_mode_max']} per withdrawal"}), 400
        
        # Check available balance
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT SUM(commission_amount) as total_earned FROM commissions 
            WHERE earner_id = ?
        ''', (user_id,))
        
        earnings = cursor.fetchone()
        total_earned = earnings['total_earned'] or 0
        
        # Get withdrawn amount
        cursor.execute('''
            SELECT SUM(amount) as total_withdrawn FROM withdrawals 
            WHERE user_id = ? AND status IN ('approved', 'pending', 'processing')
        ''', (user_id,))
        
        withdrawn = cursor.fetchone()
        total_withdrawn = withdrawn['total_withdrawn'] or 0
        available_balance = total_earned - total_withdrawn
        
        if amount > available_balance:
            conn.close()
            return jsonify({'success': False, 'error': 'Amount exceeds available balance'}), 400
        
        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        fee = amount * (WITHDRAWAL_CONFIG['processing_fee_percent'] / 100)
        net_amount = amount - fee
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO withdrawals (withdrawal_id, user_id, amount, method, account_details, status, created_at, fee, net_amount)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        ''', (withdrawal_id, user_id, amount, method, account_details, created_at, fee, net_amount))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Withdrawal request {withdrawal_id}: {user_id} - ${amount} ({method})")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'fee': round(fee, 2),
            'net_amount': round(net_amount, 2),
            'status': 'pending',
            'message': f'Withdrawal request submitted. Will receive ${round(net_amount, 2)} after {WITHDRAWAL_CONFIG["processing_fee_percent"]}% fee. Processing in {WITHDRAWAL_CONFIG["processing_days"]} business days.'
        }), 200
    
    except Exception as e:
        logger.error(f"Error requesting withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/withdrawal/history/<user_id>', methods=['GET'])
def get_withdrawal_history(user_id):
    """Get user's withdrawal history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT withdrawal_id, amount, method, status, created_at, processed_at, net_amount, fee
            FROM withdrawals
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'withdrawals': withdrawals
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting withdrawal history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/withdrawals', methods=['GET'])
@require_api_key
def admin_withdrawals():
    """Admin endpoint to view all pending withdrawals"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT w.withdrawal_id, w.user_id, u.name, u.email, w.amount, w.method, 
                   w.account_details, w.status, w.created_at, w.fee, w.net_amount
            FROM withdrawals w
            JOIN users u ON w.user_id = u.user_id
            WHERE w.status = 'pending'
            ORDER BY w.created_at ASC
        ''')
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'pending_withdrawals': withdrawals,
            'total_pending': len(withdrawals),
            'total_pending_amount': sum([float(w['amount']) for w in withdrawals])
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting admin withdrawals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/withdrawal/<withdrawal_id>/approve', methods=['POST'])
@require_api_key
def approve_withdrawal(withdrawal_id):
    """Admin endpoint to approve withdrawal"""
    try:
        data = request.get_json()
        admin_notes = data.get('notes', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE withdrawals
            SET status = 'approved', processed_at = ?, admin_notes = ?
            WHERE withdrawal_id = ?
        ''', (datetime.now().isoformat(), admin_notes, withdrawal_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Withdrawal {withdrawal_id} approved")
        
        return jsonify({
            'success': True,
            'message': 'Withdrawal approved'
        }), 200
    
    except Exception as e:
        logger.error(f"Error approving withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== DUPLICATE DATABASE SECTION REMOVED ====================
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


# ==================== AUTO-WITHDRAWAL MONITORING ====================
monitoring_thread = None
monitoring_running = False

def auto_withdrawal_monitor():
    """Background task to monitor bot profits and execute auto-withdrawals"""
    global monitoring_running
    monitoring_running = True
    logger.info("Starting auto-withdrawal monitoring thread...")
    
    while monitoring_running:
        try:
            time.sleep(30)  # Check every 30 seconds
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all active auto-withdrawal settings
            cursor.execute('''
                SELECT setting_id, bot_id, user_id, target_profit
                FROM auto_withdrawal_settings
                WHERE is_active = 1
            ''')
            
            settings = cursor.fetchall()
            
            for setting in settings:
                setting_id, bot_id, user_id, target_profit = setting
                
                # Get current bot profit
                if bot_id in active_bots:
                    bot_config = active_bots[bot_id]
                    current_profit = bot_config.get('totalProfit', 0)
                    
                    # Check if profit target reached
                    if current_profit >= target_profit:
                        logger.info(f"Profit target reached for bot {bot_id}: ${current_profit} >= ${target_profit}")
                        
                        # Check if withdrawal already triggered for this cycle
                        cursor.execute('''
                            SELECT COUNT(*) FROM auto_withdrawal_history
                            WHERE bot_id = ? AND status = 'completed'
                            AND created_at > datetime('now', '-24 hours')
                        ''', (bot_id,))
                        
                        recent_count = cursor.fetchone()[0]
                        
                        if recent_count == 0:  # Only one withdrawal per 24 hours
                            # Create withdrawal record
                            withdrawal_id = str(uuid.uuid4())
                            created_at = datetime.now().isoformat()
                            fee = current_profit * 0.02  # 2% fee
                            net_amount = current_profit - fee
                            
                            cursor.execute('''
                                INSERT INTO auto_withdrawal_history
                                (withdrawal_id, bot_id, user_id, triggered_profit, 
                                 withdrawal_amount, fee, net_amount, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (withdrawal_id, bot_id, user_id, current_profit,
                                  current_profit, fee, net_amount, 'pending', created_at))
                            
                            # Update bot profit to reset
                            active_bots[bot_id]['totalProfit'] = 0
                            active_bots[bot_id]['dailyProfit'] = 0
                            
                            # Mark as completed
                            cursor.execute('''
                                UPDATE auto_withdrawal_history
                                SET status = 'completed', completed_at = ?
                                WHERE withdrawal_id = ?
                            ''', (datetime.now().isoformat(), withdrawal_id))
                            
                            logger.info(f"Auto-withdrawal executed: {withdrawal_id} for bot {bot_id}, amount: ${net_amount}")
        
        except Exception as e:
            logger.error(f"Error in auto-withdrawal monitor: {e}")
        
        finally:
            if conn:
                conn.close()
    
    logger.info("Auto-withdrawal monitoring thread stopped")


if __name__ == '__main__':
    logger.info("Starting Zwesta Multi-Broker Backend")
    logger.info(f"MT5 Account: {MT5_CONFIG['account']}")
    logger.info(f"MT5 Server: {MT5_CONFIG['server']}")
    
    # Initialize demo bots on startup
    logger.info("Initializing demo trading bots...")
    initialize_demo_bots()
    logger.info(f"[OK] {len(active_bots)} demo bots initialized and ready")
    
    # Start auto-withdrawal monitoring thread
    monitoring_thread = threading.Thread(target=auto_withdrawal_monitor, daemon=True)
    monitoring_thread.start()
    logger.info("Auto-withdrawal monitoring thread started")
    
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
    finally:
        # Stop monitoring thread on shutdown
        monitoring_running = False
        if monitoring_thread:
            monitoring_thread.join(timeout=5)
        logger.info("Backend shutdown complete")


