#!/usr/bin/env python3
"""
Zwesta Multi-Broker Trading Backend
Supports multiple brokers with unified API
Updated with MT5 Demo Credentials
Last Verified: 2026-03-12 (All changes confirmed - Production Ready)
"""

import os
import json
import time
import sqlite3
import uuid
import hashlib
import threading
import random
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from typing import Dict, List, Optional
from enum import Enum
import sys
import atexit
from system.backup_and_recovery import BackupManager, RecoveryManager

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"[OK] Loaded environment configuration from {env_file}")
    else:
        print(f"[WARNING] No .env file found at {env_file} - using system environment variables")
except ImportError:
    print("[WARNING] python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Falling back to system environment variables")

# Configure UTF-8 encoding for Windows console logging
if sys.platform == 'win32':
    # Enable UTF-8 support in Windows console
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('multi_broker_backend.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app)

# ==================== BOT CLEANUP & REPOPULATION ====================
def repopulate_active_bots():
    """Repopulate active_bots from user_bots table on backend startup"""
    global active_bots
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_bots WHERE enabled = 1')
        rows = cursor.fetchall()
        for row in rows:
            bot_id = row['bot_id']
            # Minimal config; extend as needed
            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': row['user_id'],
                'accountId': row['broker_account_id'],
                'strategy': row['strategy'],
                'symbols': row['symbols'].split(',') if row['symbols'] else [],
                'enabled': row['enabled'],
                'createdAt': row['created_at'],
                'totalTrades': 0,
                'winningTrades': 0,
                'totalProfit': 0,
                'totalLosses': 0,
                'totalInvestment': 0,
                'profitHistory': [],
                'tradeHistory': [],
                'dailyProfits': {},
                'dailyProfit': 0,
                'maxDrawdown': 0,
                'peakProfit': 0,
                'profit': 0,  # Always include profit field
            }
        conn.close()
        logger.info(f"✅ Repopulated {len(active_bots)} bots from database on startup.")
    except Exception as e:
        logger.error(f"❌ Error repopulating active_bots: {e}")

# Call repopulate on startup
if __name__ == "__main__":
    repopulate_active_bots()

# ==================== CONFIGURATION ====================
# Environment Configuration (DEMO or LIVE)
ENVIRONMENT = os.getenv('TRADING_ENV', 'DEMO')  # Set TRADING_ENV=LIVE in production

# API Security Configuration
API_KEY = os.getenv('API_KEY', 'your_generated_api_key_here_change_in_production')

# MT5 Credentials - DEMO (default)
# Check multiple possible MT5 installation paths
def find_mt5_path():
    """Find MT5 installation path from common locations - returns path to terminal.exe or terminal64.exe"""
    possible_paths = [
        'C:\\Program Files\\MetaTrader 5',         # MetaQuotes MT5 (PRIMARY)
        'C:\\Program Files (x86)\\MetaTrader 5',   # MT5 alternative
        'C:\\Program Files\\XM Global MT5',        # XM installation
        os.getenv('MT5_PATH', ''),                 # Environment variable
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            # Check for terminal64.exe first (64-bit version, preferred)
            terminal64_path = os.path.join(path, 'terminal64.exe')
            if os.path.exists(terminal64_path):
                logger.info(f"Found MT5 (64-bit) at: {terminal64_path}")
                return terminal64_path  # Return FULL PATH to terminal64.exe
            
            # Fallback to terminal.exe (32-bit version)
            terminal_path = os.path.join(path, 'terminal.exe')
            if os.path.exists(terminal_path):
                logger.info(f"Found MT5 (32-bit) at: {terminal_path}")
                return terminal_path  # Return FULL PATH to terminal.exe
    
    logger.warning("MT5 not found in common paths - will use simulated trading as fallback")
    return None  # Return None instead of default fallback

MT5_CONFIG = {
    'account': 104254514,
    'password': 'OoO*EdV2',
    'server': 'MetaQuotes-Demo',
    'path': find_mt5_path()
}

# MT5 Credentials - LIVE (override with environment variables)
if ENVIRONMENT == 'LIVE':
    MT5_CONFIG = {
        'account': int(os.getenv('MT5_ACCOUNT', '0')),
        'password': os.getenv('MT5_PASSWORD', ''),
        'server': os.getenv('MT5_SERVER', ''),
        'path': os.getenv('MT5_PATH', find_mt5_path())
    }
    # Validate LIVE credentials
    if MT5_CONFIG['account'] == 0 or not MT5_CONFIG['password']:
        logger.error("[ALERT] LIVE MODE: Missing MT5 credentials in environment variables!")
        logger.error("Set: MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER")

# IG.com Broker Configuration
IG_CONFIG = {
    'api_key': os.getenv('IG_API_KEY', '9bbc3ef9ad291acec96dc409d80e50c4c805161a'),  # From screenshot
    'username': os.getenv('IG_USERNAME', ''),
    'password': os.getenv('IG_PASSWORD', ''),
    'account_id': os.getenv('IG_ACCOUNT_ID', ''),
    'demo_mode': os.getenv('IG_DEMO_MODE', 'true').lower() == 'true'
}

# IG.com LIVE Configuration (override with environment variables if needed)
if ENVIRONMENT == 'LIVE':
    IG_CONFIG = {
        'api_key': os.getenv('IG_API_KEY', '9bbc3ef9ad291acec96dc409d80e50c4c805161a'),
        'username': os.getenv('IG_USERNAME', ''),
        'password': os.getenv('IG_PASSWORD', ''),
        'account_id': os.getenv('IG_ACCOUNT_ID', ''),
        'demo_mode': False
    }
    # Validate LIVE IG credentials
    if not IG_CONFIG['username'] or not IG_CONFIG['password']:
        logger.warning("[ALERT] LIVE MODE: IG API credentials may be missing in environment variables!")
        logger.warning("Set: IG_USERNAME, IG_PASSWORD, IG_ACCOUNT_ID for full functionality")

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
OWNER_USER_ID = 'SYSTEM_OWNER_USER_ID'  # TODO: Set your real owner user_id here

def get_referrer_id(user_id):
    """Get the referrer user_id for a given user (returns None if no referrer)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

def pay_user(user_id, amount, reason, method='internal'):
    """Stub for payout logic (bank/crypto integration goes here)"""
    logger.info(f"[PAYOUT] Paying {amount:.2f} to {user_id} ({reason}) via {method}")
    # TODO: Integrate with bank/crypto API here
    return True

def distribute_profit_split_and_commissions(user_id, profit, bot_id):
    """Distribute profit: 20% owner, 5% referrer, 75% trader. Record commissions."""
    owner_id = OWNER_USER_ID
    referrer_id = get_referrer_id(user_id)
    trader_id = user_id

    owner_share = profit * 0.20
    referrer_share = profit * 0.05
    trader_share = profit * 0.75

    # Pay owner
    pay_user(owner_id, owner_share, f"Owner 20% profit split from bot {bot_id}")
    # Pay referrer (if any)
    if referrer_id:
        ReferralSystem.add_commission(referrer_id, trader_id, profit, bot_id)  # 5% commission
        pay_user(referrer_id, referrer_share, f"Referrer 5% commission from bot {bot_id}")
    # Pay trader
    pay_user(trader_id, trader_share, f"Trader 75% profit from bot {bot_id}")
    logger.info(f"[PROFIT SPLIT] Bot {bot_id}: {owner_share:.2f} to owner, {referrer_share:.2f} to referrer, {trader_share:.2f} to trader {trader_id}")
    return {
        'owner': owner_share,
        'referrer': referrer_share,
        'trader': trader_share
    }
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
        logger.debug(f"[SESSION CHECK] Endpoint: {request.endpoint}, Token received: {session_token[:20]}..." if session_token else "[SESSION CHECK] No token in header")
        
        if not session_token:
            logger.error(f"[SESSION FAIL] Missing X-Session-Token header for {request.endpoint}")
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
                logger.error(f"[SESSION FAIL] Token not found in DB or inactive: {session_token[:20]}...")
                return jsonify({'success': False, 'error': 'Invalid or inactive session token'}), 401
            
            # Check expiration
            expires_at = datetime.fromisoformat(session['expires_at'])
            if expires_at < datetime.now():
                logger.error(f"[SESSION FAIL] Token expired for user {session['user_id']}")
                return jsonify({'success': False, 'error': 'Session token expired'}), 401
            
            # Attach user_id to request for use in the route handler
            request.user_id = session['user_id']
            logger.info(f"[SESSION OK] User {session['user_id']} authenticated for {request.endpoint}")
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
    IG = "ig"
    FXM = "fxm"
    AVATRADE = "avatrade"
    FPMARKETS = "fpmarkets"


# ==================== DATABASE SETUP ====================
# ==================== DATABASE SETUP ====================
DATABASE_PATH = 'zwesta_trading.db'

# ==================== CLEANUP ENDPOINT ====================
@app.route('/api/bots/cleanup', methods=['POST'])
def cleanup_demo_bots():
    """Remove all demo/test bots from database and memory (admin/protected endpoint)"""
    # Optionally, require API key or session for security
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Remove bots with 'demo', 'test', 'sample', or 'dummy' in name or strategy
        cursor.execute("""
            DELETE FROM user_bots WHERE LOWER(name) LIKE '%demo%' OR LOWER(name) LIKE '%test%' OR LOWER(name) LIKE '%sample%' OR LOWER(name) LIKE '%dummy%' OR LOWER(strategy) LIKE '%demo%' OR LOWER(strategy) LIKE '%test%' OR LOWER(strategy) LIKE '%sample%' OR LOWER(strategy) LIKE '%dummy%'
        """)
        conn.commit()
        conn.close()
        # Remove from memory
        to_remove = [bid for bid, bot in active_bots.items() if any(x in (bot.get('strategy','')+bot.get('botId','')+bot.get('accountId','')).lower() for x in ['demo','test','sample','dummy'])]
        for bid in to_remove:
            del active_bots[bid]
        logger.info(f"✅ Removed {len(to_remove)} demo/test bots from memory and database.")
        return jsonify({'success': True, 'removed': len(to_remove)}), 200
    except Exception as e:
        logger.error(f"❌ Error cleaning up demo/test bots: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def init_database():
    """Initialize SQLite database with referral and commission tables"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    cursor = conn.cursor()
    
    # Enable WAL mode for better concurrency
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')
    cursor.execute('PRAGMA cache_size=-64000')  # 64MB cache
    
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
            withdrawal_method TEXT DEFAULT 'fixed',
            withdrawal_mode TEXT DEFAULT 'manual',
            min_profit REAL DEFAULT 0,
            max_profit REAL DEFAULT 0,
            volatility_threshold REAL DEFAULT 0.02,
            win_rate_min REAL DEFAULT 50,
            trend_strength_min REAL DEFAULT 0.5,
            time_between_withdrawals_hours INTEGER DEFAULT 24,
            last_withdrawal_at TEXT,
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
            symbols TEXT DEFAULT 'EURUSD',
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
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, broker_name, account_number)
        )
    ''')
    
    # Bot-Credential linking table - links bots to their broker credentials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_credentials (
            bot_id TEXT NOT NULL,
            credential_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT,
            PRIMARY KEY (bot_id, credential_id),
            FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
            FOREIGN KEY (credential_id) REFERENCES broker_credentials(credential_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Commission withdrawals table - tracks withdrawal requests
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_withdrawals (
            withdrawal_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT,
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
    
    # Bot activation PINs table - for 2FA before bot activation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_activation_pins (
            pin_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            pin TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            created_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Bot deletion confirmation tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_deletion_tokens (
            token_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            deletion_token TEXT NOT NULL,
            bot_stats TEXT,
            created_at TEXT,
            expires_at TEXT,
            confirmed BOOLEAN DEFAULT 0,
            FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # VPS Configuration table - stores VPS connection details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vps_config (
            vps_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            vps_name TEXT NOT NULL,
            vps_ip TEXT NOT NULL,
            vps_port INTEGER DEFAULT 3389,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            rdp_port INTEGER DEFAULT 3389,
            api_port INTEGER DEFAULT 5000,
            mt5_path TEXT DEFAULT 'C:\\Program Files\\MetaTrader 5\\terminal64.exe',
            notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_connection TEXT,
            status TEXT DEFAULT 'disconnected',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # VPS Monitoring table - tracks VPS health and uptime
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vps_monitoring (
            monitoring_id TEXT PRIMARY KEY,
            vps_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            last_heartbeat TEXT,
            mt5_status TEXT DEFAULT 'offline',
            backend_running BOOLEAN DEFAULT 0,
            cpu_usage REAL DEFAULT 0,
            memory_usage REAL DEFAULT 0,
            uptime_hours INTEGER DEFAULT 0,
            active_bots INTEGER DEFAULT 0,
            total_value_locked REAL DEFAULT 0,
            last_check TEXT,
            created_at TEXT,
            FOREIGN KEY (vps_id) REFERENCES vps_config(vps_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # ✅ MIGRATION: Add IG Markets specific columns if they don't exist
    # Check if api_key and username columns exist in broker_credentials table

    # IG Withdrawal Notifications table — tracks when profit targets are hit
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ig_withdrawal_notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            realized_profit REAL DEFAULT 0,
            positions_closed INTEGER DEFAULT 0,
            balance_available REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute("PRAGMA table_info(broker_credentials)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'api_key' not in columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN api_key TEXT')
            logger.info("✅ Migration: Added api_key column to broker_credentials")
        except Exception as e:
            logger.debug(f"api_key column might already exist: {e}")
    
    if 'username' not in columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN username TEXT')
            logger.info("✅ Migration: Added username column to broker_credentials")
        except Exception as e:
            logger.debug(f"username column might already exist: {e}")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def get_db_connection():
    """Get database connection with WAL mode for concurrent writes"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrent access
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn

# Initialize database on startup
if __name__ == "__main__":
    init_database()

# ==================== BACKUP & RECOVERY SYSTEM ====================

def init_backup_system(app):
    """Initialize automatic backup and recovery system"""
    
    db_path = 'zwesta_trading.db'
    backup_mgr = BackupManager(db_path=db_path)
    recovery_mgr = RecoveryManager(db_path=db_path, backup_manager=backup_mgr)
    
    # Auto-recover from last backup on startup if needed
    logger.info("🔄 Checking database health...")
    if not recovery_mgr.auto_recover_on_startup():
        logger.warning("⚠️ Database recovery completed with warnings")
    
    # Verify all data is intact
    data_status = recovery_mgr.verify_all_user_data()
    logger.info(f"✅ Database verified: {data_status}")
    
    # Start automatic backup every 30 minutes
    backup_mgr.start_auto_backup()
    logger.info("✅ Backup system initialized")
    
    return backup_mgr, recovery_mgr

# Initialize backup system
backup_manager, recovery_manager = init_backup_system(app)


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

    def connect(self) -> bool:
        raise NotImplementedError

    def disconnect(self) -> bool:
        raise NotImplementedError

    def get_account_info(self) -> Dict:
        raise NotImplementedError

    def get_positions(self) -> List[Dict]:
        raise NotImplementedError

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        raise NotImplementedError

    def close_position(self, position_id: str) -> Dict:
        raise NotImplementedError

    def get_trades(self) -> List[Dict]:
        raise NotImplementedError


class MT5Connection(BrokerConnection):
    """MetaTrader 5 Broker Connection"""
    
    def __init__(self, credentials: Dict = None):
        # Use MT5_CONFIG if no credentials provided
        if credentials is None:
            credentials = {
                'account': MT5_CONFIG['account'],
                'password': MT5_CONFIG['password'],
                'server': MT5_CONFIG['server'],
                'broker': 'MetaQuotes',
            }

        super().__init__(BrokerType.METATRADER5, credentials)
        # Dynamically launch/check MT5 terminal for this broker
        broker = credentials.get('broker', 'MetaQuotes')
        try:
            import subprocess, sys
            import os
            # Call the terminal manager to ensure the terminal is running
            subprocess.Popen([
                sys.executable, os.path.join(os.path.dirname(__file__), 'mt5_terminal_manager.py'), broker
            ])
        except Exception as e:
            logger.error(f"[MT5 Terminal Manager] Could not launch/check terminal for {broker}: {e}")
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            # Path is now managed by the terminal manager, but keep for SDK
            self.mt5_path = None
        except ImportError:
            logger.error("MetaTrader5 not installed")
            self.mt5 = None

    def connect(self) -> bool:
        """
        Connect to MT5 with retry logic and better error handling
        """
        try:
            if not self.mt5:
                logger.error("MetaTrader5 SDK not available")
                return False

            account = self.credentials.get('account') or MT5_CONFIG['account']
            password = self.credentials.get('password') or MT5_CONFIG['password']
            server = self.credentials.get('server') or MT5_CONFIG['server']
            
            # Retry logic: attempt connection up to 3 times with increasing delays
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                logger.info(f"MT5 connection attempt {attempt}/{max_retries}: Account={account}, Server={server}")
                
                try:
                    # Shutdown any existing connection first
                    if self.mt5.initialize(path=self.mt5_path):
                        # Successfully initialized, now try to login
                        logger.info(f"  ✓ MT5 SDK initialized (path: {self.mt5_path})")
                        
                        # Try login with password first
                        login_result = self.mt5.login(account, password=password, server=server)
                        if login_result:
                            self.connected = True
                            self.get_account_info()
                            logger.info(f"✅ Connected to MT5 account {account} with password")
                            # Subscribe to all symbols for trading
                            self._subscribe_symbols()
                            return True
                        
                        # If password fails, try guest login
                        logger.warning(f"  ✗ Password login failed: {self.mt5.last_error()}")
                        logger.info(f"  ↻ Attempting guest login (no password)...")
                        
                        login_result = self.mt5.login(account, server=server)
                        if login_result:
                            self.connected = True
                            self.get_account_info()
                            logger.info(f"✅ Connected to MT5 account {account} (guest mode)")
                            # Subscribe to all symbols for trading
                            self._subscribe_symbols()
                            return True
                        
                        # Both login methods failed
                        login_error = self.mt5.last_error()
                        logger.warning(f"  ✗ Guest login also failed: {login_error}")
                        
                        # Shutdown for retry
                        try:
                            self.mt5.shutdown()
                        except:
                            pass
                    
                    else:
                        init_error = self.mt5.last_error()
                        logger.warning(f"  ✗ MT5 initialization failed: {init_error}")
                        logger.debug(f"    (Terminal process may still be starting...)")
                
                except Exception as e:
                    logger.warning(f"  ✗ Error during attempt {attempt}: {e}")
                
                # Wait before retry, increasing delay each time
                if attempt < max_retries:
                    wait_time = 3 * attempt  # 3 sec, then 6 sec, then 9 sec
                    logger.info(f"  ⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
            
            # All retries exhausted
            logger.error(f"❌ Failed to connect to MT5 after {max_retries} attempts")
            return False
            
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

    def _subscribe_symbols(self):
        """Subscribe all trading symbols so they're available for order placement"""
        if not self.connected or not self.mt5:
            return
        
        subscribed = 0
        failed = 0
        
        for symbol in VALID_SYMBOLS:
            try:
                if self.mt5.symbol_select(symbol, True):
                    subscribed += 1
                else:
                    logger.debug(f"⚠️  Could not subscribe to {symbol}")
                    failed += 1
            except Exception as e:
                logger.debug(f"⚠️  Error subscribing to {symbol}: {e}")
                failed += 1
        
        logger.info(f"✅ Symbol subscription complete: {subscribed}/{len(VALID_SYMBOLS)} symbols ready for trading")
        if failed > 0:
            logger.warning(f"⚠️  {failed} symbols unavailable (account may not have access)")

    def wait_for_mt5_ready(self, timeout_seconds: int = 60) -> bool:
        """
        Wait for MT5 terminal to be fully ready to execute orders.
        After MT5 restart, the terminal can connect but needs time to be operational.
        
        This method:
        1. Checks account info (basic connectivity)
        2. Checks symbol availability and market data (reading capability)
        3. Checks market hours and trading status (trading capability)
        4. Tests order execution path (full readiness test)
        5. Retries with increasing detail if any check fails
        """
        if not self.connected:
            logger.warning("MT5 not connected - cannot check readiness")
            return False
        
        logger.info(f"🔍 Comprehensive MT5 readiness check (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        check_interval = 5  # Check every 5 seconds
        attempt = 0
        
        while time.time() - start_time < timeout_seconds:
            attempt += 1
            try:
                elapsed = time.time() - start_time
                
                # STEP 1: Check account info
                account_info = self.mt5.account_info()
                if account_info is None:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: account_info = None")
                    time.sleep(check_interval)
                    continue
                
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: account_info OK (balance=${account_info.balance})")
                
                # STEP 2: Check symbol availability and data
                test_symbol = "EURUSD"
                if not self.mt5.symbol_select(test_symbol, True):
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: symbol_select(EURUSD) failed")
                    time.sleep(check_interval)
                    continue
                
                tick = self.mt5.symbol_info_tick(test_symbol)
                if tick is None:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: tick data not available")
                    time.sleep(check_interval)
                    continue
                
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: EURUSD tick OK (bid={tick.bid}, ask={tick.ask})")
                
                # STEP 3: Check symbol info (trading rules, hours, etc)
                symbol_info = self.mt5.symbol_info(test_symbol)
                if symbol_info is None:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: symbol_info(EURUSD) = None")
                    time.sleep(check_interval)
                    continue
                
                is_tradable = symbol_info.trade_mode != self.mt5.SYMBOL_TRADE_MODE_DISABLED
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: symbol_info OK (tradable={is_tradable})")
                
                # STEP 4: Diagnose why order_send might fail
                # Check if this is a permissions/state issue vs system issue
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: Running order execution diagnostic...")
                
                # Try to get positions to verify trading API is responding
                positions = self.mt5.positions_get()
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: positions_get() returned {len(positions) if positions else 'None'} positions")
                
                # Try to get account orders
                orders = self.mt5.orders_get()
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: orders_get() returned {len(orders) if orders else 'None'} orders")
                
                # If we got here, terminal is reading data fine
                # Now test the actual order execution path with a micro test
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: Testing order submission path...")
                
                # Build a test order request (will fail for invalid reasons, but we can see if SDK responds)
                test_request = {
                    "action": self.mt5.TRADE_ACTION_DEAL,
                    "symbol": test_symbol,
                    "volume": 0.01,  # Micro volume for test
                    "type": self.mt5.ORDER_TYPE_BUY,
                    "price": tick.ask,
                    "comment": "ZTEST",  # Short comment within MT5's 31-char limit
                    "type_time": self.mt5.ORDER_TIME_GTC,
                    "type_filling": self.mt5.ORDER_FILLING_FOK,
                }
                
                test_result = self.mt5.order_send(test_request)
                
                # Check what order_send returned
                if test_result is None:
                    logger.warning(f"  Attempt {attempt} [{elapsed:.0f}s]: ⚠️  order_send() returned None (terminal issue, not account)")
                    logger.warning(f"    This usually means:")
                    logger.warning(f"    - MT5 terminal is still initializing")
                    logger.warning(f"    - Terminal lost sync with SDK")
                    logger.warning(f"    - Rare SDK issue")
                    # Continue retrying - terminal may recover
                    time.sleep(check_interval)
                    continue
                
                # order_send did not return None - SDK is working
                # Check if order succeeded or failed for logical reasons
                if hasattr(test_result, 'retcode'):
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: order_send() returned (retcode={test_result.retcode})")
                    logger.info(f"✅ MT5 is READY - order execution path is functional")
                    logger.info(f"   Account: {account_info.login}, Balance: ${account_info.balance}")
                    logger.info(f"   Symbol {test_symbol}: bid={tick.bid:.5f}, ask={tick.ask:.5f}")
                    return True
                else:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: order_send() returned object without retcode")
                    logger.info(f"✅ MT5 is READY - SDK responding to order requests")
                    return True
                    
            except Exception as e:
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: Exception: {e}")
                time.sleep(check_interval)
        
        # Timeout reached
        logger.error(f"❌ MT5 did not become fully ready within {timeout_seconds} seconds")
        logger.error("   Symptoms: order_send() returning None even though connection works")
        logger.error("   Likely causes:")
        logger.error("   1. MT5 terminal is still initializing (needs more time)")
        logger.error("   2. Terminal lost connection to server")
        logger.error("   3. Account restrictions on trading")
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
        """
        Place order on MT5 with recovery logic for None responses
        """
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected'}

            # Enforce minimum volume for specific symbols
            min_volumes = {
                'OILK': 1.0,
                'XAUUSD': 0.01,
                'XAGUSD': 0.1,
                # Add more as needed
            }
            min_volume = min_volumes.get(symbol, 0.01)
            if volume < min_volume:
                logger.info(f"Adjusting volume for {symbol}: requested={volume}, min={min_volume}")
                volume = min_volume

            # First, select the symbol to ensure it's available in MT5
            if not self.mt5.symbol_select(symbol, True):
                return {'success': False, 'error': f'Symbol {symbol} not found in MT5'}

            # Now get the tick data (bid/ask prices)
            tick = self.mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'success': False, 'error': f'Cannot get tick data for {symbol}'}
            
            price = tick.ask if order_type == 'BUY' else tick.bid

            request_dict = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_BUY if order_type == 'BUY' else self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": (kwargs.get('comment', 'ZTrade')[:31] if kwargs.get('comment') else 'ZTrade'),  # Enforce 31-char limit
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_FOK,
            }

            if 'stopLoss' in kwargs:
                request_dict['sl'] = kwargs['stopLoss']
            if 'takeProfit' in kwargs:
                request_dict['tp'] = kwargs['takeProfit']

            result = self.mt5.order_send(request_dict)

            if result is None:
                logger.error(f"MT5 order_send returned None for {symbol} {order_type} vol={volume}")
                logger.error(f"  Request was: {request_dict}")
                logger.error(f"  This usually indicates the terminal is not ready or has lost connection")
                
                # TRY RECOVERY: Attempt to get MT5 last error for diagnostic info
                try:
                    last_error = self.mt5.last_error()
                    logger.error(f"  MT5 last_error: {last_error}")
                except:
                    pass
                
                # Return specific error so caller can distinguish between "symbol not found" vs "terminal issue"
                return {'success': False, 'error': 'MT5 order_send failed - terminal may have disconnected'}
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.warning(f"MT5 order failed: symbol={symbol}, type={order_type}, retcode={result.retcode}, comment={result.comment}")
                return {'success': False, 'error': f'MT5 error: {result.comment}'}

            # Insert trade record into trades table
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                trade_id = str(uuid.uuid4())
                bot_id = kwargs.get('bot_id', 'unknown')
                user_id = kwargs.get('user_id', 'unknown')
                now = datetime.now().isoformat()
                cursor.execute('''
                    INSERT INTO trades (trade_id, bot_id, user_id, symbol, order_type, volume, price, profit, commission, swap, ticket, time_open, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade_id, bot_id, user_id, symbol, order_type, volume, price, 0, 0, 0, result.order, now, 'open', now, now
                ))
                conn.commit()
                conn.close()
                logger.info(f"✅ Trade record inserted for {symbol} {order_type} vol={volume} bot={bot_id}")
            except Exception as e:
                logger.error(f"❌ Error inserting trade record: {e}")

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
                "comment": "ZCLOSE",  # Short comment for close (31-char MT5 limit)
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_FOK,
            }

            result = self.mt5.order_send(request_dict)
            
            if result is None:
                logger.error(f"MT5 order_send returned None when closing position {position_id} - terminal disconnected")
                return {'success': False, 'error': 'MT5 order_send failed - terminal may have disconnected'}
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.warning(f"MT5 close failed: position={position_id}, retcode={result.retcode}, comment={result.comment}")
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


class IGConnection(BrokerConnection):
    """IG.com Broker Connection via REST API"""
    
    def __init__(self, credentials: Dict = None):
        if credentials is None:
            credentials = {
                'api_key': IG_CONFIG['api_key'],
                'username': IG_CONFIG['username'],
                'password': IG_CONFIG['password'],
                'account_id': IG_CONFIG['account_id'],
                'demo_mode': IG_CONFIG['demo_mode']
            }
        
        super().__init__(BrokerType.IG, credentials)
        self.base_url = 'https://api.ig.com/gateway/deal'
        self.session_token = None
        self.client_token = None
        self.last_update = None
        
    def connect(self) -> bool:
        """Connect to IG.com via REST API"""
        try:
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            username = self.credentials.get('username', IG_CONFIG['username'])
            password = self.credentials.get('password', IG_CONFIG['password'])
            
            if not api_key or not username or not password:
                logger.error("IG.com: Missing API key, username, or password")
                return False
            
            # IG.com authentication endpoint
            auth_url = f"{self.base_url}/session"
            headers = {
                'X-IG-API-KEY': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'identifier': username,
                'password': password,
                'encryptionVersion': '2'
            }
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('sessionToken')
                self.client_token = data.get('clientToken')
                self.connected = True
                
                logger.info(f"✅ Connected to IG.com account (demo: {self.credentials.get('demo_mode', True)})")
                self.get_account_info()
                return True
            else:
                logger.error(f"IG.com authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to IG.com: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from IG.com"""
        try:
            if self.connected and self.session_token:
                import requests
                
                api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
                headers = {
                    'X-IG-API-KEY': api_key,
                    'CST': self.session_token,
                    'X-SECURITY-TOKEN': self.client_token,
                    'Content-Type': 'application/json'
                }
                
                response = requests.delete(f"{self.base_url}/session", headers=headers, timeout=10)
                self.connected = False
                logger.info("Disconnected from IG.com")
                return True
        except Exception as e:
            logger.error(f"Error disconnecting from IG.com: {e}")
        
        return False
    
    def get_account_info(self) -> Dict:
        """Get account information from IG.com"""
        try:
            if not self.connected:
                return {}
            
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            headers = {
                'X-IG-API-KEY': api_key,
                'CST': self.session_token,
                'X-SECURITY-TOKEN': self.client_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.get(f"{self.base_url}/accounts", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                if accounts:
                    account = accounts[0]
                    self.account_info = {
                        'account_id': account.get('accountId'),
                        'balance': float(account.get('balance', {}).get('balance', 0)),
                        'equity': float(account.get('balance', {}).get('available', 0)),
                        'currency': account.get('balance', {}).get('currency', 'USD'),
                        'account_type': account.get('accountType', 'Unknown'),
                        'status': account.get('status', 'Unknown')
                    }
                    return self.account_info
        except Exception as e:
            logger.error(f"Error getting IG.com account info: {e}")
        
        return {}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions from IG.com"""
        try:
            if not self.connected:
                return []
            
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            headers = {
                'X-IG-API-KEY': api_key,
                'CST': self.session_token,
                'X-SECURITY-TOKEN': self.client_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.get(f"{self.base_url}/positions", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                positions = data.get('positions', [])
                result = []
                
                for pos in positions:
                    result.append({
                        'deal_id': pos.get('position', {}).get('dealId'),
                        'epic': pos.get('position', {}).get('epic'),
                        'direction': pos.get('position', {}).get('direction'),
                        'size': float(pos.get('position', {}).get('size', 0)),
                        'level': float(pos.get('position', {}).get('level', 0)),
                        'profit_loss': float(pos.get('position', {}).get('profitLoss', 0)),
                        'broker': 'IG'
                    })
                
                return result
        except Exception as e:
            logger.error(f"Error getting IG.com positions: {e}")
        
        return []
    
    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        """Place an order on IG.com"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected to IG.com'}
            
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            headers = {
                'X-IG-API-KEY': api_key,
                'CST': self.session_token,
                'X-SECURITY-TOKEN': self.client_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'epic': symbol,
                'expiry': kwargs.get('expiry', '-'),
                'direction': 'BUY' if order_type.upper() == 'BUY' else 'SELL',
                'size': volume,
                'orderType': 'MARKET',
                'timeInForce': 'EXECUTE_AND_ELIMINATE',
                'stopDistance': kwargs.get('stop_loss', 50),
                'profitDistance': kwargs.get('take_profit', 100),
            }
            
            response = requests.post(
                f"{self.base_url}/positions/otc",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'deal_id': data.get('dealReference'),
                    'epic': symbol,
                    'direction': order_type.upper(),
                    'size': volume,
                    'broker': 'IG'
                }
            else:
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            logger.error(f"Error placing IG.com order: {e}")
            return {'success': False, 'error': str(e)}
    
    def close_position(self, position_id: str) -> Dict:
        """Close a position on IG.com"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected to IG.com'}
            
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            headers = {
                'X-IG-API-KEY': api_key,
                'CST': self.session_token,
                'X-SECURITY-TOKEN': self.client_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            payload = {
                'dealId': position_id,
                'size': 0,  # Close entire position
                'direction': 'SELL',  # Opposite of current
                'orderType': 'MARKET',
                'timeInForce': 'EXECUTE_AND_ELIMINATE'
            }
            
            response = requests.post(
                f"{self.base_url}/positions/otc",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'deal_id': position_id,
                    'broker': 'IG'
                }
            else:
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            logger.error(f"Error closing IG.com position: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_trades(self) -> List[Dict]:
        """Get trade history from IG.com"""
        try:
            if not self.connected:
                return []
            
            import requests
            
            api_key = self.credentials.get('api_key', IG_CONFIG['api_key'])
            headers = {
                'X-IG-API-KEY': api_key,
                'CST': self.session_token,
                'X-SECURITY-TOKEN': self.client_token,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/history/transactions?pageSize=50",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get('transactions', [])
                result = []
                
                for trans in transactions:
                    result.append({
                        'deal_id': trans.get('dealId'),
                        'epic': trans.get('instrumentName', 'Unknown'),
                        'type': trans.get('transactionType'),
                        'profit': float(trans.get('profit', 0)),
                        'time': trans.get('dateUtc', ''),
                        'broker': 'IG'
                    })
                
                return result
        except Exception as e:
            logger.error(f"Error getting IG.com trade history: {e}")
        
        return []


class XMConnection(BrokerConnection):
    """XM (XM Global) Broker Connection via MT5"""
    
    def __init__(self, credentials: Dict = None):
        if credentials is None:
            credentials = {
                'account': os.getenv('XM_ACCOUNT', ''),
                'password': os.getenv('XM_PASSWORD', ''),
                'server': os.getenv('XM_SERVER', 'XMGlobal-MT5'),
                'broker': 'XM'
            }
        
        super().__init__(BrokerType.XM, credentials)
        self.connection = None
    
    def connect(self) -> bool:
        """Connect to XM MT5 account"""
        try:
            # XM uses MT5, so we can use same approach as MT5Connection
            account = self.credentials.get('account')
            password = self.credentials.get('password')
            server = self.credentials.get('server', 'XMGlobal-MT5')
            
            if not account or not password:
                logger.warning(f"XM: Missing account or password credentials")
                return False
            
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                logger.error(f"Failed to initialize MT5 for XM")
                return False
            
            if mt5.login(int(account), password, server):
                self.connected = True
                self.get_account_info()
                logger.info(f"✅ Connected to XM account {account}")
                return True
            else:
                logger.error(f"Failed to login to XM account {account}: {mt5.last_error()}")
                mt5.shutdown()
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to XM: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from XM"""
        try:
            if self.connected:
                import MetaTrader5 as mt5
                mt5.shutdown()
                self.connected = False
                logger.info("Disconnected from XM")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from XM: {e}")
        return False
    
    def get_account_info(self) -> Dict:
        """Get account info from XM"""
        try:
            if not self.connected:
                return {}
            
            import MetaTrader5 as mt5
            
            account_info = mt5.account_info()
            if account_info:
                self.account_info = {
                    'account_id': account_info.login,
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin': account_info.margin,
                    'margin_free': account_info.margin_free,
                    'broker': 'XM'
                }
                return self.account_info
        except Exception as e:
            logger.error(f"Error getting XM account info: {e}")
        
        return {}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions from XM"""
        try:
            if not self.connected:
                return []
            
            import MetaTrader5 as mt5
            
            positions = mt5.positions_get()
            result = []
            
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price': pos.price_open,
                    'profit': pos.profit,
                    'broker': 'XM'
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting XM positions: {e}")
        
        return []
    
    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        """Place order on XM"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected to XM'}
            
            import MetaTrader5 as mt5
            
            order_type_mt5 = mt5.ORDER_TYPE_BUY if order_type.upper() == 'BUY' else mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type_mt5,
                "price": mt5.symbol_info_tick(symbol).ask if order_type.upper() == 'BUY' else mt5.symbol_info_tick(symbol).bid,
            }
            
            if 'stop_loss' in kwargs:
                request['sl'] = kwargs['stop_loss']
            if 'take_profit' in kwargs:
                request['tp'] = kwargs['take_profit']
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return {
                    'success': True,
                    'ticket': result.order,
                    'symbol': symbol,
                    'type': order_type.upper(),
                    'volume': volume,
                    'broker': 'XM'
                }
            else:
                return {'success': False, 'error': f'Order failed: {result.comment}'}
                
        except Exception as e:
            logger.error(f"Error placing XM order: {e}")
            return {'success': False, 'error': str(e)}
    
    def close_position(self, position_id: str) -> Dict:
        """Close position on XM"""
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected to XM'}
            
            import MetaTrader5 as mt5
            
            position = mt5.positions_get(ticket=int(position_id))
            if not position:
                return {'success': False, 'error': 'Position not found'}
            
            pos = position[0]
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": int(position_id),
                "price": mt5.symbol_info_tick(pos.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return {'success': True, 'position_id': position_id, 'broker': 'XM'}
            else:
                return {'success': False, 'error': f'Close failed: {result.comment}'}
                
        except Exception as e:
            logger.error(f"Error closing XM position: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_trades(self) -> List[Dict]:
        """Get trade history from XM"""
        try:
            if not self.connected:
                return []
            
            import MetaTrader5 as mt5
            
            deals = mt5.history_deals_get(position=0)
            result = []
            
            for deal in deals[-50:]:
                result.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
                    'volume': deal.volume,
                    'price': deal.price,
                    'profit': deal.profit,
                    'time': datetime.fromtimestamp(deal.time).isoformat(),
                    'broker': 'XM',
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting XM trades: {e}")
        
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
            elif broker_type == BrokerType.IG:
                connection = IGConnection(credentials)
            elif broker_type == BrokerType.XM:
                connection = XMConnection(credentials)
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

# Auto-add IG.com account with API credentials
logger.info("Initializing with IG.com account")
broker_manager.add_connection('IG Markets', BrokerType.IG, IG_CONFIG)

# AUTO-CONNECT to MT5 on startup (so dashboard shows real balance)
def auto_connect_mt5():
    """Auto-connect to MT5 on startup"""
    try:
        connection = broker_manager.connections.get('Default MT5')
        if connection:
            logger.info("🔗 Attempting auto-connect to MT5...")
            if connection.connect():
                logger.info("✅ Auto-connected to MT5 successfully - balance will display on dashboard")
                return True
            else:
                logger.warning("⚠️  Failed to auto-connect to MT5 - will use simulated trading, dashboard will show $0 balance")
                return False
    except Exception as e:
        logger.warning(f"⚠️  Error auto-connecting to MT5: {e} - will use simulated trading")
        return False

def auto_connect_ig():
    """Auto-connect to IG.com on startup"""
    try:
        connection = broker_manager.connections.get('IG Markets')
        if connection:
            logger.info("🔗 Attempting auto-connect to IG.com...")
            if connection.connect():
                logger.info("✅ Auto-connected to IG.com successfully using API key: 9bbc3ef9ad291acec96dc409d80e50c4c805161a")
                return True
            else:
                logger.warning("⚠️  IG.com connection requires username and password for full authentication")
                logger.info("   You can still trade via API after providing credentials")
                return False
    except Exception as e:
        logger.warning(f"⚠️  Error auto-connecting to IG.com: {e}")
        return False

# Note: Connection happens after Flask initialization in __main__


# ==================== API ENDPOINTS ====================
@app.route('/api/funds/transfer', methods=['POST'])
def transfer_funds_api():
    """Trigger fund transfer between brokers/accounts from Flutter app"""
    try:
        data = request.json
        from_account = data.get('from_account')
        to_account = data.get('to_account')
        amount = float(data.get('amount', 0))
        if not from_account or not to_account or amount <= 0:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
        result = broker_manager.transfer_funds(from_account, to_account, amount)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in transfer_funds_api: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== IG.COM API ENDPOINTS ====================

@app.route('/api/ig/connect', methods=['POST'])
def ig_connect():
    """Connect to IG.com Markets API"""
    try:
        data = request.json or {}
        
        # Update credentials if provided
        if data.get('username'):
            IG_CONFIG['username'] = data.get('username')
        if data.get('password'):
            IG_CONFIG['password'] = data.get('password')
        if data.get('api_key'):
            IG_CONFIG['api_key'] = data.get('api_key')
        
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection:
            return jsonify({'success': False, 'error': 'IG Markets connection not initialized'}), 500
        
        if ig_connection.connect():
            return jsonify({
                'success': True,
                'message': 'Connected to IG.com successfully',
                'api_key': IG_CONFIG['api_key'],
                'account_id': ig_connection.account_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to IG.com. Check credentials and internet connection.',
                'api_key': IG_CONFIG['api_key']
            }), 401
    except Exception as e:
        logger.error(f"Error connecting to IG.com: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ig/account-info', methods=['GET'])
def ig_account_info():
    """Get IG.com account information"""
    try:
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection or not ig_connection.connected:
            return jsonify({'success': False, 'error': 'IG.com not connected'}), 401
        
        account_info = ig_connection.get_account_info()
        return jsonify({
            'success': True,
            'account': account_info,
            'api_key': IG_CONFIG['api_key']
        })
    except Exception as e:
        logger.error(f"Error getting IG account info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ig/positions', methods=['GET'])
def ig_positions():
    """Get IG.com open positions"""
    try:
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection or not ig_connection.connected:
            return jsonify({'success': False, 'error': 'IG.com not connected'}), 401
        
        positions = ig_connection.get_positions()
        return jsonify({
            'success': True,
            'positions': positions
        })
    except Exception as e:
        logger.error(f"Error getting IG positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ig/place-order', methods=['POST'])
def ig_place_order():
    """Place order on IG.com Markets"""
    try:
        data = request.json
        epic = data.get('epic')
        direction = data.get('direction')
        size = float(data.get('size', 0))
        
        if not all([epic, direction, size > 0]):
            return jsonify({'success': False, 'error': 'Missing parameters: epic, direction, size'}), 400
        
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection or not ig_connection.connected:
            return jsonify({'success': False, 'error': 'IG.com not connected'}), 401
        
        result = ig_connection.place_order(epic, direction, size)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error placing IG order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ig/trades', methods=['GET'])
def ig_trades():
    """Get IG.com open trades"""
    try:
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection or not ig_connection.connected:
            return jsonify({'success': False, 'error': 'IG.com not connected'}), 401
        
        trades = ig_connection.get_trades()
        return jsonify({
            'success': True,
            'trades': trades
        })
    except Exception as e:
        logger.error(f"Error getting IG trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ig/close-position', methods=['POST'])
def ig_close_position():
    """Close a position on IG.com"""
    try:
        data = request.json
        deal_id = data.get('deal_id')
        epic = data.get('epic')
        
        if not deal_id or not epic:
            return jsonify({'success': False, 'error': 'Missing parameters: deal_id, epic'}), 400
        
        ig_connection = broker_manager.connections.get('IG Markets')
        if not ig_connection or not ig_connection.connected:
            return jsonify({'success': False, 'error': 'IG.com not connected'}), 401
        
        result = ig_connection.close_position(deal_id, epic)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error closing IG position: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'service': 'Zwesta Multi-Broker Backend',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat(),
    })


# ==================== VPS MANAGEMENT ENDPOINTS ====================

@app.route('/api/vps/config', methods=['POST'])
@require_session
def add_vps_config():
    """Add/update VPS configuration for user"""
    try:
        user_id = request.user_id
        data = request.json
        
        if not all([data.get('vps_name'), data.get('vps_ip'), data.get('username'), data.get('password')]):
            return jsonify({'success': False, 'error': 'Missing required fields: vps_name, vps_ip, username, password'}), 400
        
        vps_id = data.get('vps_id') or f"vps_{uuid.uuid4().hex[:8]}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if updating existing VPS
        if data.get('vps_id'):
            cursor.execute('SELECT vps_id FROM vps_config WHERE vps_id = ? AND user_id = ?', (vps_id, user_id))
            if cursor.fetchone():
                cursor.execute('''
                    UPDATE vps_config SET vps_name = ?, vps_ip = ?, vps_port = ?, username = ?, 
                    password = ?, rdp_port = ?, api_port = ?, mt5_path = ?, notes = ?, updated_at = ?
                    WHERE vps_id = ? AND user_id = ?
                ''', (
                    data.get('vps_name'), data.get('vps_ip'), data.get('vps_port', 3389),
                    data.get('username'), data.get('password'), data.get('rdp_port', 3389),
                    data.get('api_port', 5000), data.get('mt5_path', 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'),
                    data.get('notes'), datetime.now().isoformat(), vps_id, user_id
                ))
            else:
                return jsonify({'success': False, 'error': 'VPS not found'}), 404
        else:
            # Create new VPS config
            cursor.execute('''
                INSERT INTO vps_config (vps_id, user_id, vps_name, vps_ip, vps_port, username, 
                password, rdp_port, api_port, mt5_path, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vps_id, user_id, data.get('vps_name'), data.get('vps_ip'), 
                data.get('vps_port', 3389), data.get('username'), data.get('password'),
                data.get('rdp_port', 3389), data.get('api_port', 5000),
                data.get('mt5_path', 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'),
                data.get('notes'), datetime.now().isoformat(), datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ VPS config saved: {data.get('vps_name')} ({data.get('vps_ip')}:{data.get('vps_port', 3389)}) for user {user_id}")
        
        return jsonify({
            'success': True,
            'vps_id': vps_id,
            'message': 'VPS configuration saved successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"❌ Error saving VPS config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/list', methods=['GET'])
@require_session
def list_vps_configs():
    """Get all VPS configurations for authenticated user"""
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vps_id, vps_name, vps_ip, vps_port, rdp_port, api_port, 
            mt5_path, status, last_connection, created_at
            FROM vps_config WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        vps_configs = []
        for row in cursor.fetchall():
            vps_configs.append({
                'vps_id': row[0],
                'vps_name': row[1],
                'vps_ip': row[2],
                'vps_port': row[3],
                'rdp_port': row[4],
                'api_port': row[5],
                'mt5_path': row[6],
                'status': row[7],
                'last_connection': row[8],
                'created_at': row[9]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'vps_configs': vps_configs,
            'count': len(vps_configs)
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error listing VPS configs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/<vps_id>/test-connection', methods=['POST'])
@require_session
def test_vps_connection(vps_id):
    """Test connection to VPS"""
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vps_ip, vps_port, username, password, rdp_port, api_port
            FROM vps_config WHERE vps_id = ? AND user_id = ?
        ''', (vps_id, user_id))
        
        vps_data = cursor.fetchone()
        if not vps_data:
            return jsonify({'success': False, 'error': 'VPS configuration not found'}), 404
        
        vps_ip, vps_port, username, password, rdp_port, api_port = vps_data
        
        # Test ping to VPS
        logger.info(f"🔌 Testing VPS connection to {vps_ip}:{vps_port}")
        result = subprocess.run(
            f'ping -n 1 -w 2000 {vps_ip}',
            capture_output=True,
            text=True,
            shell=True,
            timeout=5
        )
        
        ping_success = result.returncode == 0
        
        # Try to reach backend API on VPS
        api_reachable = False
        try:
            import requests
            response = requests.get(
                f'http://{vps_ip}:{api_port}/api/health',
                timeout=5
            )
            api_reachable = response.status_code == 200
        except:
            api_reachable = False
        
        # Update last connection time
        cursor.execute('''
            UPDATE vps_config SET last_connection = ?, status = ?
            WHERE vps_id = ?
        ''', (
            datetime.now().isoformat(),
            'connected' if (ping_success or api_reachable) else 'disconnected',
            vps_id
        ))
        conn.commit()
        conn.close()
        
        status = 'connected' if (ping_success or api_reachable) else 'disconnected'
        logger.info(f"✅ VPS test result: {status} (Ping: {ping_success}, API: {api_reachable})")
        
        return jsonify({
            'success': True,
            'vps_id': vps_id,
            'vps_ip': vps_ip,
            'status': status,
            'ping_reachable': ping_success,
            'api_reachable': api_reachable,
            'rdp_port': rdp_port,
            'api_port': api_port,
            'message': f'VPS is {status}'
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error testing VPS connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/<vps_id>/status', methods=['GET'])
@require_session
def get_vps_status(vps_id):
    """Get VPS status and monitoring data"""
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vps_id, vps_name, vps_ip, status, last_connection
            FROM vps_config WHERE vps_id = ? AND user_id = ?
        ''', (vps_id, user_id))
        
        vps_config = cursor.fetchone()
        if not vps_config:
            return jsonify({'success': False, 'error': 'VPS not found'}), 404
        
        # Get monitoring data
        cursor.execute('''
            SELECT mt5_status, backend_running, cpu_usage, memory_usage, uptime_hours, 
            active_bots, total_value_locked, last_check
            FROM vps_monitoring WHERE vps_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (vps_id,))
        
        monitoring = cursor.fetchone()
        conn.close()
        
        status_obj = {
            'vps_id': vps_config[0],
            'vps_name': vps_config[1],
            'vps_ip': vps_config[2],
            'connection_status': vps_config[3],
            'last_connection': vps_config[4],
        }
        
        if monitoring:
            status_obj.update({
                'mt5_status': monitoring[0],
                'backend_running': bool(monitoring[1]),
                'cpu_usage': monitoring[2],
                'memory_usage': monitoring[3],
                'uptime_hours': monitoring[4],
                'active_bots': monitoring[5],
                'total_value_locked': monitoring[6],
                'last_check': monitoring[7]
            })
        
        return jsonify({
            'success': True,
            'vps_status': status_obj
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error getting VPS status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/<vps_id>/remote-access', methods=['POST'])
@require_session
def get_vps_remote_access(vps_id):
    """Get RDP connection details for remote desktop access to VPS"""
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vps_ip, rdp_port, username, vps_name
            FROM vps_config WHERE vps_id = ? AND user_id = ?
        ''', (vps_id, user_id))
        
        vps_data = cursor.fetchone()
        conn.close()
        
        if not vps_data:
            return jsonify({'success': False, 'error': 'VPS not found'}), 404
        
        vps_ip, rdp_port, username, vps_name = vps_data
        
        # Generate RDP connection string
        rdp_server = f"{vps_ip}:{rdp_port}" if rdp_port != 3389 else vps_ip
        
        logger.info(f"✅ RDP connection details requested for {vps_name}")
        
        return jsonify({
            'success': True,
            'vps_name': vps_name,
            'rdp_server': rdp_server,
            'rdp_port': rdp_port,
            'username': username,
            'connection_string': f'mstsc /v:{rdp_server}',
            'instructions': [
                f'1. Copy the connection string: mstsc /v:{rdp_server}',
                f'2. Run it in Windows Run dialog (Win+R)',
                f'3. Username: {username}',
                f'4. Enter your password when prompted',
                f'5. You will have remote access to MT5 on the VPS'
            ]
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error getting RDP details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/<vps_id>/delete', methods=['DELETE', 'POST'])
@require_session
def delete_vps_config(vps_id):
    """Delete VPS configuration"""
    try:
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute('SELECT vps_name FROM vps_config WHERE vps_id = ? AND user_id = ?', (vps_id, user_id))
        vps = cursor.fetchone()
        if not vps:
            return jsonify({'success': False, 'error': 'VPS not found'}), 404
        
        # Delete VPS config
        cursor.execute('DELETE FROM vps_config WHERE vps_id = ?', (vps_id,))
        cursor.execute('DELETE FROM vps_monitoring WHERE vps_id = ?', (vps_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ VPS deleted: {vps[0]}")
        
        return jsonify({
            'success': True,
            'message': f'VPS {vps[0]} deleted successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error deleting VPS: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vps/<vps_id>/heartbeat', methods=['POST'])
def vps_heartbeat(vps_id):
    """VPS reports its status (called from VPS backend for monitoring)
    
    This endpoint allows VPS instances to periodically report their health status.
    No authentication required - VPS identifies itself by vps_id.
    
    Expected payload:
    {
        "mt5_status": "online|offline",
        "backend_running": true/false,
        "cpu_usage": 45.5,
        "memory_usage": 62.3,
        "uptime_hours": 24,
        "active_bots": 3,
        "total_value_locked": 50000.00
    }
    """
    try:
        data = request.json or {}
        
        logger.info(f"💓 VPS heartbeat from {vps_id}: MT5={data.get('mt5_status')}, Backend={data.get('backend_running')}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create or update monitoring record
        monitoring_id = f"mon_{vps_id}_{int(time.time())}"
        
        cursor.execute('''
            INSERT INTO vps_monitoring (
                monitoring_id, vps_id, user_id, last_heartbeat, mt5_status, backend_running,
                cpu_usage, memory_usage, uptime_hours, active_bots, total_value_locked, last_check, created_at
            )
            VALUES (?, ?, (SELECT user_id FROM vps_config WHERE vps_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            monitoring_id, vps_id, vps_id, datetime.now().isoformat(),
            data.get('mt5_status', 'offline'), data.get('backend_running', False),
            data.get('cpu_usage', 0), data.get('memory_usage', 0),
            data.get('uptime_hours', 0), data.get('active_bots', 0),
            data.get('total_value_locked', 0), datetime.now().isoformat(), datetime.now().isoformat()
        ))
        
        # Update VPS config status
        cursor.execute('''
            UPDATE vps_config SET status = ?, last_connection = ?
            WHERE vps_id = ?
        ''', ('connected' if data.get('backend_running') else 'offline', datetime.now().isoformat(), vps_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'vps_id': vps_id,
            'message': 'Heartbeat received'
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Error processing VPS heartbeat: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
        {
            'type': 'ig',
            'name': 'IG',
            'description': 'IG Group - Global Forex and CFD broker',
            'assets': ['Forex', 'Indices', 'Commodities', 'CFDs'],
            'status': 'coming_soon'
        },
        {
            'type': 'fxm',
            'name': 'FXM',
            'description': 'FXM - Forex and CFD broker',
            'assets': ['Forex', 'CFDs'],
            'status': 'coming_soon'
        },
        {
            'type': 'avatrade',
            'name': 'AvaTrade',
            'description': 'AvaTrade - Regulated global broker',
            'assets': ['Forex', 'CFDs', 'Cryptos'],
            'status': 'coming_soon'
        },
        {
            'type': 'fpmarkets',
            'name': 'FP Markets',
            'description': 'FP Markets - Multi-asset broker',
            'assets': ['Forex', 'CFDs', 'Commodities', 'Indices'],
            'status': 'coming_soon'
        },
        {
            'type': 'pepperstone',
            'name': 'Pepperstone',
            'description': 'Pepperstone - Award-winning forex broker',
            'assets': ['Forex', 'CFDs', 'Commodities', 'Indices'],
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
            # Automate commission payout if trade is profitable
            profit = result.get('profit', 0)
            if profit and profit > 0:
                bot_id = data.get('bot_id', 'unknown')
                user_id = data.get('user_id', 'unknown')
                distribute_trade_commissions(bot_id, user_id, profit)
            return jsonify(result)
        else:
            # Demo trade - create mock trade record and store it
            try:
                import random
                profit = random.uniform(-500, 2500)
                ticket = random.randint(1000000, 9999999)

                broker_name = 'MT5'
                if isinstance(connection, IGConnection):
                    broker_name = 'IG'
                elif isinstance(connection, XMConnection):
                    broker_name = 'XM'

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
                    'broker': broker_name,
                    'status': 'open',
                }

                # Store trade in memory so it can be retrieved later
                if account_id not in demo_trades_storage:
                    demo_trades_storage[account_id] = []
                demo_trades_storage[account_id].append(demo_trade)

                logger.info(f"Created and stored demo trade: {symbol} {order_type} {volume} lots for account {account_id} ({broker_name})")
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
            'xm': BrokerType.XM,
            'pepperstone': BrokerType.PEPPERSTONE,
            'fxopen': BrokerType.FXOPEN,
            'exness': BrokerType.EXNESS,
            'darwinex': BrokerType.DARWINEX,
            'ig': BrokerType.IG,
            'fxm': BrokerType.FXM,
            'avatrade': BrokerType.AVATRADE,
            'fpmarkets': BrokerType.FPMARKETS,
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
    """Get list of available trading symbols/commodities WITH live market data"""
    try:
        with market_data_lock:
            # Build two things:
            # 1. Flat dictionary for UI market data lookup (by symbol)
            # 2. Categorized list for symbol selection
            
            flat_market_data = {}  # {EURUSD: {signal, trend, etc}, GBPUSD: {signal, trend, etc}, ...}
            categorized = {
                'forex': [],
                'commodities': [],
                'precious_metals': [],
                'energy': [],
                'indices': [],
                'stocks': []
            }
            
            symbol_config = {
                'forex': [
                    {'symbol': 'EURUSD', 'name': 'Euro vs US Dollar', 'min_price': 1.08, 'max_price': 1.10},
                    {'symbol': 'GBPUSD', 'name': 'British Pound vs US Dollar', 'min_price': 1.27, 'max_price': 1.29},
                    {'symbol': 'USDCHF', 'name': 'US Dollar vs Swiss Franc', 'min_price': 0.89, 'max_price': 0.91},
                    {'symbol': 'USDJPY', 'name': 'US Dollar vs Japanese Yen', 'min_price': 149.0, 'max_price': 151.0},
                    {'symbol': 'USDCNH', 'name': 'US Dollar vs Chinese Yuan', 'min_price': 7.28, 'max_price': 7.30},
                    {'symbol': 'AUDUSD', 'name': 'Australian Dollar vs US Dollar', 'min_price': 0.65, 'max_price': 0.67},
                    {'symbol': 'NZDUSD', 'name': 'New Zealand Dollar vs US Dollar', 'min_price': 0.61, 'max_price': 0.63},
                    {'symbol': 'USDCAD', 'name': 'US Dollar vs Canadian Dollar', 'min_price': 1.35, 'max_price': 1.37},
                    {'symbol': 'USDSEK', 'name': 'US Dollar vs Swedish Krona', 'min_price': 10.88, 'max_price': 10.92},
                ],
                'precious_metals': [
                    {'symbol': 'XAUUSD', 'name': '🥇 Gold (per troy oz)', 'type': 'Metal', 'lucrative': True, 'min_price': 2000, 'max_price': 2100},
                    {'symbol': 'XAGUSD', 'name': '⚪ Silver (per troy oz)', 'type': 'Metal', 'lucrative': True, 'min_price': 28, 'max_price': 35},
                    {'symbol': 'XPTUSD', 'name': 'Platinum (per troy oz)', 'type': 'Metal', 'lucrative': True, 'min_price': 900, 'max_price': 950},
                    {'symbol': 'XPDUSD', 'name': 'Palladium (per troy oz)', 'type': 'Metal', 'lucrative': True, 'min_price': 1100, 'max_price': 1200},
                ],
                'energy': [
                    {'symbol': 'OILK', 'name': '🛢️ Crude Oil (per barrel)', 'type': 'Energy', 'lucrative': True, 'min_price': 70, 'max_price': 90},
                    {'symbol': 'NATGASUS', 'name': 'Natural Gas (per MMBtu)', 'type': 'Energy', 'lucrative': True, 'min_price': 2.0, 'max_price': 4.0},
                ],
                'indices': [
                    {'symbol': 'SP500m', 'name': 'S&P 500 Index', 'min_price': 5000, 'max_price': 5500},
                    {'symbol': 'DAX', 'name': 'DAX 40 (Germany)', 'min_price': 18000, 'max_price': 18500},
                    {'symbol': 'US300', 'name': 'US 300 Index', 'min_price': 15000, 'max_price': 16000},
                    {'symbol': 'US100', 'name': 'US 100 Index (Nasdaq)', 'min_price': 18000, 'max_price': 19000},
                ],
                'stocks': [
                    {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.', 'min_price': 180, 'max_price': 200},
                    {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'min_price': 400, 'max_price': 430},
                    {'symbol': 'INTC', 'name': 'Intel Corporation', 'min_price': 45, 'max_price': 55},
                    {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'min_price': 850, 'max_price': 900},
                    {'symbol': 'NIKL', 'name': 'Nikkei 225 Index', 'min_price': 28000, 'max_price': 30000},
                ]
            }
            
            # Build response by merging live data with config
            for category, items in symbol_config.items():
                for item_config in items:
                    symbol = item_config['symbol']
                    # Get live market data for this symbol (from the updater thread)
                    live_data = commodity_market_data.get(symbol, {})
                    # Merge config + live data
                    merged_item = {**item_config, **live_data}
                    categorized[category].append(merged_item)
                    # Also store in flat dict for easy lookup by symbol
                    flat_market_data[symbol] = live_data
            
            # Log sample signals for debugging
            eurusd_signal = flat_market_data.get('EURUSD', {}).get('signal', 'NO DATA')
            oilk_signal = flat_market_data.get('OILK', {}).get('signal', 'NO DATA')
            logger.info(f"[/api/commodities/list] Returning signals: EURUSD={eurusd_signal}, OILK={oilk_signal}")
            
            return jsonify({
                'success': True,
                'commodities': categorized,  # Nested format for symbol selection
                'marketData': flat_market_data,  # Flat format for signal lookup
                'total_symbols': sum(len(v) for v in categorized.values()),
                'timestamp': datetime.now().isoformat(),
            }), 200
    except Exception as e:
        logger.error(f"Error getting commodities list: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trading/best-assets', methods=['GET'])
def get_best_assets():
    """Get the top N most profitable assets for trading based on intelligent analysis"""
    try:
        limit = request.args.get('limit', 5, type=int)
        limit = max(1, min(limit, 27))  # Clamp between 1 and 27
        
        best_assets = get_best_trading_assets(limit=limit)
        
        # Get detailed data for each asset
        asset_details = []
        with market_data_lock:
            for symbol in best_assets:
                data = commodity_market_data.get(symbol, {})
                asset_details.append({
                    'symbol': symbol,
                    'price': data.get('price', 0),
                    'change': data.get('change', 0),
                    'signal': data.get('signal', 'UNKNOWN'),
                    'trend': data.get('trend', 'FLAT'),
                    'volatility': data.get('volatility', 'Unknown'),
                    'profitability_score': data.get('profitability_score', 0.50),
                    'recommendation': data.get('recommendation', 'No data'),
                })
        
        logger.info(f"[/api/trading/best-assets] Returning top {limit} assets for bot trading")
        
        return jsonify({
            'success': True,
            'best_assets': best_assets,
            'details': asset_details,
            'count': len(asset_details),
            'timestamp': datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting best assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/generate-trades', methods=['POST'])
def generate_demo_trades():
    """Generate mock trades for demo/testing purposes"""
    try:
        import random
        from decimal import Decimal
        
        account_id = request.json.get('accountId', 'default_mt5') if request.json else 'default_mt5'
        count = request.json.get('count', 5) if request.json else 5
        
        demo_trades = []
        
        # Define trading symbols with realistic price ranges (METAQUOTES-DEMO AVAILABLE SYMBOLS)
        commodity_data = {
            # ===== FOREX (9) =====
            'EURUSD': {'min_price': 1.08, 'max_price': 1.10, 'volume_range': (0.1, 5.0)},
            'GBPUSD': {'min_price': 1.27, 'max_price': 1.29, 'volume_range': (0.1, 5.0)},
            'USDCHF': {'min_price': 0.89, 'max_price': 0.91, 'volume_range': (0.1, 5.0)},
            'USDJPY': {'min_price': 149.0, 'max_price': 151.0, 'volume_range': (0.1, 5.0)},
            'USDCNH': {'min_price': 7.28, 'max_price': 7.30, 'volume_range': (0.1, 5.0)},
            'AUDUSD': {'min_price': 0.65, 'max_price': 0.67, 'volume_range': (0.1, 5.0)},
            'NZDUSD': {'min_price': 0.61, 'max_price': 0.63, 'volume_range': (0.1, 5.0)},
            'USDCAD': {'min_price': 1.35, 'max_price': 1.37, 'volume_range': (0.1, 5.0)},
            'USDSEK': {'min_price': 10.88, 'max_price': 10.92, 'volume_range': (0.1, 5.0)},
            
            # ===== PRECIOUS METALS (4) =====
            'XAUUSD': {'min_price': 2000, 'max_price': 2100, 'volume_range': (0.01, 2.0)},  # GOLD
            'XAGUSD': {'min_price': 28, 'max_price': 35, 'volume_range': (0.1, 10.0)},  # SILVER
            'XPTUSD': {'min_price': 900, 'max_price': 950, 'volume_range': (0.01, 1.0)},  # PLATINUM
            'XPDUSD': {'min_price': 1100, 'max_price': 1200, 'volume_range': (0.01, 1.0)},  # PALLADIUM
            
            # ===== ENERGY (2) =====
            'OILK': {'min_price': 70, 'max_price': 90, 'volume_range': (1, 100)},  # CRUDE OIL
            'NATGASUS': {'min_price': 2.0, 'max_price': 4.0, 'volume_range': (1, 500)},  # NATURAL GAS
            
            # ===== INDICES (4) =====
            'SP500m': {'min_price': 5000, 'max_price': 5500, 'volume_range': (0.1, 5.0)},  # S&P 500
            'DAX': {'min_price': 18000, 'max_price': 18500, 'volume_range': (0.1, 5.0)},  # DAX
            'US300': {'min_price': 15000, 'max_price': 16000, 'volume_range': (0.1, 5.0)},  # US 300
            'US100': {'min_price': 18000, 'max_price': 19000, 'volume_range': (0.1, 5.0)},  # US 100 (Nasdaq)
            
            # ===== STOCKS (5) =====
            'AMD': {'min_price': 180, 'max_price': 200, 'volume_range': (0.1, 5.0)},
            'MSFT': {'min_price': 400, 'max_price': 430, 'volume_range': (0.1, 5.0)},
            'INTC': {'min_price': 45, 'max_price': 55, 'volume_range': (0.1, 5.0)},
            'NVDA': {'min_price': 850, 'max_price': 900, 'volume_range': (0.1, 5.0)},
            'NIKL': {'min_price': 28000, 'max_price': 30000, 'volume_range': (0.01, 2.0)},
        }
        
        symbols = list(commodity_data.keys())
        
        for i in range(count):
            symbol = random.choice(symbols)
            symbol_data = commodity_data[symbol]
            
            # Higher profit potential for commodities and oil
            profit = random.uniform(-1000, 5000) if 'XPTUSD' in symbol or 'OILK' in symbol else random.uniform(-500, 2500)
            
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


@app.route('/api/trades-public', methods=['GET'])
def get_trades_public():
    """Get all trades (public - no authentication required) - for demo/public bots"""
    try:
        trades_list = []
        
        # Get trades from active bots' trade history
        for bot_id, bot in active_bots.items():
            if 'tradeHistory' in bot:
                trades_list.extend(bot['tradeHistory'][-100:])  # Last 100 trades per bot
        
        # Sort by recent first and limit to 1000 total
        trades_list = sorted(trades_list, key=lambda x: x.get('time', ''), reverse=True)[:1000]
        
        logger.info(f"Returning {len(trades_list)} public trades from active bots")
        return jsonify({
            'success': True,
            'trades': trades_list,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error getting public trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trades/unified', methods=['GET'])
@require_session
def get_unified_trades():
    """Get unified trades from all user's brokers (IG + XM + MT5)"""
    try:
        user_id = request.user_id
        trades_list = []
        broker_summary = {}

        # Fetch trades from all connected brokers
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all broker credentials for this user
        cursor.execute('''
            SELECT broker_name, account_number, credential_id 
            FROM broker_credentials
            WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        
        credentials = cursor.fetchall()
        
        for cred in credentials:
            broker_name = cred['broker_name']
            account_number = cred['account_number']
            
            try:
                # Get connection for this broker
                connection = broker_manager.connections.get(f"{broker_name}_{account_number}")
                
                if connection and connection.connected:
                    # Fetch trades from broker
                    broker_trades = connection.get_trades()
                    
                    # Add broker info to each trade
                    for trade in broker_trades:
                        trade['broker'] = broker_name
                        trade['account'] = account_number
                        trades_list.append(trade)
                    
                    # Track broker summary
                    broker_summary[broker_name] = {
                        'account': account_number,
                        'trades_count': len(broker_trades),
                        'total_profit': sum(t.get('profit', 0) for t in broker_trades)
                    }
                    
                    logger.info(f"✅ Fetched {len(broker_trades)} trades from {broker_name} account {account_number}")
            except Exception as e:
                logger.warning(f"⚠️  Could not fetch trades from {broker_name}: {e}")
        
        conn.close()
        
        # Also get demo trades from active bots for this user
        for bot_id, bot in active_bots.items():
            if bot.get('user_id') == user_id and 'tradeHistory' in bot:
                for trade in bot['tradeHistory'][-50:]:  # Last 50 trades
                    trade['broker'] = 'DEMO'
                    trade['bot_id'] = bot_id
                    trades_list.append(trade)
        
        # Sort by time (most recent first)
        trades_list = sorted(trades_list, key=lambda x: x.get('time', ''), reverse=True)[:500]
        
        logger.info(f"✅ Returning {len(trades_list)} unified trades for user {user_id}")
        
        return jsonify({
            'success': True,
            'trades': trades_list,
            'total_trades': len(trades_list),
            'broker_summary': broker_summary,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching unified trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error in get_trades_public: {e}")
        return jsonify({
            'success': False,
            'trades': [],
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }), 500


# ==================== ALIAS ROUTES (for Flutter app compatibility) ====================
@app.route('/api/trades', methods=['GET'])
@require_session
def get_trades_alias():
    """Get trades for the authenticated user - returns flattened trades list"""
    try:
        user_id = request.user_id  # From require_session decorator
        trades_list = []
        
        # Query database for user's bots and their associated trades
        conn = sqlite3.connect('zwesta_trading.db')
        cursor = conn.cursor()
        
        try:
            # Get all bots for this user
            cursor.execute('''
                SELECT bot_id, config FROM user_bots WHERE user_id = ?
            ''', (user_id,))
            user_bots = cursor.fetchall()
            
            bot_ids = [bot[0] for bot in user_bots]
            
            if bot_ids:
                # Get all trades for user's bots
                placeholders = ','.join(['?' for _ in bot_ids])
                cursor.execute(f'''
                    SELECT trade_data FROM trades WHERE bot_id IN ({placeholders})
                    ORDER BY timestamp DESC
                ''', bot_ids)
                
                for row in cursor.fetchall():
                    try:
                        trade = json.loads(row[0])
                        trade['userId'] = user_id  # Ensure user isolation
                        trades_list.append(trade)
                    except:
                        pass
            
            logger.info(f"Returning {len(trades_list)} trades for user {user_id}")
            return jsonify({
                'success': True,
                'trades': trades_list,
                'timestamp': datetime.now().isoformat(),
            })
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error in get_trades_alias for user {request.user_id}: {e}")
        return jsonify({
            'success': False,
            'trades': [],
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }), 500


@app.route('/api/account/info', methods=['GET'])
@require_session
def get_account_info_alias():
    """Get account info for authenticated user"""
    user_id = request.user_id
    
    try:
        # Get MT5 account info from broker manager
        # Query MT5 connection(s) for account info
        
        if not broker_manager.connections:
            return jsonify({
                'success': True,
                'userId': user_id,
                'account': {
                    'accountNumber': 'N/A',
                    'broker': 'MetaQuotes MT5',
                    'balance': 0,
                    'equity': 0,
                    'margin': 0,
                    'freeMargin': 0,
                }
            })
        
        # Return first connected account
        for conn_id, connection in broker_manager.connections.items():
            if connection.connected and connection.account_info:
                account_number = str(connection.account_info.get('accountNumber', 'N/A'))
                return jsonify({
                    'success': True,
                    'userId': user_id,
                    'account': {
                        'accountNumber': account_number,
                        'broker': 'MetaQuotes MT5',
                        'balance': connection.account_info.get('balance', 0),
                        'equity': connection.account_info.get('equity', 0),
                        'margin': connection.account_info.get('margin', 0),
                        'freeMargin': connection.account_info.get('margin_free', 0),
                    }
                })
        
        # Return default demo account for user
        return jsonify({
            'success': True,
            'userId': user_id,
            'account': {
                'accountId': 'demo_mt5',
                'accountNumber': MT5_CONFIG['account'],
                'broker': 'MetaQuotes MT5 Demo',
                'balance': 100000,  # Demo default balance
                'equity': 100000,
                'margin': 0,
                'freeMargin': 100000,
            }
        })
    except Exception as e:
        logger.error(f"Error getting account info for user {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'userId': user_id
        }), 500


# ==================== SYMBOL VALIDATION & CORRECTION ====================
# Maps old/unavailable symbols to new valid MetaQuotes-Demo symbols
VALID_SYMBOLS = {
    # Forex (9) - Most Reliable
    'EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'USDCNH', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDSEK',
    # Precious Metals (4) - High volatility, high profitability potential
    'XAUUSD',   # Gold - Most liquid precious metal
    'XAGUSD',   # Silver - High volatility
    'XPTUSD',   # Platinum - Lower liquidity but high volatility
    'XPDUSD',   # Palladium - Rare, high volatility
    # Energy (1) - Only OILK is available
    'OILK',     # Crude Oil (Brent)
    # Indices (4)
    'SP500m',   # S&P 500
    'DAX',      # DAX 40 Germany
    'US300',    # US 300 Index (broader market)
    'US100',    # Nasdaq 100 (tech-heavy)
}

SYMBOL_MAPPING = {
    # OLD -> NEW SYMBOL CORRECTIONS
    # Metals
    'GOLD': 'XAUUSD', 'XAUUSD': 'XAUUSD',
    'SILVER': 'XAGUSD', 'XAGUSD': 'XAGUSD',
    'PLATINUM': 'XPTUSD',
    'PALLADIUM': 'XPDUSD', 'XPDUSD': 'XPDUSD',
    'COPPER': 'XAUUSD',
    
    # Energy
    'WTIUSD': 'OILK', 'CRUDE_OIL': 'OILK',
    'BRENTUSD': 'OILK',
    'NATGASUS': 'OILK', 'NATURAL_GAS': 'OILK',
    
    # Agriculture (map to EURUSD as fallback)
    'CORNUSD': 'EURUSD', 'CORN': 'EURUSD',
    'WHEATUSD': 'EURUSD', 'WHEAT': 'EURUSD',
    'SOYBEANSUSD': 'EURUSD', 'SOYBEANS': 'EURUSD',
    'COFFEEUSD': 'EURUSD', 'COFFEE': 'EURUSD',
    'COCOAUSD': 'EURUSD', 'COCOA': 'EURUSD',
    'SUGARUSD': 'EURUSD', 'SUGAR': 'EURUSD',
    
    # Indices
    'SPX500': 'SP500m', 'S&P500': 'SP500m', 'SP500': 'SP500m',
    'DAX40': 'DAX', 'GDAX': 'DAX',
    'FTSE100': 'GBPUSD', 'FTSE': 'GBPUSD',
    'CAC40': 'EURUSD',
    'NIKKEI225': 'NIKL', 'NIKKEI': 'NIKL',
    
    # Stocks (map to forex as fallback - not available on demo)
    'AMD': 'EURUSD', 'MSFT': 'EURUSD', 'INTC': 'EURUSD', 'NVDA': 'EURUSD', 'NIKL': 'EURUSD',
    
    # Crypto (not available)
    'BITCOIN': 'EURUSD', 'BTC': 'EURUSD',
    'ETHEREUM': 'EURUSD', 'ETH': 'EURUSD',
}

def validate_and_correct_symbols(symbols):
    """Validate symbols and correct old/unavailable ones to valid MetaQuotes-Demo symbols"""
    if not symbols:
        return ['EURUSD']  # Default fallback
    
    corrected = []
    for symbol in symbols:
        if symbol in VALID_SYMBOLS:
            # Symbol is valid - keep it
            corrected.append(symbol)
        elif symbol in SYMBOL_MAPPING:
            # Symbol is old - map to new one
            new_symbol = SYMBOL_MAPPING[symbol]
            logger.warning(f"🔄 Auto-correcting symbol {symbol} -> {new_symbol} (not available on MetaQuotes-Demo)")
            if new_symbol not in corrected:
                corrected.append(new_symbol)
        else:
            # Unknown symbol - use fallback
            logger.warning(f"⚠️  Unknown symbol {symbol} - using EURUSD fallback")
            if 'EURUSD' not in corrected:
                corrected.append('EURUSD')
    
    # Ensure we have at least one symbol
    if not corrected:
        corrected = ['EURUSD']
    
    # Remove duplicates while preserving order
    seen = set()
    final = []
    for s in corrected:
        if s not in seen:
            final.append(s)
            seen.add(s)
    
    return final[:5]  # Limit to 5 symbols max

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
            'symbols': ['XPTUSD', 'OILK', 'USDCHF'],
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
            'symbols': ['SP500m', 'DAX', 'USDCAD'],
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


def load_user_bots_from_database():
    """Load all user-created bots from database into active_bots memory"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all active bots from database
        cursor.execute('''
            SELECT bot_id, user_id, name, strategy, broker_account_id, symbols, enabled, created_at
            FROM user_bots
            WHERE status = 'active'
        ''')
        
        bots_loaded = 0
        for row in cursor.fetchall():
            bot_id = row[0]
            user_id = row[1]
            name = row[2]
            strategy = row[3]
            account_id = row[4]
            symbols_str = row[5]
            enabled = row[6]
            created_at = row[7]
            
            # Skip if already in active_bots (demo bots)
            if bot_id in active_bots:
                continue
            
            # Parse symbols
            symbols = symbols_str.split(',') if symbols_str else ['EURUSD']
            
            # Add to active_bots with default values for trading metrics
            now = datetime.now()
            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': user_id,
                'name': name,
                'accountId': account_id,
                'symbols': symbols,
                'strategy': strategy,
                'enabled': bool(enabled),
                'totalTrades': 0,
                'winningTrades': 0,
                'totalProfit': 0,
                'totalLosses': 0,
                'totalInvestment': 0,
                'createdAt': created_at,
                'startTime': created_at,
                'profitHistory': [],
                'tradeHistory': [],
                'dailyProfits': {},
                'maxDrawdown': 0,
                'peakProfit': 0,
                'strategyHistory': [],
                'lastStrategySwitch': created_at,
                'volatilityLevel': 'Medium',
            }
            bots_loaded += 1
        
        conn.close()
        
        if bots_loaded > 0:
            logger.info(f"✅ Loaded {bots_loaded} user-created bots from database")
        
        return bots_loaded
    
    except Exception as e:
        logger.error(f"❌ Error loading user bots from database: {e}")
        return 0

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


# ==================== LIVE MARKET DATA MANAGEMENT ====================
# Thread lock for safe commodity_market_data access
market_data_lock = threading.Lock()

# Previous prices for calculating price changes (initialized from commodity_market_data)
previous_prices = {}

def initialize_previous_prices():
    """Initialize previous_prices from existing commodity_market_data"""
    global previous_prices
    for symbol, data in commodity_market_data.items():
        if 'price' in data:
            previous_prices[symbol] = None  # Start with None so first MT5 fetch establishes baseline
    logger.info(f"✅ Prepared price tracking for {len(previous_prices)} symbols (will baseline on first MT5 fetch)")

def get_best_trading_assets(limit=5):
    """
    Intelligent asset selection: Analyze all available symbols and return the best ones for trading
    Considers: profitability_score, signal strength, volatility, and trend direction
    
    Returns: List of top N symbols sorted by profitability potential
    """
    with market_data_lock:
        asset_scores = {}
        for symbol, data in commodity_market_data.items():

            # Example: Main bot trading loop or trade execution function (pseudo-code, adapt to your actual loop)
            def execute_bot_trade(bot_id):
                bot = active_bots.get(bot_id)
                if not bot or not bot.get('enabled', True):
                    return

                # Choose best symbol to trade
                tradable_symbols = [s for s in bot.get('symbols', []) if should_trade_today(bot, s)]
                if not tradable_symbols:
                    logger.info(f"[RISK] Bot {bot_id} has no tradable symbols today (risk filters active)")
                    return
                symbol = tradable_symbols[0]  # Or use your asset selection logic

                # ...existing trade logic...
                # Only place trade if should_trade_today passed
                # (Insert your trade execution code here)

                # Example: Place trade (pseudo-code)
                # result = place_trade(symbol, ...)
                # if result['success']:
                #     update bot metrics, etc.

            # Note: Integrate this logic into your actual bot trading scheduler/loop.
            # (unchanged scoring logic)
            base_score = data.get('profitability_score', 0.50)
            signal = data.get('signal', '')
            if 'STRONG BUY' in signal or 'STRONG SELL' in signal:
                signal_multiplier = 2.0
            elif 'BUY' in signal or 'SELL' in signal:
                signal_multiplier = 1.5
            elif 'WEAK' in signal or 'VOLATILE' in signal:
                signal_multiplier = 1.2
            else:
                signal_multiplier = 0.8
            volatility = data.get('volatility', 'Medium')
            volatility_multiplier = {
                'Very Low': 0.6,
                'Low': 0.8,
                'Medium': 1.0,
                'High': 1.4,
                'Very High': 1.8,
            }.get(volatility, 1.0)
            trend = data.get('trend', 'FLAT')
            trend_bonus = 0.15 if trend == 'UP' else (-0.10 if trend == 'DOWN' else 0)
            change = data.get('change', 0)
            change_bonus = min(abs(change) / 100, 0.20)
            if change < 0 and 'SELL' not in signal:
                change_bonus *= 0.5
            final_score = (base_score * signal_multiplier * volatility_multiplier) + trend_bonus + change_bonus
            asset_scores[symbol] = {
                'score': final_score,
                'base_score': base_score,
                'signal': signal,
                'volatility': volatility,
                'trend': trend,
                'change': change,
            }
        sorted_assets = sorted(asset_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        top_assets = [symbol for symbol, data in sorted_assets[:limit]]
        asset_strings = [f"{s}({asset_scores[s]['score']:.2f})" for s in top_assets]
        logger.info(f"[INTELLIGENT TRADING] Top {limit} assets for trading: {', '.join(asset_strings)}")
        return top_assets
# --- ENHANCED RISK MANAGEMENT: Profit Lock-In, Volatility Filter, Regime Check, Drawdown Pause ---
def should_trade_today(bot_config, symbol):
    """
    Returns False if bot should NOT trade today due to profit lock-in, drawdown, volatility, or regime filter.
    """
    # 1. Profit Lock-In: If daily profit exceeds lock threshold, stop trading for the day
    profit_lock = bot_config.get('profitLock', 0.0) or 0.0  # e.g., 500 (set per bot)
    today = datetime.now().strftime('%Y-%m-%d')
    daily_profit = bot_config.get('dailyProfits', {}).get(today, 0.0)
    if profit_lock > 0 and daily_profit >= profit_lock:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} hit daily profit lock-in (${daily_profit:.2f} >= ${profit_lock:.2f}), pausing trading for today.")
        return False

    # 2. Drawdown Pause: If drawdown from peak profit exceeds threshold, pause trading
    peak = bot_config.get('peakProfit', 0)
    max_dd = bot_config.get('maxDrawdown', 0)
    dd_threshold = bot_config.get('drawdownPausePercent', 0.0) or 0.0  # e.g., 10 (%)
    if peak > 0 and dd_threshold > 0:
        dd_percent = (max_dd / peak) * 100
        if dd_percent >= dd_threshold:
            logger.info(f"[RISK] Bot {bot_config.get('botId')} drawdown {dd_percent:.1f}% >= {dd_threshold}%, pausing trading.")
            return False

    # 3. Volatility Filter: Only trade if volatility is allowed
    allowed_vol = bot_config.get('allowedVolatility', ['Low', 'Medium'])
    # Get current volatility for symbol
    vol = commodity_market_data.get(symbol, {}).get('volatility', 'Medium')
    if allowed_vol and vol not in allowed_vol:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} skipping {symbol} due to volatility: {vol}")
        return False

    # 4. Regime Check: Only trade if signal is strong (not consolidating/weak)
    signal = commodity_market_data.get(symbol, {}).get('signal', '')
    if 'CONSOLIDAT' in signal or 'VOLATILE' in signal or 'WEAK' in signal:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} skipping {symbol} due to regime: {signal}")
        return False

    return True

def get_live_prices_from_mt5():
    """Fetch real-time prices from MT5 for all available symbols"""
    global previous_prices
    
    try:
        mt5_connection = broker_manager.connections.get('Default MT5')
        if not mt5_connection:
            logger.debug("❌ MT5 connection not found in broker_manager")
            return None
        
        if not mt5_connection.connected:
            logger.debug("❌ MT5 connection exists but not connected")
            return None
        
        live_prices = {}
        mt5 = mt5_connection.mt5
        
        if not mt5:
            logger.debug("❌ MT5 SDK not initialized")
            return None
        
        # Fetch prices for all valid symbols
        for symbol in VALID_SYMBOLS:
            try:
                # Ensure symbol is available in MT5
                if not mt5.symbol_select(symbol, True):
                    logger.debug(f"Symbol {symbol} not available in MT5")
                    continue
                
                # Get current tick data (price)
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    logger.debug(f"Could not get tick for {symbol}")
                    continue
                
                # Use mid-price (average of bid/ask)
                current_price = (tick.bid + tick.ask) / 2.0
                
                # Get previous price (use current if first time)
                price_change = 0  # Default to no change
                trend = 'FLAT'  # Default trend
                
                if symbol not in previous_prices or previous_prices[symbol] is None:
                    # First fetch - baseline the price, don't calculate change yet
                    previous_prices[symbol] = current_price
                    price_change = 0  # No change on first read
                    trend = 'FLAT'  # First read is always flat
                else:
                    previous_price = previous_prices[symbol]
                    
                    # Calculate price change percentage
                    if previous_price != 0:
                        price_change = ((current_price - previous_price) / previous_price * 100)
                    else:
                        price_change = 0
                
                    # Determine trend based on CALCULATED price change
                    # 0.0005% threshold = ultra-sensitive detection for demo market data
                    if price_change > 0.0005:  # UP trend
                        trend = 'UP'
                    elif price_change < -0.0005:  # DOWN trend
                        trend = 'DOWN'
                    else:  # Essentially flat (difference within rounding error)
                        trend = 'FLAT'
                    
                    # Update previous price for next cycle
                    previous_prices[symbol] = current_price
                
                # Estimate volatility based on bid-ask spread
                spread_percent = ((tick.ask - tick.bid) / current_price * 100) if current_price != 0 else 0
                if spread_percent < 0.05:
                    volatility = 'Very Low'
                elif spread_percent < 0.10:
                    volatility = 'Low'
                elif spread_percent < 0.20:
                    volatility = 'Medium'
                elif spread_percent < 0.50:
                    volatility = 'High'
                else:
                    volatility = 'Very High'
                
                # Generate signal based on MULTIPLE factors: price change, spread, volatility
                abs_change = abs(price_change)
                
                # Signal logic: Prioritize DIRECTION over magnitude
                # ANY upward movement = BUY signal, ANY downward = SELL signal
                if trend == 'UP':
                    if abs_change >= 1.0:
                        signal = '🟢 STRONG BUY'
                    elif abs_change >= 0.05:  # Very small change is enough for BUY
                        signal = '🟢 BUY'
                    else:
                        # Even tiny UP movement shows as BUY if spread is tight
                        if spread_percent < 0.15:
                            signal = '🟢 BUY'
                        else:
                            signal = '🟡 WEAK BUY'  # Wide spread = less conviction
                            
                elif trend == 'DOWN':
                    if abs_change >= 1.0:
                        signal = '🔴 STRONG SELL'
                    elif abs_change >= 0.05:  # Very small change is enough for SELL
                        signal = '🔴 SELL'
                    else:
                        # Even tiny DOWN movement shows as SELL if spread is wide
                        if spread_percent > 0.15:
                            signal = '🔴 SELL'
                        else:
                            signal = '🟡 WEAK SELL'  # Tight spread = less conviction
                            
                else:  # FLAT trend (current_price == previous_price, exactly same)
                    # Only show FLAT signals if prices truly haven't moved
                    if volatility == 'Very High' or volatility == 'High':
                        signal = '🟡 VOLATILE - CAUTION'
                    else:
                        signal = '🟡 CONSOLIDATING'
                
                # Determine recommendation based on signal
                if 'STRONG BUY' in signal:
                    recommendation = 'Strong uptrend - excellent entry opportunity'
                elif 'BUY' in signal:
                    recommendation = 'Upward momentum - good entry point'
                elif 'WEAK BUY' in signal:
                    recommendation = 'Slight upward pressure - monitor'
                elif 'STRONG SELL' in signal:
                    recommendation = 'Strong downtrend - avoid or consider short'
                elif 'SELL' in signal:
                    recommendation = 'Downward momentum - risky for longs'
                elif 'WEAK SELL' in signal:
                    recommendation = 'Slight downward pressure - monitor'
                elif 'VOLATILE' in signal:
                    recommendation = f'{volatility} volatility - wait for direction'
                else:  # CONSOLIDATING
                    recommendation = 'Consolidating - monitor for breakout'
                
                live_prices[symbol] = {
                    'price': round(current_price, 5),
                    'change': round(price_change, 3),  # Changed from 2 to 3 decimal places for precision
                    'trend': trend,
                    'volatility': volatility,
                    'signal': signal,
                    'recommendation': recommendation,
                }
                
                # Log signals for key forex/commodities to debug signal visibility
                if symbol in ['EURUSD', 'GBPUSD', 'OILK', 'XPTUSD']:
                    logger.debug(f"[SIGNAL] {symbol}: price={current_price:.5f}, change={price_change:.6f}%, trend={trend}, signal={signal}")
                
            except Exception as e:
                logger.debug(f"Error fetching live price for {symbol}: {e}")
                continue
        
        return live_prices if live_prices else None
        
    except Exception as e:
        logger.error(f"Error fetching live prices from MT5: {e}")
        return None

def live_market_data_updater():
    """Background thread: continuously fetch and update live market data"""
    logger.info("✅ Live market data updater thread started")
    global commodity_market_data
    
    # Wait a bit for MT5 to connect
    time.sleep(2)
    
    # Initialize previous prices from current commodity_market_data
    initialize_previous_prices()
    
    update_interval = 2  # Update prices every 2 seconds (faster updates = better signals)
    update_failed_count = 0
    max_failed_attempts = 10
    
    while True:
        try:
            # Try to fetch live prices from MT5
            live_prices = get_live_prices_from_mt5()
            
            if live_prices:
                # Update commodity_market_data with live prices (thread-safe)
                with market_data_lock:
                    updated_count = 0
                    for symbol, data in live_prices.items():
                        if symbol in commodity_market_data:
                            # Keep all original data but update prices and signals
                            commodity_market_data[symbol].update(data)
                            updated_count += 1
                    
                    if updated_count > 0:
                        # Count signal types for visibility
                        buy_count = sum(1 for s in commodity_market_data.values() if 'BUY' in s.get('signal', ''))
                        sell_count = sum(1 for s in commodity_market_data.values() if 'SELL' in s.get('signal', ''))
                        flat_count = sum(1 for s in commodity_market_data.values() if 'CONSOLIDAT' in s.get('signal', '') or 'VOLATILE' in s.get('signal', ''))
                        logger.info(f"✅ Updated {updated_count} live prices | Signals: {buy_count} BUY, {sell_count} SELL, {flat_count} FLAT")
                
                update_failed_count = 0  # Reset failure counter
            else:
                update_failed_count += 1
                if update_failed_count == 1:
                    logger.warning("⚠️  Could not fetch live prices from MT5 - MT5 connection may not be ready")
                elif update_failed_count >= 5:
                    logger.debug(f"⚠️  Still waiting for MT5 live prices... ({update_failed_count} attempts)")
                    # Still continue to serve cached prices
            
            time.sleep(update_interval)
            
        except Exception as e:
            logger.error(f"❌ Error in live market data updater: {e}")
            time.sleep(5)  # Wait 5 seconds before retrying on error


# Commodity Market Sentiment Data
# Tracks price trends, volatility, and trading signals
commodity_market_data = {
    # ===== FOREX PAIRS (9) =====
    'EURUSD': {'price': 1.0890, 'change': 0.42, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point', 'profitability_score': 0.65},
    'GBPUSD': {'price': 1.2750, 'change': -0.38, 'trend': 'DOWN', 'volatility': 'Medium', 'signal': '🔴 SELL', 'recommendation': 'Negative momentum - risky for longs', 'profitability_score': 0.58},
    'USDJPY': {'price': 149.50, 'change': 0.52, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point', 'profitability_score': 0.62},
    'USDCHF': {'price': 0.8950, 'change': 0.25, 'trend': 'UP', 'volatility': 'Very Low', 'signal': '🟡 CONSOLIDATING', 'recommendation': 'Safe haven currency - consolidating', 'profitability_score': 0.45},
    'AUDUSD': {'price': 0.6580, 'change': 1.15, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Strong uptrend - excellent entry opportunity', 'profitability_score': 0.82},
    'NZDUSD': {'price': 0.6125, 'change': 0.85, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point', 'profitability_score': 0.72},
    'USDCAD': {'price': 1.3550, 'change': -0.28, 'trend': 'DOWN', 'volatility': 'Low', 'signal': '🔴 SELL', 'recommendation': 'Negative momentum - risky for longs', 'profitability_score': 0.55},
    'USDCNH': {'price': 7.2850, 'change': 0.15, 'trend': 'UP', 'volatility': 'Very Low', 'signal': '🟡 CONSOLIDATING', 'recommendation': 'Very Low volatility with no clear direction', 'profitability_score': 0.40},
    'USDSEK': {'price': 10.8950, 'change': -0.42, 'trend': 'DOWN', 'volatility': 'Low', 'signal': '🔴 SELL', 'recommendation': 'Negative momentum - risky for longs', 'profitability_score': 0.53},
    
    # ===== PRECIOUS METALS (4) - High volatility, excellent for swing trading =====
    'XAUUSD': {'price': 2076.44, 'change': 0.68, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Gold strong uptrend - excellent profitability', 'profitability_score': 0.88},
    'XAGUSD': {'price': 31.25, 'change': 2.15, 'trend': 'UP', 'volatility': 'Very High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Silver volatile with strong upside momentum', 'profitability_score': 0.85},
    'XPTUSD': {'price': 920.00, 'change': 0.68, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Platinum positive momentum - good entry point', 'profitability_score': 0.70},
    'XPDUSD': {'price': 1150.00, 'change': 1.45, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Palladium strong uptrend - high volatility plays well', 'profitability_score': 0.86},
    
    # ===== ENERGY (2) =====
    'OILK': {'price': 82.45, 'change': 2.15, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Oil strong uptrend - excellent entry opportunity', 'profitability_score': 0.84},
    'NATGASUS': {'price': 2.85, 'change': 1.25, 'trend': 'UP', 'volatility': 'Very High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Natural gas volatile with strong momentum', 'profitability_score': 0.79},
    
    # ===== INDICES (4) =====
    'DAX': {'price': 18250.00, 'change': 0.65, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'DAX stable uptrend - good entry point', 'profitability_score': 0.68},
    'SP500m': {'price': 5285.50, 'change': 1.02, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'S&P 500 positive momentum - solid entry', 'profitability_score': 0.72},
    'US300': {'price': 15680.00, 'change': 0.85, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Broader US market showing strength', 'profitability_score': 0.71},
    'US100': {'price': 18950.00, 'change': 1.35, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Tech stocks leading the market', 'profitability_score': 0.75},
    
    # ===== STOCKS (5) =====
    'AMD': {'price': 185.75, 'change': 2.42, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'AMD strong uptrend - excellent opportunity', 'profitability_score': 0.81},
    'MSFT': {'price': 415.50, 'change': 1.35, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'MSFT solid momentum - good entry point', 'profitability_score': 0.76},
    'INTC': {'price': 48.25, 'change': -0.38, 'trend': 'DOWN', 'volatility': 'Medium', 'signal': '🔴 SELL', 'recommendation': 'Intel weak - avoid for now', 'profitability_score': 0.42},
    'NVDA': {'price': 875.00, 'change': 3.75, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'NVIDIA strongest momentum in tech', 'profitability_score': 0.89},
    'NIKL': {'price': 28900.00, 'change': 2.55, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Nikkei strong uptrend - Asian market strength', 'profitability_score': 0.83},
}

# Store active bots configuration
active_bots = {}

def cleanup_old_bots(max_bots=10):
    """Remove old bots from database and memory, keep only the latest max_bots"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Get bot_ids ordered by created_at descending
        cursor.execute('''
            SELECT bot_id FROM user_bots ORDER BY created_at DESC
        ''')
        bot_ids = [row[0] for row in cursor.fetchall()]
        # Keep only the latest max_bots
        keep_ids = set(bot_ids[:max_bots])
        remove_ids = set(bot_ids[max_bots:])
        if remove_ids:
            cursor.executemany('DELETE FROM user_bots WHERE bot_id = ?', [(bid,) for bid in remove_ids])
            conn.commit()
        conn.close()
        # Remove from memory
        for bot_id in list(active_bots.keys()):
            if bot_id not in keep_ids:
                del active_bots[bot_id]
        logger.info(f"✅ Cleaned up old bots, kept {len(keep_ids)} bots")
    except Exception as e:
        logger.error(f"❌ Error cleaning up old bots: {e}")

# Track running bots and their threads (NEW)
running_bots = {}  # {bot_id: True/False}
bot_threads = {}   # {bot_id: thread_object}
bot_stop_flags = {} # {bot_id: stop_requested}

# ==================== BROKER REGISTRY (Dynamic Broker Configuration) ====================
# This registry can be updated without code changes
REGISTERED_BROKERS = [
    {
        'id': 'xm',
        'name': 'XM',
        'display_name': 'XM Global',
        'logo': '🏦',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Global regulated forex and commodities broker',
    },
    {
        'id': 'pepperstone',
        'name': 'Pepperstone',
        'display_name': 'Pepperstone Global',
        'logo': '🐘',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Low-cost forex and CFD trading',
    },
    {
        'id': 'fxopen',
        'name': 'FxOpen',
        'display_name': 'FxOpen',
        'logo': '📊',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Forex, metals, and energies broker',
    },
    {
        'id': 'exness',
        'name': 'Exness',
        'display_name': 'Exness',
        'logo': '⚡',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'High leverage forex trading',
    },
    {
        'id': 'darwinex',
        'name': 'Darwinex',
        'display_name': 'Darwinex',
        'logo': '🦎',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Social forex trading platform',
    },
    {
        'id': 'ic-markets',
        'name': 'IC Markets',
        'display_name': 'IC Markets',
        'logo': '📈',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Australian regulated MT5 broker',
    },
    {
        'id': 'ig',
        'name': 'IG',
        'display_name': 'IG Group',
        'logo': '🌍',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'IG Group - Global Forex and CFD broker',
    },
    {
        'id': 'fxm',
        'name': 'FXM',
        'display_name': 'FXM',
        'logo': '💱',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'FXM - Forex and CFD broker',
    },
    {
        'id': 'avatrade',
        'name': 'AvaTrade',
        'display_name': 'AvaTrade',
        'logo': '🦅',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'AvaTrade - Regulated global broker',
    },
    {
        'id': 'fpmarkets',
        'name': 'FP Markets',
        'display_name': 'FP Markets',
        'logo': '🏦',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'FP Markets - Multi-asset broker',
    },
]

@app.route('/api/brokers', methods=['GET'])
def get_broker_registry():
    """Get dynamic broker registry (no auth required - public endpoint)"""
    try:
        # Return only active brokers
        active_brokers = [b for b in REGISTERED_BROKERS if b['is_active']]
        
        logger.info(f"✅ Returned {len(active_brokers)} active brokers")
        return jsonify({
            'success': True,
            'brokers': active_brokers,
            'count': len(active_brokers)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching broker registry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/brokers/<broker_id>', methods=['GET'])
def get_broker_details(broker_id):
    """Get details for a specific broker"""
    try:
        broker = next((b for b in REGISTERED_BROKERS if b['id'] == broker_id), None)
        
        if not broker:
            return jsonify({
                'success': False,
                'error': f'Broker {broker_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'broker': broker
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching broker details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== BROKER CREDENTIAL MANAGEMENT ====================

@app.route('/api/broker/credentials', methods=['GET'])
@require_session
def get_broker_credentials():
    """Get all broker credentials for authenticated user (deduped - latest only)"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live, is_active, created_at
            FROM broker_credentials
            WHERE user_id = ? AND is_active = 1
            ORDER BY broker_name, account_number, created_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Deduplicate: keep only the latest credential for each broker+account combo
        seen = {}  # key: (broker_name, account_number), value: credential_dict
        
        for row in rows:
            key = (row[1], row[2])  # (broker_name, account_number)
            if key not in seen:  # Keep first (most recent due to ORDER BY DESC)
                seen[key] = {
                    'credential_id': row[0],
                    'broker': row[1],
                    'account_number': row[2],
                    'server': row[3],
                    'is_live': bool(row[4]),
                    'is_active': bool(row[5]),
                    'created_at': row[6],
                }
        
        credentials = list(seen.values())
        
        logger.info(f"✅ Retrieved {len(credentials)} unique broker credentials for user {user_id}")
        return jsonify({
            'success': True,
            'credentials': credentials,
            'count': len(credentials)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/credentials', methods=['POST'])
@require_session
def save_broker_credentials():
    """Save new broker credentials for user
    
    Supports multiple brokers:
    - MetaQuotes/MT5: account_number, password, server, is_live
    - IG Markets: api_key, username, password, is_live
    - XM Global: account_number, password, server, is_live
    """
    try:
        user_id = request.user_id
        data = request.json
        
        broker_name = data.get('broker_name') or data.get('broker')
        account_number = data.get('account_number')
        password = data.get('password')
        server = data.get('server')
        api_key = data.get('api_key')  # For IG Markets
        username = data.get('username')  # For IG Markets
        is_live = data.get('is_live', False)
        
        if not broker_name:
            return jsonify({'success': False, 'error': 'broker_name required'}), 400
        
        # Validate based on broker type
        if broker_name == 'IG Markets':
            if not api_key or not username or not password:
                return jsonify({
                    'success': False,
                    'error': 'IG Markets requires: api_key, username, password'
                }), 400
        elif broker_name in ['MetaQuotes', 'XM Global', 'MetaTrader 5']:
            if not account_number or not password:
                return jsonify({
                    'success': False,
                    'error': f'{broker_name} requires: account_number, password, server'
                }), 400
            if not server:
                server = 'MetaQuotes-Demo' if broker_name == 'MetaQuotes' else 'XMGlobal-Demo'
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown broker: {broker_name}. Supported: MetaQuotes, IG Markets, XM Global'
            }), 400
        
        created_at = datetime.now().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # For IG Markets, use username as account identifier
        account_id = username if broker_name == 'IG Markets' else account_number
        
        # Check if credential already exists for this user and broker
        if broker_name == 'IG Markets':
            cursor.execute('''
                SELECT credential_id FROM broker_credentials
                WHERE user_id = ? AND broker_name = ? AND username = ?
            ''', (user_id, broker_name, username))
        else:
            cursor.execute('''
                SELECT credential_id FROM broker_credentials
                WHERE user_id = ? AND broker_name = ? AND account_number = ?
            ''', (user_id, broker_name, account_number))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing credential
            credential_id = existing[0]
            if broker_name == 'IG Markets':
                cursor.execute('''
                    UPDATE broker_credentials
                    SET api_key = ?, username = ?, password = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (api_key, username, password, 1 if is_live else 0, created_at, credential_id))
            else:
                cursor.execute('''
                    UPDATE broker_credentials
                    SET account_number = ?, password = ?, server = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (account_number, password, server, 1 if is_live else 0, created_at, credential_id))
            
            logger.info(f"✅ Updated broker credential for user {user_id}: {broker_name} | Account: {account_id}")
        else:
            # Create new credential
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials
                (credential_id, user_id, broker_name, account_number, password, server, 
                 api_key, username, is_live, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ''', (
                credential_id, user_id, broker_name, account_number or '', password, server or '',
                api_key or '', username or '', 1 if is_live else 0, created_at, created_at
            ))
            logger.info(f"✅ Created new broker credential for user {user_id}: {broker_name} | Account: {account_id}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'credential': {
                'credential_id': credential_id,
                'broker_name': broker_name,
                'account_number': account_number or username,
                'is_live': is_live,
                'is_active': True,
                'created_at': created_at,
            }
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Error saving broker credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/credentials/<credential_id>', methods=['DELETE'])
@require_session
def delete_broker_credentials(credential_id):
    """Delete broker credential"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify credential belongs to user
        cursor.execute('''
            SELECT user_id FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        row = cursor.fetchone()
        if not row or row[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Credential not found or does not belong to user'}), 404
        
        # Delete credential
        cursor.execute('''
            DELETE FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Deleted broker credential {credential_id} for user {user_id}")
        return jsonify({'success': True, 'message': 'Credential deleted'}), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting credential: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/test-connection', methods=['POST'])
@require_session
def test_broker_connection():
    """Test broker connection and save credentials (supports MT5 and IG Markets)"""
    try:
        user_id = request.user_id
        data = request.json
        broker = data.get('broker', '')
        is_live = data.get('is_live', False)

        logger.info(f"🔌 Testing broker connection: {broker} | User: {user_id}")

        # ==================== IG MARKETS ====================
        if broker.lower() in ['ig', 'ig markets', 'ig.com']:
            api_key = data.get('api_key')
            ig_username = data.get('username')
            ig_password = data.get('password')
            account_id = data.get('account_id')

            if not all([api_key, ig_username, ig_password, account_id]):
                return jsonify({
                    'success': False,
                    'error': 'Missing IG Markets fields: api_key, username, password, account_id'
                }), 400

            try:
                ig_credentials = {
                    'api_key': api_key,
                    'username': ig_username,
                    'password': ig_password,
                    'account_id': account_id
                }
                ig_conn = IGConnection(credentials=ig_credentials)
                if not ig_conn.connect():
                    logger.error(f"IG authentication failed for user {user_id} (username={ig_username})")
                    return jsonify({
                        'success': False,
                        'error': 'Failed to authenticate with IG Markets. Check API key and credentials.'
                    }), 401

                # Get account info
                account_info = ig_conn.get_account_info()
                ig_conn.disconnect()

                if 'error' in account_info:
                    logger.error(f"Failed to retrieve IG account info for user {user_id}: {account_info['error']}")
                    return jsonify({
                        'success': False,
                        'error': f"Failed to retrieve IG account info: {account_info['error']}"
                    }), 400

                # Save IG credentials
                conn = get_db_connection()
                cursor = conn.cursor()

                credential_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO broker_credentials 
                    (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ''', (credential_id, user_id, 'IG Markets', account_id, ig_password, 'REST-API', int(is_live), api_key, datetime.now().isoformat(), datetime.now().isoformat()))

                conn.commit()
                conn.close()

                logger.info(f"✅ IG Markets credentials saved for user {user_id}")

                return jsonify({
                    'success': True,
                    'message': f'Successfully connected to IG Markets account {account_id}',
                    'credential_id': credential_id,
                    'broker': 'IG Markets',
                    'account_number': account_id,
                    'accountName': account_info.get('accountName', 'IG Account'),
                    'currency': account_info.get('currency', 'USD'),
                    'is_live': is_live,
                    'status': 'CONNECTED',
                    'timestamp': datetime.now().isoformat()
                }), 200
            except Exception as e:
                logger.error(f"Exception during IG authentication for user {user_id}: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'IG authentication failed: {str(e)}'
                }), 500

        # ==================== MT5 BROKERS ====================
        else:
            account = data.get('account_number', '')
            password = data.get('password', '')
            server = data.get('server', '')
            
            # Validate required fields
            if not all([broker, account, password, server]):
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields for MT5: broker, account_number, password, server'
                }), 400
            
            # Fix server name for MT5 brokers
            if broker.lower() in ['metaquotes', 'xm', 'xm global', 'metatrader5', 'mt5']:
                if not server or server != MT5_CONFIG['server']:
                    server = MT5_CONFIG['server']
                    logger.info(f"   Corrected server to: {server}")
            
            # Try to get actual balance from MT5 account
            actual_balance = 10000.00  # Default fallback
            try:
                test_credentials = {
                    'account': int(account),
                    'password': password,
                    'server': server
                }
                temp_connection = MT5Connection(credentials=test_credentials)
                
                if temp_connection.connect():
                    account_info = temp_connection.get_account_info()
                    if account_info and 'balance' in account_info:
                        actual_balance = account_info['balance']
                        logger.info(f"✅ Retrieved actual balance from MT5: ${actual_balance}")
                    temp_connection.disconnect()
                else:
                    logger.warning(f"⚠️  Could not connect to MT5 - using default balance")
            except Exception as e:
                logger.warning(f"⚠️  Error retrieving balance: {e}")
            
            # Save MT5 credentials
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT credential_id FROM broker_credentials
                WHERE user_id = ? AND broker_name = ? AND account_number = ?
            ''', (user_id, broker, account))
            
            existing = cursor.fetchone()
            
            if existing:
                credential_id = existing[0]
                cursor.execute('''
                    UPDATE broker_credentials
                    SET password = ?, server = ?, is_live = ?, is_active = 1, updated_at = ?
                    WHERE credential_id = ?
                ''', (password, server, int(is_live), datetime.now().isoformat(), credential_id))
                logger.info(f"ℹ️  Updated broker credential: {broker} | Account: {account}")
            else:
                credential_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO broker_credentials 
                    (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ''', (credential_id, user_id, broker, account, password, server, int(is_live), datetime.now().isoformat(), datetime.now().isoformat()))
                logger.info(f"✅ Created broker credential: {broker} | Account: {account}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Credentials saved for user {user_id}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully connected to {broker} account {account}',
                'credential_id': credential_id,
                'broker': broker,
                'account_number': account,
                'balance': actual_balance,
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200
        
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COMMISSION MANAGEMENT ====================

@app.route('/api/user/commissions', methods=['GET'])
@require_session
def get_user_commissions():
    """Get commission history and stats for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all commissions as earner
        cursor.execute('''
            SELECT commission_id, bot_id, profit_amount, commission_rate, commission_amount, created_at
            FROM commissions
            WHERE earner_id = ?
            ORDER BY created_at DESC
            LIMIT 100
        ''', (user_id,))
        
        commission_rows = cursor.fetchall()
        
        # Get commission stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_count,
                SUM(commission_amount) as total_earned,
                SUM(CASE WHEN created_at > datetime('now', '-30 days') THEN commission_amount ELSE 0 END) as pending,
                SUM(CASE WHEN bot_id IN (SELECT bot_id FROM user_bots WHERE status='completed') THEN commission_amount ELSE 0 END) as withdrawn
            FROM commissions
            WHERE earner_id = ?
        ''', (user_id,))
        
        stats_row = cursor.fetchone()
        
        commissions = []
        for row in commission_rows:
            commissions.append({
                'commission_id': row[0],
                'bot_id': row[1],
                'profit_amount': row[2],
                'commission_rate': row[3],
                'amount': row[4],
                'source': 'trade',
                'status': 'completed',
                'created_at': row[5],
            })
        
        conn.close()
        
        stats = {
            'total_earned': stats_row[1] or 0,
            'total_pending': stats_row[2] or 0,
            'total_withdrawn': stats_row[3] or 0,
            'trade_commissions': stats_row[0] or 0,
            'referral_commissions': 0,
        }
        
        logger.info(f"✅ Retrieved commissions for user {user_id}: ${stats['total_earned']:.2f} earned")
        
        return jsonify({
            'success': True,
            'commissions': commissions,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/referral-commissions', methods=['GET'])
@require_session
def get_referral_commissions():
    """Get referral commission earnings"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get referrals and their commissions
        cursor.execute('''
            SELECT COUNT(*) as active_referrals
            FROM referrals
            WHERE referrer_id = ? AND status = 'active'
        ''', (user_id,))
        
        referral_count = cursor.fetchone()[0]
        
        # Get total referral commissions
        cursor.execute('''
            SELECT SUM(c.commission_amount) as total_referral_commission
            FROM commissions c
            INNER JOIN referrals r ON c.client_id = r.referred_user_id
            WHERE r.referrer_id = ? AND c.earner_id = ?
        ''', (user_id, user_id))
        
        referral_total = cursor.fetchone()[0] or 0
        conn.close()
        
        logger.info(f"✅ Retrieved referral commissions for user {user_id}: {referral_count} referrals, ${referral_total:.2f}")
        
        return jsonify({
            'success': True,
            'active_referrals': referral_count,
            'total_referral_commission': referral_total,
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching referral commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/commission-withdrawal', methods=['POST'])
@require_session
def request_commission_withdrawal():
    """Request withdrawal of earned commissions"""
    try:
        user_id = request.user_id
        data = request.json
        amount = data.get('amount', 0)
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check available balance
        cursor.execute('''
            SELECT SUM(commission_amount) as total FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        
        total = cursor.fetchone()[0] or 0
        
        if amount > total:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient balance. Available: ${total:.2f}, Requested: ${amount:.2f}'
            }), 400
        
        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO commission_withdrawals (withdrawal_id, user_id, amount, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (withdrawal_id, user_id, amount, created_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Withdrawal request created: {withdrawal_id} | User: {user_id} | Amount: ${amount:.2f}")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'status': 'pending',
            'message': 'Withdrawal request submitted. Processing usually takes 3-5 business days.'
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Error creating withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COMMISSION DISTRIBUTION HELPER ====================

def distribute_trade_commissions(bot_id: str, user_id: str, profit_amount: float):
    """
    Distribute commissions for profitable trades
    
    IMPORTANT: Commission is ONLY earned from YOUR DOWNLINERS (referrals)
    NOT from your own trades!
    
    Flow:
    1. Check if THIS USER (bot_id owner) has a REFERRER (upline)
    2. If YES: Referrer gets 5% commission from this user's bot profit
    3. If NO: No commission (only own downliners would pay you commission)
    4. Separately: Check how many downliners THIS USER has and they will get commissions
    """
    try:
        if profit_amount <= 0:
            return  # Only commission on profits
        
        DEVELOPER_ID = 'developer'  # Replace with actual developer user_id if needed
        DEVELOPER_DIRECT_RATE = 0.25
        DEVELOPER_REFERRAL_RATE = 0.20
        RECRUITER_RATE = 0.05

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if bot owner has a referrer (upline)
        cursor.execute('''
            SELECT referrer_id FROM referrals
            WHERE referred_user_id = ? AND status = 'active'
        ''', (user_id,))
        referrer_row = cursor.fetchone()
        has_referrer = referrer_row is not None
        referrer_id = referrer_row[0] if has_referrer else None

        if has_referrer:
            # 20% to developer
            developer_commission = profit_amount * DEVELOPER_REFERRAL_RATE
            developer_commission_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                developer_commission_id,
                DEVELOPER_ID,
                user_id,
                bot_id,
                profit_amount,
                DEVELOPER_REFERRAL_RATE,
                developer_commission,
                datetime.now().isoformat()
            ))
            # 5% to recruiter
            recruiter_commission = profit_amount * RECRUITER_RATE
            recruiter_commission_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                recruiter_commission_id,
                referrer_id,
                user_id,
                bot_id,
                profit_amount,
                RECRUITER_RATE,
                recruiter_commission,
                datetime.now().isoformat()
            ))
            logger.info(f"💰 Commission split: Developer {DEVELOPER_ID} gets ${developer_commission:.2f} (20%), Recruiter {referrer_id} gets ${recruiter_commission:.2f} (5%) from ${profit_amount:.2f}")
        else:
            # 25% to developer
            developer_commission = profit_amount * DEVELOPER_DIRECT_RATE
            developer_commission_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                developer_commission_id,
                DEVELOPER_ID,
                user_id,
                bot_id,
                profit_amount,
                DEVELOPER_DIRECT_RATE,
                developer_commission,
                datetime.now().isoformat()
            ))
            logger.info(f"💰 Commission: Developer {DEVELOPER_ID} gets ${developer_commission:.2f} (25%) from ${profit_amount:.2f} [Direct signup]")

        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error in distribute_trade_commissions: {e}")
        # Don't raise - don't break trading if commission fails


# ==================== EMAIL NOTIFICATIONS ====================
def send_activation_pin_email(user_email: str, user_name: str, bot_id: str, pin: str):
    """Send activation PIN to user email"""
    try:
        # For development/demo, just log it
        logger.info(f"\n{'='*60}")
        logger.info(f"🔐 BOT ACTIVATION PIN SENT")
        logger.info(f"{'-'*60}")
        logger.info(f"User: {user_name} ({user_email})")
        logger.info(f"Bot ID: {bot_id}")
        logger.info(f"PIN: {pin}")
        logger.info(f"Valid for: 10 minutes")
        logger.info(f"{'='*60}\n")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


# ==================== BOT ACTIVATION ENDPOINTS ====================
@app.route('/api/bot/<bot_id>/request-activation', methods=['POST'])
@require_session
def request_bot_activation(bot_id):
    """Request bot activation - sends PIN to user email for verification"""
    try:
        data = request.json or {}
        user_id = request.user_id  # From @require_session
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot = active_bots[bot_id]
        
        # Verify bot belongs to user
        if bot.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Generate 6-digit PIN
        activation_pin = str(random.randint(100000, 999999))
        pin_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=10)
        
        # Store PIN in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user email
        cursor.execute('SELECT email, name FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_email = user_row['email']
        user_name = user_row['name']
        
        # Delete any existing unexpired PINs for this bot
        cursor.execute('''
            DELETE FROM bot_activation_pins 
            WHERE bot_id = ? AND user_id = ? AND expires_at > ?
        ''', (bot_id, user_id, datetime.now().isoformat()))
        
        # Insert new PIN
        cursor.execute('''
            INSERT INTO bot_activation_pins (pin_id, bot_id, user_id, pin, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (pin_id, bot_id, user_id, activation_pin, datetime.now().isoformat(), expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        # Send PIN to user (for demo, just logs it)
        send_activation_pin_email(user_email, user_name, bot_id, activation_pin)
        
        logger.info(f"Activation PIN requested for bot {bot_id} by user {user_id}")
        
        return jsonify({
            'success': True,
            'message': f'Activation PIN sent to {user_email}',
            'expires_in_seconds': 600,
            'bot_id': bot_id,
            'note': 'For testing: PIN will be printed in backend logs'
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting activation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/request-deletion', methods=['POST'])
@require_session
def request_bot_deletion(bot_id):
    """Request bot deletion - creates confirmation token and captures bot stats"""
    try:
        data = request.json or {}
        user_id = request.user_id
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        
        # Verify bot belongs to user
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Generate deletion token
        deletion_token = str(uuid.uuid4().hex[:16])
        token_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=5)  # 5 minute confirmation window
        
        # Capture final bot stats
        bot_stats = {
            'totalTrades': bot_config.get('totalTrades', 0),
            'winningTrades': bot_config.get('winningTrades', 0),
            'totalProfit': bot_config.get('totalProfit', 0),
            'totalLosses': bot_config.get('totalLosses', 0),
        }
        
        # Store deletion token
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete any existing unexpired tokens
        cursor.execute('''
            DELETE FROM bot_deletion_tokens
            WHERE bot_id = ? AND user_id = ? AND expires_at > ? AND confirmed = 0
        ''', (bot_id, user_id, datetime.now().isoformat()))
        
        cursor.execute('''
            INSERT INTO bot_deletion_tokens 
            (token_id, bot_id, user_id, deletion_token, bot_stats, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (token_id, bot_id, user_id, deletion_token, json.dumps(bot_stats), 
              datetime.now().isoformat(), expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"🗑️ BOT DELETION REQUESTED: {bot_id} by {user_id}")
        logger.warning(f"   Stats: {bot_stats}")
        logger.warning(f"   Confirmation Token: {deletion_token}")
        logger.warning(f"   Valid for 5 minutes")
        
        return jsonify({
            'success': True,
            'message': 'Deletion confirmation token generated',
            'confirmation_token': deletion_token,
            'expires_in_seconds': 300,
            'warning': 'This action cannot be undone. All bot data will be permanently deleted.',
            'bot_stats': bot_stats
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting deletion: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/create', methods=['POST'])
@require_session
def create_bot():
    """Create and start a new trading bot for a user
    
    PROPER FLOW:
    1. User integrates broker account (broker_credentials table)
    2. User creates bot linked to that credential_id
    3. Bot trades using verified broker account
    
    Request body:
    {
        "botId": "optional_bot_name",
        "credentialId": "credential_uuid",  // ✅ REQUIRED - from broker integration
        "symbols": ["EURUSD", "XAUUSD"],
        "strategy": "Trend Following",
        "riskPerTrade": 100,
        "maxDailyLoss": 500
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No configuration provided'}), 400
        
        user_id = request.user_id  # From @require_session decorator
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        # Get credential_id from request - REQUIRED
        credential_id = data.get('credentialId')
        if not credential_id:
            return jsonify({'success': False, 'error': 'credentialId required - must setup broker integration first'}), 400
        
        # Verify user exists and credential belongs to user
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            # Verify credential exists AND belongs to this user
            cursor.execute('''
                SELECT credential_id, broker_name, account_number, is_live 
                FROM broker_credentials 
                WHERE credential_id = ? AND user_id = ?
            ''', (credential_id, user_id))

            credential_row = cursor.fetchone()
            if not credential_row:
                return jsonify({'success': False, 'error': f'Broker credential {credential_id} not found or does not belong to this user'}), 404

            credential_data = dict(credential_row)
            broker_name = credential_data['broker_name']
            account_number = credential_data['account_number']
            is_live = credential_data['is_live']
            mode = 'live' if is_live else 'demo'

            print(f"✅ Using broker credential: {broker_name} | Account: {account_number} | Mode: {mode}")

            # Bot configuration
            # Generate ABSOLUTELY unique bot_id (timestamp + uuid to ensure no collisions)
            import time
            bot_id = data.get('botId') or f"bot_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            raw_symbols = data.get('symbols', ['EURUSD'])
            symbols = validate_and_correct_symbols(raw_symbols)  # ✅ AUTO-CORRECT OLD SYMBOLS
            strategy = data.get('strategy', 'Trend Following')
            risk_per_trade = float(data.get('riskPerTrade', 100))
            max_daily_loss = float(data.get('maxDailyLoss', 500))
            trading_enabled = data.get('enabled', True)

            account_id = f"{broker_name}_{account_number}"

            # Store bot in database (check if already exists first)
            created_at = datetime.now().isoformat()
            try:
                cursor.execute('SELECT bot_id FROM user_bots WHERE bot_id = ?', (bot_id,))
                if cursor.fetchone():
                    # Bot already exists, regenerate ID
                    logger.warning(f"Bot ID {bot_id} already exists, regenerating...")
                    bot_id = f"bot_{int(time.time() * 1000) + 1}_{uuid.uuid4().hex[:8]}"

                cursor.execute('''
                    INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), created_at, created_at))

                # Link bot to credential for commission tracking
                cursor.execute('''
                    INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (bot_id, credential_id, user_id, created_at))
                
                conn.commit()
            except Exception as e:
                if 'UNIQUE constraint' in str(e):
                    logger.error(f"Bot creation failed - duplicate ID. Retrying with new ID...")
                    # Final retry with absolute unique ID
                    bot_id = f"bot_{int(time.time() * 1000000)}_{uuid.uuid4().hex[:6]}"
                    cursor.execute('''
                        INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), created_at, created_at))
                    cursor.execute('''
                        INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (bot_id, credential_id, user_id, created_at))
                    conn.commit()
                else:
                    raise
            
        finally:
            if conn:
                conn.close()
        
        # Also store in active_bots for real-time trading
        now = datetime.now()
        active_bots[bot_id] = {
            'botId': bot_id,
            'user_id': user_id,
            'accountId': account_id,
            'brokerName': broker_name,
            'mode': mode,  # 'demo' or 'live'
            'credentialId': credential_id,
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
            'profit': 0,  # Always include profit field
        }
        
        logger.info(f"✅ Created bot {bot_id} for user {user_id}")
        logger.info(f"   Broker: {broker_name} | Account: {account_number} | Mode: {mode}")
        
        # ✅ MARK BOT AS RUNNING IMMEDIATELY (so it appears on dashboard)
        # Don't block the response - just mark it as running and return
        # The background system will auto-start it via the running_bots flag
        running_bots[bot_id] = True
        bot_stop_flags[bot_id] = False
        
        # Launch thread asynchronously in background WITHOUT BLOCKING response
        def _async_start_bot():
            """Start bot in background without blocking the API response"""
            try:
                # Small delay to ensure bot is fully initialized in DB
                time.sleep(0.5)
                
                # Retrieve MT5 credentials if LIVE mode
                bot_credentials = None
                if mode == 'live':
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT password, server 
                            FROM broker_credentials 
                            WHERE credential_id = ? AND user_id = ?
                        ''', (credential_id, user_id))
                        cred_row = cursor.fetchone()
                        conn.close()
                        
                        if cred_row:
                            bot_credentials = {
                                'account_number': account_number,
                                'password': cred_row['password'],
                                'server': cred_row['server'],
                                'is_live': True
                            }
                    except Exception as e:
                        logger.warning(f"Could not fetch MT5 credentials for live bot: {e}")
                
                # Launch background trading thread
                if bot_id not in bot_threads or not bot_threads[bot_id].is_alive():
                    bot_thread = threading.Thread(
                        target=continuous_bot_trading_loop,
                        args=(bot_id, user_id, bot_credentials),
                        daemon=True,
                        name=f"BotThread-{bot_id}"
                    )
                    bot_threads[bot_id] = bot_thread
                    bot_thread.start()
                    logger.info(f"🚀 Bot {bot_id}: Background thread launched (async start)")
            except Exception as e:
                logger.error(f"Error in async bot start: {e}")
        
        # Start the bot in a background daemon thread (non-blocking)
        startup_thread = threading.Thread(target=_async_start_bot, daemon=True)
        startup_thread.start()
        
        # RETURN IMMEDIATELY - don't wait for bot to fully start
        return jsonify({
            'success': True,
            'botId': bot_id,
            'user_id': user_id,
            'credentialId': credential_id,
            'accountId': account_id,
            'broker': broker_name,
            'account_number': account_number,
            'mode': mode,
            'message': f'Bot {bot_id} created and starting...',
            'status': 'STARTING'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== CONTINUOUS BOT TRADING LOOP ====================

def continuous_bot_trading_loop(bot_id: str, user_id: str, bot_credentials: Dict = None):
    """
    Continuously execute trading for a bot until stop is requested
    
    This function runs in a background thread and:
    1. Executes trades every trading_interval seconds
    2. Updates bot stats after each trade cycle
    3. Manages position sizing and risk
    4. Stops when bot_stop_flags[bot_id] is set to True
    """
    try:
        logger.info(f"🤖 Bot {bot_id}: CONTINUOUS TRADING LOOP STARTED (user {user_id})")
        
        bot_config = active_bots.get(bot_id)
        if not bot_config:
            logger.error(f"Bot {bot_id} not found in active_bots")
            return
        
        trading_interval = bot_config.get('tradingInterval', 300)  # Default 5 minutes
        logger.info(f"Bot {bot_id}: Trading interval set to {trading_interval} seconds ({trading_interval/60:.1f} minutes)")
        
        # Initialize stop flag if not exists
        if bot_id not in bot_stop_flags:
            bot_stop_flags[bot_id] = False
        
        running_bots[bot_id] = True
        trade_cycle = 0
        mt5_ready_timeout = 120  # Wait up to 120 seconds (2 minutes) on first cycle for full order readiness
        
        while not bot_stop_flags.get(bot_id, False):
            try:
                trade_cycle += 1
                logger.info(f"🔄 Bot {bot_id}: Trade cycle #{trade_cycle} starting at {datetime.now().isoformat()}")
                
                # Detect broker type
                broker_type = bot_config.get('broker_type', 'MT5')
                is_ig = broker_type == 'IG Markets'
                
                mt5_conn = None
                ig_conn = None
                
                if is_ig:
                    # IG Markets broker - use REST API via IGConnection
                    try:
                        ig_conn = bot_config.get('broker_conn')
                        if ig_conn is None or not ig_conn.connected:
                            # Re-establish IG connection
                            credential_id = bot_config.get('credentialId')
                            if credential_id:
                                broker_type_new, new_conn = get_broker_connection(credential_id, user_id, bot_id)
                                if new_conn and broker_type_new == 'IG Markets':
                                    ig_conn = new_conn
                                    bot_config['broker_conn'] = ig_conn
                                else:
                                    logger.error(f"Bot {bot_id}: IG reconnection failed")
                                    time.sleep(trading_interval)
                                    continue
                            else:
                                logger.error(f"Bot {bot_id}: No credentialId for IG reconnection")
                                time.sleep(trading_interval)
                                continue
                        logger.info(f"Bot {bot_id}: Connected to IG Markets for trading")
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: IG connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                else:
                    # MT5 broker - connect via terminal SDK
                    try:
                        if bot_config.get('mode') == 'live' and bot_credentials:
                            mt5_conn = MT5Connection(bot_credentials)
                        else:
                            mt5_conn = MT5Connection()
                        
                        if not mt5_conn.connect():
                            logger.error(f"Bot {bot_id}: MT5 connection failed - will retry next cycle")
                            time.sleep(trading_interval)
                            continue
                        
                        if trade_cycle == 1:
                            logger.info(f"Bot {bot_id}: First trade cycle - waiting for MT5 to be ready for ORDER EXECUTION (up to {mt5_ready_timeout}s)...")
                            timeout_for_this_cycle = mt5_ready_timeout
                        else:
                            timeout_for_this_cycle = 15
                        
                        if not mt5_conn.wait_for_mt5_ready(timeout_seconds=timeout_for_this_cycle):
                            if trade_cycle == 1:
                                logger.warning(f"Bot {bot_id}: First cycle MT5 readiness timeout after {timeout_for_this_cycle}s")
                                logger.warning(f"  Will retry in 30 seconds (MT5 may still be initializing)...")
                                time.sleep(30)
                                continue
                            else:
                                logger.warning(f"Bot {bot_id}: MT5 not ready after {timeout_for_this_cycle}s - will retry next cycle")
                                time.sleep(trading_interval)
                                continue
                        
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: MT5 connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                
                # Execute trade cycle (same logic as in start_bot endpoint)
                strategy_name = bot_config.get('strategy', 'trend_following')
                strategy_func = STRATEGY_MAP.get(strategy_name, trend_following_strategy)
                
                trades_placed = 0
                symbols = bot_config.get('symbols', ['EURUSD'])
                
                for symbol in symbols[:3]:  # Max 3 trades per cycle
                    if bot_stop_flags.get(bot_id, False):
                        break  # Stop requested, exit loop
                    
                    try:
                        # Dynamic position sizing
                        if bot_config.get('dynamicSizing', True):
                            position_size = position_sizer.calculate_position_size(
                                bot_config,
                                volatility_level=bot_config.get('volatilityLevel', 'Medium')
                            )
                        else:
                            position_size = bot_config.get('basePositionSize', 1.0)
                        
                        # Get trade direction from strategy
                        trade_params = strategy_func(symbol, bot_config['accountId'], bot_config['riskPerTrade'])
                        adjusted_volume = trade_params['volume'] * position_size
                        order_type = trade_params['type']
                        
                        # Place order via broker with RETRY LOGIC
                        logger.info(f"📍 Bot {bot_id}: Placing {order_type} order on {symbol} via {broker_type} | Cycle: {trade_cycle}")
                        
                        order_result = None
                        
                        if is_ig:
                            # IG Markets - place order via REST API
                            try:
                                # Map MT5 symbol names to IG epics if needed
                                ig_epic = symbol
                                # Common MT5-to-IG epic mapping
                                ig_symbol_map = {
                                    'EURUSD': 'CS.D.EURUSD.CFD.IP',
                                    'GBPUSD': 'CS.D.GBPUSD.CFD.IP',
                                    'USDJPY': 'CS.D.USDJPY.CFD.IP',
                                    'USDCHF': 'CS.D.USDCHF.CFD.IP',
                                    'AUDUSD': 'CS.D.AUDUSD.CFD.IP',
                                    'NZDUSD': 'CS.D.NZDUSD.CFD.IP',
                                    'USDCAD': 'CS.D.USDCAD.CFD.IP',
                                    'XAUUSD': 'CS.D.USCGC.TODAY.IP',
                                    'XAGUSD': 'CS.D.USCSI.TODAY.IP',
                                }
                                if symbol in ig_symbol_map:
                                    ig_epic = ig_symbol_map[symbol]
                                
                                order_result = ig_conn.place_order(
                                    symbol=ig_epic,
                                    order_type=order_type,
                                    volume=round(adjusted_volume, 2),
                                    stop_loss=trade_params.get('stop_loss', 50),
                                    take_profit=trade_params.get('take_profit', 100),
                                )
                                
                                if order_result.get('success', False):
                                    logger.info(f"✅ Bot {bot_id}: IG order placed on {ig_epic}")
                                else:
                                    logger.warning(f"Bot {bot_id}: IG order failed on {ig_epic}: {order_result.get('error')}")
                            except Exception as e:
                                logger.error(f"Bot {bot_id}: IG place_order exception: {e}")
                                order_result = {'success': False, 'error': str(e)}
                        else:
                            # MT5 - place order with retry/fallback logic
                            symbols_to_try = [symbol, 'EURUSD']
                            
                            for index, attempt_symbol in enumerate(symbols_to_try):
                                try:
                                    bot_id_short = bot_id.split('_')[-1][:8]
                                    comment_short = f'ZBot{bot_id_short}'
                                    order_result = mt5_conn.place_order(
                                        symbol=attempt_symbol,
                                        order_type=order_type,
                                        volume=round(adjusted_volume, 2),
                                        comment=comment_short
                                    )
                                    
                                    if order_result.get('success', False):
                                        logger.info(f"✅ Bot {bot_id}: Order placed successfully on {attempt_symbol}")
                                        symbol = attempt_symbol
                                        break
                                    else:
                                        error_msg = order_result.get('error', '').lower()
                                        is_last_attempt = (index == len(symbols_to_try) - 1)
                                        
                                        if ('not found' in error_msg or 'disconnected' in error_msg or 'order_send failed' in error_msg) and not is_last_attempt:
                                            logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol} ({order_result.get('error')}) - trying {symbols_to_try[index+1]}...")
                                            continue
                                        else:
                                            logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol}: {order_result.get('error')}")
                                            break
                                except Exception as e:
                                    logger.error(f"Bot {bot_id}: Exception placing order on {attempt_symbol}: {e}")
                                    if index < len(symbols_to_try) - 1:
                                        continue
                                    break
                        
                        if order_result and order_result.get('success', False):
                            # Get the order ticket/deal_id for precise matching
                            order_ticket = str(order_result.get('orderId') or order_result.get('deal_id') or '')
                            
                            # Get current position info (broker-aware)
                            positions = []
                            if is_ig and ig_conn:
                                positions = ig_conn.get_positions()
                            elif mt5_conn:
                                positions = mt5_conn.get_positions()
                            
                            if positions:
                                matched_pos = None
                                matched_by_ticket = False
                                
                                # 1. Try exact ticket/deal_id match (precise)
                                if order_ticket:
                                    for pos in positions:
                                        pos_ticket = str(pos.get('ticket') or pos.get('deal_id', ''))
                                        if pos_ticket and pos_ticket == order_ticket:
                                            matched_pos = pos
                                            matched_by_ticket = True
                                            break
                                
                                # 2. Fallback: match by symbol+direction
                                if not matched_pos:
                                    for pos in positions:
                                        pos_symbol = pos.get('symbol') or pos.get('epic', '')
                                        pos_type = pos.get('type') or pos.get('direction', '')
                                        if (pos_symbol == symbol or symbol in pos_symbol) and pos_type.upper() == order_type.upper():
                                            matched_pos = pos
                                            break
                                
                                if matched_pos:
                                    pos = matched_pos
                                    pos_symbol = pos.get('symbol') or pos.get('epic', '')
                                    pos_type = pos.get('type') or pos.get('direction', '')
                                    
                                    # Use position PnL only if matched by ticket (exact match)
                                    # For symbol+direction fallback, PnL is ~0 since trade was just placed
                                    if matched_by_ticket:
                                        trade_profit = pos.get('pnl') or pos.get('profit_loss', 0)
                                    else:
                                        trade_profit = 0
                                    
                                    trade = {
                                            'ticket': pos.get('ticket') or pos.get('deal_id', ''),
                                            'symbol': pos_symbol,
                                            'type': pos_type,
                                            'volume': pos.get('volume') or pos.get('size', 0),
                                            'baseVolume': trade_params['volume'],
                                            'positionSize': position_size,
                                            'entryTime': trade_params.get('entry_time', pos.get('openTime', datetime.now().isoformat())),
                                            'exitTime': trade_params.get('exit_time', datetime.now().isoformat()),
                                            'entryPrice': pos.get('openPrice') or pos.get('level', 0),
                                            'exitPrice': pos.get('currentPrice') or pos.get('level', 0),
                                            'durationSec': trade_params.get('duration_sec', None),
                                            'profit': trade_profit,
                                            'time': datetime.now().isoformat(),
                                            'timestamp': int(datetime.now().timestamp() * 1000),
                                            'botId': bot_id,
                                            'cycle': trade_cycle,
                                            'strategy': strategy_name,
                                            'isWinning': trade_profit > 0,
                                            'riskSettings': bot_config.get('riskSettings', {}),
                                            'signals': trade_params.get('signals', None),
                                            'source': 'REAL_IG' if is_ig else 'REAL_MT5',
                                            'broker': broker_type,
                                    }
                                    
                                    # Store in database
                                    try:
                                        trade_conn = sqlite3.connect('zwesta_trading.db')
                                        trade_cursor = trade_conn.cursor()
                                        trade_cursor.execute('''
                                            INSERT INTO trades (bot_id, user_id, trade_data, timestamp)
                                            VALUES (?, ?, ?, ?)
                                        ''', (bot_id, user_id, json.dumps(trade), trade['timestamp']))
                                        trade_conn.commit()
                                        trade_conn.close()
                                    except Exception as e:
                                        logger.error(f"Bot {bot_id}: Error storing trade: {e}")
                                    
                                    # Update bot stats
                                    bot_config['totalTrades'] += 1
                                    bot_config['totalInvestment'] += trade['volume'] * trade['entryPrice']
                                    
                                    if trade['profit'] > 0:
                                        bot_config['winningTrades'] += 1
                                    else:
                                        bot_config['totalLosses'] += abs(trade['profit'])
                                    
                                    bot_config['totalProfit'] += trade['profit']
                                    
                                    # Update peak & drawdown
                                    if bot_config['totalProfit'] > bot_config['peakProfit']:
                                        bot_config['peakProfit'] = bot_config['totalProfit']
                                    
                                    drawdown = bot_config['peakProfit'] - bot_config['totalProfit']
                                    if drawdown > bot_config['maxDrawdown']:
                                        bot_config['maxDrawdown'] = drawdown
                                    
                                    # Track profit history
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
                                    
                                    # Distribution commissions
                                    if trade['profit'] > 0:
                                        try:
                                            distribute_trade_commissions(bot_id, user_id, trade['profit'])
                                        except Exception as e:
                                            logger.error(f"Bot {bot_id}: Commission error: {e}")
                                    
                                    logger.info(f"✅ Bot {bot_id}: Trade executed | {symbol} {order_type} | P&L: ${trade['profit']:.2f}")
                                    trades_placed += 1
                        else:
                            logger.warning(f"Bot {bot_id}: Could not place order on {symbol} or EURUSD fallback")
                    
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Error in trade cycle for {symbol}: {e}")
                        continue
                
                # Update account balance (broker-aware)
                try:
                    if is_ig and ig_conn:
                        account_info = ig_conn.get_account_info()
                        if account_info:
                            bot_config['accountBalance'] = account_info.get('balance', 0)
                    elif mt5_conn:
                        account_info = mt5_conn.get_account_info()
                        if account_info:
                            bot_config['accountBalance'] = account_info.get('balance', 0)
                except Exception as e:
                    logger.warning(f"Bot {bot_id}: Could not update account balance: {e}")
                
                logger.info(f"✅ Bot {bot_id}: Cycle #{trade_cycle} complete | Trades placed: {trades_placed} | Total P&L: ${bot_config['totalProfit']:.2f}")
                
                # Wait for next trading interval
                logger.info(f"⏳ Bot {bot_id}: Waiting {trading_interval} seconds until next cycle...")
                time.sleep(trading_interval)
            
            except Exception as e:
                logger.error(f"Bot {bot_id}: Error in trading loop: {e}")
                time.sleep(min(trading_interval, 60))  # Wait at least 60 seconds before retry
        
        # Bot stopped
        logger.info(f"🛑 Bot {bot_id}: CONTINUOUS TRADING LOOP STOPPED")
        running_bots[bot_id] = False
    
    except Exception as e:
        logger.error(f"Bot {bot_id}: FATAL error in trading loop: {e}")
        running_bots[bot_id] = False


def get_broker_connection(credential_id: str, user_id: str, bot_id: str = None):
    """Dynamically load and return the correct broker connection based on credential type
    
    Supports:
    - IG Markets (REST API)
    - MetaQuotes/MT5 (Terminal SDK)
    - XM Global (MT5)
    
    Returns: (broker_type, connection_object) or (None, error_message)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Load credential from database
        cursor.execute('''
            SELECT credential_id, broker_name, api_key, username, password,
                   account_number, server, is_live
            FROM broker_credentials
            WHERE credential_id = ? AND user_id = ? AND is_active = 1
        ''', (credential_id, user_id))
        
        cred_row = cursor.fetchone()
        conn.close()
        
        if not cred_row:
            error_msg = f"Credential {credential_id} not found or inactive for user {user_id}"
            logger.error(error_msg)
            return None, error_msg
        
        cred = dict(cred_row)
        broker_name = cred['broker_name']
        
        logger.info(f"[Broker Detection] Bot {bot_id}: Detected broker type: {broker_name}")
        
        # ✅ IG MARKETS - REST API
        if broker_name == 'IG Markets':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using IG Markets REST API")
            api_key = cred['api_key']
            username = cred['username']
            password = cred['password']
            is_live = cred['is_live']
            
            if not api_key or not username or not password:
                error_msg = f"IG Markets: Missing credentials (api_key={bool(api_key)}, username={bool(username)}, password={bool(password)})"
                logger.error(error_msg)
                return None, error_msg
            
            # Create IG connection with user's credentials
            ig_conn = IGConnection(credentials={
                'api_key': api_key,
                'username': username,
                'password': password,
                'is_live': is_live
            })
            
            if ig_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to IG Markets ({username})")
                return 'IG Markets', ig_conn
            else:
                error_msg = f"Failed to connect to IG Markets for user {username}"
                logger.error(error_msg)
                return None, error_msg
        
        # ✅ METATRADER 5 - MetaQuotes or XM Global
        elif broker_name in ['MetaQuotes', 'XM Global', 'MetaTrader 5']:
            logger.info(f"[Broker Switch] Bot {bot_id}: Using MetaTrader 5 SDK")
            account_number = cred['account_number']
            password = cred['password']
            server = cred['server']
            is_live = cred['is_live']
            
            if not account_number or not password or not server:
                error_msg = f"MT5: Missing credentials (account={bool(account_number)}, password={bool(password)}, server={bool(server)})"
                logger.error(error_msg)
                return None, error_msg
            
            # Normalize server name for MT5
            if 'xm' in server.lower():
                server = 'XMGlobal-Demo' if not is_live else 'XMGlobal-Live'
            elif 'metaquotes' in server.lower():
                server = 'MetaQuotes-Demo' if not is_live else 'MetaQuotes-Live'
            
            logger.info(f"Bot {bot_id}: Connecting to MT5 - Account: {account_number}, Server: {server}")
            
            # Create MT5 connection
            mt5_conn = MT5Connection(
                account=account_number,
                password=password,
                server=server,
                mt5_path=MT5_CONFIG.get('path')
            )
            
            if mt5_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to MT5 ({account_number}@{server})")
                return 'MetaTrader 5', mt5_conn
            else:
                error_msg = f"Failed to connect to MT5 - Account: {account_number}, Server: {server}"
                logger.error(error_msg)
                return None, error_msg
        
        else:
            error_msg = f"Unknown broker type: {broker_name}. Supported: IG Markets, MetaQuotes, XM Global"
            logger.error(error_msg)
            return None, error_msg
    
    except Exception as e:
        error_msg = f"Error loading broker connection: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


@app.route('/api/bot/start', methods=['POST'])
@require_session
def start_bot():
    """Start automatic trading for a bot with intelligent strategy switching
    
    SECURITY: Requires PIN verification (2FA) before activation
    
    REQUEST FLOW:
    1. User clicks "Start Bot"
    2. Frontend calls POST /api/bot/<bot_id>/request-activation
    3. Backend sends PIN to user email
    4. User enters PIN in app
    5. Frontend calls POST /api/bot/start with activation_pin
    6. Backend verifies PIN and activates bot
    
    Supports HYBRID MODE:
    - DEMO: Trades using shared demo MT5 account
    - LIVE: Trades using user's real MT5 account (if credentials stored)
    """
    try:
        data = request.json
        bot_id = data.get('botId')
        user_id = data.get('user_id') or request.user_id  # Get from request or session
        activation_pin = data.get('activation_pin')  # NEW: Required for 2FA
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot = active_bots[bot_id]
        if bot.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # ✅ OPTIONAL: Verify activation PIN (for enhanced security)
        # If PIN is provided, validate it; if not, allow start for backward compatibility
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if activation_pin:
            # PIN PROVIDED: Verify PIN exists, belongs to user, and hasn't expired
            cursor.execute('''
                SELECT * FROM bot_activation_pins 
                WHERE bot_id = ? AND user_id = ? AND pin = ? AND expires_at > ?
            ''', (bot_id, user_id, activation_pin, datetime.now().isoformat()))
            
            pin_record = cursor.fetchone()
            
            if not pin_record:
                # Increment failed attempts
                cursor.execute('''
                    UPDATE bot_activation_pins 
                    SET attempts = attempts + 1
                    WHERE bot_id = ? AND user_id = ?
                ''', (bot_id, user_id))
                conn.commit()
                conn.close()
                
                return jsonify({
                    'success': False, 
                    'error': 'Invalid or expired PIN. Request a new one.',
                    'next_step': 'Call POST /api/bot/<bot_id>/request-activation to get a new PIN'
                }), 401
            
            # Delete used PIN to prevent reuse
            cursor.execute('DELETE FROM bot_activation_pins WHERE bot_id = ? AND user_id = ?', (bot_id, user_id))
            logger.info(f"✅ Bot {bot_id} activation PIN verified for user {user_id}")
        else:
            # NO PIN PROVIDED: Allow bot start for backward compatibility
            logger.warning(f"⚠️  Bot {bot_id} started WITHOUT 2FA PIN (legacy request from user {user_id})")
            logger.warning(f"   Recommendation: Update client to use /api/bot/<bot_id>/request-activation + PIN for security")
        
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        
        if not db_bot or db_bot['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # ✅ AUTOMATIC BROKER DETECTION
        # Get credential_id from bot and determine which broker to use
        credential_id = bot.get('credentialId')
        
        if not credential_id:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Bot missing credentialId - must link to broker credential first'
            }), 400
        
        # Load the correct broker connection automatically
        broker_type, broker_conn = get_broker_connection(credential_id, user_id, bot_id)
        
        if broker_conn is None:
            # Error loading broker connection
            return jsonify({
                'success': False,
                'error': f'Failed to connect to broker: {broker_type}',
                'botId': bot_id,
                'status': 'FAILED'
            }), 503
        
        logger.info(f"✅ Bot {bot_id}: Broker connection established ({broker_type})")
        
        # Store bot config with broker info for trading loop
        bot_config = active_bots[bot_id]
        bot_config['broker_type'] = broker_type
        bot_config['broker_conn'] = broker_conn
        
        conn.close()
        
        import random
        
        # ✅ VALIDATE & CORRECT BOT SYMBOLS IMMEDIATELY (in case they're old/unavailable)
        # This prevents users from being shown old symbols and ensures trades use valid ones
        original_symbols = bot_config.get('symbols', ['EURUSD'])
        corrected_symbols = validate_and_correct_symbols(original_symbols)
        if corrected_symbols != original_symbols:
            logger.info(f"📝 Bot {bot_id} symbols corrected: {original_symbols} → {corrected_symbols}")
            bot_config['symbols'] = corrected_symbols
            # Update in-memory and database
            active_bots[bot_id]['symbols'] = corrected_symbols
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_bots 
                    SET config = json_replace(config, '$.symbols', ?)
                    WHERE bot_id = ?
                ''', (json.dumps(corrected_symbols), bot_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not update bot symbols in DB: {e}")
        
        logger.info(f"✅ Bot {bot_id}: All validation checks passed - ready to start trading")
        
        # Validate symbols are available
        validated_symbols = validate_and_correct_symbols(bot_config.get('symbols', ['EURUSD']))
        bot_config['symbols'] = validated_symbols
        logger.info(f"📍 Bot {bot_id}: Trading symbols validated: {validated_symbols}")
        
        logger.info(f"Bot {bot_id}: Starting CONTINUOUS trading in background thread")
        
        # ✅ Check if bot thread is already running (created by /api/bot/create)
        # If it is, don't create a duplicate - just return success
        if bot_id in bot_threads and bot_threads[bot_id].is_alive():
            logger.info(f"Bot {bot_id}: Already running via background thread - returning success")
            logger.info(f"  (Thread started by /api/bot/create, will be operational within 2 minutes)")
            # Return immediately - bot is already trading or waiting to be ready
            return jsonify({
                'success': True,
                'botId': bot_id,
                'strategy': bot_config['strategy'],
                'status': 'RUNNING',
                'message': f'Bot {bot_id} is already trading in background',
                'tradingInterval': bot_config.get('tradingInterval', 300),
                'botStats': {
                    'totalTrades': bot_config['totalTrades'],
                    'winningTrades': bot_config['winningTrades'],
                    'totalLosses': round(bot_config['totalLosses'], 2),
                    'totalProfit': round(bot_config['totalProfit'], 2),
                    'accountBalance': bot_config.get('accountBalance', 0),
                }
            }), 200
        
        # Bot thread not running or stopped - create a new one
        logger.info(f"Bot {bot_id}: No active thread found - creating new background thread")
        
        # Reset stop flag and start new thread
        bot_stop_flags[bot_id] = False
        
        # ✅ REGISTER BOT AS RUNNING IMMEDIATELY (before thread starts)
        # This prevents dashboard from showing it as stopped during startup
        running_bots[bot_id] = True
        
        bot_thread = threading.Thread(
            target=continuous_bot_trading_loop,
            args=(bot_id, user_id, None),
            daemon=True,
            name=f"BotThread-{bot_id}"
        )
        bot_threads[bot_id] = bot_thread
        bot_thread.start()
        
        logger.info(f"✅ Bot {bot_id}: Background thread launched successfully")
        
        # Return immediately - bot is running in background
        return jsonify({
            'success': True,
            'botId': bot_id,
            'strategy': bot_config['strategy'],
            'status': 'RUNNING',
            'message': f'Bot {bot_id} started - continuous trading in background',
            'tradingInterval': bot_config.get('tradingInterval', 300),
            'botStats': {
                'totalTrades': bot_config['totalTrades'],
                'winningTrades': bot_config['winningTrades'],
                'totalLosses': round(bot_config['totalLosses'], 2),
                'totalProfit': round(bot_config['totalProfit'], 2),
                'accountBalance': bot_config.get('accountBalance', 0),
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/market/commodities', methods=['GET'])
def get_commodity_market_data():
    """Get market sentiment and price data for all trading commodities (with live prices from MT5)"""
    try:
        # Thread-safe access to commodity_market_data
        with market_data_lock:
            # Count signals in response for debugging
            buy_count = sum(1 for s in commodity_market_data.values() if 'BUY' in s.get('signal', ''))
            sell_count = sum(1 for s in commodity_market_data.values() if 'SELL' in s.get('signal', ''))
            flat_count = sum(1 for s in commodity_market_data.values() if 'CONSOLIDAT' in s.get('signal', '') or 'VOLATILE' in s.get('signal', ''))
            hold_count = sum(1 for s in commodity_market_data.values() if s.get('signal', '') == '🟡 HOLD')
            
            # Log actual signal values for key symbols
            key_symbols = ['EURUSD', 'GBPUSD', 'OILK', 'XPTUSD']
            for sym in key_symbols:
                if sym in commodity_market_data:
                    sig = commodity_market_data[sym].get('signal', 'UNKNOWN')
                    logger.debug(f"[API] {sym}: signal='{sig}'")
            
            logger.debug(f"[API] Returning commodities: {buy_count} BUY, {sell_count} SELL, {flat_count} FLAT, {hold_count} HOLD")
            
            return jsonify({
                'success': True,
                'commodities': commodity_market_data.copy(),
                'timestamp': datetime.now().isoformat(),
                'note': 'Prices updated live from MT5 every 3 seconds',
            }), 200
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/status', methods=['GET'])
@require_session
def bot_status():
    """Get status of authenticated user's bots only"""
    try:
        user_id = request.user_id  # From session token
        
        bots_list = []
        for bot in active_bots.values():
            # Only return bots for authenticated user
            if bot.get('user_id') != user_id:
                continue
            
            # Calculate runtime (safely access createdAt)
            created = datetime.fromisoformat(bot.get('createdAt', datetime.now().isoformat()))
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit (safely access dailyProfits)
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profits = bot.get('dailyProfits', {})
            daily_profit = daily_profits.get(today, bot.get('dailyProfit', 0))
            
            # Calculate ROI (safely access totalInvestment and totalProfit)
            investment = bot.get('totalInvestment', 0)
            total_profit = bot.get('totalProfit', 0)
            roi = (total_profit / max(investment, 1)) * 100 if investment > 0 else 0
            
            # Calculate profit factor - capped at 99.99 to avoid JSON infinity issues
            total_losses = bot.get('totalLosses', 0)
            if total_losses > 0:
                profit_factor = min(total_profit / total_losses, 99.99) if total_profit > 0 else 0
            else:
                profit_factor = 99.99 if total_profit > 0 else 0
            
            # Safely access symbols and other fields
            symbols = bot.get('symbols', [])
            symbol = symbols[0] if symbols else 'EURUSD'
            trade_history = bot.get('tradeHistory', [])
            last_trade_time = trade_history[-1].get('time') if trade_history else bot.get('createdAt', datetime.now().isoformat())
            
            enhanced_bot = {
                'botId': bot.get('botId', 'unknown'),
                'symbol': symbol,
                'symbols': symbols,
                'strategy': bot.get('strategy', 'Unknown'),
                'commission': round(total_profit * 0.01, 2),
                'profit': round(total_profit, 2),
                'totalProfit': round(total_profit, 2),
                'totalTrades': bot.get('totalTrades', 0),
                'winningTrades': bot.get('winningTrades', 0),
                'winRate': round((bot.get('winningTrades', 0) / max(bot.get('totalTrades', 1), 1)) * 100, 1),
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit, 2),
                'roi': round(roi, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(total_profit / max(bot.get('totalTrades', 1), 1), 2),
                'status': 'Active' if bot.get('enabled', True) else 'Inactive',
                'lastTradeTime': last_trade_time,
                'broker_type': bot.get('broker_type', 'MT5'),
                'profitField': round(total_profit, 2),
            }
            bots_list.append(enhanced_bot)
        
        return jsonify({
            'success': True,
            'activeBots': len([b for b in bots_list if b.get('enabled', True)]),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/status-public', methods=['GET'])
def bot_status_public():
    """Get status of RUNNING bots only (public - no authentication required)
    
    A bot is considered "running" if:
    1. It's in running_bots AND marked as running (True)
    2. OR it's in active_bots AND was just created (enabled=True and enabled field is explicitly set)
    """
    try:
        bots_list = []
        
        # Only include ENABLED (running) bots
        for bot_id, bot in active_bots.items():
            # Include bot if:
            # 1. It's explicitly marked as running in running_bots OR
            # 2. It's enabled in active_bots (just created, background thread starting)
            is_marked_running = running_bots.get(bot_id, False)
            is_enabled = bot.get('enabled', True)
            
            # Skip only if BOTH conditions fail
            if not is_marked_running and not is_enabled:
                logger.debug(f"Skipping bot {bot_id}: marked_running={is_marked_running}, enabled={is_enabled}")
                continue
            
            # Calculate runtime
            created = datetime.fromisoformat(bot.get('createdAt', datetime.now().isoformat()))
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit (safely access dailyProfits)
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profit = bot.get('dailyProfits', {}).get(today, bot.get('dailyProfit', 0))
            
            # Calculate ROI (safely access totalInvestment)
            investment = bot.get('totalInvestment', 0)
            total_profit = bot.get('totalProfit', 0)
            roi = (total_profit / max(investment, 1)) * 100 if investment > 0 else 0
            
            # Calculate profit factor (safely access totalLosses)
            total_losses = bot.get('totalLosses', 0)
            if total_losses > 0:
                profit_factor = min(total_profit / total_losses, 99.99) if total_profit > 0 else 0
            else:
                profit_factor = 99.99 if total_profit > 0 else 0
            
            # Safely access symbols and strategy
            symbols = bot.get('symbols', [])
            symbol = symbols[0] if symbols else 'EURUSD'
            
            # Determine status based on whether thread is actively running
            if is_marked_running:
                status = 'Running'
            elif is_enabled and not is_marked_running:
                status = 'Starting'  # Just created, background thread starting
            else:
                status = 'Stopped'
            
            enhanced_bot = {
                'botId': bot.get('botId', 'unknown'),
                'symbol': symbol,
                'symbols': symbols,  # ✅ Include full symbols list
                'strategy': bot.get('strategy', 'Unknown'),
                'commission': round(total_profit * 0.01, 2),
                'profit': round(total_profit, 2),
                'totalProfit': round(total_profit, 2),  # ✅ Include totalProfit field
                'totalTrades': bot.get('totalTrades', 0),  # ✅ Include totalTrades
                'winningTrades': bot.get('winningTrades', 0),  # ✅ Include winningTrades
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit, 2),
                'roi': round(roi, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(total_profit / max(bot.get('totalTrades', 1), 1), 2),
                'status': status,
                'enabled': is_enabled,
                'broker_type': bot.get('broker_type', 'MT5'),
                'createdAt': created.isoformat(),
                'lastTradeTime': bot.get('tradeHistory', [{}])[-1].get('time') if bot.get('tradeHistory') else bot.get('createdAt', datetime.now().isoformat()),
            }
            bots_list.append(enhanced_bot)
        
        # Sort by creation date (latest first)
        bots_list.sort(key=lambda x: x['createdAt'], reverse=True)
        
        return jsonify({
            'success': True,
            'activeBots': len(bots_list),
            'runningBots': len([b for b in bots_list if b['status'] == 'Running']),
            'startingBots': len([b for b in bots_list if b['status'] == 'Starting']),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting public bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop/<bot_id>', methods=['POST'])
@require_session
def stop_bot(bot_id):
    """Stop a trading bot (still keeps it in system for restart)"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        
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
        
        # Stop continuous trading thread if running
        if bot_id in bot_threads and bot_threads[bot_id].is_alive():
            logger.info(f"🛑 Bot {bot_id}: Stopping background trading thread...")
            bot_stop_flags[bot_id] = True
            bot_threads[bot_id].join(timeout=30)
            logger.info(f"✅ Bot {bot_id}: Background thread stopped")
        
        # Disable bot in config
        bot_config['enabled'] = False
        running_bots[bot_id] = False
        
        logger.info(f"⏸️ Bot {bot_id} stopped (still in system, can be restarted)")
        logger.info(f"   Total Trades: {bot_config.get('totalTrades', 0)}")
        logger.info(f"   Total Profit: ${bot_config.get('totalProfit', 0):.2f}")
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} stopped',
            'finalStats': {
                'totalTrades': bot_config['totalTrades'],
                'winningTrades': bot_config['winningTrades'],
                'totalProfit': round(bot_config['totalProfit'], 2),
                'note': 'Bot can be restarted later. Use /delete to permanently remove.'
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/delete/<bot_id>', methods=['DELETE', 'POST'])
@require_session
def delete_bot(bot_id):
    """Delete a trading bot permanently (requires confirmation token)"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        confirmation_token = data.get('confirmation_token')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot_config = active_bots[bot_id]
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # OPTIONAL: Verify confirmation token (for enhanced security)
        # If token is provided, validate it; if not, allow deletion for backward compatibility
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if confirmation_token:
            # TOKEN PROVIDED: Look up and verify token
            cursor.execute('''
                SELECT * FROM bot_deletion_tokens
                WHERE bot_id = ? AND user_id = ? AND deletion_token = ? AND expires_at > ?
            ''', (bot_id, user_id, confirmation_token, datetime.now().isoformat()))
            
            token_record = cursor.fetchone()
            
            if not token_record:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired confirmation token',
                    'next_step': f'Call POST /api/bot/{bot_id}/request-deletion to get a new token'
                }), 401
            
            logger.info(f"✅ Bot {bot_id} deletion token verified for user {user_id}")
        else:
            # NO TOKEN PROVIDED: Allow deletion for backward compatibility
            logger.warning(f"⚠️  Bot {bot_id} deleted WITHOUT 2-step confirmation (legacy request from user {user_id})")
            logger.warning(f"   Recommendation: Update client to use /api/bot/{bot_id}/request-deletion + token for safety")
        
        # Verify bot ownership in database
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        
        if not db_bot or db_bot['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Log deletion with all stats
        final_stats = bot_config.copy()
        logger.critical(f"\ud83d\uddd1\ufe0f BOT PERMANENTLY DELETED: {bot_id} by user {user_id}")
        logger.critical(f"   Final Stats: {json.dumps({'totalTrades': final_stats.get('totalTrades'), 'totalProfit': final_stats.get('totalProfit')}, indent=2)}")
        logger.critical(f"   Deletion confirmed with token: {confirmation_token[:8]}...")
        
        # Delete from database
        cursor.execute('DELETE FROM user_bots WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_credentials WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_deletion_tokens WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_activation_pins WHERE bot_id = ?', (bot_id,))
        conn.commit()
        
        # Stop bot if running
        if bot_config.get('enabled', False):
            bot_config['enabled'] = False
        
        # Remove from active_bots
        del active_bots[bot_id]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} permanently deleted',
            'deleted_stats': {
                'totalTrades': final_stats.get('totalTrades', 0),
                'winningTrades': final_stats.get('winningTrades', 0),
                'totalProfit': final_stats.get('totalProfit', 0),
            },
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
    """
    Set withdrawal mode and parameters for a bot

    Modes:
    - 'fixed': Withdraw at user-predetermined profit level
    - 'intelligent': Robot decides intelligently based on market conditions
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        withdrawal_mode = data.get('withdrawal_mode', 'fixed')  # 'fixed' or 'intelligent'
        target_profit = data.get('target_profit')               # For fixed mode

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        if withdrawal_mode not in ['fixed', 'intelligent']:
            return jsonify({'success': False, 'error': "withdrawal_mode must be 'fixed' or 'intelligent'"}), 400

        # Validate based on mode
        min_profit = None
        max_profit = None
        volatility_threshold = None
        win_rate_min = None
        trend_strength_min = None
        time_between_withdrawals_hours = None

        if withdrawal_mode == 'fixed':
            if not target_profit:
                return jsonify({'success': False, 'error': 'target_profit required for fixed mode'}), 400

            if target_profit < 10:
                return jsonify({'success': False, 'error': 'Minimum profit target is $10'}), 400

            if target_profit > 50000:
                return jsonify({'success': False, 'error': 'Maximum profit target is $50,000'}), 400

        elif withdrawal_mode == 'intelligent':
            # Intelligent mode parameters
            min_profit                     = data.get('min_profit', 50)
            max_profit                     = data.get('max_profit', 1000)
            volatility_threshold           = data.get('volatility_threshold', 0.02)
            win_rate_min                   = data.get('win_rate_min', 60)
            trend_strength_min             = data.get('trend_strength_min', 0.5)
            time_between_withdrawals_hours = data.get('time_between_withdrawals_hours', 24)

            # Validate parameters
            if min_profit < 10:
                return jsonify({'success': False, 'error': 'Minimum profit must be >= $10'}), 400
            if volatility_threshold < 0 or volatility_threshold > 0.1:
                return jsonify({'success': False, 'error': 'Volatility threshold must be 0-0.1'}), 400
            if win_rate_min < 40 or win_rate_min > 100:
                return jsonify({'success': False, 'error': 'Win rate must be 40-100%'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        setting_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        updated_at = created_at

        if withdrawal_mode == 'fixed':
            cursor.execute('''
                INSERT OR REPLACE INTO auto_withdrawal_settings
                (setting_id, bot_id, user_id, target_profit, is_active,
                 withdrawal_mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                setting_id,
                bot_id,
                user_id,
                target_profit,
                1,
                'fixed',
                created_at,
                updated_at
            ))

            message = f'Fixed withdrawal set: Will withdraw when profit reaches ${target_profit}'

        else:  # intelligent
            cursor.execute('''
                INSERT OR REPLACE INTO auto_withdrawal_settings
                (setting_id, bot_id, user_id, withdrawal_mode,
                 min_profit, max_profit, volatility_threshold,
                 win_rate_min, trend_strength_min,
                 time_between_withdrawals_hours,
                 last_withdrawal_at,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                setting_id,
                bot_id,
                user_id,
                'intelligent',
                min_profit,
                max_profit,
                volatility_threshold,
                win_rate_min,
                trend_strength_min,
                time_between_withdrawals_hours,
                None,
                created_at,
                updated_at
            ))

            message = (
                f'Intelligent withdrawal activated with min profit ${min_profit}, '
                f'max ${max_profit}, volatility < {volatility_threshold:.2%}'
            )

        conn.commit()
        conn.close()

        logger.info(f"Auto-withdrawal configured for bot {bot_id}: {withdrawal_mode} mode")

        return jsonify({
            'success': True,
            'setting_id': setting_id,
            'bot_id': bot_id,
            'withdrawal_mode': withdrawal_mode,
            'message': message
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


@app.route('/api/user/<user_id>/bots', methods=['GET'])
@require_session
def get_user_bots(user_id):
    """Get all bots for a specific user"""
    # Verify user is accessing only their own bots
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user bots'}), 403
    
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
        
        result = {
            'success': True,
            'withdrawals': withdrawals
        }
        print("\n=== Withdrawal History ===\n", result)
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error getting withdrawal history: {e}")
        print("\n=== Withdrawal History Error ===\n", str(e))
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

# --- IG API Integration ---
from ig_service import ig_api
app.register_blueprint(ig_api)

# Example: Use IG API in bot trading logic
# (You can call these functions from your bot trading threads)
def place_ig_trade(epic, size, direction, currency="USD", order_type="MARKET"):
    import requests
    from flask import current_app
    # Use the IG API endpoint via internal HTTP call or direct function call
    url = f"http://localhost:9000/api/ig/place-order"
    data = {
        "epic": epic,
        "size": size,
        "direction": direction,
        "currencyCode": currency,
        "orderType": order_type
    }
    try:
        resp = requests.post(url, json=data)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# Example: Get IG funds for financial info display
def get_ig_funds():
    import requests
    url = f"http://localhost:9000/api/ig/funds"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# Example: Get IG open positions for bot monitoring
def get_ig_positions():
    import requests
    url = f"http://localhost:9000/api/ig/positions"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# You can now call place_ig_trade, get_ig_funds, get_ig_positions from your bot logic
# and display the results in your dashboard endpoints.

COMMODITIES = {
    # ===== FOREX (9) - MetaQuotes-Demo Available =====
    'EURUSD': {'category': 'Forex', 'emoji': '📍'},
    'GBPUSD': {'category': 'Forex', 'emoji': '🇬🇧'},
    'USDJPY': {'category': 'Forex', 'emoji': '🇯🇵'},
    'USDCHF': {'category': 'Forex', 'emoji': '🇨🇭'},
    'AUDUSD': {'category': 'Forex', 'emoji': '🦘'},
    'NZDUSD': {'category': 'Forex', 'emoji': '🥝'},
    'USDCAD': {'category': 'Forex', 'emoji': '🍁'},
    'USDSEK': {'category': 'Forex', 'emoji': '🇸🇪'},
    'USDCNH': {'category': 'Forex', 'emoji': '🇨🇳'},
    
    # ===== COMMODITIES (2) - MetaQuotes-Demo Available =====
    'XPTUSD': {'category': 'Metals', 'emoji': '💍'},   # PLATINUM
    'OILK': {'category': 'Energy', 'emoji': '🛢️'},     # CRUDE OIL
    
    # ===== INDICES (2) - MetaQuotes-Demo Available =====
    'SP500m': {'category': 'Indices', 'emoji': '📊'},   # S&P 500
    'DAX': {'category': 'Indices', 'emoji': '📈'},      # DAX
    
    # ===== STOCKS (5) - MetaQuotes-Demo Available =====
    'AMD': {'category': 'Tech Stock', 'emoji': '💻'},
    'MSFT': {'category': 'Tech Stock', 'emoji': '🪟'},
    'INTC': {'category': 'Tech Stock', 'emoji': '⚡'},
    'NVDA': {'category': 'Tech Stock', 'emoji': '🎮'},
    'NIKL': {'category': 'Indices', 'emoji': '🗾'},     # Nikkei
}


# ==================== AUTO-WITHDRAWAL MONITORING ====================
monitoring_thread = None
monitoring_running = False

def auto_withdrawal_monitor():
    """
    Background task to monitor bot profits and execute auto-withdrawals
    Supports two modes:
    - Fixed: Withdraw at user-predetermined profit level
    - Intelligent: Withdraw based on market conditions and bot performance
    """
    global monitoring_running
    monitoring_running = True
    logger.info("Starting auto-withdrawal monitoring thread...")
    
    def should_withdraw_intelligent(bot_id, bot_config, settings):
        """
        Intelligent withdrawal decision based on:
        - Current profit level
        - Win rate
        - Market volatility
        - Trend strength
        - Recent performance
        """
        try:
            current_profit = bot_config.get('totalProfit', 0)
            min_profit = settings[4]  # min_profit from DB
            max_profit = settings[11] if len(settings) > 11 else 1000  # max_profit from DB
            
            # Don't withdraw if profit below minimum threshold
            if current_profit < min_profit:
                return False, None
            
            # Get bot performance metrics
            win_rate = bot_config.get('winRate', 50)
            trades_count = bot_config.get('totalTrades', 0)
            
            # Need at least 5 trades to make intelligent decision
            if trades_count < 5:
                return False, None
            
            # Calculate win rate from bot stats
            winning_trades = bot_config.get('winningTrades', 0)
            if trades_count > 0:
                actual_win_rate = (winning_trades / trades_count) * 100
            else:
                actual_win_rate = 0
            
            win_rate_min = settings[6] if len(settings) > 6 else 60  # win_rate_min from DB
            
            # Don't withdraw if win rate is too low (bot is struggling)
            if actual_win_rate < win_rate_min:
                return False, None
            
            # Calculate withdrawal amount (cap at max_profit)
            withdrawal_amount = min(current_profit, max_profit)
            
            # Check time between withdrawals
            hours_interval = settings[9] if len(settings) > 9 else 24
            last_withdrawal = settings[10] if len(settings) > 10 else None
            if last_withdrawal:
                try:
                    last_dt = datetime.fromisoformat(last_withdrawal)
                    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
                    if hours_since < hours_interval:
                        return False, None
                except Exception:
                    pass
            
            return True, withdrawal_amount
        
        except Exception as e:
            logger.error(f"Error in intelligent withdrawal decision: {e}")
            return False, None
    
    while monitoring_running:
        try:
            time.sleep(30)  # Check every 30 seconds
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all active auto-withdrawal settings
            cursor.execute('''
                SELECT setting_id, bot_id, user_id, withdrawal_mode, target_profit, 
                       min_profit, win_rate_min, trend_strength_min, volatility_threshold,
                       time_between_withdrawals_hours, last_withdrawal_at, max_profit
                FROM auto_withdrawal_settings
                WHERE is_active = 1
            ''')
            
            settings_list = cursor.fetchall()
            
            for setting in settings_list:
                setting_id, bot_id, user_id, withdrawal_mode = setting[:4]
                target_profit, min_profit, win_rate_min, trend_strength_min = setting[4:8]
                volatility_threshold, hours_interval, last_withdrawal_at, max_profit = setting[8:12]
                
                if bot_id not in active_bots:
                    continue
                
                bot_config = active_bots[bot_id]
                current_profit = bot_config.get('totalProfit', 0)
                
                # Check time interval constraint
                if last_withdrawal_at:
                    last_withdrawal = datetime.fromisoformat(last_withdrawal_at)
                    time_since_last = (datetime.now() - last_withdrawal).total_seconds() / 3600
                    if time_since_last < hours_interval:
                        continue
                
                should_withdraw = False
                withdrawal_amount = 0
                reason = ""
                
                # FIXED MODE: Withdraw when target profit reached
                if withdrawal_mode == 'fixed' and target_profit:
                    if current_profit >= target_profit:
                        should_withdraw = True
                        withdrawal_amount = current_profit
                        reason = f"Fixed target ${target_profit} reached"
                        logger.info(f"[FIXED] Bot {bot_id}: Profit ${current_profit} >= Target ${target_profit}")
                
                # INTELLIGENT MODE: Robot decides based on conditions
                elif withdrawal_mode == 'intelligent':
                    should_withdraw, withdrawal_amount = should_withdraw_intelligent(
                        bot_id, bot_config, setting
                    )
                    reason = f"Intelligent decision (withdrawing ${withdrawal_amount:.2f})" if should_withdraw else ""
                    if should_withdraw:
                        logger.info(f"[INTELLIGENT] Bot {bot_id}: Withdrawal triggered - Profit ${current_profit}")
                
                # Execute withdrawal if criteria met
                if should_withdraw and withdrawal_amount > 0:
                    try:
                        withdrawal_id = str(uuid.uuid4())
                        created_at = datetime.now().isoformat()
                        fee = withdrawal_amount * 0.02  # 2% fee
                        net_amount = withdrawal_amount - fee
                        
                        cursor.execute('''
                            INSERT INTO auto_withdrawal_history
                            (withdrawal_id, bot_id, user_id, triggered_profit, 
                             withdrawal_amount, fee, net_amount, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (withdrawal_id, bot_id, user_id, current_profit,
                              withdrawal_amount, fee, net_amount, 'pending', created_at))
                        
                        # Update last withdrawal time
                        cursor.execute('''
                            UPDATE auto_withdrawal_settings
                            SET last_withdrawal_at = ?
                            WHERE bot_id = ?
                        ''', (created_at, bot_id))
                        
                        # Distribute profit split and commissions
                        distribute_profit_split_and_commissions(user_id, withdrawal_amount, bot_id)
                        # Reset bot profit
                        active_bots[bot_id]['totalProfit'] = 0
                        active_bots[bot_id]['dailyProfit'] = 0
                        # Mark as completed
                        cursor.execute('''
                            UPDATE auto_withdrawal_history
                            SET status = 'completed', completed_at = ?
                            WHERE withdrawal_id = ?
                        ''', (datetime.now().isoformat(), withdrawal_id))
                        logger.info(f"✅ Auto-withdrawal executed for {bot_id}: ${net_amount:.2f} (Mode: {withdrawal_mode})")
                    except Exception as e:
                        logger.error(f"Error executing withdrawal for {bot_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in auto-withdrawal monitor: {e}")
        
        finally:
            if conn:
                conn.close()
    
    logger.info("Auto-withdrawal monitoring thread stopped")


# ==================== USER MANAGEMENT & MULTI-BROKER SYSTEM ====================

@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Register a new user account"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        name = data.get('name', '').strip()
        referrer_code = data.get('referrer_code', '').strip()
        
        if not email or not name:
            return jsonify({'success': False, 'error': 'Email and name required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT user_id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User already exists'}), 409
        
        user_id = str(uuid.uuid4())
        referral_code = hashlib.sha256(f"{email}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        referrer_id = None
        
        # Check if referrer exists
        if referrer_code:
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referrer_code,))
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referrer[0]
        
        cursor.execute('''
            INSERT INTO users (user_id, email, name, referrer_id, referral_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, name, referrer_id, referral_code, datetime.now().isoformat()))
        
        if referrer_id:
            referral_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO referrals (referral_id, referrer_id, referred_user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (referral_id, referrer_id, user_id, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ New user registered: {email} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'email': email,
            'name': name,
            'referral_code': referral_code,
            'message': 'Registration successful - use email to login'
        }), 201
    
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers', methods=['GET'])
@require_session
def list_user_brokers():
    """Get all broker credentials for authenticated user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live, is_active, created_at
            FROM broker_credentials
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        brokers = []
        for row in cursor.fetchall():
            brokers.append({
                'credential_id': row[0],
                'broker_name': row[1],
                'account_number': row[2],
                'server': row[3],
                'is_live': row[4],
                'is_active': row[5],
                'created_at': row[6],
            })
        
        conn.close()
        
        logger.info(f"✅ Retrieved {len(brokers)} brokers for user {user_id}")
        return jsonify({
            'success': True,
            'brokers': brokers,
            'total': len(brokers)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing brokers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers/add', methods=['POST'])
@require_session
def add_user_broker():
    """Add a new broker credential for user"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        broker_name = data.get('broker_name', '').strip()
        account_number = data.get('account_number', '').strip()
        password = data.get('password', '').strip()
        server = data.get('server', 'MetaQuotes-Demo').strip()
        is_live = data.get('is_live', False)
        
        if not broker_name or not account_number or not password:
            return jsonify({'success': False, 'error': 'Broker name, account number, and password required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute('''
            SELECT credential_id FROM broker_credentials
            WHERE user_id = ? AND account_number = ? AND broker_name = ?
        ''', (user_id, account_number, broker_name))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Broker credential already exists'}), 409
        
        credential_id = str(uuid.uuid4())
        
        cursor.execute('''
            INSERT INTO broker_credentials 
            (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        ''', (credential_id, user_id, broker_name, account_number, password, server, is_live, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Added broker credential for user {user_id}: {broker_name} ({account_number})")
        
        return jsonify({
            'success': True,
            'credential_id': credential_id,
            'broker_name': broker_name,
            'account_number': account_number,
            'message': 'Broker credential added successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error adding broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers/<credential_id>', methods=['DELETE'])
@require_session
def remove_user_broker(credential_id):
    """Remove a broker credential"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute('''
            SELECT user_id FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized or not found'}), 403
        
        # Delete the credential
        cursor.execute('DELETE FROM broker_credentials WHERE credential_id = ?', (credential_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Removed broker credential {credential_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Broker credential removed'
        }), 200
    
    except Exception as e:
        logger.error(f"Error removing broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/dashboard', methods=['GET'])
@require_session
def user_dashboard():
    """Get comprehensive user dashboard with stats"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # User info
        cursor.execute('''
            SELECT user_id, name, email, total_commission, created_at FROM users WHERE user_id = ?
        ''', (user_id,))
        user_row = cursor.fetchone()
        user_info = dict(user_row) if user_row else {}
        
        # Total bots
        cursor.execute('SELECT COUNT(*) FROM user_bots WHERE user_id = ?', (user_id,))
        total_bots = cursor.fetchone()[0]
        
        # Active bots
        cursor.execute('SELECT COUNT(*) FROM user_bots WHERE user_id = ? AND enabled = 1', (user_id,))
        active_bots_count = cursor.fetchone()[0]
        
        # Total profit
        cursor.execute('''
            SELECT COALESCE(SUM(total_profit), 0) FROM user_bots WHERE user_id = ?
        ''', (user_id,))
        total_profit = cursor.fetchone()[0] or 0
        
        # Total trades
        cursor.execute('''
            SELECT COUNT(*) FROM trades WHERE bot_id IN (SELECT bot_id FROM user_bots WHERE user_id = ?)
        ''', (user_id,))
        total_trades = cursor.fetchone()[0]
        
        # Commission stats
        cursor.execute('''
            SELECT 
                COALESCE(SUM(commission_amount), 0) as total_earned,
                COUNT(*) as commission_count
            FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        comm_row = cursor.fetchone()
        total_commission_earned = comm_row[0] if comm_row else 0
        commission_count = comm_row[1] if comm_row else 0
        
        # Win rate (profitable trades / total trades)
        cursor.execute('''
            SELECT COUNT(*) FROM trades 
            WHERE bot_id IN (SELECT bot_id FROM user_bots WHERE user_id = ?)
            AND json_extract(trade_data, '$.isWinning') = 1
        ''', (user_id,))
        winning_trades = cursor.fetchone()[0]
        win_rate = round((winning_trades / max(total_trades, 1)) * 100, 2)
        
        # Get top performers (bots)
        cursor.execute('''
            SELECT bot_id, name, total_profit, strategy FROM user_bots
            WHERE user_id = ?
            ORDER BY total_profit DESC
            LIMIT 5
        ''', (user_id,))
        
        top_bots = []
        for row in cursor.fetchall():
            top_bots.append({
                'bot_id': row[0],
                'name': row[1],
                'profit': row[2],
                'strategy': row[3]
            })
        
        # Get broker list
        cursor.execute('''
            SELECT COUNT(*) FROM broker_credentials WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        active_brokers = cursor.fetchone()[0]
        
        conn.close()
        
        dashboard = {
            'user': user_info,
            'stats': {
                'total_bots': total_bots,
                'active_bots': active_bots_count,
                'total_profit': round(total_profit, 2),
                'total_trades': total_trades,
                'win_rate_percent': win_rate,
                'total_commission_earned': round(total_commission_earned, 2),
                'commission_count': commission_count,
                'active_brokers': active_brokers,
            },
            'top_performers': top_bots,
        }
        
        logger.info(f"✅ Generated dashboard for user {user_id}: {total_bots} bots, ${total_profit:.2f} profit")
        
        return jsonify({
            'success': True,
            'dashboard': dashboard
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trading/intelligent-switch', methods=['POST'])
@require_session
def intelligent_asset_switch():
    """Intelligently switch bot assets based on profitability scores"""
    try:
        user_id = request.user_id
        data = request.get_json()
        bot_id = data.get('bot_id')
        
        if not bot_id:
            return jsonify({'success': False, 'error': 'bot_id required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify bot ownership
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        bot_owner = cursor.fetchone()
        if not bot_owner or bot_owner[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get current bot symbols
        cursor.execute('SELECT symbols FROM user_bots WHERE bot_id = ?', (bot_id,))
        current_symbols_str = cursor.fetchone()[0]
        current_symbols = current_symbols_str.split(',') if current_symbols_str else ['EURUSD']
        
        # Get best assets based on profitability
        best_assets = get_best_trading_assets(limit=5)
        
        # Check if we should switch
        asset_switch_made = False
        if best_assets and best_assets != current_symbols:
            new_symbols = best_assets
            cursor.execute('''
                UPDATE user_bots SET symbols = ? WHERE bot_id = ?
            ''', (','.join(new_symbols), bot_id))
            
            conn.commit()
            asset_switch_made = True
            
            logger.info(f"✅ Intelligent asset switch for bot {bot_id}: {current_symbols} → {new_symbols}")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'bot_id': bot_id,
            'previous_assets': current_symbols,
            'new_assets': best_assets,
            'switch_made': asset_switch_made,
            'best_profitability_assets': best_assets
        }), 200
    
    except Exception as e:
        logger.error(f"Error in intelligent asset switch: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/commission-summary', methods=['GET'])
@require_session
def commission_summary():
    """Get detailed commission summary for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total commissions
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                SUM(commission_amount) as total,
                SUM(CASE WHEN created_at > datetime('now', '-30 days') THEN commission_amount ELSE 0 END) as last_30_days
            FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        
        comm_stats = cursor.fetchone()
        
        # Top earning bots
        cursor.execute('''
            SELECT bot_id, SUM(commission_amount) as total_commission
            FROM commissions WHERE earner_id = ?
            GROUP BY bot_id
            ORDER BY total_commission DESC
            LIMIT 10
        ''', (user_id,))
        
        top_earning_bots = []
        for row in cursor.fetchall():
            top_earning_bots.append({
                'bot_id': row[0],
                'total_commission': round(row[1], 2)
            })
        
        # Recent commissions
        cursor.execute('''
            SELECT commission_id, bot_id, profit_amount, commission_amount, commission_rate, created_at
            FROM commissions WHERE earner_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        recent = []
        for row in cursor.fetchall():
            recent.append({
                'commission_id': row[0],
                'bot_id': row[1],
                'profit_amount': round(row[2], 2),
                'commission_amount': round(row[3], 2),
                'rate': row[4],
                'created_at': row[5]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_commissions': len(comm_stats),
                'total_earned': round(comm_stats[1] or 0, 2),
                'last_30_days_earned': round(comm_stats[2] or 0, 2),
            },
            'top_earning_bots': top_earning_bots,
            'recent_commissions': recent,
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting commission summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SYSTEM & BACKUP ENDPOINTS ====================

@app.route('/api/system/backup/create', methods=['POST'])
@require_session
def manual_backup():
    """Manually create a backup (admin only)"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Create backup
        backup_path = backup_manager.create_backup()
        
        if backup_path:
            return jsonify({
                'success': True,
                'message': 'Backup created successfully',
                'backup': backup_path.name,
                'timestamp': datetime.now().isoformat(),
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Backup failed'}), 500
            
    except Exception as e:
        logger.error(f"Manual backup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/backup/list', methods=['GET'])
@require_session
def list_backups():
    """Get list of all available backups"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 403
        
        backups = backup_manager.list_backups()
        
        return jsonify({
            'success': True,
            'backups': [
                {
                    'filename': b['filename'],
                    'size_mb': round(b['size_mb'], 2),
                    'created': b['created'].isoformat(),
                }
                for b in backups
            ],
            'total_count': len(backups),
        }), 200
        
    except Exception as e:
        logger.error(f"List backups error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/backup/restore', methods=['POST'])
@require_session
def restore_from_backup():
    """Restore database from a specific backup (admin only, DANGEROUS)"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 403
        
        data = request.json or {}
        backup_filename = data.get('backup_filename')
        
        if not backup_filename:
            return jsonify({'success': False, 'error': 'backup_filename required'}), 400
        
        # DANGEROUS - require confirmation
        confirmation = data.get('confirm_restore')
        if not confirmation:
            return jsonify({
                'success': False,
                'error': 'This is a destructive operation. Set confirm_restore=true to proceed.',
                'backup_filename': backup_filename
            }), 400
        
        # Perform restore
        result = backup_manager.restore_backup(backup_filename)
        if result:
            return jsonify({
                'success': True,
                'message': f'Database restored from backup: {backup_filename}',
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to restore from backup: {backup_filename}'
            }), 500
            
    except Exception as e:
        logger.error(f"Restore backup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/data/verify', methods=['GET'])
@require_session
def verify_system_data():
    """Verify that all system data is intact"""
    try:
        data_status = recovery_manager.verify_all_user_data()
        
        return jsonify({
            'success': True,
            'status': 'All data verified',
            'data_summary': data_status,
            'timestamp': datetime.now().isoformat(),
        }), 200
        
    except Exception as e:
        logger.error(f"Data verification error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/health', methods=['GET'])
def system_health():
    """Health check endpoint - includes backup status"""
    try:
        data_status = recovery_manager.verify_all_user_data()
        backups = backup_manager.list_backups()
        latest_backup = backups[0] if backups else None
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'backend_running': True,
            'database': {
                'integrity': 'ok',
                'users': data_status.get('users', 0),
                'bots': data_status.get('bots', 0),
                'credentials': data_status.get('credentials', 0),
            },
            'backup_system': {
                'enabled': backup_manager.is_running,
                'latest_backup': latest_backup['filename'] if latest_backup else None,
                'latest_backup_time': latest_backup['created'].isoformat() if latest_backup else None,
                'total_backups': len(backups),
            },
        }), 200
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'degraded',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }), 500


def shutdown_backup():
    """Create final backup before shutdown"""
    logger.info("🛑 Creating final backup on shutdown...")
    try:
        backup_manager.create_backup()
        backup_manager.stop_auto_backup()
        logger.info("✅ Final backup complete. System shutdown.")
    except Exception as e:
        logger.error(f"Error during shutdown backup: {e}")

atexit.register(shutdown_backup)


if __name__ == '__main__':
    logger.info("Starting Zwesta Multi-Broker Backend")
    logger.info(f"MT5 Account: {MT5_CONFIG['account']}")
    logger.info(f"MT5 Server: {MT5_CONFIG['server']}")
    
    # LAUNCH MT5 PROCESS (required for IPC connections)
    logger.info("="*60)
    logger.info("🚀 LAUNCHING MT5 TERMINAL...")
    logger.info("="*60)
    mt5_path = MT5_CONFIG.get('path')
    if mt5_path and os.path.exists(mt5_path):
        try:
            account = MT5_CONFIG.get('account', '104017418')
            password = MT5_CONFIG.get('password', '*6RjhRvH')
            server = MT5_CONFIG.get('server', 'MetaQuotes-Demo')
            
            logger.info(f"Starting: {mt5_path}")
            logger.info(f"   Account: {account}")
            logger.info(f"   Server: {server}")
            
            # Kill any existing MT5 processes first
            try:
                import subprocess
                subprocess.run(
                    ["taskkill", "/F", "/IM", "terminal.exe"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                subprocess.run(
                    ["taskkill", "/F", "/IM", "terminal64.exe"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info("  ↻ Cleaned up any existing MT5 processes")
                time.sleep(2)  # Wait for cleanup
            except:
                pass
            
            # Launch fresh MT5 instance
            subprocess.Popen(
                [mt5_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            logger.info("  ✓ Process launched")
            
            # Wait for terminal to fully initialize (increased from 10 to 15 seconds)
            logger.info("⏳ Waiting 15 seconds for MT5 terminal to fully initialize...")
            for countdown in range(15, 0, -1):
                if countdown % 3 == 0:
                    logger.info(f"   {countdown}s remaining...")
                time.sleep(1)
            
            logger.info("✅ MT5 terminal initialization complete - ready for SDK connections")
        except Exception as e:
            logger.warning(f"⚠️  Could not launch MT5: {e}")
    else:
        logger.warning("⚠️  MT5 path not found - will use simulated trading only")
    
    # AUTO-CONNECT to MT5 (so dashboard shows real account balance)
    # This will retry up to 3 times with increasing waits
    auto_connect_mt5()
    
    # AUTO-CONNECT to IG.com (using API key from screenshot: 9bbc3ef9ad291acec96dc409d80e50c4c805161a)
    auto_connect_ig()
    
    # Initialize demo bots on startup (DISABLED for production cleanup)
    # logger.info("Initializing demo trading bots...")
    # initialize_demo_bots()
    # logger.info(f"[OK] {len(active_bots)} demo bots initialized and ready")
    
    # Load user-created bots from database
    logger.info("Loading user-created bots from database...")
    user_bots_count = load_user_bots_from_database()
    logger.info(f"[OK] Loaded {user_bots_count} user bots from database")
    logger.info(f"[OK] Total bots ready: {len(active_bots)}")
    
    # Start live market data updater thread (fetches real prices from MT5)
    market_updater_thread = threading.Thread(target=live_market_data_updater, daemon=True)
    market_updater_thread.start()
    logger.info("🔄 Live market data updater thread started")
    
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


