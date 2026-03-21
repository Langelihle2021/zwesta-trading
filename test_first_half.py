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
import string
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from typing import Any, Dict, List, Optional
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

# ==================== GLOBAL MT5 CONNECTION LOCK ====================
# Prevents multiple simultaneous MT5 connections which cause IPC conflicts
# Only ONE thread should connect to MT5 at a time
mt5_connection_lock = threading.Lock()
logger.info("✅ MT5 connection lock initialized - ensures sequential MT5 connections")

# ==================== BOT CREATION LOCK ====================
# Prevents multiple simultaneous bot creations which compete for MT5 resources
# Only ONE bot should be created at a time to avoid MT5 lock contention
bot_creation_lock = threading.Lock()
logger.info("✅ Bot creation lock initialized - prevents concurrent bot creation")

app = Flask(__name__)
CORS(app)

# ==================== BOT CLEANUP & REPOPULATION ====================
def repopulate_active_bots():
    """Repopulate active_bots from user_bots table on backend startup"""
    try:
        restored_count = load_user_bots_from_database(enabled_only=True)
        logger.info(f"✅ Repopulated {restored_count} bots from database on startup.")
    except Exception as e:
        logger.error(f"❌ Error repopulating active_bots: {e}")

# Note: repopulate_active_bots() is called later after get_db_connection is defined

# ==================== CONFIGURATION ====================
# Environment Configuration (DEMO or LIVE)
ENVIRONMENT = os.getenv('TRADING_ENV', 'DEMO')  # Set TRADING_ENV=LIVE in production
AUTO_RESTART_BOTS_ON_STARTUP = os.getenv('AUTO_RESTART_BOTS_ON_STARTUP', 'false').lower() == 'true'
BOT_STARTUP_RESTART_DELAY_SECONDS = max(0.0, float(os.getenv('BOT_STARTUP_RESTART_DELAY_SECONDS', '2')))
BOT_STARTUP_RESTART_LIMIT = max(0, int(os.getenv('BOT_STARTUP_RESTART_LIMIT', '0')))

# API Security Configuration
API_KEY = os.getenv('API_KEY', 'your_generated_api_key_here_change_in_production')

# MT5 Credentials - DEMO (default)
# Exness MT5 Configuration Only (NO standalone MT5 fallback)
MT5_CONFIG = {
    'broker': 'Exness',
    'account': 298997455,  # Demo account
    'password': 'Zwesta@1985',
    'server': 'Exness-MT5Trial9',  # Demo server
    'path': None
}

# Try to find Exness terminal specifically (PRIORITY: broker-specific only)
exness_paths = [
    r'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe',
    r'C:\Program Files\Exness MT5\terminal64.exe',
    r'C:\Program Files (x86)\Exness MT5\terminal64.exe',
    r'C:\MT5\Exness\terminal64.exe',
]
for path in exness_paths:
    if os.path.exists(path):
        MT5_CONFIG['path'] = path
        logger.info(f"Found Exness MT5 at: {path}")
        break

if MT5_CONFIG['path'] is None:
    logger.warning("⚠️  Exness MT5 not found in common paths - ensure Exness MT5 is installed")
    # Do NOT fallback to generic MT5 - require Exness-specific installation

# XM Global MT5 Configuration - Support DEMO and LIVE modes
XM_CONFIG = {
    'broker': 'XM Global',
    'account': int(os.getenv('XM_ACCOUNT', '12345678')),  # Demo account placeholder
    'password': os.getenv('XM_PASSWORD', ''),
    'server': os.getenv('XM_SERVER', 'XMGlobal-MT5Demo'),  # Demo server
    'path': None
}

# Try to find XM Global terminal specifically
xm_paths = [
    r'C:\Program Files\MetaTrader 5 XM\terminal64.exe',
    r'C:\Program Files\XM Global MT5\terminal64.exe',
    r'C:\Program Files (x86)\XM MT5\terminal64.exe',
    r'C:\MT5\XM\terminal64.exe',
    r'C:\Program Files\MetaTrader 5\terminal64.exe',  # Generic MT5 can work with XM creds
]
for path in xm_paths:
    if os.path.exists(path):
        XM_CONFIG['path'] = path
        logger.info(f"Found XM Global MT5 at: {path}")
        break

if XM_CONFIG['path'] is None:
    logger.warning("⚠️  XM Global MT5 not found in common paths - ensure MetaTrader 5 is installed with XM credentials")

# Exness Credentials - Support DEMO and LIVE modes
if ENVIRONMENT == 'LIVE':
    MT5_CONFIG = {
        'broker': 'Exness',
        'account': int(os.getenv('EXNESS_ACCOUNT', '295619855')),  # Live account: 295619855
        'password': os.getenv('EXNESS_PASSWORD', ''),  # Set via environment variable
        'server': os.getenv('EXNESS_SERVER', 'Exness-Real'),  # Live server
        'path': os.getenv('EXNESS_PATH', MT5_CONFIG.get('path'))
    }
    if not MT5_CONFIG['password']:
        logger.error("[ALERT] LIVE MODE: EXNESS_PASSWORD environment variable not set!")
else:
    # DEMO mode - uses default credentials above
    logger.info(f"[DEMO] Using Exness demo credentials - Account: {MT5_CONFIG['account']}")
    logger.info(f"[DEMO] Server: {MT5_CONFIG['server']}")
    logger.info(f"[DEMO] Live account available at: 295619855 (set ENVIRONMENT=LIVE to use)")

# Removed: IG.com Broker Configuration (IG Markets integration removed)

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
    logger.warning(f"[ALERT] LIVE TRADING MODE - Exness Account: {MT5_CONFIG['account']}")
else:
    logger.info(f"[DEMO] DEMO MODE - Exness Account: {MT5_CONFIG['account']} (Demo)")
    logger.info(f"[DEMO] Available in DEMO: 298997455")
    logger.info(f"[DEMO] Available in LIVE: 295619855")

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
        # Get session token from header - CRITICAL DEBUGGING FOR 401 ISSUES
        session_token = request.headers.get('X-Session-Token')
        
        # Log all headers to diagnose missing token issue
        if not session_token:
            logger.warning(f"🚨 [CRITICAL] MISSING X-Session-Token for {request.method} {request.path}")
            logger.warning(f"📋 Headers received: {dict(request.headers)}")
            logger.warning(f"🌐 Client IP: {request.remote_addr}")
        else:
            logger.debug(f"[SESSION CHECK] Endpoint: {request.endpoint}, Token received: {session_token[:20]}...")
        
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

def require_admin(f):
    """Decorator to require admin authorization"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key for admin verification
        valid, message = validate_api_key()
        if not valid:
            return jsonify({'success': False, 'error': 'Admin authentication required'}), 401
        
        # Optionally add additional admin role check from database if needed
        # For now, API key validation is sufficient for admin endpoints
        return f(*args, **kwargs)
    
    return decorated_function

class BrokerType(Enum):
    """Supported broker types"""
    METATRADER5 = "mt5"
    INTERACTIVE_BROKERS = "ib"
    BINANCE = "binance"
    OANDA = "oanda"
    XM = "xm"
    PEPPERSTONE = "pepperstone"
    FXOPEN = "fxopen"
    EXNESS = "exness"
    DARWINEX = "darwinex"

    FXM = "fxm"
    AVATRADE = "avatrade"
    FPMARKETS = "fpmarkets"


# ==================== DATABASE SETUP ====================
# ==================== DATABASE SETUP ====================
DATABASE_PATH = r'C:\backend\zwesta_trading.db'

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


@app.route('/api/bots/delete-all', methods=['POST'])
@require_session
def delete_all_user_bots():
    """Delete ALL bots for the current user to start fresh"""
    try:
        user_id = request.user_id  # From session decorator
        
        # Get all bot IDs for this user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT bot_id FROM user_bots WHERE user_id = ?', (user_id,))
        bot_ids = [row[0] for row in cursor.fetchall()]
        
        # Delete all bots from database
        cursor.execute('DELETE FROM user_bots WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        # Stop and remove from memory
        removed_count = 0
        for bot_id in bot_ids:
            if bot_id in active_bots:
                # Stop the bot thread if running
                bot = active_bots[bot_id]
                if bot.get('running'):
                    bot['stop_event'].set()
                    if bot.get('thread') and bot['thread'].is_alive():
                        bot['thread'].join(timeout=2)
                del active_bots[bot_id]
                removed_count += 1
        
        logger.info(f"✅ Deleted {len(bot_ids)} bots for user {user_id} ({removed_count} were running)")
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {len(bot_ids)} bots',
            'deleted_count': len(bot_ids),
            'stopped_count': removed_count
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting all bots for user: {e}", exc_info=True)
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
            symbols TEXT DEFAULT 'EURUSDm',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    cursor.execute("PRAGMA table_info(user_bots)")
    user_bots_columns = {row[1] for row in cursor.fetchall()}
    if 'runtime_state' not in user_bots_columns:
        cursor.execute("ALTER TABLE user_bots ADD COLUMN runtime_state TEXT")
    
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

    # Exness withdrawals table - tracks Exness MT5 profit withdrawals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exness_withdrawals (
            withdrawal_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            broker_account_id TEXT NOT NULL,
            withdrawal_type TEXT NOT NULL,
            source_type TEXT,
            profit_from_trades REAL DEFAULT 0,
            commission_earned REAL DEFAULT 0,
            total_amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            net_amount REAL,
            status TEXT DEFAULT 'pending',
            withdrawal_method TEXT,
            payment_details TEXT,
            created_at TEXT,
            submitted_at TEXT,
            completed_at TEXT,
            admin_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Exness trade profits table - tracks profits from closed trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exness_trade_profits (
            profit_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            broker_account_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            volume REAL NOT NULL,
            side TEXT,
            profit_loss REAL NOT NULL,
            commission REAL DEFAULT 0,
            pnl_percentage REAL,
            trade_duration_seconds INTEGER,
            closed_at TEXT,
            withdrawal_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (withdrawal_id) REFERENCES exness_withdrawals(withdrawal_id)
        )
    ''')
    
    # User wallets table - tracks user's earned profits available for withdrawal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_wallets (
            wallet_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            balance REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            last_updated TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Wallet transactions table - audit trail for wallet changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            transaction_id TEXT PRIMARY KEY,
            wallet_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT,
            source_withdrawal_id TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT,
            FOREIGN KEY (wallet_id) REFERENCES user_wallets(wallet_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (source_withdrawal_id) REFERENCES exness_withdrawals(withdrawal_id)
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

    # Commission Configuration table — dynamic commission rates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_config (
            config_id TEXT PRIMARY KEY,
            developer_id TEXT DEFAULT 'developer',
            developer_direct_rate REAL DEFAULT 0.25,
            developer_referral_rate REAL DEFAULT 0.20,
            recruiter_rate REAL DEFAULT 0.05,
            ig_commission_enabled BOOLEAN DEFAULT 1,
            ig_developer_rate REAL DEFAULT 0.20,
            ig_recruiter_rate REAL DEFAULT 0.05,
            multi_tier_enabled BOOLEAN DEFAULT 0,
            tier2_rate REAL DEFAULT 0.02,
            updated_at TEXT,
            updated_by TEXT
        )
    ''')

    # Seed default config if empty
    cursor.execute('SELECT COUNT(*) FROM commission_config')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO commission_config
            (config_id, developer_id, developer_direct_rate, developer_referral_rate,
             recruiter_rate, ig_commission_enabled, ig_developer_rate, ig_recruiter_rate,
             multi_tier_enabled, tier2_rate, updated_at)
            VALUES ('default', 'developer', 0.25, 0.20, 0.05, 1, 0.20, 0.05, 0, 0.02, ?)
        ''', (datetime.now().isoformat(),))
        logger.info("✅ Seeded default commission config")

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

    # Shared broker withdrawal notifications table (used by OANDA/FXCM/Binance services)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broker_withdrawal_notifications (
            notification_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            broker_name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            message TEXT,
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
    
    # Trading symbols management table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_symbols (
            symbol_id TEXT PRIMARY KEY,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            symbol_type TEXT NOT NULL,
            broker TEXT,
            min_price REAL,
            max_price REAL,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # Bot strategies configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_strategies (
            strategy_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            bot_id TEXT,
            strategy_name TEXT NOT NULL,
            description TEXT,
            strategy_type TEXT,
            parameters TEXT,
            symbols TEXT,
            risk_level TEXT,
            profit_target REAL,
            stop_loss REAL,
            is_active BOOLEAN DEFAULT 1,
            performance_stats TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # User accounts management table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_type TEXT,
            broker TEXT,
            account_number TEXT,
            account_balance REAL DEFAULT 0,
            available_balance REAL DEFAULT 0,
            total_profit REAL DEFAULT 0,
            is_primary BOOLEAN DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # User trading settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_trading_settings (
            setting_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            risk_profile TEXT,
            daily_loss_limit REAL,
            max_position_size REAL,
            leverage INTEGER DEFAULT 1,
            auto_trade_enabled BOOLEAN DEFAULT 0,
            notifications_enabled BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Bot trade history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            order_type TEXT NOT NULL,
            volume REAL DEFAULT 0,
            price REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            commission REAL DEFAULT 0,
            swap REAL DEFAULT 0,
            ticket INTEGER,
            time_open TEXT,
            time_close TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Migration: Add trade_data and timestamp columns to trades table if missing
    cursor.execute("PRAGMA table_info(trades)")
    trades_columns = [col[1] for col in cursor.fetchall()]
    if 'trade_data' not in trades_columns:
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN trade_data TEXT')
            logger.info("✅ Migration: Added trade_data column to trades")
        except Exception as e:
            logger.debug(f"trade_data column might already exist: {e}")
    if 'timestamp' not in trades_columns:
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN timestamp INTEGER')
            logger.info("✅ Migration: Added timestamp column to trades")
        except Exception as e:
            logger.debug(f"timestamp column might already exist: {e}")

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
    
    db_path = r'C:\backend\zwesta_trading.db'
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
        # CRITICAL FIX: DO NOT launch terminal on every connection attempt!
        # Terminal should only be launched ONCE during backend startup
        # Reuse the existing terminal for all subsequent connections
        broker = canonicalize_broker_name(credentials.get('broker', 'Exness'))
        
        # Check if terminal is already running (avoid duplicate launches)
        try:
            import subprocess, sys, os
            # Simply skip terminal launch - assume it was launched at startup
            # If terminal crashes, MT5Connection.connect() will timeout and retry
            logger.info(f"[MT5 Terminal] Using Exness MT5 terminal (launched on backend startup)")
        except Exception as e:
            logger.error(f"[MT5 Terminal Manager] Error checking terminal: {e}")
        
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            # Use path from MT5_CONFIG or credentials
            self.mt5_path = credentials.get('path') or MT5_CONFIG.get('path')
        except ImportError:
            logger.error("MetaTrader5 not installed")
            self.mt5 = None

    def connect(self) -> bool:
        """
        Connect to MT5 with retry logic and better error handling
        CRITICAL: Uses global lock to prevent simultaneous MT5 connections
        """
        global mt5_connection_lock
        
        # Acquire lock with timeout to prevent indefinite hangs when multiple bots compete
        logger.info(f"⏳ Waiting for exclusive MT5 connection lock (max 30 seconds, sequential mode)...")
        lock_acquired = mt5_connection_lock.acquire(timeout=30.0)  # Timeout after 30 seconds
        
        if not lock_acquired:
            logger.warning(f"⚠️ TIMEOUT: Could not acquire MT5 lock after 30 seconds - another bot may be stuck")
            logger.warning(f"   Skipping this trade cycle - will retry in {self.credentials.get('tradingInterval', 300)} seconds")
            return False  # Return False to signal connection failed, bot will retry next cycle
        
        try:
            logger.info(f"✅ Acquired MT5 connection lock - proceeding with connection")
            return self._connect_with_lock()
        finally:
            # CRITICAL: Always release the lock, even if connection fails
            mt5_connection_lock.release()
    
    def _connect_with_lock(self) -> bool:
        """Internal connection method - always called within mt5_connection_lock
        
        SAFE CONNECTION STRATEGY:
        1. Check if SDK is already initialized (terminal_info works) → skip initialize
        2. Check if already logged into the correct account → skip login, return True
        3. If SDK not initialized, initialize ONCE with short wait (terminal already running)
        4. Login with credentials
        5. NEVER call mt5.shutdown() or taskkill — that kills ALL connections globally
        """
        try:
            if not self.mt5:
                logger.error("MetaTrader5 SDK not available")
                return False

            # Fix: accept both 'account' and 'account_number' credential keys
            account = self.credentials.get('account') or self.credentials.get('account_number') or MT5_CONFIG['account']
            password = self.credentials.get('password') or MT5_CONFIG['password']
            server = self.credentials.get('server') or MT5_CONFIG['server']
            
            # Ensure account is an integer for MT5 login
            try:
                account = int(account)
            except (ValueError, TypeError):
                logger.error(f"❌ Invalid MT5 account number: {account}")
                return False
            
            logger.info(f"MT5 connection: Account={account}, Server={server}")
            
            # ─── STEP 1: Check if SDK is already initialized ───
            sdk_ready = False
            try:
                term_info = self.mt5.terminal_info()
                if term_info is not None:
                    sdk_ready = True
                    logger.info(f"  ✓ MT5 SDK already initialized (terminal running)")
            except Exception:
                pass
            
            # ─── STEP 2: If SDK ready, check if already logged into correct account ───
            if sdk_ready:
                try:
                    acct_info = self.mt5.account_info()
                    if acct_info is not None and acct_info.login == account:
                        # Already connected to the right account — no action needed
                        self.connected = True
                        self.get_account_info()
                        logger.info(f"  ♻️  Already logged into account {account} — reusing connection")
                        self._subscribe_symbols()
                        return True
                    elif acct_info is not None:
                        logger.info(f"  ↻ SDK connected to account {acct_info.login}, need to switch to {account}")
                except Exception:
                    logger.debug(f"  Could not check current account — will attempt login")
            
            # ─── STEP 3: Initialize SDK only if not already initialized ───
            if not sdk_ready:
                if not self.mt5_path:
                    logger.error("❌ No Exness MT5 path configured")
                    return False
                
                normalized_path = str(self.mt5_path).strip().strip('"').strip("'")
                if os.path.isdir(normalized_path):
                    candidate_64 = os.path.join(normalized_path, 'terminal64.exe')
                    candidate_32 = os.path.join(normalized_path, 'terminal.exe')
                    if os.path.isfile(candidate_64):
                        normalized_path = candidate_64
                    elif os.path.isfile(candidate_32):
                        normalized_path = candidate_32

                if not os.path.isfile(normalized_path):
                    logger.error(f"❌ MT5 terminal not found: {normalized_path}")
                    return False
                
                init_ok = self.mt5.initialize(path=normalized_path)
                if not init_ok:
                    logger.warning(f"  ✗ MT5 initialization failed: {self.mt5.last_error()}")
                    # Short wait and one retry — terminal may be starting up
                    time.sleep(5)
                    init_ok = self.mt5.initialize(path=normalized_path)
                    if not init_ok:
                        logger.error(f"  ✗ MT5 initialization failed on retry: {self.mt5.last_error()}")
                        return False
                
                self.mt5_path = normalized_path
                logger.info(f"  ✓ MT5 SDK initialized (path: {self.mt5_path})")
                
                # Brief wait for IPC stabilization — terminal is already running from startup
                ipc_wait = 5
                logger.info(f"  ⏳ Waiting {ipc_wait}s for MT5 IPC stabilization...")
                time.sleep(ipc_wait)
            
            # ─── STEP 4: Login to account ───
            logger.info(f"  🔐 Attempting login to account {account}...")
            try:
                login_result = self.mt5.login(account, password=password, server=server)
                login_error = self.mt5.last_error()
                logger.info(f"     Login result: {login_result}, Error: {login_error}")
            except Exception as login_ex:
                logger.warning(f"  ✗ Login exception: {login_ex}")
                login_result = False
            
            if login_result:
                self.connected = True
                self.get_account_info()
                logger.info(f"✅ Connected to MT5 account {account}")
                self._subscribe_symbols()
                return True
            
            # Password login failed — try guest login as fallback
            logger.warning(f"  ✗ Password login failed, trying guest login...")
            try:
                login_result = self.mt5.login(account, server=server)
                login_error = self.mt5.last_error()
                logger.info(f"     Guest login result: {login_result}, Error: {login_error}")
            except Exception as guest_ex:
                logger.warning(f"  ✗ Guest login exception: {guest_ex}")
                login_result = False
            
            if login_result:
                self.connected = True
                self.get_account_info()
                logger.info(f"✅ Connected to MT5 account {account} (guest mode)")
                self._subscribe_symbols()
                return True
            
            # Login failed — return False but DO NOT call mt5.shutdown() or taskkill
            # The SDK singleton is shared; shutting down would kill ALL connections
            logger.error(f"❌ MT5 login failed for account {account} — will retry next trade cycle")
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
        failed_symbols = []
        
        for symbol in VALID_SYMBOLS:
            try:
                if self.mt5.symbol_select(symbol, True):
                    subscribed += 1
                else:
                    logger.warning(f"⚠️  Could not subscribe to {symbol} - may not be available on this account/broker")
                    failed += 1
                    failed_symbols.append(symbol)
            except Exception as e:
                logger.warning(f"⚠️  Error subscribing to {symbol}: {e}")
                failed += 1
                failed_symbols.append(symbol)
        
        logger.info(f"✅ Symbol subscription complete: {subscribed}/{len(VALID_SYMBOLS)} symbols ready for trading")
        if failed > 0:
            logger.warning(f"⚠️  {failed} symbols unavailable: {failed_symbols}")
            logger.warning(f"   These symbols may not be tradable on your account/broker")
            available = [s for s in VALID_SYMBOLS if s not in failed_symbols]
            logger.warning(f"   Available symbols: {available}")

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
                test_symbol = "EURUSDm"  # Use actual Exness symbol with "m" suffix
                if not self.mt5.symbol_select(test_symbol, True):
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: symbol_select({test_symbol}) failed")
                    time.sleep(check_interval)
                    continue
                
                tick = self.mt5.symbol_info_tick(test_symbol)
                if tick is None:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: tick data not available")
                    time.sleep(check_interval)
                    continue
                
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: {test_symbol} tick OK (bid={tick.bid}, ask={tick.ask})")
                
                # STEP 3: Check symbol info (trading rules, hours, etc)
                symbol_info = self.mt5.symbol_info(test_symbol)
                if symbol_info is None:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: symbol_info({test_symbol}) = None")
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
        """Get account information - Always return USD currency"""
        try:
            if not self.connected:
                return None

            info = self.mt5.account_info()
            self.account_info = {
                'accountNumber': info.login,
                'balance': round(float(info.balance), 2),
                'equity': round(float(info.equity), 2),
                'margin': round(float(info.margin), 2),
                'marginFree': round(float(info.margin_free), 2),
                'marginLevel': round(float(info.margin_level), 2),
                'currency': 'USD',  # Force USD
                'leverage': info.leverage,
                'broker': info.server,
                'displayCurrency': 'USD',  # Explicit display currency
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

    def is_symbol_available(self, symbol: str) -> bool:
        """Check if a symbol is available for trading on this account"""
        try:
            if not self.connected or not self.mt5:
                return False
            # Try to select the symbol and get tick data
            if not self.mt5.symbol_select(symbol, True):
                return False
            tick = self.mt5.symbol_info_tick(symbol)
            return tick is not None
        except:
            return False
    
    def get_fallback_symbol(self) -> str:
        """Get the first available symbol from VALID_SYMBOLS for fallback"""
        for symbol in sorted(VALID_SYMBOLS):
            if self.is_symbol_available(symbol):
                return symbol
        return "EURUSDm"  # Last resort fallback

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        """
        Place order on MT5 with enhanced validation and fallback logic
        """
        try:
            if not self.connected:
                return {'success': False, 'error': 'Not connected'}

            # STEP 1: Validate requested symbol before attempting order
            original_symbol = symbol
            if not self.is_symbol_available(symbol):
                logger.warning(f"⚠️  Symbol {symbol} is NOT available - checking if it's in VALID_SYMBOLS")
                if symbol in VALID_SYMBOLS:
                    logger.warning(f"   Symbol {symbol} IS in VALID_SYMBOLS but NOT available on this account")
                    logger.warning(f"   This may be due to: insufficient permissions, broker restrictions, or initialization delay")
                    
                    # ❌ CRITICAL FIX: Don't silently fall back for important symbols like BTC/ETH
                    # This was causing BTC trades to execute as EUR/USD instead
                    critical_symbols = {'BTCUSDm', 'ETHUSDm'}  # High-value symbols that must execute correctly
                    if symbol in critical_symbols:
                        logger.error(f"❌ CRITICAL: {symbol} requested but NOT available - refusing to fall back to another symbol")
                        logger.error(f"   User requested {symbol}, but system would execute on wrong symbol if we fell back")
                        logger.error(f"   This indicates MT5 initialization incomplete. Waiting for symbol to load...")
                        return {'success': False, 'error': f'{symbol} not yet available on MT5. Please ensure Exness MT5 terminal is connected and symbols are loaded. Retry in a few seconds.', 'retry_after_seconds': 5}
                else:
                    logger.warning(f"   Symbol {symbol} is NOT in VALID_SYMBOLS (list: {sorted(VALID_SYMBOLS)})")
                
                # For non-critical symbols, try fallback
                if original_symbol not in critical_symbols:
                    fallback = self.get_fallback_symbol()
                    logger.info(f"🔄 Falling back from {original_symbol} to {fallback}")
                    symbol = fallback
                    
                    if not self.is_symbol_available(symbol):
                        return {'success': False, 'error': f'Symbol {original_symbol} not available, and fallback {fallback} also unavailable'}

            # STEP 2: Enforce minimum volume for specific symbols
            min_volumes = {
                'OILK': 1.0,
                'XAUUSD': 0.01,
                'XAGUSD': 0.1,
                'XAUUSDm': 0.01,
                'XAGUSDm': 0.1,
                # Add more as needed
            }
            min_volume = min_volumes.get(symbol, 0.01)
            if volume < min_volume:
                logger.info(f"Adjusting volume for {symbol}: requested={volume}, min={min_volume}")
                volume = min_volume

            # STEP 3: Select symbol and get tick data
            if not self.mt5.symbol_select(symbol, True):
                return {'success': False, 'error': f'Failed to select symbol {symbol}'}

            # Get the tick data (bid/ask prices)
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

            # TIMEOUT WRAPPER: order_send can hang for 10+ seconds if MT5 is busy/disconnected
            # Set a 5-second timeout to fail fast instead of freezing bot
            import threading
            result = None
            result_holder = []
            error_holder = []
            
            def mt5_order_with_timeout():
                try:
                    res = self.mt5.order_send(request_dict)
                    result_holder.append(res)
                except Exception as e:
                    error_holder.append(e)
            
            thread = threading.Thread(target=mt5_order_with_timeout, daemon=True)
            thread.start()
            thread.join(timeout=5.0)  # Wait max 5 seconds
            
            if error_holder:
                logger.error(f"MT5 order_send exception: {error_holder[0]}")
                result = None
            elif result_holder:
                result = result_holder[0]
            else:
                logger.error(f"MT5 order_send TIMEOUT after 5 seconds - terminal likely disconnected")
                result = None

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
                # Retcode 10027 = AutoTrading disabled in MT5 terminal
                if result.retcode == 10027:
                    return {
                        'success': False,
                        'error': 'AutoTrading is disabled in MT5 terminal. Enable it by clicking the AutoTrading button in the MT5 toolbar, or run: mt5.terminal_info().trade_allowed',
                        'retcode': 10027,
                        'action_required': 'Enable AutoTrading in MT5 terminal'
                    }
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


# Removed: IGConnection class (IG Markets integration removed)


class BinanceConnection(BrokerConnection):
    """Binance broker connection via REST API."""

    def __init__(self, credentials: Dict = None):
        if credentials is None:
            credentials = {
                'api_key': os.getenv('BINANCE_API_KEY', ''),
                'api_secret': os.getenv('BINANCE_API_SECRET', ''),
                'is_live': False,
                'market': 'spot',
            }

        super().__init__(BrokerType.BINANCE, credentials)
        self.market = (credentials.get('market') or credentials.get('server') or 'spot').lower()
        is_live = bool(credentials.get('is_live', False))
        self.base_url = 'https://api.binance.com/api' if is_live else 'https://testnet.binance.vision/api'
        self.fapi_url = 'https://fapi.binance.com/fapi' if is_live else 'https://testnet.binancefuture.com/fapi'

    def _headers(self) -> Dict:
        return {
            'X-MBX-APIKEY': self.credentials.get('api_key', ''),
            'Content-Type': 'application/json',
        }

    def _sign_params(self, params: Dict) -> Dict:
        import hmac
        from urllib.parse import urlencode

        signed_params = dict(params)
        signed_params['timestamp'] = int(time.time() * 1000)
        query_string = urlencode(signed_params)
        signature = hmac.new(
            str(self.credentials.get('api_secret', '')).encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        signed_params['signature'] = signature
        return signed_params

    def _normalize_symbol(self, symbol: str) -> Optional[str]:
        if not symbol:
            return None

        symbol = symbol.upper().replace('/', '').replace('_', '')
        symbol_map = {
            'BTCUSD': 'BTCUSDT',
            'ETHUSD': 'ETHUSDT',
            'BNBUSD': 'BNBUSDT',
            'SOLUSD': 'SOLUSDT',
            'XRPUSD': 'XRPUSDT',
            'ADAUSD': 'ADAUSDT',
            'DOGEUSD': 'DOGEUSDT',
        }
        if symbol in symbol_map:
            return symbol_map[symbol]
        if symbol.endswith(('USDT', 'BUSD', 'USDC', 'BTC', 'ETH')):
            return symbol
        return None

    def connect(self) -> bool:
        try:
            import requests

            if not self.credentials.get('api_key') or not self.credentials.get('api_secret'):
                logger.error('Binance: Missing API key or API secret')
                return False

            resp = requests.get(
                f"{self.base_url}/v3/account",
                headers=self._headers(),
                params=self._sign_params({}),
                timeout=15,
            )
            if resp.status_code == 200:
                self.connected = True
                self.get_account_info()
                return True

            logger.error(f"Binance authentication failed: {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to Binance: {e}")
            return False

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_account_info(self) -> Dict:
        try:
            import requests

            if not self.connected:
                return {}

            resp = requests.get(
                f"{self.base_url}/v3/account",
                headers=self._headers(),
                params=self._sign_params({}),
                timeout=10,
            )
            if resp.status_code == 200:
                acct = resp.json()
                balances = acct.get('balances', [])
                usdt = next((b for b in balances if b.get('asset') == 'USDT'), {'free': '0', 'locked': '0'})
                balance = float(usdt.get('free', 0)) + float(usdt.get('locked', 0))
                self.account_info = {
                    'account_id': self.credentials.get('account_id') or self.credentials.get('account_number') or 'BINANCE',
                    'balance': balance,
                    'equity': balance,
                    'margin_free': float(usdt.get('free', 0)),
                    'currency': 'USDT',
                    'broker': 'Binance',
                }
                return self.account_info
        except Exception as e:
            logger.error(f"Error getting Binance account info: {e}")

        return {}

    def get_positions(self) -> List[Dict]:
        try:
            import requests

            if not self.connected:
                return []

            if self.market == 'futures':
                resp = requests.get(
                    f"{self.fapi_url}/v2/positionRisk",
                    headers=self._headers(),
                    params=self._sign_params({}),
                    timeout=10,
                )
                if resp.status_code == 200:
                    result = []
                    for pos in resp.json():
                        amount = float(pos.get('positionAmt', 0))
                        if amount == 0:
                            continue
                        result.append({
                            'deal_id': pos.get('symbol', ''),
                            'symbol': pos.get('symbol', ''),
                            'type': 'BUY' if amount > 0 else 'SELL',
                            'size': abs(amount),
                            'level': float(pos.get('entryPrice', 0)),
                            'profit_loss': float(pos.get('unRealizedProfit', 0)),
                            'broker': 'Binance',
                        })
                    return result
            else:
                resp = requests.get(
                    f"{self.base_url}/v3/openOrders",
                    headers=self._headers(),
                    params=self._sign_params({}),
                    timeout=10,
                )
                if resp.status_code == 200:
                    return [{
                        'deal_id': str(order.get('orderId', '')),
                        'symbol': order.get('symbol', ''),
                        'type': order.get('side', ''),
                        'size': float(order.get('origQty', 0)),
                        'level': float(order.get('price', 0)),
                        'profit_loss': 0,
                        'broker': 'Binance',
                    } for order in resp.json()]
        except Exception as e:
            logger.error(f"Error getting Binance positions: {e}")

        return []

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        try:
            import requests

            if not self.connected:
                return {'success': False, 'error': 'Not connected to Binance'}

            instrument = self._normalize_symbol(symbol)
            if not instrument:
                return {'success': False, 'error': f'Unsupported Binance symbol: {symbol}. Use crypto pairs like BTCUSDT.'}

            quantity = max(round(float(volume), 4), 0.001)
            params = {
                'symbol': instrument,
                'side': order_type.upper(),
                'type': 'MARKET',
                'quantity': str(quantity),
            }
            endpoint = f"{self.fapi_url}/v1/order" if self.market == 'futures' else f"{self.base_url}/v3/order"
            resp = requests.post(endpoint, headers=self._headers(), params=self._sign_params(params), timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                return {
                    'success': True,
                    'orderId': result.get('orderId', ''),
                    'symbol': instrument,
                    'type': order_type.upper(),
                    'broker': 'Binance',
                }
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Error placing Binance order: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, position_id: str) -> Dict:
        try:
            import requests
            if not self.connected:
                return {'success': False, 'error': 'Not connected to Binance'}
            if self.market == 'futures':
                positions = self.get_positions()
                pos = next((p for p in positions if str(p.get('deal_id')) == str(position_id)), None)
                if not pos:
                    return {'success': False, 'error': f'Futures position {position_id} not found'}
                close_side = 'SELL' if pos['type'] == 'BUY' else 'BUY'
                params = {
                    'symbol': pos['symbol'],
                    'side': close_side,
                    'type': 'MARKET',
                    'quantity': str(pos['size']),
                    'reduceOnly': 'true',
                }
                resp = requests.post(
                    f'{self.fapi_url}/v1/order',
                    headers=self._headers(),
                    params=self._sign_params(params),
                    timeout=15,
                )
            else:
                params = self._sign_params({'orderId': position_id})
                resp = requests.delete(
                    f'{self.base_url}/v3/openOrders',
                    headers=self._headers(),
                    params=params,
                    timeout=15,
                )
            if resp.status_code in (200, 201):
                return {'success': True, 'position_id': position_id, 'broker': 'Binance'}
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f'Error closing Binance position: {e}')
            return {'success': False, 'error': str(e)}

    def get_trades(self) -> List[Dict]:
        try:
            import requests
            if not self.connected:
                return []
            result = []
            endpoint = f'{self.fapi_url}/v1/userTrades' if self.market == 'futures' else f'{self.base_url}/v3/myTrades'
            watch_symbols = getattr(self, '_active_symbols', ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'])
            for symbol in watch_symbols[:5]:  # limit to avoid rate limits
                try:
                    resp = requests.get(
                        endpoint,
                        headers=self._headers(),
                        params=self._sign_params({'symbol': symbol, 'limit': 20}),
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        for trade in resp.json():
                            result.append({
                                'deal_id': str(trade.get('id', '')),
                                'symbol': trade.get('symbol', ''),
                                'type': 'BUY' if trade.get('isBuyer') else 'SELL',
                                'volume': float(trade.get('qty', 0)),
                                'price': float(trade.get('price', 0)),
                                'profit': float(trade.get('realizedPnl', 0)),
                                'time': trade.get('time'),
                                'broker': 'Binance',
                            })
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.error(f'Error getting Binance trades: {e}')
            return []


class FXCMConnection(BrokerConnection):
    """FXCM broker connection via REST API."""

    def __init__(self, credentials: Dict = None):
        if credentials is None:
            credentials = {
                'api_key': os.getenv('FXCM_API_TOKEN', ''),
                'account_number': os.getenv('FXCM_ACCOUNT_ID', ''),
                'is_live': False,
            }

        super().__init__(BrokerType.FXM, credentials)
        is_live = bool(credentials.get('is_live', False))
        self.base_url = 'https://api.fxcm.com' if is_live else 'https://api-demo.fxcm.com'

    def _headers(self, content_type: bool = True) -> Dict:
        headers = {
            'Authorization': f"Bearer {self.credentials.get('api_key', '')}",
            'Accept': 'application/json',
        }
        if content_type:
            headers['Content-Type'] = 'application/json'
        return headers

    def _normalize_symbol(self, symbol: str) -> Optional[str]:
        if not symbol:
            return None

        symbol = symbol.upper().replace('_', '').replace('/', '')
        symbol_map = {
            'EURUSD': 'EUR/USD',
            'GBPUSD': 'GBP/USD',
            'USDJPY': 'USD/JPY',
            'USDCHF': 'USD/CHF',
            'AUDUSD': 'AUD/USD',
            'NZDUSD': 'NZD/USD',
            'USDCAD': 'USD/CAD',
            'XAUUSD': 'XAU/USD',
            'XAGUSD': 'XAG/USD',
        }
        if symbol in symbol_map:
            return symbol_map[symbol]
        if len(symbol) == 6 and symbol.isalpha():
            return f"{symbol[:3]}/{symbol[3:]}"
        return None

    def _display_symbol(self, instrument: str) -> str:
        return (instrument or '').replace('/', '').upper()

    def connect(self) -> bool:
        try:
            import requests

            if not self.credentials.get('api_key'):
                logger.error('FXCM: Missing API token')
                return False

            resp = requests.get(
                f"{self.base_url}/trading/get_model",
                headers=self._headers(content_type=False),
                params={'models': 'Account'},
                timeout=15,
            )
            if resp.status_code == 200:
                self.connected = True
                self.get_account_info()
                return True
            logger.error(f"FXCM authentication failed: {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to FXCM: {e}")
            return False

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_account_info(self) -> Dict:
        try:
            import requests

            if not self.connected:
                return {}

            resp = requests.get(
                f"{self.base_url}/trading/get_model",
                headers=self._headers(content_type=False),
                params={'models': 'Account'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                accounts = data.get('accounts', data.get('response', {}).get('accounts', []))
                account_id = str(self.credentials.get('account_number', '') or '')
                account = {}
                if isinstance(accounts, list):
                    for item in accounts:
                        if str(item.get('accountId', '')) == account_id or not account_id:
                            account = item
                            break
                    if not account and accounts:
                        account = accounts[0]
                if account and not self.credentials.get('account_number'):
                    self.credentials['account_number'] = str(account.get('accountId', ''))
                self.account_info = {
                    'account_id': account.get('accountId', ''),
                    'balance': float(account.get('balance', 0)),
                    'equity': float(account.get('equity', 0)),
                    'margin_free': float(account.get('usableMargin', 0)),
                    'currency': account.get('mc', 'USD'),
                    'broker': 'FXCM',
                }
                return self.account_info
        except Exception as e:
            logger.error(f"Error getting FXCM account info: {e}")

        return {}

    def get_positions(self) -> List[Dict]:
        try:
            import requests

            if not self.connected:
                return []

            resp = requests.get(
                f"{self.base_url}/trading/get_model",
                headers=self._headers(content_type=False),
                params={'models': 'OpenPosition'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get('open_positions', data.get('openPositions', []))
                return [{
                    'deal_id': str(pos.get('tradeId', '')),
                    'symbol': self._display_symbol(pos.get('currency', '')),
                    'type': 'BUY' if pos.get('isBuy', False) else 'SELL',
                    'size': abs(float(pos.get('amountK', 0))),
                    'level': float(pos.get('open', 0)),
                    'profit_loss': float(pos.get('grossPL', 0)),
                    'broker': 'FXCM',
                } for pos in (raw if isinstance(raw, list) else [])]
        except Exception as e:
            logger.error(f"Error getting FXCM positions: {e}")

        return []

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        try:
            import requests

            if not self.connected:
                return {'success': False, 'error': 'Not connected to FXCM'}

            instrument = self._normalize_symbol(symbol)
            if not instrument:
                return {'success': False, 'error': f'Unsupported FXCM instrument: {symbol}'}

            payload = {
                'account_id': self.credentials.get('account_number', ''),
                'symbol': instrument,
                'is_buy': order_type.upper() == 'BUY',
                'amount': max(float(volume), 1.0),
                'order_type': 'AtMarket',
                'time_in_force': 'GTC',
            }
            resp = requests.post(
                f"{self.base_url}/trading/open_trade",
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                result = resp.json().get('data', {})
                return {
                    'success': True,
                    'orderId': result.get('orderId', ''),
                    'tradeId': result.get('tradeId', ''),
                    'symbol': self._display_symbol(instrument),
                    'type': order_type.upper(),
                    'broker': 'FXCM',
                }
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Error placing FXCM order: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, position_id: str) -> Dict:
        try:
            import requests

            resp = requests.post(
                f"{self.base_url}/trading/close_trade",
                headers=self._headers(),
                json={'trade_id': str(position_id)},
                timeout=15,
            )
            if resp.status_code == 200:
                return {'success': True, 'trade_id': position_id, 'broker': 'FXCM'}
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Error closing FXCM position: {e}")
            return {'success': False, 'error': str(e)}

    def get_trades(self) -> List[Dict]:
        return []


class OANDAConnection(BrokerConnection):
    """OANDA broker connection via REST API."""

    def __init__(self, credentials: Dict = None):
        if credentials is None:
            credentials = {
                'api_key': os.getenv('OANDA_API_KEY', ''),
                'account_number': os.getenv('OANDA_ACCOUNT_ID', ''),
                'is_live': False,
            }

        super().__init__(BrokerType.OANDA, credentials)
        is_live = bool(credentials.get('is_live', False))
        self.base_url = 'https://api-fxtrade.oanda.com/v3' if is_live else 'https://api-fxpractice.oanda.com/v3'

    def _headers(self, content_type: bool = True) -> Dict:
        headers = {
            'Authorization': f"Bearer {self.credentials.get('api_key', '')}",
            'Accept': 'application/json',
        }
        if content_type:
            headers['Content-Type'] = 'application/json'
        return headers

    def _normalize_symbol(self, symbol: str) -> Optional[str]:
        if not symbol:
            return None

        symbol = symbol.upper().replace('/', '').replace('_', '')
        if len(symbol) == 6 and symbol.isalpha():
            return f"{symbol[:3]}_{symbol[3:]}"
        symbol_map = {
            'XAUUSD': 'XAU_USD',
            'XAGUSD': 'XAG_USD',
        }
        return symbol_map.get(symbol)

    def _display_symbol(self, instrument: str) -> str:
        return (instrument or '').replace('_', '').upper()

    def connect(self) -> bool:
        try:
            import requests

            if not self.credentials.get('api_key'):
                logger.error('OANDA: Missing API key')
                return False

            account_id = self.credentials.get('account_number', '')
            if account_id:
                resp = requests.get(
                    f"{self.base_url}/accounts/{account_id}/summary",
                    headers=self._headers(content_type=False),
                    timeout=10,
                )
            else:
                resp = requests.get(
                    f"{self.base_url}/accounts",
                    headers=self._headers(content_type=False),
                    timeout=10,
                )

            if resp.status_code == 200:
                if not account_id:
                    accounts = resp.json().get('accounts', [])
                    if accounts:
                        self.credentials['account_number'] = accounts[0].get('id', '')
                self.connected = True
                self.get_account_info()
                return True
            logger.error(f"OANDA authentication failed: {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to OANDA: {e}")
            return False

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def get_account_info(self) -> Dict:
        try:
            import requests

            if not self.connected:
                return {}

            account_id = self.credentials.get('account_number', '')
            if not account_id:
                return {}

            resp = requests.get(
                f"{self.base_url}/accounts/{account_id}/summary",
                headers=self._headers(content_type=False),
                timeout=10,
            )
            if resp.status_code == 200:
                account = resp.json().get('account', {})
                self.account_info = {
                    'account_id': account.get('id', account_id),
                    'balance': float(account.get('balance', 0)),
                    'equity': float(account.get('NAV', 0)),
                    'margin_free': float(account.get('marginAvailable', 0)),
                    'currency': account.get('currency', 'USD'),
                    'broker': 'OANDA',
                }
                return self.account_info
        except Exception as e:
            logger.error(f"Error getting OANDA account info: {e}")

        return {}

    def get_positions(self) -> List[Dict]:
        try:
            import requests

            if not self.connected:
                return []

            account_id = self.credentials.get('account_number', '')
            resp = requests.get(
                f"{self.base_url}/accounts/{account_id}/openTrades",
                headers=self._headers(content_type=False),
                timeout=10,
            )
            if resp.status_code == 200:
                return [{
                    'deal_id': trade.get('id', ''),
                    'symbol': self._display_symbol(trade.get('instrument', '')),
                    'type': 'BUY' if float(trade.get('currentUnits', 0)) > 0 else 'SELL',
                    'size': abs(float(trade.get('currentUnits', 0))),
                    'level': float(trade.get('price', 0)),
                    'profit_loss': float(trade.get('unrealizedPL', 0)),
                    'broker': 'OANDA',
                } for trade in resp.json().get('trades', [])]
        except Exception as e:
            logger.error(f"Error getting OANDA positions: {e}")

        return []

    def place_order(self, symbol: str, order_type: str, volume: float, **kwargs) -> Dict:
        try:
            import requests

            if not self.connected:
                return {'success': False, 'error': 'Not connected to OANDA'}

            instrument = self._normalize_symbol(symbol)
            if not instrument:
                return {'success': False, 'error': f'Unsupported OANDA instrument: {symbol}'}

            units = max(1, int(round(float(volume))))
            if order_type.upper() == 'SELL':
                units = -units

            payload = {
                'order': {
                    'instrument': instrument,
                    'units': str(units),
                    'type': 'MARKET',
                    'timeInForce': 'FOK',
                    'positionFill': 'DEFAULT',
                }
            }
            account_id = self.credentials.get('account_number', '')
            resp = requests.post(
                f"{self.base_url}/accounts/{account_id}/orders",
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            if resp.status_code == 201:
                result = resp.json().get('orderFillTransaction', {})
                return {
                    'success': True,
                    'orderId': result.get('id', ''),
                    'deal_id': result.get('tradeOpened', {}).get('tradeID', ''),
                    'symbol': self._display_symbol(instrument),
                    'type': order_type.upper(),
                    'broker': 'OANDA',
                }
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Error placing OANDA order: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, position_id: str) -> Dict:
        try:
            import requests

            account_id = self.credentials.get('account_number', '')
            resp = requests.put(
                f"{self.base_url}/accounts/{account_id}/trades/{position_id}/close",
                headers=self._headers(),
                json={'units': 'ALL'},
                timeout=15,
            )
            if resp.status_code == 200:
                return {'success': True, 'trade_id': position_id, 'broker': 'OANDA'}
            return {'success': False, 'error': resp.text}
        except Exception as e:
            logger.error(f"Error closing OANDA position: {e}")
            return {'success': False, 'error': str(e)}

    def get_trades(self) -> List[Dict]:
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
            if positions is None:
                logger.warning(f'XM: mt5.positions_get() returned None: {mt5.last_error()}')
                return []
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
            
            date_from = datetime.now() - timedelta(days=30)
            deals = mt5.history_deals_get(date_from, datetime.now())
            if deals is None:
                logger.warning(f'XM: history_deals_get returned None: {mt5.last_error()}')
                return []
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
            elif broker_type == BrokerType.BINANCE:
                connection = BinanceConnection(credentials)
            elif broker_type == BrokerType.OANDA:
                connection = OANDAConnection(credentials)

            elif broker_type == BrokerType.FXM:
                connection = FXCMConnection(credentials)
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


def canonicalize_broker_name(broker_name: str) -> str:
    normalized = (broker_name or '').strip().lower()
    broker_map = {
        
        'metaquotes': 'MetaQuotes',
        'metatrader 5': 'MetaTrader 5',
        'metatrader5': 'MetaTrader 5',
        'mt5': 'MetaTrader 5',
        'xm': 'XM',
        'xm global': 'XM Global',
        'binance': 'Binance',
        'fxcm': 'FXCM',
        'fxm': 'FXCM',
        'oanda': 'OANDA',
        'exness': 'Exness',
        'xness': 'Exness',
    }
    return broker_map.get(normalized, broker_name)


def is_mt5_broker_name(broker_name: str) -> bool:
    return canonicalize_broker_name(broker_name) in ['Exness', 'MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5']

# ==================== IN-MEMORY STORAGE ====================
# Store demo trades placed via API (temporary storage for this session)
demo_trades_storage = {}

# Auto-add default Exness MT5 account
logger.info("Initializing with Exness MT5 account")
broker_manager.add_connection('Exness MT5', BrokerType.METATRADER5, MT5_CONFIG)

# Removed: IG Markets auto-connection (IG Markets integration removed)

# Auto-add XM Global MT5 account
logger.info("Initializing with XM Global MT5 account")
broker_manager.add_connection('XM Global MT5', BrokerType.METATRADER5, XM_CONFIG)

# AUTO-CONNECT to Exness MT5 on startup (so dashboard shows real balance)
def auto_connect_mt5():
    """Auto-connect to Exness MT5 on startup"""
    try:
        connection = broker_manager.connections.get('Exness MT5')
        if connection:
            logger.info("🔗 Attempting auto-connect to Exness MT5...")
            if connection.connect():
                logger.info("✅ Auto-connected to Exness MT5 successfully - balance will display on dashboard")
                return True
            else:
                logger.warning("⚠️  Failed to auto-connect to Exness MT5 - will use simulated trading, dashboard will show $0 balance")
                return False
    except Exception as e:
        logger.warning(f"⚠️  Error auto-connecting to MT5: {e} - will use simulated trading")
        return False

# Removed: auto_connect_ig() function (IG Markets integration removed)

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


# ==================== IG.COM API ENDPOINTS REMOVED ====================
# NOTE: IG Markets integration has been removed from the system.
# Legacy endpoints removed: /api/legacy/ig/*


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


# ==================== BROKER DETECTION ====================

def detect_exness_mt5():
    """Detect if Exness MT5 is available on the system"""
    try:
        import MetaTrader5 as mt5
        
        # Try to initialize MT5 to check if it's installed
        if hasattr(mt5, 'version'):
            logger.info("✅ Exness MT5 detected on system")
            return {
                'available': True,
                'installed': True,
                'version': str(mt5.version if hasattr(mt5, 'version') else 'Unknown')
            }
        else:
            logger.warning("⚠️ MetaTrader 5 library found but version info unavailable")
            return {
                'available': True,
                'installed': True,
                'version': 'Unknown'
            }
    except ImportError:
        logger.warning("⚠️ MetaTrader 5 library not installed")
        return {
            'available': False,
            'installed': False,
            'reason': 'MetaTrader 5 library not installed. Install with: pip install MetaTrader5'
        }
    except Exception as e:
        logger.error(f"❌ Error detecting Exness MT5: {e}")
        return {
            'available': False,
            'installed': False,
            'error': str(e)
        }


def check_exness_connectivity(account_id=None, password=None, server='Exness-MT5'):
    """Check if Exness MT5 server is reachable"""
    try:
        import MetaTrader5 as mt5
        
        # If credentials provided, try to login
        if account_id and password:
            if mt5.initialize(login=int(account_id), password=password, server=server):
                account_info = mt5.account_info()
                mt5.shutdown()
                if account_info:
                    logger.info(f"✅ Exness connectivity verified for account {account_id}")
                    return {
                        'connected': True,
                        'account_id': account_id,
                        'server': server,
                        'message': 'Successfully connected to Exness'
                    }
            else:
                error = mt5.last_error()
                logger.error(f"❌ Exness login failed: {error}")
                return {
                    'connected': False,
                    'error': str(error)
                }
        else:
            # Just check if MT5 library responds
            logger.info("✅ Exness MT5 library responding")
            return {
                'connected': True,
                'message': 'MT5 library is available (credentials not tested)'
            }
    except Exception as e:
        logger.error(f"❌ Error checking Exness connectivity: {e}")
        return {
            'connected': False,
            'error': str(e)
        }


@app.route('/api/brokers/check-exness', methods=['GET'])
def check_exness():
    """Check if Exness is available and can be used"""
    try:
        exness_info = detect_exness_mt5()
        return jsonify(exness_info), 200
    except Exception as e:
        logger.error(f"❌ Error checking Exness availability: {e}")
        return jsonify({
            'available': False,
            'error': str(e)
        }), 500


@app.route('/api/brokers/verify-exness', methods=['POST'])
def verify_exness():
    """Verify Exness connectivity with credentials"""
    try:
        data = request.get_json()
        account_id = data.get('accountId')
        password = data.get('password')
        server = data.get('server', 'Exness-MT5')
        
        if not account_id or not password:
            return jsonify({
                'success': False,
                'error': 'Missing accountId or password'
            }), 400
        
        result = check_exness_connectivity(account_id, password, server)
        result['success'] = result.get('connected', False)
        
        return jsonify(result), 200 if result['success'] else 401
    except Exception as e:
        logger.error(f"❌ Error verifying Exness credentials: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/brokers/list', methods=['GET'])
def list_brokers():
    """List available brokers"""
    # Detect Exness availability
    exness_status = detect_exness_mt5()
    exness_broker_status = 'active' if exness_status.get('available') else 'inactive'
    
    brokers = [
        {
            'type': 'exness',
            'name': 'Exness MT5',
            'description': 'Exness - MetaTrader 5 - Professional Forex & CFD broker',
            'assets': ['Forex', 'Metals', 'Indices', 'Stocks', 'Cryptos', 'Energies'],
            'status': exness_broker_status,
            'installed': exness_status.get('installed', False),
            'version': exness_status.get('version', 'Not installed')
        },
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


# ==================== SYMBOL MANAGEMENT ====================

@app.route('/api/symbols', methods=['GET'])
@require_api_key
def list_symbols():
    """List all available trading symbols"""
    try:
        symbol_type = request.args.get('type')  # Filter by type (Forex, Crypto, Commodity, etc.)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if symbol_type:
            cursor.execute('''
                SELECT * FROM trading_symbols 
                WHERE is_active = 1 AND symbol_type = ?
                ORDER BY symbol
            ''', (symbol_type,))
        else:
            cursor.execute('''
                SELECT * FROM trading_symbols 
                WHERE is_active = 1
                ORDER BY symbol_type, symbol
            ''')
        
        symbols = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'symbols': symbols,
            'total': len(symbols)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing symbols: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/symbols/add', methods=['POST'])
@require_api_key
def add_symbol():
    """Add a new trading symbol"""
    try:
        data = request.get_json()
        symbol_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trading_symbols 
            (symbol_id, symbol, name, symbol_type, broker, min_price, max_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol_id,
            data.get('symbol').upper(),
            data.get('name'),
            data.get('symbol_type'),
            data.get('broker'),
            data.get('min_price'),
            data.get('max_price'),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Symbol added: {data.get('symbol')}")
        
        return jsonify({
            'success': True,
            'symbol_id': symbol_id,
            'message': f"Symbol {data.get('symbol')} added successfully"
        }), 201
    
    except Exception as e:
        logger.error(f"Error adding symbol: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/symbols/<symbol_id>', methods=['DELETE'])
@require_api_key
def delete_symbol(symbol_id):
    """Delete a trading symbol"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE trading_symbols SET is_active = 0 WHERE symbol_id = ?', (symbol_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Symbol deleted: {symbol_id}")
        
        return jsonify({
            'success': True,
            'message': 'Symbol deleted successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error deleting symbol: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== USER MANAGEMENT ====================

@app.route('/api/admin/users', methods=['GET'])
@require_api_key
def list_users():
    """List all users (admin only)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, email, name, referral_code, total_commission, created_at 
            FROM users 
            ORDER BY created_at DESC
        ''')
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users,
            'total': len(users)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/create', methods=['POST'])
@require_api_key
def create_user():
    """Create a new user"""
    try:
        data = request.get_json()
        user_id = str(uuid.uuid4())
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users 
            (user_id, email, name, referral_code, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('email'),
            data.get('name'),
            referral_code,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ User created: {data.get('email')}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'referral_code': referral_code,
            'message': f"User {data.get('name')} created successfully"
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/users/<user_id>', methods=['GET'])
@require_api_key
def get_user(user_id):
    """Get user details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = dict(cursor.fetchone() or {})
        
        # Get user accounts
        cursor.execute('SELECT * FROM user_accounts WHERE user_id = ?', (user_id,))
        accounts = [dict(row) for row in cursor.fetchall()]
        
        # Get user trading settings
        cursor.execute('SELECT * FROM user_trading_settings WHERE user_id = ?', (user_id,))
        settings = dict(cursor.fetchone() or {})
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': user,
            'accounts': accounts,
            'settings': settings
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== BOT STRATEGY MANAGEMENT ====================

@app.route('/api/strategies', methods=['GET'])
@require_api_key
def list_strategies():
    """List all bot strategies for user"""
    try:
        user_id = request.headers.get('X-User-ID', 'default_user')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM bot_strategies 
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
        ''', (user_id,))
        
        strategies = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'strategies': strategies,
            'total': len(strategies)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/create', methods=['POST'])
@require_api_key
def create_strategy():
    """Create a new bot strategy"""
    try:
        data = request.get_json()
        user_id = request.headers.get('X-User-ID', 'default_user')
        strategy_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bot_strategies 
            (strategy_id, user_id, strategy_name, description, strategy_type, 
             parameters, symbols, risk_level, profit_target, stop_loss, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_id,
            user_id,
            data.get('strategy_name'),
            data.get('description'),
            data.get('strategy_type'),  # 'TREND_FOLLOW', 'MEAN_REVERSION', 'SCALPING', etc.
            json.dumps(data.get('parameters', {})),
            json.dumps(data.get('symbols', [])),
            data.get('risk_level'),  # 'LOW', 'MEDIUM', 'HIGH'
            data.get('profit_target'),
            data.get('stop_loss'),
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Strategy created: {data.get('strategy_name')} for user {user_id}")
        
        return jsonify({
            'success': True,
            'strategy_id': strategy_id,
            'message': f"Strategy {data.get('strategy_name')} created successfully"
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/<strategy_id>', methods=['PUT'])
@require_api_key
def update_strategy(strategy_id):
    """Update a bot strategy"""
    try:
        data = request.get_json()
        user_id = request.headers.get('X-User-ID', 'default_user')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE bot_strategies 
            SET 
                strategy_name = ?,
                description = ?,
                strategy_type = ?,
                parameters = ?,
                symbols = ?,
                risk_level = ?,
                profit_target = ?,
                stop_loss = ?,
                updated_at = ?
            WHERE strategy_id = ? AND user_id = ?
        ''', (
            data.get('strategy_name'),
            data.get('description'),
            data.get('strategy_type'),
            json.dumps(data.get('parameters', {})),
            json.dumps(data.get('symbols', [])),
            data.get('risk_level'),
            data.get('profit_target'),
            data.get('stop_loss'),
            datetime.now().isoformat(),
            strategy_id,
            user_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Strategy updated: {strategy_id}")
        
        return jsonify({
            'success': True,
            'message': 'Strategy updated successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/strategies/<strategy_id>', methods=['DELETE'])
@require_api_key
def delete_strategy(strategy_id):
    """Delete a bot strategy"""
    try:
        user_id = request.headers.get('X-User-ID', 'default_user')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE bot_strategies 
            SET is_active = 0 
            WHERE strategy_id = ? AND user_id = ?
        ''', (strategy_id, user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Strategy deleted: {strategy_id}")
        
        return jsonify({
            'success': True,
            'message': 'Strategy deleted successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error deleting strategy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== DEMO/LIVE MODE SWITCHING ====================

@app.route('/api/user/trading-mode', methods=['GET'])
@require_api_key
def get_trading_mode():
    """Get users current trading mode (DEMO or LIVE)"""
    try:
        user_id = request.headers.get('X-User-ID', 'default_user')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if trading_mode exists in user preferences
        cursor.execute('''
            SELECT trading_mode FROM user_preferences 
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        mode = result['trading_mode'] if result else 'DEMO'
        
        conn.close()
        
        return jsonify({
            'success': True,
            'mode': mode,
            'user_id': user_id
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting trading mode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/switch-mode', methods=['POST'])
@require_api_key
def switch_trading_mode():
    """Switch between DEMO and LIVE trading modes"""
    try:
        data = request.get_json()
        user_id = request.headers.get('X-User-ID', 'default_user')
        mode = data.get('mode', 'DEMO').upper()
        
        if mode not in ['DEMO', 'LIVE']:
            return jsonify({'success': False, 'error': 'Invalid mode. Use DEMO or LIVE'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create user_preferences table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                trading_mode TEXT DEFAULT 'DEMO',
                live_account TEXT,
                live_server TEXT,
                updated_at TEXT
            )
        ''')
        
        # Update or insert user preference
        cursor.execute('''
            INSERT OR REPLACE INTO user_preferences 
            (user_id, trading_mode, live_account, live_server, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            mode,
            data.get('account') if mode == 'LIVE' else None,
            data.get('server') if mode == 'LIVE' else None,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ User {user_id} switched to {mode} trading mode")
        
        return jsonify({
            'success': True,
            'message': f'Switched to {mode} trading mode',
            'mode': mode,
            'user_id': user_id
        }), 200
    
    except Exception as e:
        logger.error(f"Error switching trading mode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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


@app.route('/api/accounts/balances', methods=['GET'])
@require_session
def get_account_balances():
    """Get account balances from all user's brokers (Exness, XM, Binance, etc.)
    
    Returns unified account summary with balances from all integrated brokers.
    This is what displays in the dashboard showing real broker balances.
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all active broker credentials for this user
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, is_live, api_key, password, server
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        
        credentials = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        accounts_summary = {
            'success': True,
            'accounts': [],
            'totalBalance': 0,
            'totalEquity': 0,
            'brokers': {},  # Grouped by broker: {Exness: {...}, XM: {...}, Binance: {...}}
        }
        
        # Fetch balance from each broker
        # OPTIMIZATION: Reuse existing broker_manager connections instead of creating new ones.
        # Creating new MT5Connection calls mt5.initialize() which disrupts the shared SDK singleton.
        for cred in credentials:
            broker_name = canonicalize_broker_name(cred['broker_name'])
            account_num = cred['account_number']
            is_live = cred['is_live']
            mode = 'Live' if is_live else 'Demo'
            
            account_info = None
            error_msg = None
            
            try:
                if is_mt5_broker_name(broker_name):
                    # Reuse existing broker_manager MT5 connection — never create a new one here
                    # because mt5.initialize() / mt5.shutdown() would disrupt live price feeds.
                    cached_id = None
                    if canonicalize_broker_name(broker_name) == 'Exness':
                        cached_id = 'Exness MT5'
                    elif canonicalize_broker_name(broker_name) in ['XM', 'XM Global']:
                        cached_id = 'XM Global MT5'
                    
                    cached_conn = broker_manager.connections.get(cached_id) if cached_id else None
                    if cached_conn and cached_conn.connected:
                        # Check if this cached connection is logged into the right account
                        acct = cached_conn.account_info
                        if acct and str(acct.get('accountNumber', '')) == str(account_num):
                            account_info = acct
                        else:
                            # Cached conn is for a different account — try quick SDK call
                            try:
                                mt5_mod = cached_conn.mt5
                                if mt5_mod:
                                    raw_info = mt5_mod.account_info()
                                    if raw_info and raw_info.login == int(account_num):
                                        account_info = {
                                            'accountNumber': raw_info.login,
                                            'balance': raw_info.balance,
                                            'equity': raw_info.equity,
                                            'margin': raw_info.margin,
                                            'marginFree': raw_info.margin_free,
                                            'currency': raw_info.currency,
                                            'leverage': raw_info.leverage,
                                        }
                                    else:
                                        error_msg = f"MT5 connected to different account — balance will update when bot runs"
                            except Exception:
                                error_msg = f"Could not read account {account_num} from shared MT5 connection"
                    else:
                        error_msg = f"{broker_name} MT5 not connected — balance updates when bot runs"
                
                elif broker_name == 'Binance':
                    # Binance uses REST API — safe to create temporary connection
                    binance_conn = BinanceConnection({
                        'api_key': cred['api_key'],
                        'api_secret': cred['password'],
                        'account_number': account_num,
                        'is_live': is_live,
                    })
                    if binance_conn.connect():
                        balance_info = binance_conn.get_balance()
                        account_info = {
                            'accountNumber': account_num,
                            'balance': balance_info.get('balance', 0),
                            'equity': balance_info.get('balance', 0),
                            'marginFree': balance_info.get('available', 0),
                            'currency': balance_info.get('currency', 'USDT'),
                            'displayCurrency': balance_info.get('currency', 'USDT'),
                            'broker': 'Binance',
                            'leverage': 1,
                        }
                        binance_conn.disconnect()
                    else:
                        error_msg = "Failed to connect to Binance API"
                
                else:
                    error_msg = f"Unsupported broker: {broker_name}"
                
            except Exception as e:
                logger.warning(f"Error fetching balance from {broker_name} account {account_num}: {e}")
                error_msg = str(e)
            
            # Build account entry
            account_entry = {
                'credentialId': cred['credential_id'],
                'broker': broker_name,
                'accountNumber': account_num,
                'mode': mode,
                'error': error_msg,
            }
            
            if account_info:
                account_entry.update({
                    'balance': account_info.get('balance', 0),
                    'equity': account_info.get('equity', account_info.get('balance', 0)),
                    'marginFree': account_info.get('marginFree', 0),
                    'currency': account_info.get('currency', 'USD'),
                    'connected': True,
                })
                # Add to broker group
                if broker_name not in accounts_summary['brokers']:
                    accounts_summary['brokers'][broker_name] = []
                accounts_summary['brokers'][broker_name].append(account_entry)
                
                # Accumulate totals
                accounts_summary['totalBalance'] += account_entry['balance']
                accounts_summary['totalEquity'] += account_entry['equity']
            else:
                account_entry['connected'] = False
                if broker_name not in accounts_summary['brokers']:
                    accounts_summary['brokers'][broker_name] = []
                accounts_summary['brokers'][broker_name].append(account_entry)
            
            accounts_summary['accounts'].append(account_entry)
        
        logger.info(f"✅ Fetched account balances for user {user_id}: {len(accounts_summary['accounts'])} accounts, Total: ${accounts_summary['totalBalance']:.2f}")
        
        return jsonify(accounts_summary)
    
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
                # IG Markets integration removed
                if isinstance(connection, XMConnection):
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
            'binance': BrokerType.BINANCE,
            'ib': BrokerType.INTERACTIVE_BROKERS,
            'oanda': BrokerType.OANDA,
            'xm': BrokerType.XM,
            'pepperstone': BrokerType.PEPPERSTONE,
            'fxopen': BrokerType.FXOPEN,
            'exness': BrokerType.EXNESS,
            'darwinex': BrokerType.DARWINEX,

            'fxcm': BrokerType.FXM,
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
            
            flat_market_data = {}  # {EURUSDm: {signal, trend, etc}, BTCUSDm: {signal, trend, etc}, ...}
            categorized = {
                'forex': [],
                'commodities': [],
                'precious_metals': [],
                'energy': [],
                'indices': [],
                'stocks': []
            }
            
            # Exness symbols verified in MT5 Market Watch for the current account/server.
            symbol_config = {
                'forex': [
                    {'symbol': 'EURUSDm', 'name': 'Euro vs US Dollar (Exness)', 'min_price': 1.08, 'max_price': 1.10},
                    {'symbol': 'USDJPYm', 'name': 'US Dollar vs Japanese Yen (Exness)', 'min_price': 149.0, 'max_price': 151.0},
                ],
                'precious_metals': [
                    {'symbol': 'XAUUSDm', 'name': '🥇 Gold (per troy oz)', 'type': 'Metal', 'lucrative': True, 'min_price': 2000, 'max_price': 2100},
                ],
                'energy': [],
                'indices': [],
                'stocks': [
                    {'symbol': 'AAPLm', 'name': 'Apple Inc.', 'type': 'Stock CFD', 'min_price': 180, 'max_price': 260},
                    {'symbol': 'AMDm', 'name': 'Advanced Micro Devices, Inc.', 'type': 'Stock CFD', 'min_price': 120, 'max_price': 230},
                    {'symbol': 'MSFTm', 'name': 'Microsoft Corporation', 'type': 'Stock CFD', 'min_price': 380, 'max_price': 520},
                    {'symbol': 'NVDAm', 'name': 'NVIDIA Corporation', 'type': 'Stock CFD', 'min_price': 700, 'max_price': 1100},
                    {'symbol': 'JPMm', 'name': 'J P Morgan Chase & Co', 'type': 'Stock CFD', 'min_price': 170, 'max_price': 280},
                    {'symbol': 'BACm', 'name': 'Bank of America Corporation', 'type': 'Stock CFD', 'min_price': 28, 'max_price': 55},
                    {'symbol': 'WFCm', 'name': 'Wells Fargo & Company', 'type': 'Stock CFD', 'min_price': 45, 'max_price': 85},
                    {'symbol': 'GOOGLm', 'name': 'Alphabet Inc.', 'type': 'Stock CFD', 'min_price': 130, 'max_price': 230},
                    {'symbol': 'METAm', 'name': 'META Platforms, Inc.', 'type': 'Stock CFD', 'min_price': 350, 'max_price': 700},
                    {'symbol': 'ORCLm', 'name': 'Oracle Corporation', 'type': 'Stock CFD', 'min_price': 100, 'max_price': 220},
                    {'symbol': 'TSMm', 'name': 'Taiwan Semiconductor Manufacturing Company, Limited', 'type': 'Stock CFD', 'min_price': 110, 'max_price': 240},
                ]
            }
            
            # Add crypto symbols (available on Exness)
            symbol_config['commodities'] = [
                {'symbol': 'BTCUSDm', 'name': '₿ Bitcoin (BTC/USD)', 'type': 'Crypto', 'lucrative': True, 'min_price': 40000, 'max_price': 70000},
                {'symbol': 'ETHUSDm', 'name': 'Ethereum (ETH/USD)', 'type': 'Crypto', 'lucrative': True, 'min_price': 2000, 'max_price': 4000},
            ]
            
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
            eurusd_signal = flat_market_data.get('EURUSDm', {}).get('signal', 'NO DATA')
            btc_signal = flat_market_data.get('BTCUSDm', {}).get('signal', 'NO DATA')
            total_symbols = sum(len(items) for items in categorized.values())
            logger.info(f"[/api/commodities/list] Returning {total_symbols} Exness symbols: EURUSDm={eurusd_signal}, BTCUSDm={btc_signal}")
            
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
    """Get unified trades from all user's brokers (XM + MT5)"""
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
        conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
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
    # Verified Exness/MT5 symbols currently supported by the app and backend.
    'BTCUSDm',   # Bitcoin / USD
    'ETHUSDm',   # Ethereum / USD
    'EURUSDm',   # Euro / USD
    'USDJPYm',   # USD / Japanese Yen
    'XAUUSDm',   # Gold / USD
    'AAPLm',     # Apple Inc.
    'AMDm',      # Advanced Micro Devices, Inc.
    'MSFTm',     # Microsoft Corporation
    'NVDAm',     # NVIDIA Corporation
    'JPMm',      # J P Morgan Chase & Co
    'BACm',      # Bank of America Corporation
    'WFCm',      # Wells Fargo & Company
    'GOOGLm',    # Alphabet Inc.
    'METAm',     # META Platforms, Inc.
    'ORCLm',     # Oracle Corporation
    'TSMm',      # Taiwan Semiconductor Manufacturing Company, Limited
}

BINANCE_VALID_SYMBOLS = {
    # Tier 1 — Large Cap
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT',
    # Tier 2 — High Volume Alt-coins
    'AVAXUSDT', 'MATICUSDT', 'LINKUSDT', 'LTCUSDT', 'TRXUSDT', 'DOTUSDT', 'ATOMUSDT',
    # Tier 3 — DeFi & Layer-2 (high volatility / liquidity)
    'SHIBUSDT', 'UNIUSDT', 'NEARUSDT', 'ARBUSDT', 'OPUSDT', 'APTUSDT',
    'INJUSDT',  'SUIUSDT',  'FTMUSDT',  'AAVEUSDT',
    # Tier 4 — Gaming / Metaverse / Cross-chain
    'SANDUSDT', 'MANAUSDT', 'RUNEUSDT', 'ALGOUSDT',
}

SYMBOL_MAPPING = {
    # Exness "m" suffix mappings (symbols received without "m" need to map to "m" version)
    'BTCUSD': 'BTCUSDm',
    'ETHUSD': 'ETHUSDm',
    'EURUSD': 'EURUSDm',
    'USDJPY': 'USDJPYm',
    'XAUUSD': 'XAUUSDm',
    'AAPL': 'AAPLm',
    'AMD': 'AMDm',
    'MSFT': 'MSFTm',
    'NVDA': 'NVDAm',
    'JPM': 'JPMm',
    'BAC': 'BACm',
    'WFC': 'WFCm',
    'GOOGL': 'GOOGLm',
    'META': 'METAm',
    'ORCL': 'ORCLm',
    'TSM': 'TSMm',
    
    # OLD -> NEW SYMBOL CORRECTIONS
    # Metals
    'GOLD': 'XAUUSDm', 'XAGUSD': 'XAUUSDm',
    'SILVER': 'XAUUSDm',
    'PLATINUM': 'XAUUSDm',
    'PALLADIUM': 'XAUUSDm',
    'COPPER': 'XAUUSDm',
    
    # Energy (not available on Exness demo - map to EURUSDm)
    'WTIUSD': 'EURUSDm', 'CRUDE_OIL': 'EURUSDm',
    'BRENTUSD': 'EURUSDm',
    'NATGASUS': 'EURUSDm', 'NATURAL_GAS': 'EURUSDm',
    'OILK': 'EURUSDm',
    
    # Agriculture (not available on Exness demo - map to EURUSDm)
    'CORNUSD': 'EURUSDm', 'CORN': 'EURUSDm',
    'WHEATUSD': 'EURUSDm', 'WHEAT': 'EURUSDm',
    'SOYBEANSUSD': 'EURUSDm', 'SOYBEANS': 'EURUSDm',
    'COFFEEUSD': 'EURUSDm', 'COFFEE': 'EURUSDm',
    'COCOAUSD': 'EURUSDm', 'COCOA': 'EURUSDm',
    'SUGARUSD': 'EURUSDm', 'SUGAR': 'EURUSDm',
    
    # Indices (not available on Exness demo - map to EURUSDm)
    'SPX500': 'EURUSDm', 'S&P500': 'EURUSDm', 'SP500': 'EURUSDm', 'SP500m': 'EURUSDm',
    'DAX40': 'EURUSDm', 'GDAX': 'EURUSDm', 'DAX': 'EURUSDm',
    'FTSE100': 'EURUSDm', 'FTSE': 'EURUSDm',
    'CAC40': 'EURUSDm',
    'NIKKEI225': 'EURUSDm', 'NIKKEI': 'EURUSDm', 'NIKL': 'EURUSDm',
    
    # Stocks aliases
    'APPLE': 'AAPLm',
    'ALPHABET': 'GOOGLm',
    'GOOGLE': 'GOOGLm',
    'MICROSOFT': 'MSFTm',
    'NVIDIA': 'NVDAm',
    
    # Crypto variants
    'BITCOIN': 'BTCUSDm', 'BTC': 'BTCUSDm',
    'ETHEREUM': 'ETHUSDm', 'ETH': 'ETHUSDm',
}

def validate_and_correct_symbols(symbols, broker_name=None):
    """Validate symbols based on broker type and correct old/unavailable ones when possible."""
    broker_name = canonicalize_broker_name(broker_name or '')

    if broker_name == 'Binance':
        if not symbols:
            return ['BTCUSDT']

        corrected = []
        binance_symbol_map = {
            # BTC / ETH / BNB
            'BTCUSD': 'BTCUSDT', 'BTC/USDT': 'BTCUSDT', 'BTC_USDT': 'BTCUSDT', 'BITCOIN': 'BTCUSDT',
            'ETHUSD': 'ETHUSDT', 'ETH/USDT': 'ETHUSDT', 'ETH_USDT': 'ETHUSDT', 'ETHEREUM': 'ETHUSDT',
            'BNBUSD': 'BNBUSDT', 'BNB/USDT': 'BNBUSDT',
            # SOL / XRP / ADA / DOGE
            'SOLUSD': 'SOLUSDT', 'SOL/USDT': 'SOLUSDT',
            'XRPUSD': 'XRPUSDT', 'XRP/USDT': 'XRPUSDT',
            'ADAUSD': 'ADAUSDT', 'ADA/USDT': 'ADAUSDT',
            'DOGEUSD': 'DOGEUSDT', 'DOGE/USDT': 'DOGEUSDT',
            # Tier 2
            'AVAXUSD': 'AVAXUSDT', 'MATICS': 'MATICUSDT', 'MATIC/USDT': 'MATICUSDT', 'POLUSD': 'MATICUSDT',
            'LINKUSD': 'LINKUSDT', 'LTCUSD': 'LTCUSDT', 'TRXUSD': 'TRXUSDT',
            'DOTUSD': 'DOTUSDT', 'ATOMUSD': 'ATOMUSDT',
            # Tier 3
            'SHIBUSD': 'SHIBUSDT', 'SHIB/USDT': 'SHIBUSDT',
            'UNIUSD': 'UNIUSDT',  'UNI/USDT': 'UNIUSDT',
            'NEARUSD': 'NEARUSDT', 'ARBUSD': 'ARBUSDT', 'OPUSD': 'OPUSDT',
            'APTUSD': 'APTUSDT',  'INJUSD': 'INJUSDT', 'SUIUSD': 'SUIUSDT',
            'FTMUSD': 'FTMUSDT',  'AAVEUSD': 'AAVEUSDT',
            # Tier 4
            'SANDUSD': 'SANDUSDT', 'MANAUSD': 'MANAUSDT',
            'RUNEUSD': 'RUNEUSDT', 'ALGOUSD': 'ALGOUSDT',
        }

        for symbol in symbols:
            normalized = str(symbol).upper().replace('/', '').replace('_', '')
            normalized = binance_symbol_map.get(str(symbol).upper(), normalized)
            normalized = binance_symbol_map.get(normalized, normalized)

            if normalized in BINANCE_VALID_SYMBOLS and normalized not in corrected:
                corrected.append(normalized)
            else:
                logger.warning(f"⚠️ Unsupported Binance symbol {symbol} - skipping")

        return corrected or ['BTCUSDT']

    if broker_name in ('XM', 'XM Global'):
        if not symbols:
            return ['EURUSDm']
        corrected = []
        for symbol in symbols:
            # Strip XM server suffixes (.r, .stp, .ecn, etc.)
            base = str(symbol).split('.')[0].upper()
            if base in VALID_SYMBOLS and base not in corrected:
                corrected.append(base)
            elif base in SYMBOL_MAPPING:
                mapped = SYMBOL_MAPPING[base]
                if mapped not in corrected:
                    corrected.append(mapped)
            elif symbol in VALID_SYMBOLS and symbol not in corrected:
                corrected.append(symbol)
            else:
                logger.warning(f'⚠️ Unknown XM symbol {symbol} -> defaulting to EURUSDm')
                if 'EURUSDm' not in corrected:
                    corrected.append('EURUSDm')
        return corrected[:5] or ['EURUSDm']

    if not symbols:
        return ['EURUSDm']  # Default fallback to Exness EURUSDm
    
    corrected = []
    for symbol in symbols:
        if symbol in VALID_SYMBOLS:
            # Symbol is valid - keep it
            corrected.append(symbol)
        elif symbol in SYMBOL_MAPPING:
            # Symbol is old - map to new one
            new_symbol = SYMBOL_MAPPING[symbol]
            logger.warning(f"🔄 Auto-correcting symbol {symbol} -> {new_symbol} based on configured Exness symbol mappings")
            if new_symbol not in corrected:
                corrected.append(new_symbol)
        else:
            # Unknown symbol - use fallback to valid Exness symbol
            logger.warning(f"⚠️  Unknown symbol {symbol} - using EURUSDm fallback based on current Exness defaults")
            if 'EURUSDm' not in corrected:
                corrected.append('EURUSDm')
    
    # Ensure we have at least one symbol
    if not corrected:
        corrected = ['EURUSDm']
    
    # Remove duplicates while preserving order
    seen = set()
    final = []
    for s in corrected:
        if s not in seen:
            final.append(s)
            seen.add(s)
    
    return final[:5]  # Limit to 5 symbols max

# ==================== SYMBOL-SPECIFIC TRADING PARAMETERS ====================
SYMBOL_PARAMETERS = {
    # FOREX PAIRS - High liquidity, tight spreads
    'EURUSDm': {
        'atr_multiplier': 1.2,  # Tighter stops for liquid pairs
        'stop_loss_pips': 8,
        'take_profit_pips': 15,
        'max_slippage': 0.0005,
        'min_signal_strength': 50,
        'volatility_high': 0.15,  # 0.15% is high volatility for FX
        'volatility_low': 0.02,
    },
    'USDJPYm': {
        'atr_multiplier': 1.2,
        'stop_loss_pips': 8,
        'take_profit_pips': 16,
        'max_slippage': 0.0006,
        'min_signal_strength': 50,
        'volatility_high': 0.12,
        'volatility_low': 0.02,
    },
    # STOCKS - Higher volatility, wider spreads
    'AAPLm': {
        'atr_multiplier': 1.5,
        'stop_loss_pips': 15,
        'take_profit_pips': 30,
        'max_slippage': 0.001,
        'min_signal_strength': 60,
        'volatility_high': 2.0,
        'volatility_low': 0.5,
    },
    'AMDm': {  # Semiconductor - highly volatile
        'atr_multiplier': 1.8,
        'stop_loss_pips': 20,
        'take_profit_pips': 40,
        'max_slippage': 0.0015,
        'min_signal_strength': 65,
        'volatility_high': 3.0,
        'volatility_low': 1.0,
    },
    'TSMm': {  # Semiconductor - highly volatile
        'atr_multiplier': 1.8,
        'stop_loss_pips': 20,
        'take_profit_pips': 40,
        'max_slippage': 0.0015,
        'min_signal_strength': 65,
        'volatility_high': 3.0,
        'volatility_low': 1.0,
    },
    'MSFTm': {  # Tech mega-cap - moderate volatility
        'atr_multiplier': 1.5,
        'stop_loss_pips': 14,
        'take_profit_pips': 28,
        'max_slippage': 0.0012,
        'min_signal_strength': 60,
        'volatility_high': 1.8,
        'volatility_low': 0.6,
    },
    'NVDAm': {  # GPU leader - high volatility
        'atr_multiplier': 1.7,
        'stop_loss_pips': 18,
        'take_profit_pips': 36,
        'max_slippage': 0.0015,
        'min_signal_strength': 63,
        'volatility_high': 2.8,
        'volatility_low': 0.9,
    },
    'BACm': {  # Bank of America - moderate volatility
        'atr_multiplier': 1.4,
        'stop_loss_pips': 12,
        'take_profit_pips': 24,
        'max_slippage': 0.001,
        'min_signal_strength': 58,
        'volatility_high': 1.6,
        'volatility_low': 0.4,
    },
    # PRECIOUS METALS - High volatility
    'XAUUSDm': {
        'atr_multiplier': 1.6,
        'stop_loss_pips': 12,
        'take_profit_pips': 25,
        'max_slippage': 0.001,
        'min_signal_strength': 55,
        'volatility_high': 1.5,
        'volatility_low': 0.3,
    },
    # CRYPTOCURRENCIES - Extreme volatility
    'BTCUSDm': {
        'atr_multiplier': 2.0,  # Wide stops for crypto
        'stop_loss_pips': 50,
        'take_profit_pips': 100,
        'max_slippage': 0.002,
        'min_signal_strength': 70,
        'volatility_high': 5.0,
        'volatility_low': 1.0,
    },
    'ETHUSDm': {
        'atr_multiplier': 2.0,
        'stop_loss_pips': 40,
        'take_profit_pips': 80,
        'max_slippage': 0.002,
        'min_signal_strength': 70,
        'volatility_high': 4.0,
        'volatility_low': 1.0,
    },
}

# Default parameters for symbols not in the list
DEFAULT_SYMBOL_PARAMS = {
    'atr_multiplier': 1.5,
    'stop_loss_pips': 15,
    'take_profit_pips': 30,
    'max_slippage': 0.001,
    'min_signal_strength': 55,
    'volatility_high': 2.0,
    'volatility_low': 0.5,
}

# ==================== REAL TECHNICAL INDICATOR CALCULATIONS ====================

def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index (RSI) from price list
    
    RSI > 70 = Overbought (SELL signal)
    RSI < 30 = Oversold (BUY signal)
    RSI 30-70 = Neutral
    """
    if len(prices) < period + 1:
        return 50  # Neutral if insufficient data
    
    # Calculate price changes
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Separate gains and losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    # Calculate average gain and loss
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 50
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return min(100, max(0, rsi))


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)
    
    Returns: (macd_line, signal_line, histogram)
    - MACD > Signal = BUY signal
    - MACD < Signal = SELL signal
    """
    if len(prices) < slow + signal:
        return 0, 0, 0
    
    # Calculate exponential moving averages
    ema_fast = sum(prices[-fast:]) / fast
    ema_slow = sum(prices[-slow:]) / slow
    
    macd_line = ema_fast - ema_slow
    signal_line = (macd_line + sum([prices[i] - prices[i-1] for i in range(-signal, 0)]) / signal) / 2
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_moving_averages(prices, short=10, long=20):
    """Calculate short and long moving averages
    
    Returns: (sma_short, sma_long)
    - Price > MA20 = Uptrend
    - Price < MA20 = Downtrend
    - MA10 > MA20 = Strong uptrend
    """
    if len(prices) < long:
        return prices[-1] if prices else 0, prices[-1] if prices else 0
    
    sma_short = sum(prices[-short:]) / short
    sma_long = sum(prices[-long:]) / long
    
    return sma_short, sma_long


def calculate_atr(highs, lows, closes, period=14):
    """Calculate Average True Range (ATR) for volatility measurement
    
    Higher ATR = More volatile
    Lower ATR = Less volatile
    
    Used for position sizing: wider stops on high ATR, tighter on low ATR
    """
    if len(closes) < period:
        return 0.5  # Default minimum ATR
    
    true_ranges = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        tr = max(high_low, high_close, low_close)
        true_ranges.append(tr)
    
    atr = sum(true_ranges[-period:]) / period if true_ranges else 0.5
    return max(atr, 0.1)  # Ensure minimum of 0.1


def evaluate_real_trade_signal(symbol: str, market_data: Dict) -> Dict:
    """Evaluate a REAL trading signal based on technical indicators
    
    Returns: {
        'signal': 'STRONG_BUY' | 'BUY' | 'SELL' | 'STRONG_SELL' | 'NEUTRAL',
        'strength': 0-100,  # Signal confidence
        'rsi': RSI value,
        'trend': 'UP' | 'DOWN' | 'RANGING',
        'volatility': 'HIGH' | 'MEDIUM' | 'LOW',
        'entry_reason': string explanation,
    }
    """
    try:
        # Get price data from market_data
        current_price = market_data.get('current_price', 0)
        if current_price <= 0:
            return {
                'signal': 'NEUTRAL',
                'strength': 0,
                'rsi': 50,
                'trend': 'RANGING',
                'volatility': 'MEDIUM',
                'entry_reason': 'Invalid price data',
            }
        
        # Get price history
        price_history = market_data.get('price_history', [current_price] * 30)[-30:]
        if len(price_history) < 5:
            price_history = [current_price] * 30
        
        # Calculate technical indicators
        rsi = calculate_rsi(price_history, period=14)
        ma_short, ma_long = calculate_moving_averages(price_history, short=10, long=20)
        macd_line, signal_line, histogram = calculate_macd(price_history)
        
        # Determine trend
        if current_price > ma_long:
            if ma_short > ma_long:
                trend = 'UP'
            else:
                trend = 'RANGING'
        else:
            trend = 'DOWN'
        
        # Determine volatility from market data
        volatility_pct = market_data.get('volatility_pct', 1.0)
        params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
        
        if volatility_pct > params['volatility_high']:
            volatility = 'HIGH'
        elif volatility_pct > params['volatility_low']:
            volatility = 'MEDIUM'
        else:
            volatility = 'LOW'
        
        # SIGNAL GENERATION
        strength = 0
        signal = 'NEUTRAL'
        entry_reason = []
        
        # RSI-based signals (0-40)
        if rsi < 30:
            strength += 30
            signal = 'BUY'
            entry_reason.append(f'RSI oversold ({rsi:.0f})')
        elif rsi > 70:
            strength += 30
            signal = 'SELL'
            entry_reason.append(f'RSI overbought ({rsi:.0f})')
        elif 45 < rsi < 55:
            strength += 10
            entry_reason.append(f'RSI neutral ({rsi:.0f})')
        
        # MACD-based signals (0-30)
        if histogram > 0 and macd_line > signal_line:
            strength += 20
            if signal == 'NEUTRAL':
                signal = 'BUY'
            entry_reason.append('MACD bullish')
        elif histogram < 0 and macd_line < signal_line:
            strength += 20
            if signal == 'NEUTRAL':
                signal = 'SELL'
            entry_reason.append('MACD bearish')
        
        # Trend-based signals (0-30)
        if trend == 'UP':
            if signal != 'SELL':
                strength += 15
                if signal == 'NEUTRAL':
                    signal = 'BUY'
                entry_reason.append('Uptrend confirmed')
        elif trend == 'DOWN':
            if signal != 'BUY':
                strength += 15
                if signal == 'NEUTRAL':
                    signal = 'SELL'
                entry_reason.append('Downtrend confirmed')
        
        # Volatility adjustment (0-10)
        if volatility == 'LOW':
            strength += 5
            entry_reason.append('Low volatility - good for tight stops')
        elif volatility == 'HIGH' and signal != 'NEUTRAL':
            strength -= 10
            entry_reason.append('High volatility - reduced confidence')
        
        # Determine signal strength category
        if signal == 'NEUTRAL':
            strength = 0
        else:
            # Amplify if multiple indicators agree
            if len(entry_reason) > 2:
                strength = min(100, strength + 20)
                signal = f'STRONG_{signal}'
        
        strength = min(100, max(0, strength))
        
        return {
            'signal': signal,
            'strength': strength,
            'rsi': round(rsi, 1),
            'trend': trend,
            'volatility': volatility,
            'entry_reason': ' + '.join(entry_reason) if entry_reason else 'No clear signal',
        }
    
    except Exception as e:
        logger.warning(f"Error evaluating signal for {symbol}: {e}")
        return {
            'signal': 'NEUTRAL',
            'strength': 0,
            'rsi': 50,
            'trend': 'RANGING',
            'volatility': 'MEDIUM',
            'entry_reason': f'Error: {str(e)}',
        }


# ==================== BOT TRADING STRATEGY IMPLEMENTATIONS (REAL MARKET BASED) ====================

def scalping_strategy(symbol, account_id, risk_amount, market_data=None):
    """Scalping: Quick trades with small profits (2-3 pips). HIGH WIN RATE, LOW REWARD.
    
    Best for: Liquid pairs (EURUSD), low volatility
    Entry: Strong support/resistance, RSI extreme
    Exit: Quick profit or bounceback stop
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Check if signal is strong enough
    if signal_eval['strength'] < params['min_signal_strength']:
        return None  # Don't trade on weak signal
    
    # Determine direction from signal
    order_type = 'BUY' if 'BUY' in signal_eval['signal'] else 'SELL'
    
    # Tight parameters for scalping
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.0 * (1.0 if signal_eval['strength'] > 70 else 0.7),  # Position size based on signal strength
        'stop_loss': params['stop_loss_pips'] * 0.5,  # Half the normal stop for scalping
        'take_profit': params['take_profit_pips'] * 0.3,  # Tight TP for quick exit
        'signal': signal_eval,
        'duration_seconds': 300,  # 5 minute scalp
    }


def momentum_strategy(symbol, account_id, risk_amount, market_data=None):
    """Momentum: Follow strong price movements. MODERATE WIN RATE, GOOD REWARDS.
    
    Best for: Trending markets, moving averages aligned
    Entry: Price breaks above/below key level with volume
    Exit: Profit target or MA crossover
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Only trade strong signals in momentum mode
    if signal_eval['strength'] < params['min_signal_strength'] + 5:
        return None
    
    # Only trade if trend exists
    if signal_eval['trend'] == 'RANGING':
        return None
    
    order_type = 'BUY' if signal_eval['trend'] == 'UP' else 'SELL'
    
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.5 * (signal_eval['strength'] / 80),  # Scale with signal strength
        'stop_loss': params['stop_loss_pips'],
        'take_profit': params['take_profit_pips'] * 1.5,  # Bigger TP for momentum
        'signal': signal_eval,
        'duration_seconds': 900,  # 15 minutes
    }


def trend_following_strategy(symbol, account_id, risk_amount, market_data=None):
    """Trend Following: Hold trades longer (big trends). LOWER WIN RATE, HIGHER REWARDS.
    
    Best for: Long-term trending markets
    Entry: Breakout on trend confirmation
    Exit: Trend reversal or fixed profit target
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Trend following needs strong trend + strong signal
    if signal_eval['trend'] == 'RANGING':
        return None
    
    if signal_eval['strength'] < params['min_signal_strength']:
        return None
    
    order_type = 'BUY' if signal_eval['trend'] == 'UP' else 'SELL'
    
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.2,
        'stop_loss': params['stop_loss_pips'] * 1.3,  # Wider stop for trend
        'take_profit': params['take_profit_pips'] * 2.0,  # Large TP for big move
        'signal': signal_eval,
        'duration_seconds': 3600,  # 1 hour
    }


def mean_reversion_strategy(symbol, account_id, risk_amount, market_data=None):
    """Mean Reversion: Trade when price extreme. HIGH WIN RATE, MEDIUM REWARDS.
    
    Best for: Ranging markets, overbought/oversold conditions
    Entry: RSI extreme (>70 or <30)
    Exit: Return to mean or fixed profit
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Mean reversion works best when price is extreme (RSI <30 or >70)
    if not (signal_eval['rsi'] < 30 or signal_eval['rsi'] > 70):
        return None  # Only trade at extremes
    
    if signal_eval['strength'] < params['min_signal_strength'] - 5:
        return None
    
    # Trade against the extreme
    order_type = 'BUY' if signal_eval['rsi'] > 70 else 'SELL'
    
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.1,
        'stop_loss': params['stop_loss_pips'],
        'take_profit': params['take_profit_pips'],  # Standard TP
        'signal': signal_eval,
        'duration_seconds': 600,  # 10 minutes
    }


def range_trading_strategy(symbol, account_id, risk_amount, market_data=None):
    """Range Trading: Buy low, sell high within range. VERY HIGH WIN RATE, LOWER REWARDS.
    
    Best for: Consolidating markets with clear support/resistance
    Entry: Price near support (BUY) or resistance (SELL)
    Exit: Opposite level or reversal
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Range trading only works in ranging market
    if signal_eval['trend'] != 'RANGING':
        return None
    
    if signal_eval['strength'] < params['min_signal_strength'] - 10:
        return None
    
    order_type = 'BUY' if 'BUY' in signal_eval['signal'] else 'SELL'
    
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.3,
        'stop_loss': params['stop_loss_pips'] * 0.7,  # Tighter stop for range
        'take_profit': params['take_profit_pips'] * 0.7,  # Quick exit when range breaks
        'signal': signal_eval,
        'duration_seconds': 480,  # 8 minutes
    }


def breakout_strategy(symbol, account_id, risk_amount, market_data=None):
    """Breakout: Trade when price breaks support/resistance. MODERATE WIN RATE, HIGH REWARDS.
    
    Best for: Price nearing key levels
    Entry: Break above/below with momentum
    Exit: Continuation target or failed breakout
    """
    if market_data is None:
        market_data = commodity_market_data.get(symbol, {})
    
    signal_eval = evaluate_real_trade_signal(symbol, market_data)
    params = SYMBOL_PARAMETERS.get(symbol, DEFAULT_SYMBOL_PARAMS)
    
    # Breakout needs strong signal and trend presence
    if signal_eval['strength'] < params['min_signal_strength'] + 10:
        return None
    
    if signal_eval['trend'] == 'RANGING':
        return None
    
    order_type = 'BUY' if signal_eval['trend'] == 'UP' else 'SELL'
    
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': 1.0,
        'stop_loss': params['stop_loss_pips'] * 1.2,  # Protective stop behind level
        'take_profit': params['take_profit_pips'] * 2.5,  # Large profit target for breakout continuation
        'signal': signal_eval,
        'duration_seconds': 1200,  # 20 minutes
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
    """Auto-initialize demo trading bots on startup using VALID_SYMBOLS"""
    # Convert VALID_SYMBOLS set to sorted list for consistent distribution
    valid_symbols_list = sorted(list(VALID_SYMBOLS))
    
    # Dynamically distribute symbols across 3 demo bots
    # Split symbols into 3 groups to ensure each bot has a different strategy focus
    symbols_per_bot = len(valid_symbols_list) // 3
    
    forex_symbols = [s for s in valid_symbols_list if s in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDSEK']]
    metals_symbols = [s for s in valid_symbols_list if s in ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']]
    crypto_stock_symbols = [s for s in valid_symbols_list if s in ['BTCUSD', 'ETHUSD', 'XNIUSD', 'NVDA', 'AMD', 'INTC']]
    
    # Ensure we have symbols for each bot, fallback to evenly distributed if needed
    if not forex_symbols:
        forex_symbols = valid_symbols_list[:symbols_per_bot]
    if not metals_symbols:
        metals_symbols = valid_symbols_list[symbols_per_bot:2*symbols_per_bot]
    if not crypto_stock_symbols:
        crypto_stock_symbols = valid_symbols_list[2*symbols_per_bot:]
    
    demo_bots_config = [
        {
            'botId': 'DemoBot_EURUSD_TrendFollow',
            'accountId': 'Demo MT5 - XM Global',
            'symbols': forex_symbols if forex_symbols else valid_symbols_list[:max(1, len(valid_symbols_list)//3)],
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
            'symbols': metals_symbols if metals_symbols else valid_symbols_list[max(1, len(valid_symbols_list)//3):max(2, 2*len(valid_symbols_list)//3)],
            'strategy': 'Mean Reversion',
            'riskPerTrade': 75,
            'maxDailyLoss': 400,
            'enabled': True,
            'autoSwitch': True,
            'dynamicSizing': True,
            'basePositionSize': 0.8
        },
        {
            'botId': 'DemoBot_Crypto_AlternativeAssets',
            'accountId': 'Demo MT5 - XM Global',
            'symbols': crypto_stock_symbols if crypto_stock_symbols else valid_symbols_list[max(2, 2*len(valid_symbols_list)//3):],
            'strategy': 'Momentum Trading',
            'riskPerTrade': 80,
            'maxDailyLoss': 450,
            'enabled': True,
            'autoSwitch': True,
            'dynamicSizing': True,
            'basePositionSize': 0.9
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


PERSISTED_BOT_STATE_FIELDS = {
    'accountBalance',
    'accountId',
    'allowedVolatility',
    'autoSwitch',
    'basePositionSize',
    'botId',
    'brokerName',
    'broker_type',
    'createdAt',
    'credentialId',
    'dailyProfit',
    'dailyProfits',
    'displayCurrency',
    'drawdownPauseHours',
    'drawdownPausePercent',
    'drawdownPauseUntil',
    'dynamicSizing',
    'enabled',
    'lastStrategySwitch',
    'maxDailyLoss',
    'maxDrawdown',
    'mode',
    'name',
    'peakProfit',
    'profit',
    'profitHistory',
    'profitLock',
    'riskPerTrade',
    'startTime',
    'strategy',
    'strategyHistory',
    'symbols',
    'totalInvestment',
    'totalLosses',
    'totalProfit',
    'totalTrades',
    'tradeHistory',
    'user_id',
    'volatilityLevel',
    'winningTrades',
}


def _default_bot_runtime_state(row: sqlite3.Row) -> Dict[str, Any]:
    created_at = row['created_at'] or datetime.now().isoformat()
    daily_profit = float(row['daily_profit'] or 0.0)
    total_profit = float(row['total_profit'] or 0.0)

    return {
        'botId': row['bot_id'],
        'user_id': row['user_id'],
        'name': row['name'],
        'accountId': row['broker_account_id'],
        'credentialId': row['credential_id'],
        'brokerName': row['broker_name'],
        'broker_type': row['broker_name'] or 'MT5',
        'mode': 'live' if row['is_live'] else 'demo',
        'symbols': row['symbols'].split(',') if row['symbols'] else ['EURUSDm'],
        'strategy': row['strategy'],
        'enabled': bool(row['enabled']),
        'riskPerTrade': 20.0,
        'maxDailyLoss': 60.0,
        'profitLock': 80.0,
        'drawdownPausePercent': 5.0,
        'drawdownPauseHours': 6.0,
        'allowedVolatility': ['Low', 'Medium'],
        'displayCurrency': 'USD',
        'totalTrades': 0,
        'winningTrades': 0,
        'totalProfit': total_profit,
        'totalLosses': 0.0,
        'totalInvestment': 0.0,
        'createdAt': created_at,
        'startTime': created_at,
        'profitHistory': [],
        'tradeHistory': [],
        'dailyProfits': {},
        'dailyProfit': daily_profit,
        'maxDrawdown': 0.0,
        'peakProfit': max(total_profit, 0.0),
        'strategyHistory': [],
        'lastStrategySwitch': created_at,
        'volatilityLevel': 'Medium',
        'profit': total_profit,
        'drawdownPauseUntil': None,
        'accountBalance': 0.0,
    }


def _restore_bot_runtime_state(row: sqlite3.Row) -> Dict[str, Any]:
    bot_state = _default_bot_runtime_state(row)
    runtime_state_raw = row['runtime_state']

    if runtime_state_raw:
        try:
            runtime_state = json.loads(runtime_state_raw)
            if isinstance(runtime_state, dict):
                for key, value in runtime_state.items():
                    if key in PERSISTED_BOT_STATE_FIELDS:
                        bot_state[key] = value
        except Exception as e:
            logger.warning(f"Could not restore runtime state for bot {row['bot_id']}: {e}")

    bot_state['botId'] = row['bot_id']
    bot_state['user_id'] = row['user_id']
    bot_state['name'] = row['name']
    bot_state['accountId'] = row['broker_account_id']
    bot_state['credentialId'] = row['credential_id']
    broker_name = canonicalize_broker_name(row['broker_name']) if row['broker_name'] else 'MT5'
    bot_state['brokerName'] = broker_name
    bot_state['broker_type'] = bot_state.get('broker_type') or broker_name
    bot_state['mode'] = bot_state.get('mode') or ('live' if row['is_live'] else 'demo')
    bot_state['strategy'] = row['strategy']
    bot_state['enabled'] = bool(row['enabled'])
    bot_state['createdAt'] = row['created_at'] or bot_state.get('createdAt') or datetime.now().isoformat()
    restored_symbols = bot_state.get('symbols') or (row['symbols'].split(',') if row['symbols'] else ['EURUSDm'])
    bot_state['symbols'] = validate_and_correct_symbols(restored_symbols, broker_name)
    bot_state['tradeHistory'] = bot_state.get('tradeHistory') or []
    # If tradeHistory is empty after runtime restore, load from trades DB table
    if not bot_state['tradeHistory']:
        try:
            tconn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
            tconn.row_factory = sqlite3.Row
            tcursor = tconn.cursor()
            tcursor.execute(
                'SELECT trade_data FROM trades WHERE bot_id = ? AND trade_data IS NOT NULL ORDER BY timestamp ASC',
                (row['bot_id'],)
            )
            for trow in tcursor.fetchall():
                try:
                    trade = json.loads(trow['trade_data'])
                    bot_state['tradeHistory'].append(trade)
                except Exception:
                    pass
            tconn.close()
            if bot_state['tradeHistory']:
                logger.info(f"📊 Restored {len(bot_state['tradeHistory'])} trades from DB for bot {row['bot_id']}")
        except Exception as e:
            logger.warning(f"Could not load trades from DB for bot {row['bot_id']}: {e}")
    bot_state['profitHistory'] = bot_state.get('profitHistory') or []
    bot_state['dailyProfits'] = bot_state.get('dailyProfits') or {}
    bot_state['strategyHistory'] = bot_state.get('strategyHistory') or []
    bot_state['displayCurrency'] = str(bot_state.get('displayCurrency') or 'USD').upper()
    bot_state['profit'] = bot_state.get('totalProfit', 0.0) or 0.0

    return bot_state


def _extract_persistable_bot_state(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: bot_config.get(key)
        for key in PERSISTED_BOT_STATE_FIELDS
        if key in bot_config
    }


def persist_bot_runtime_state(bot_id: str):
    """Persist bot runtime metrics so they can be restored after a VPS restart."""
    bot_config = active_bots.get(bot_id)
    if not bot_config:
        return

    today = datetime.now().strftime('%Y-%m-%d')
    daily_profit = float(bot_config.get('dailyProfits', {}).get(today, bot_config.get('dailyProfit', 0.0)) or 0.0)
    total_profit = float(bot_config.get('totalProfit', 0.0) or 0.0)
    bot_config['dailyProfit'] = daily_profit
    bot_config['profit'] = total_profit

    runtime_state = _extract_persistable_bot_state(bot_config)
    updated_at = datetime.now().isoformat()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE user_bots
            SET enabled = ?,
                daily_profit = ?,
                total_profit = ?,
                runtime_state = ?,
                updated_at = ?
            WHERE bot_id = ?
            ''',
            (
                1 if bot_config.get('enabled', False) else 0,
                daily_profit,
                total_profit,
                json.dumps(runtime_state),
                updated_at,
                bot_id,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not persist runtime state for bot {bot_id}: {e}")


def _get_bot_thread_credentials(bot_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    credential_id = bot_config.get('credentialId')
    if not credential_id:
        return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT broker_name, account_number, password, server, is_live, api_key
            FROM broker_credentials
            WHERE credential_id = ?
            ''',
            (credential_id,),
        )
        credential_row = cursor.fetchone()
        conn.close()
        if not credential_row:
            return None

        broker_name = canonicalize_broker_name(credential_row['broker_name'])
        if broker_name == 'Binance':
            return {
                'api_key': credential_row['api_key'],
                'api_secret': credential_row['password'],
                'account_number': credential_row['account_number'],
                'server': credential_row['server'] or 'spot',
                'is_live': bool(credential_row['is_live']),
            }

        return {
            'account_number': credential_row['account_number'],
            'password': credential_row['password'],
            'server': credential_row['server'],
            'is_live': bool(credential_row['is_live']),
        }
    except Exception as e:
        logger.warning(f"Could not load broker credentials for bot {bot_config.get('botId')}: {e}")
        return None


def start_enabled_bots_on_startup():
    """Restart previously enabled bots after a backend/VPS restart."""
    if not AUTO_RESTART_BOTS_ON_STARTUP:
        logger.warning("⏸️ Auto-restart of bots on backend startup is disabled (set AUTO_RESTART_BOTS_ON_STARTUP=true to enable)")
        return 0

    restarted_bots = 0

    for bot_id, bot_config in active_bots.items():
        if not bot_config.get('enabled'):
            continue
        if bot_id in bot_threads and bot_threads[bot_id].is_alive():
            continue
        if BOT_STARTUP_RESTART_LIMIT and restarted_bots >= BOT_STARTUP_RESTART_LIMIT:
            logger.warning(
                f"⏸️ Reached BOT_STARTUP_RESTART_LIMIT={BOT_STARTUP_RESTART_LIMIT}; remaining enabled bots were not auto-restarted"
            )
            break

        bot_config['symbols'] = validate_and_correct_symbols(
            bot_config.get('symbols', ['EURUSDm']),
            bot_config.get('brokerName') or bot_config.get('broker_type'),
        )
        bot_stop_flags[bot_id] = False
        running_bots[bot_id] = True
        bot_credentials = _get_bot_thread_credentials(bot_config)
        persist_bot_runtime_state(bot_id)

        bot_thread = threading.Thread(
            target=continuous_bot_trading_loop,
            args=(bot_id, bot_config.get('user_id'), bot_credentials),
            daemon=True,
            name=f"BotThread-{bot_id}",
        )
        bot_threads[bot_id] = bot_thread
        bot_thread.start()
        restarted_bots += 1
        logger.info(f"♻️ Restarted bot {bot_id} from persisted runtime state")
        if BOT_STARTUP_RESTART_DELAY_SECONDS > 0:
            time.sleep(BOT_STARTUP_RESTART_DELAY_SECONDS)

    return restarted_bots


def stop_bot_runtime(bot_id: str, bot_config: Dict[str, Any]) -> Dict[str, Any]:
    if bot_id in bot_threads and bot_threads[bot_id].is_alive():
        logger.info(f"🛑 Bot {bot_id}: Stopping background trading thread...")
        bot_stop_flags[bot_id] = True
        bot_threads[bot_id].join(timeout=30)
        logger.info(f"✅ Bot {bot_id}: Background thread stopped")

    bot_config['enabled'] = False
    running_bots[bot_id] = False
    
    # OPTIMIZATION: Clean up cached connections for this bot to free memory
    user_id = bot_config.get('user_id', '')
    account = bot_config.get('account_number', bot_config.get('accountId', 'unknown'))
    if user_id and account:
        cache_key = f"{user_id}|Exness|{account}"
        with broker_connection_cache_lock:
            if cache_key in broker_connection_cache:
                broker_connection_cache.pop(cache_key)
                logger.debug(f"♻️  Bot {bot_id}: Cached connection cleaned up ({len(broker_connection_cache)} remaining)")
    
    persist_bot_runtime_state(bot_id)

    logger.info(f"⏸️ Bot {bot_id} stopped (still in system, can be restarted)")
    logger.info(f"   Total Trades: {bot_config.get('totalTrades', 0)}")
    logger.info(f"   Total Profit: ${bot_config.get('totalProfit', 0):.2f}")

    return {
        'botId': bot_id,
        'totalTrades': bot_config.get('totalTrades', 0),
        'winningTrades': bot_config.get('winningTrades', 0),
        'totalProfit': round(float(bot_config.get('totalProfit', 0.0) or 0.0), 2),
        'mode': bot_config.get('mode', 'demo'),
        'symbols': bot_config.get('symbols', []),
    }


def load_user_bots_from_database(enabled_only: bool = False):
    """Load user-created bots from database into active_bots memory."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = '''
            SELECT
                ub.bot_id,
                ub.user_id,
                ub.name,
                ub.strategy,
                ub.broker_account_id,
                ub.symbols,
                ub.enabled,
                ub.created_at,
                ub.daily_profit,
                ub.total_profit,
                ub.runtime_state,
                bc.credential_id,
                bcr.broker_name,
                bcr.is_live
            FROM user_bots ub
            LEFT JOIN bot_credentials bc ON bc.bot_id = ub.bot_id AND bc.user_id = ub.user_id
            LEFT JOIN broker_credentials bcr ON bcr.credential_id = bc.credential_id
            WHERE ub.status = 'active'
        '''
        if enabled_only:
            query += ' AND ub.enabled = 1'

        cursor.execute(query)
        
        bots_loaded = 0
        for row in cursor.fetchall():
            bot_id = row['bot_id']

            if bot_id in active_bots:
                continue

            active_bots[bot_id] = _restore_bot_runtime_state(row)
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
                    'displayCurrency': bot.get('displayCurrency', 'USD'),
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
                'drawdownPauseUntil': bot.get('drawdownPauseUntil'),
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
    max_daily_loss = bot_config.get('maxDailyLoss', 0.0) or 0.0
    drawdown_pause_hours = bot_config.get('drawdownPauseHours', 6.0) or 6.0
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()
    daily_profit = bot_config.get('dailyProfits', {}).get(today, 0.0)
    if profit_lock > 0 and daily_profit >= profit_lock:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} hit daily profit lock-in (${daily_profit:.2f} >= ${profit_lock:.2f}), pausing trading for today.")
        return False

    # 2. Daily Loss Cutoff: If today's realized loss exceeds threshold, stop trading for the day
    realized_loss = abs(daily_profit) if daily_profit < 0 else 0.0
    if max_daily_loss > 0 and realized_loss >= max_daily_loss:
        logger.info(
            f"[RISK] Bot {bot_config.get('botId')} hit max daily loss "
            f"(${realized_loss:.2f} >= ${max_daily_loss:.2f}), pausing trading for today."
        )
        return False

    # 3. Drawdown cooldown: pause for a cooldown period, then automatically resume from a fresh baseline.
    drawdown_pause_until_raw = bot_config.get('drawdownPauseUntil')
    if drawdown_pause_until_raw:
        try:
            drawdown_pause_until = datetime.fromisoformat(drawdown_pause_until_raw)
            if now < drawdown_pause_until:
                logger.info(
                    f"[RISK] Bot {bot_config.get('botId')} is in drawdown cooldown until "
                    f"{drawdown_pause_until.isoformat()}, skipping {symbol}."
                )
                return False

            current_total_profit = bot_config.get('totalProfit', 0.0) or 0.0
            bot_config['drawdownPauseUntil'] = None
            bot_config['maxDrawdown'] = 0.0
            bot_config['peakProfit'] = current_total_profit
            logger.info(
                f"[RISK] Bot {bot_config.get('botId')} drawdown cooldown expired; "
                f"resuming trading from fresh baseline profit ${current_total_profit:.2f}."
            )
        except Exception as e:
            logger.warning(f"[RISK] Bot {bot_config.get('botId')} had invalid drawdownPauseUntil value: {e}")
            bot_config['drawdownPauseUntil'] = None

    # 4. Drawdown Pause: If drawdown from peak profit exceeds threshold, pause trading
    peak = bot_config.get('peakProfit', 0)
    max_dd = bot_config.get('maxDrawdown', 0)
    dd_threshold = bot_config.get('drawdownPausePercent', 0.0) or 0.0  # e.g., 10 (%)
    if peak > 0 and dd_threshold > 0:
        dd_percent = (max_dd / peak) * 100
        if dd_percent >= dd_threshold:
            pause_until = now + timedelta(hours=drawdown_pause_hours)
            bot_config['drawdownPauseUntil'] = pause_until.isoformat()
            logger.info(
                f"[RISK] Bot {bot_config.get('botId')} drawdown {dd_percent:.1f}% >= {dd_threshold}%, "
                f"pausing trading until {pause_until.isoformat()}."
            )
            return False

    # 5. Volatility Filter: Only trade if volatility is allowed
    allowed_vol = bot_config.get('allowedVolatility', ['Low', 'Medium'])
    # Get current volatility for symbol
    vol = commodity_market_data.get(symbol, {}).get('volatility', 'Medium')
    if allowed_vol and vol not in allowed_vol:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} skipping {symbol} due to volatility: {vol}")
        return False

    # 6. Regime Check: Only trade if signal is strong (not consolidating/weak)
    signal = commodity_market_data.get(symbol, {}).get('signal', '')
    if 'CONSOLIDAT' in signal or 'VOLATILE' in signal or 'WEAK' in signal:
        logger.info(f"[RISK] Bot {bot_config.get('botId')} skipping {symbol} due to regime: {signal}")
        return False

    return True

def get_live_prices_from_mt5():
    """Fetch real-time prices from MT5 for all available symbols"""
    global previous_prices
    
    try:
        mt5_connection = broker_manager.connections.get('Exness MT5')
        if not mt5_connection:
            logger.debug("❌ Exness MT5 connection not found in broker_manager")
            return None
        
        if not mt5_connection.connected:
            logger.debug("❌ Exness MT5 connection exists but not connected")
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
                momentum_change = 0.0
                breakout_bias = None
                
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

                # Single-tick movement is often too small for FX pairs, so use short-term candle momentum
                # as a fallback before classifying a symbol as consolidating.
                try:
                    recent_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 6)
                except Exception:
                    recent_rates = None

                if recent_rates is not None and len(recent_rates) >= 4:
                    closes = [float(rate['close']) for rate in recent_rates]
                    highs = [float(rate['high']) for rate in recent_rates[-3:]]
                    lows = [float(rate['low']) for rate in recent_rates[-3:]]
                    anchor_close = closes[0]
                    latest_close = closes[-1]

                    if anchor_close:
                        momentum_change = ((latest_close - anchor_close) / anchor_close) * 100

                    recent_high = max(highs)
                    recent_low = min(lows)
                    range_span_pct = ((recent_high - recent_low) / latest_close * 100) if latest_close else 0.0

                    if current_price >= recent_high * 0.9998:
                        breakout_bias = 'UP'
                    elif current_price <= recent_low * 1.0002:
                        breakout_bias = 'DOWN'

                    if trend == 'FLAT':
                        if momentum_change > 0.01 or breakout_bias == 'UP':
                            trend = 'UP'
                            if abs(price_change) < abs(momentum_change):
                                price_change = momentum_change
                        elif momentum_change < -0.01 or breakout_bias == 'DOWN':
                            trend = 'DOWN'
                            if abs(price_change) < abs(momentum_change):
                                price_change = momentum_change
                        elif range_span_pct < 0.03:
                            trend = 'FLAT'
                
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
                            
                else:  # FLAT trend after checking tick + short-term momentum
                    if breakout_bias == 'UP':
                        signal = '🟢 WEAK BUY'
                    elif breakout_bias == 'DOWN':
                        signal = '🔴 WEAK SELL'
                    elif volatility == 'Very High' or volatility == 'High':
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
                if symbol in ['EURUSDm', 'XAUUSDm', 'BTCUSDm', 'ETHUSDm']:
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
    # ===== EXNESS / MT5 MARKET DATA DEFAULTS =====
    'EURUSDm': {'price': 1.0890, 'change': 0.42, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point', 'profitability_score': 0.65},
    'USDJPYm': {'price': 149.50, 'change': 0.52, 'trend': 'UP', 'volatility': 'Low', 'signal': '🟢 BUY', 'recommendation': 'Positive momentum - good entry point', 'profitability_score': 0.62},
    'XAUUSDm': {'price': 2076.44, 'change': 0.68, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Gold strong uptrend - excellent profitability', 'profitability_score': 0.88},
    'BTCUSDm': {'price': 43560.00, 'change': 2.15, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Bitcoin volatile with strong momentum', 'profitability_score': 0.85},
    'ETHUSDm': {'price': 2280.45, 'change': 1.75, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Ethereum strong uptrend - excellent opportunity', 'profitability_score': 0.82},
    'AAPLm': {'price': 215.40, 'change': 0.84, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Steady technology momentum with manageable volatility', 'profitability_score': 0.66},
    'AMDm': {'price': 182.30, 'change': 1.28, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 BUY', 'recommendation': 'Semiconductor strength but watch volatility around news', 'profitability_score': 0.71},
    'MSFTm': {'price': 428.15, 'change': 0.61, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Large-cap trend remains constructive', 'profitability_score': 0.68},
    'NVDAm': {'price': 932.75, 'change': 1.96, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 STRONG BUY', 'recommendation': 'Strong trend but keep tighter risk controls', 'profitability_score': 0.79},
    'JPMm': {'price': 198.60, 'change': 0.39, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Stable financial sector momentum', 'profitability_score': 0.61},
    'BACm': {'price': 41.80, 'change': 0.22, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Lower-priced financial stock with moderate momentum', 'profitability_score': 0.58},
    'WFCm': {'price': 58.40, 'change': 0.31, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Financial sector remains constructive', 'profitability_score': 0.57},
    'GOOGLm': {'price': 176.20, 'change': 0.73, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Large-cap tech trend remains favorable', 'profitability_score': 0.67},
    'METAm': {'price': 498.35, 'change': 1.12, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 BUY', 'recommendation': 'Growth momentum is strong but reactive to earnings', 'profitability_score': 0.72},
    'ORCLm': {'price': 144.70, 'change': 0.48, 'trend': 'UP', 'volatility': 'Medium', 'signal': '🟢 BUY', 'recommendation': 'Cloud and enterprise trend remains positive', 'profitability_score': 0.62},
    'TSMm': {'price': 162.25, 'change': 0.95, 'trend': 'UP', 'volatility': 'High', 'signal': '🟢 BUY', 'recommendation': 'Semiconductor leader with strong directional bias', 'profitability_score': 0.69},
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

# ==================== CONNECTION CACHING (Performance Optimization) ====================
# Cache broker connections to reduce reconnection overhead from 3-5s per cycle to ~100ms
# Format: {f"{user_id}|{broker}|{account}": connection_object}
broker_connection_cache = {}
broker_connection_cache_lock = threading.Lock()  # Thread-safe access

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
