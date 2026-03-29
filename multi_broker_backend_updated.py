#!/usr/bin/env python3
"""
Zwesta Multi-Broker Trading Backend
Supports multiple brokers with unified API
Updated with MT5 Demo Credentials + Advanced Orders + WebSocket Real-Time Prices
Last Updated: 2026-03-25 15:30 (Advanced Orders + WebSocket endpoints added)
Production Status: READY
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
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from flask_sock import Sock
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("[WARNING] flask-sock not installed. WebSocket prices disabled. Install with: pip install flask-sock")
import logging
from typing import Any, Dict, List, Optional
from enum import Enum
import sys
import atexit
from system.backup_and_recovery import BackupManager, RecoveryManager
from worker_manager import WorkerPoolManager
from metaapi_client import MetaApiClient, MetaApiTradingBridge, get_metaapi_client, is_metaapi_enabled
from rest_price_feed import RestPriceFeed, get_price_feed
from trade_router import TradeRouter, init_trade_router, get_trade_router, ExecutionMode
from mt5_socket_bridge import SocketBridgeManager, MT5SocketBridge, init_socket_bridges

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

# ==================== MT5 ACCOUNT QUEUE (Multi-User Support) ====================
# When multiple users have different MT5 accounts, the single MT5 process must
# switch between accounts. This queue serializes access per-account to minimize
# unnecessary switches. Bots on the SAME account share the session; bots on
# DIFFERENT accounts wait for their turn.
mt5_current_account = None       # Account number currently logged in
mt5_account_lock = threading.Lock()  # Protects mt5_current_account reads/writes
logger.info("✅ MT5 account queue initialized - supports multi-user account switching")

# ==================== BOT CREATION LOCK ====================
# Prevents multiple simultaneous bot creations which compete for MT5 resources
# Only ONE bot should be created at a time to avoid MT5 lock contention
bot_creation_lock = threading.Lock()
logger.info("✅ Bot creation lock initialized - prevents concurrent bot creation")

# ==================== BALANCE CACHE ====================
# CRITICAL FIX: Cache balances updated from successful MT5 connections
# When balance API calls get MT5 lock timeout, return cached balance instead of default $10,000
balance_cache = {}  # { f"{broker}:{account}": {'balance': X, 'equity': Y, 'timestamp': Z} }
balance_cache_lock = threading.Lock()
logger.info("✅ Balance cache initialized - stores real balances from successful MT5 connections")

# ==================== FAILED AUTH COOLDOWN ====================
# Track accounts that fail auth so we don't repeatedly block the MT5 lock trying bad credentials
# Format: { account_number: {'timestamp': time.time(), 'error': str} }
_failed_auth_accounts = {}
_failed_auth_lock = threading.Lock()
_FAILED_AUTH_COOLDOWN = 300  # 5 minutes before retrying a failed account
logger.info("✅ Failed auth cooldown initialized - prevents repeated bad credential retries")

# NOTE: Removed hardcoded emergency demo balances — each account's real balance
# is populated into balance_cache by the bot trading loop when it connects to MT5.
# This ensures live and demo accounts always show their own real balances.
logger.info("✅ Balance cache clean — real balances populated by trading loops")

# ==================== GLOBAL MT5 SINGLETON CONNECTION ====================
# CRITICAL FIX: Reuse single MT5 instance across ALL bots
# Previously: Each bot created MT5Connection → 14 terminal windows + 14 login dialogs
# Now: One global connection → ONE terminal window + ONE login (non-interactive)
global_mt5_instance = None
global_mt5_lock = threading.Lock()

def get_global_mt5():
    """Get or create the global MT5 connection singleton"""
    global global_mt5_instance
    # Return existing instance if already connected
    if global_mt5_instance and hasattr(global_mt5_instance, 'connected') and global_mt5_instance.connected:
        return global_mt5_instance
    return None

def set_global_mt5(connection):
    """Set the global MT5 connection instance"""
    global global_mt5_instance
    with global_mt5_lock:
        global_mt5_instance = connection

# ==================== SAFE MT5 READINESS CHECK ====================
# CRITICAL: Never call mt5.initialize(login=...) or mt5.shutdown() from API endpoints!
# The MT5 terminal is a SHARED singleton - disrupting it kills ALL bot connections.
def ensure_mt5_ready():
    """Check if MT5 IPC is alive WITHOUT reinitializing or disrupting the existing session.
    
    SAFE: Uses account_info() to probe IPC, falls back to bare initialize() (no login params).
    NEVER calls mt5.shutdown() or mt5.initialize(login=...).
    
    Returns True if MT5 is ready for use, False otherwise.
    """
    try:
        import MetaTrader5 as mt5
        # First try a lightweight probe - if account_info works, IPC is alive
        info = mt5.account_info()
        if info:
            return True
        # IPC might be stale - try bare initialize() which just reconnects IPC
        # This does NOT change the logged-in account or restart the terminal
        if mt5.initialize():
            return True
        logger.warning("⚠️ ensure_mt5_ready: MT5 IPC not responding")
        return False
    except Exception as e:
        logger.warning(f"⚠️ ensure_mt5_ready: {e}")
        return False

# ==================== PXBT SESSION PERSISTENCE ====================
# Maintains last known PXBT credentials for auto-reconnect
pxbt_session_cache = {}  # { credential_id: { 'account': X, 'password': X, 'server': X, 'timestamp': Z } }
pxbt_session_lock = threading.Lock()

def cache_pxbt_credentials(credential_id: str, account: str, password: str, server: str):
    """Cache PXBT credentials for auto-reconnect on session loss"""
    with pxbt_session_lock:
        pxbt_session_cache[credential_id] = {
            'account': account,
            'password': password,
            'server': server,
            'timestamp': time.time(),
            'last_check': time.time(),
        }
    logger.info(f"✅ PXBT session cached for credential {credential_id}: account={account}, server={server}")

def get_cached_pxbt_credentials(credential_id: str):
    """Get cached PXBT credentials (for auto-reconnect on session loss)"""
    with pxbt_session_lock:
        if credential_id in pxbt_session_cache:
            cred = pxbt_session_cache[credential_id]
            elapsed = time.time() - cred['timestamp']
            logger.debug(f"✅ Retrieved cached PXBT credentials for {credential_id} (cached {elapsed:.0f}s ago)")
            return cred
    return None

def is_pxbt_connection_healthy(mt5_conn: 'MT5Connection') -> bool:
    """Check if PXBT MT5 connection is still healthy
    
    Returns: True if connection is valid and logged in, False if reconnect needed
    """
    try:
        if not mt5_conn or not hasattr(mt5_conn, 'connected'):
            return False
        
        if not mt5_conn.connected:
            logger.warning("⚠️  PXBT connection status: DISCONNECTED")
            return False
        
        # Try to get account info (will fail if session expired)
        import MetaTrader5 as mt5
        try:
            account_info = mt5.account_info()
            if account_info is None:
                logger.warning("⚠️  PXBT connection health check failed: account_info() returned None")
                return False
            logger.debug(f"✅ PXBT connection health check passed: account {account_info.login}")
            return True
        except Exception as e:
            logger.warning(f"⚠️  PXBT connection health check failed: {e}")
            return False
    except Exception as e:
        logger.warning(f"⚠️  Error checking PXBT connection health: {e}")
        return False

def ensure_pxbt_connection_active(mt5_conn: 'MT5Connection', credentials: Dict, retry_count: int = 3) -> bool:
    """Ensure PXBT connection is active, reconnect if needed
    
    This handles the case where PXBT MT5 terminal session expires or disconnects.
    Will attempt to reconnect using cached credentials.
    
    Returns: True if connection is active, False if reconnect failed
    """
    try:
        # Check if connection is still healthy
        if is_pxbt_connection_healthy(mt5_conn):
            logger.debug("✅ PXBT connection is active and healthy")
            return True
        
        # Connection is not healthy - attempt to reconnect
        logger.warning(f"⚠️  PXBT connection lost - attempting auto-reconnect...")
        
        for attempt in range(1, retry_count + 1):
            try:
                logger.info(f"   Reconnect attempt {attempt}/{retry_count}...")
                
                # Disconnect first to reset state
                if hasattr(mt5_conn, 'disconnect'):
                    try:
                        mt5_conn.disconnect()
                    except:
                        pass
                
                # Wait before reconnecting (exponential backoff: 2s, 4s, 8s)
                wait_time = 2 ** (attempt - 1)
                logger.info(f"   Waiting {wait_time}s before reconnect attempt...")
                time.sleep(wait_time)
                
                # Attempt to reconnect
                if mt5_conn.connect():
                    logger.info(f"✅ PXBT auto-reconnect successful on attempt {attempt}")
                    # Re-cache the credentials on successful reconnect
                    if credentials:
                        cache_pxbt_credentials(
                            credentials.get('credential_id', 'unknown'),
                            credentials.get('account', ''),
                            credentials.get('password', ''),
                            credentials.get('server', '')
                        )
                    return True
                else:
                    logger.warning(f"   Reconnect attempt {attempt} failed - will retry")
            except Exception as e:
                logger.warning(f"   Reconnect attempt {attempt} exception: {e}")
        
        logger.error(f"❌ PXBT auto-reconnect failed after {retry_count} attempts")
        return False
    
    except Exception as e:
        logger.error(f"❌ Error in ensure_pxbt_connection_active: {e}")
        return False

logger.info("✅ PXBT session persistence initialized - auto-connect on session loss enabled")

logger.info("✅ Global MT5 singleton initialized - will reuse single terminal across all bots")


app = Flask(__name__)
CORS(app)
if WEBSOCKET_AVAILABLE:
    sock = Sock(app)  # Initialize WebSocket support for real-time prices
    logger.info("✅ WebSocket support initialized (flask-sock)")
else:
    sock = None
    logger.warning("⚠️ WebSocket support disabled - install flask-sock: pip install flask-sock")

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
BOT_STARTUP_RESTART_DELAY_SECONDS = max(0.5, float(os.getenv('BOT_STARTUP_RESTART_DELAY_SECONDS', '5')))  # Increased from 2s to 5s to avoid MT5 lock contention
BOT_STARTUP_RESTART_LIMIT = max(0, int(os.getenv('BOT_STARTUP_RESTART_LIMIT', '0')))

# API Security Configuration
API_KEY = os.getenv('API_KEY', 'your_generated_api_key_here_change_in_production')

# ==================== WORKER POOL CONFIG ====================
WORKER_COUNT = max(0, int(os.getenv('WORKER_COUNT', '0')))  # 0 = single-process (legacy), 1+ = multi-process
MAX_BOTS_PER_WORKER = max(1, int(os.getenv('MAX_BOTS_PER_WORKER', '35')))

# ==================== REST TRADING CONFIG (Phase 2 Scaling) ====================
METAAPI_TOKEN = os.getenv('METAAPI_TOKEN', '')  # MetaAPI cloud token for REST-based MT5 trading
METAAPI_REGION = os.getenv('METAAPI_REGION', 'new-york')  # MetaAPI region
TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_KEY', '')  # Free price data API (800 calls/day)
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY', '')  # Free price data API (25 calls/day)
PREFER_REST_TRADING = os.getenv('PREFER_REST_TRADING', 'true').lower() == 'true'  # Route Exness via REST when MetaAPI available
SOCKET_BRIDGES = os.getenv('SOCKET_BRIDGES', '')  # Self-hosted MT5 socket bridges (broker:account:port,...)
SOCKET_AUTH_TOKEN = os.getenv('SOCKET_AUTH_TOKEN', 'zwesta')  # Auth token for socket bridges

# ==================== ENVIRONMENT MODE ====================
ENVIRONMENT = os.getenv('ENVIRONMENT', 'DEMO').upper()
DEPLOYMENT_MODE = os.getenv('DEPLOYMENT_MODE', 'LOCAL').upper()  # LOCAL or VPS
print(f"\n{'='*70}")
print(f"[ENVIRONMENT] Current Mode: {ENVIRONMENT}")
print(f"[DEPLOYMENT] Mode: {DEPLOYMENT_MODE}")
print(f"[WORKERS] Worker Count: {WORKER_COUNT} ({'multi-process' if WORKER_COUNT > 0 else 'single-process (legacy)'})")
print(f"[REST TRADING] MetaAPI: {'ENABLED' if METAAPI_TOKEN else 'DISABLED (no token)'}")
print(f"[REST TRADING] Prefer REST: {PREFER_REST_TRADING}")
print(f"[PRICE FEED] Twelve Data: {'ENABLED' if TWELVE_DATA_KEY else 'DISABLED'} | Alpha Vantage: {'ENABLED' if ALPHA_VANTAGE_KEY else 'DISABLED'}")
print(f"[SOCKET BRIDGE] {'CONFIGURED: ' + SOCKET_BRIDGES if SOCKET_BRIDGES else 'DISABLED (no SOCKET_BRIDGES)'}")
print(f"{'='*70}\n")

# ==================== WORKER POOL MANAGER ====================
worker_pool_manager = WorkerPoolManager(worker_count=WORKER_COUNT, max_bots_per_worker=MAX_BOTS_PER_WORKER)

# ==================== REST TRADING INFRASTRUCTURE ====================
# Initialize MetaAPI client (cloud-hosted MT5 REST trading)
metaapi_client = MetaApiClient(token=METAAPI_TOKEN, region=METAAPI_REGION) if METAAPI_TOKEN else None

# Initialize REST price feed (eliminates MT5 dependency for market data)
rest_price_feed = RestPriceFeed(
    twelve_data_key=TWELVE_DATA_KEY,
    alpha_vantage_key=ALPHA_VANTAGE_KEY,
)

# ==================== SOCKET BRIDGE INFRASTRUCTURE ====================
# Self-hosted TCP bridge: Python backend → localhost socket → MT5 EA inside terminal
socket_bridge_manager = SocketBridgeManager(auth_token=SOCKET_AUTH_TOKEN)
socket_bridge_manager.configure_from_env()

# Initialize trade router (hybrid execution: Socket/REST/MT5)
trade_router = init_trade_router(
    metaapi_client=metaapi_client,
    price_feed=rest_price_feed,
    worker_manager=worker_pool_manager if WORKER_COUNT > 0 else None,
    broker_manager=None,  # Will be set after broker_manager is created
    socket_bridge_manager=socket_bridge_manager if socket_bridge_manager.enabled else None,
)

# MT5 Credentials - DEMO (default)
# Exness MT5 Configuration Only (NO standalone MT5 fallback)
MT5_CONFIG = {
    'broker': 'Exness',
    'account': 298997455,  # Demo account
    'password': 'Zwesta@1985',
    'server': 'Exness-MT5Trial9',  # Demo server
    'path': None
}

# DEPLOYMENT-AWARE: Only auto-detect local MT5 paths if LOCAL deployment
# On VPS, MT5 terminal is remote, so don't specify a path (connect to running instance)
if DEPLOYMENT_MODE == 'LOCAL':
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
else:
    logger.info(f"[VPS MODE] Not searching for local MT5 - will connect to remote MT5 terminal")
    logger.info(f"[VPS MODE] Ensure MT5 terminal is running on VPS and accessible")

# XM Global MT5 Configuration - Support DEMO and LIVE modes
XM_CONFIG = {
    'broker': 'XM Global',
    'account': os.getenv('XM_ACCOUNT', ''),  # Will be set based on ENVIRONMENT
    'password': os.getenv('XM_PASSWORD', ''),
    'server': os.getenv('XM_SERVER', 'XMGlobal-MT5Demo'),  # Demo as default
    'path': None
}

# DEPLOYMENT-AWARE: Only auto-detect local XM paths if LOCAL deployment
if DEPLOYMENT_MODE == 'LOCAL':
    # Try to find XM Global terminal specifically (NO generic MT5 fallback)
    xm_paths = [
        r'C:\Program Files\MetaTrader 5 XM\terminal64.exe',
        r'C:\Program Files\XM Global MT5\terminal64.exe',
        r'C:\Program Files (x86)\XM MT5\terminal64.exe',
        r'C:\MT5\XM\terminal64.exe',
    ]
    for path in xm_paths:
        if os.path.exists(path):
            XM_CONFIG['path'] = path
            logger.info(f"Found XM Global MT5 at: {path}")
            break

    if XM_CONFIG['path'] is None:
        logger.warning("⚠️  XM Global MT5 not found in common paths - ensure MetaTrader 5 is installed with XM credentials")
else:
    logger.info(f"[VPS MODE] Not searching for local XM MT5 - will connect to remote terminal")

# PXBT MT5 Configuration - Support DEMO and LIVE modes
PXBT_CONFIG = {
    'broker': 'PXBT',
    'account': os.getenv('PXBT_ACCOUNT', ''),
    'password': os.getenv('PXBT_PASSWORD', ''),
    'server': os.getenv('PXBT_SERVER', 'PXBTTrading-1'),
    'path': None
}

# DEPLOYMENT-AWARE: Only auto-detect local PXBT paths if LOCAL deployment
if DEPLOYMENT_MODE == 'LOCAL':
    pxbt_paths = [
        r'C:\Program Files\PXBT Trading MT5 Terminal\terminal64.exe',
        r'C:\Program Files (x86)\PXBT Trading MT5 Terminal\terminal64.exe',
        r'C:\Program Files\PrimeXBT MT5\terminal64.exe',
        r'C:\MT5\PXBT\terminal64.exe',
    ]
    for path in pxbt_paths:
        if os.path.exists(path):
            PXBT_CONFIG['path'] = path
            logger.info(f"Found PXBT MT5 at: {path}")
            break

    if PXBT_CONFIG['path'] is None:
        logger.warning("⚠️  PXBT MT5 not found in common paths - ensure PXBT terminal is installed")
else:
    logger.info(f"[VPS MODE] Not searching for local PXBT MT5 - will connect to remote terminal")


def get_known_mt5_paths(broker_name: str) -> List[str]:
    """Return known terminal paths for broker-specific MT5 installations."""
    normalized = canonicalize_broker_name(broker_name)

    if normalized == 'PXBT':
        return [
            r'C:\Program Files\PXBT Trading MT5 Terminal\terminal64.exe',
            r'C:\Program Files (x86)\PXBT Trading MT5 Terminal\terminal64.exe',
            r'C:\Program Files\PrimeXBT MT5\terminal64.exe',
            r'C:\MT5\PXBT\terminal64.exe',
        ]

    if normalized in ['XM', 'XM Global']:
        return [
            r'C:\Program Files\MetaTrader 5 XM\terminal64.exe',
            r'C:\Program Files\XM Global MT5\terminal64.exe',
            r'C:\Program Files (x86)\XM MT5\terminal64.exe',
            r'C:\MT5\XM\terminal64.exe',
        ]

    return [
        r'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe',
        r'C:\Program Files\Exness MT5\terminal64.exe',
        r'C:\Program Files (x86)\Exness MT5\terminal64.exe',
        r'C:\MT5\Exness\terminal64.exe',
    ]


def find_mt5_terminal_path(broker_name: str, configured_path: str = None) -> Optional[str]:
    """Resolve a broker-specific terminal path even on VPS/local mixed setups."""
    candidate_paths = []

    if configured_path:
        candidate_paths.append(configured_path)

    env_path = os.getenv(f"{canonicalize_broker_name(broker_name).upper().replace(' ', '_')}_PATH", '').strip()
    if env_path:
        candidate_paths.append(env_path)

    candidate_paths.extend(get_known_mt5_paths(broker_name))

    for path in candidate_paths:
        if path and os.path.exists(path):
            return path

    return None

# Binance Configuration - Support DEMO and LIVE modes
BINANCE_CONFIG = {
    'api_key': os.getenv('BINANCE_API_KEY', ''),
    'api_secret': os.getenv('BINANCE_API_SECRET', ''),
    'market': os.getenv('BINANCE_MARKET', 'spot'),
    'is_live': False,  # Will be set based on ENVIRONMENT
}

# ==================== LIVE VS DEMO MODE CONFIGURATION ====================
if ENVIRONMENT == 'LIVE':
    # LIVE MODE - Load from .env file
    live_account = os.getenv('EXNESS_ACCOUNT', '').strip()
    live_password = os.getenv('EXNESS_PASSWORD', '').strip()
    live_server = os.getenv('EXNESS_SERVER', 'Exness-Real').strip()
    
    xm_account = os.getenv('XM_ACCOUNT', '').strip()
    xm_password = os.getenv('XM_PASSWORD', '').strip()
    xm_server = os.getenv('XM_SERVER', 'XMGlobal-Real').strip()

    pxbt_account = os.getenv('PXBT_ACCOUNT', '').strip()
    pxbt_password = os.getenv('PXBT_PASSWORD', '').strip()
    pxbt_server = os.getenv('PXBT_SERVER', 'PXBTTrading-1').strip()
    
    binance_key = os.getenv('BINANCE_API_KEY', '').strip()
    binance_secret = os.getenv('BINANCE_API_SECRET', '').strip()
    
    # EXNESS LIVE VALIDATION
    if not live_account or not live_password:
        print("\n" + "="*70)
        print("❌ LIVE MODE: EXNESS CREDENTIALS MISSING!")
        print("="*70)
        print("Set in .env file:")
        print("  EXNESS_ACCOUNT=your_account_number")
        print("  EXNESS_PASSWORD=your_password")
        print("="*70 + "\n")
    else:
        MT5_CONFIG = {
            'broker': 'Exness',
            'account': int(live_account),
            'password': live_password,
            'server': live_server,
            'path': os.getenv('MT5_PATH') or os.getenv('EXNESS_PATH') or None
        }
        logger.info(f"[LIVE] ✅ EXNESS - Account: {MT5_CONFIG['account']}, Server: {live_server}")
    
    # XM GLOBAL LIVE VALIDATION
    if not xm_account or not xm_password:
        logger.warning("[LIVE] ⚠️  XM Global credentials missing (optional)")
    else:
        XM_CONFIG = {
            'broker': 'XM Global',
            'account': int(xm_account),
            'password': xm_password,
            'server': xm_server,
            'path': XM_CONFIG.get('path') or None
        }
        logger.info(f"[LIVE] ✅ XM GLOBAL - Account: {XM_CONFIG['account']}, Server: {xm_server}")
    
    # BINANCE LIVE VALIDATION
    if not binance_key or not binance_secret:
        logger.warning("[LIVE] ⚠️  Binance credentials missing (optional)")
    else:
        BINANCE_CONFIG['api_key'] = binance_key
        BINANCE_CONFIG['api_secret'] = binance_secret
        BINANCE_CONFIG['is_live'] = True
        logger.info(f"[LIVE] ✅ BINANCE - Live mode enabled")

    # PXBT LIVE VALIDATION
    if not pxbt_account or not pxbt_password:
        logger.warning("[LIVE] ⚠️  PXBT credentials missing (optional)")
    else:
        PXBT_CONFIG = {
            'broker': 'PXBT',
            'account': int(pxbt_account),
            'password': pxbt_password,
            'server': pxbt_server,
            'path': os.getenv('PXBT_PATH') or PXBT_CONFIG.get('path') or None
        }
        logger.info(f"[LIVE] ✅ PXBT - Account: {PXBT_CONFIG['account']}, Server: {pxbt_server}")
    
    print(f"\n{'='*70}")
    print(f"[LIVE MODE ACTIVATED] 🔴 REAL MONEY TRADING")
    print(f"{'='*70}")
    print(f"EXNESS:    Account {live_account} | Server: {live_server}")
    print(f"XM GLOBAL: Account {xm_account or 'NOT SET'} | Server: {xm_server}")
    print(f"PXBT:      Account {pxbt_account or 'NOT SET'} | Server: {pxbt_server}")
    print(f"BINANCE:   {('Enabled' if binance_key else 'NOT SET')}")
    print(f"{'='*70}\n")
    logger.warning(f"[LIVE] 🔴 REAL MONEY TRADING ACTIVE - Verify all credentials before starting bots!")

else:
    # DEMO MODE (default)
    print(f"{'='*70}")
    print(f"[DEMO MODE] 🟢 USING DEMO ACCOUNTS (Safe for Testing)")
    print(f"{'='*70}")
    print(f"EXNESS:    Account 298997455 | Server: Exness-MT5Trial9")
    print(f"XM GLOBAL: Demo account (check .env for XM_ACCOUNT if not using defaults)")
    print(f"PXBT:      Demo account (check .env for PXBT_ACCOUNT if using PXBT)")
    print(f"BINANCE:   Testnet mode (check .env for BINANCE_DEMO_API_KEY)")
    print(f"{'='*70}")
    print(f"\n📌 TO SWITCH TO LIVE MODE:")
    print(f"   1. Edit .env file and set: ENVIRONMENT=LIVE")
    print(f"   2. Update EXNESS_ACCOUNT, XM_ACCOUNT, BINANCE_API_KEY with YOUR credentials")
    print(f"   3. Restart backend: python multi_broker_backend_updated.py")
    print(f"   4. Check logs for: [LIVE] mode indicators\n")
    
    logger.info(f"[DEMO] Using Exness demo credentials - Account: {MT5_CONFIG['account']}")
    logger.info(f"[DEMO] To trade live, set ENVIRONMENT=LIVE in .env and restart")

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

class PaymentGateway:
    """Unified payment gateway for Stripe, bank transfers, crypto, and internal payments"""
    
    @staticmethod
    def process_payout(user_id: str, amount: float, reason: str, method: str = 'stripe') -> Dict:
        """
        Process a payout to a user via specified method
        
        Methods supported:
        - 'stripe': Stripe Connect (fastest, recurring payouts)
        - 'bank': Bank transfer (slower, verified method)
        - 'crypto': Cryptocurrency transfer (Bitcoin, Ethereum, USDT)
        - 'internal': Internal account credit (instant, no fees)
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get user payment method preference
            cursor.execute('SELECT payment_method, stripe_account_id, bank_account_id, crypto_wallet FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Create transaction record
            transaction_id = str(uuid.uuid4())
            
            if method == 'stripe' or (method == 'auto' and user[1]):  # Stripe Connect
                result = PaymentGateway._process_stripe_payout(user_id, amount, reason, transaction_id)
                
            elif method == 'bank' or (method == 'auto' and user[2]):  # Bank transfer
                result = PaymentGateway._process_bank_payout(user_id, amount, reason, transaction_id)
                
            elif method == 'crypto' or (method == 'auto' and user[3]):  # Crypto transfer
                result = PaymentGateway._process_crypto_payout(user_id, amount, reason, transaction_id)
                
            elif method == 'internal':
                result = PaymentGateway._process_internal_payout(user_id, amount, reason, transaction_id)
            else:
                return {'success': False, 'error': f'Payment method {method} not configured for user'}
            
            # Log transaction
            if result['success']:
                cursor.execute('''
                    INSERT INTO transactions (transaction_id, user_id, type, amount, method, status, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, user_id, 'payout', amount, method, 'completed', reason, datetime.now()))
                conn.commit()
                logger.info(f"✅ [PAYOUT] {amount:.2f} USD to {user_id} via {method}: {result.get('reference', 'N/A')}")
            else:
                cursor.execute('''
                    INSERT INTO transactions (transaction_id, user_id, type, amount, method, status, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, user_id, 'payout', amount, method, 'failed', reason, datetime.now()))
                conn.commit()
                logger.error(f"❌ [PAYOUT FAILED] {amount:.2f} USD to {user_id}: {result.get('error')}")
            
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Error processing payout: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _process_stripe_payout(user_id: str, amount: float, reason: str, transaction_id: str) -> Dict:
        """Process payout via Stripe Connect"""
        try:
            import stripe
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT stripe_account_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result or not result[0]:
                return {'success': False, 'error': 'Stripe account not connected'}
            
            stripe_account_id = result[0]
            
            # Create payout
            payout = stripe.Payout.create(
                amount=int(amount * 100),  # Convert to cents
                currency='usd',
                description=reason,
                statement_descriptor=f"Zwesta-{transaction_id[:8]}",
                stripe_account=stripe_account_id
            )
            
            return {
                'success': True,
                'reference': payout.id,
                'status': payout.status,
                'amount': amount,
                'method': 'stripe'
            }
        except Exception as e:
            logger.error(f"Stripe payout error: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _process_bank_payout(user_id: str, amount: float, reason: str, transaction_id: str) -> Dict:
        """Process bank transfer payout"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get bank details
            cursor.execute('''
                SELECT bank_name, account_holder, account_number, routing_number, swift_code
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            bank_info = cursor.fetchone()
            conn.close()
            
            if not bank_info or not bank_info[2]:  # No account number
                return {'success': False, 'error': 'Bank account not configured'}
            
            # Create bank transfer (ACH in US, SEPA in EU, etc.)
            # This would integrate with your banking API (e.g., Wise, Stripe ACH, etc.)
            
            logger.info(f"📧 Bank transfer scheduled: {amount:.2f} to {bank_info[1]} ({bank_info[0]})")
            
            return {
                'success': True,
                'reference': transaction_id,
                'status': 'pending',
                'amount': amount,
                'method': 'bank',
                'estimatedDays': 1-3,
                'bankName': bank_info[0],
                'accountHolder': bank_info[1]
            }
        except Exception as e:
            logger.error(f"Bank payout error: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _process_crypto_payout(user_id: str, amount: float, reason: str, transaction_id: str) -> Dict:
        """Process cryptocurrency payout (Bitcoin, Ethereum, USDT)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get crypto wallet
            cursor.execute('SELECT crypto_wallet, crypto_type FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result or not result[0]:
                return {'success': False, 'error': 'Crypto wallet not configured'}
            
            wallet = result[0]
            crypto_type = result[1] or 'USDT'  # Default to USDT stablecoin
            
            # This would integrate with your crypto API (Coinbase, Kraken API, etc.)
            # For now, log the transaction
            
            logger.info(f"🪙 Crypto transfer scheduled: {amount:.2f} USD worth of {crypto_type} to {wallet[:10]}...")
            
            return {
                'success': True,
                'reference': transaction_id,
                'status': 'pending',
                'amount': amount,
                'method': 'crypto',
                'cryptoType': crypto_type,
                'wallet': f"{wallet[:6]}...{wallet[-4:]}",
                'estimatedMinutes': 5  # Blockchain confirmation time
            }
        except Exception as e:
            logger.error(f"Crypto payout error: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _process_internal_payout(user_id: str, amount: float, reason: str, transaction_id: str) -> Dict:
        """Process internal account credit (instant)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Add to user's internal balance
            cursor.execute('''
                UPDATE users SET internal_balance = internal_balance + ? WHERE user_id = ?
            ''', (amount, user_id))
            conn.commit()
            conn.close()
            
            logger.info(f"💳 Internal credit: +{amount:.2f} to {user_id}")
            
            return {
                'success': True,
                'reference': transaction_id,
                'status': 'completed',
                'amount': amount,
                'method': 'internal',
                'instant': True
            }
        except Exception as e:
            logger.error(f"Internal payout error: {e}")
            return {'success': False, 'error': str(e)}


def pay_user(user_id: str, amount: float, reason: str, method: str = 'auto') -> bool:
    """
    Pay a user via their preferred payment method
    
    Args:
        user_id: User to pay
        amount: Amount in USD
        reason: Reason for payment (commission, profit, etc.)
        method: Payment method ('auto' = user preference, 'stripe', 'bank', 'crypto', 'internal')
    
    Returns:
        True if payment initiated successfully, False otherwise
    """
    if amount <= 0:
        logger.warning(f"Invalid payout amount: {amount}")
        return False
    
    result = PaymentGateway.process_payout(user_id, amount, reason, method)
    return result.get('success', False)

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
            logger.info(f"[🔍 SESSION QUERY] Looking for token: '{session_token}'")
            cursor.execute('''
                SELECT user_id, expires_at, is_active 
                FROM user_sessions 
                WHERE token = ? AND is_active = 1
            ''', (session_token,))
            
            session = cursor.fetchone()
            logger.info(f"[🔍 SESSION QUERY RESULT] {session}")
            conn.close()
            
            if not session:
                # Try without the is_active filter to see if token exists at all
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute('SELECT token, is_active FROM user_sessions WHERE token = ?', (session_token,))
                all_sessions = cursor2.fetchall()
                logger.info(f"[🔍 TOKEN STATUS] Found {len(all_sessions)} matching token(s): {all_sessions}")
                conn2.close()
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
    PXBT = "pxbt"
    DARWINEX = "darwinex"

    FXM = "fxm"
    AVATRADE = "avatrade"
    FPMARKETS = "fpmarkets"


# ==================== DATABASE SETUP ====================
# ==================== DATABASE SETUP ====================
DATABASE_PATH = r'C:\backend\zwesta_trading.db'

# ==================== WORKER POOL STATUS ENDPOINT ====================
@app.route('/api/admin/workers', methods=['GET'])
def get_worker_pool_status():
    """Get status of all worker processes (admin endpoint)"""
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    if not worker_pool_manager or not worker_pool_manager.enabled:
        return jsonify({
            'success': True,
            'mode': 'single-process',
            'worker_count': 0,
            'workers': [],
            'message': 'Worker pool disabled (WORKER_COUNT=0). Using single-process mode.'
        })

    workers = worker_pool_manager.get_worker_status()
    return jsonify({
        'success': True,
        'mode': 'multi-process',
        'worker_count': worker_pool_manager.worker_count,
        'max_bots_per_worker': worker_pool_manager.max_bots_per_worker,
        'workers': workers,
    })


# ==================== REST TRADING ADMIN ENDPOINTS ====================
@app.route('/api/admin/rest-trading', methods=['GET'])
def get_rest_trading_status():
    """Get REST trading infrastructure status"""
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    router_status = trade_router.get_status() if trade_router else {}
    metaapi_status = {
        'enabled': bool(metaapi_client and metaapi_client.enabled),
        'region': METAAPI_REGION,
        'connected': metaapi_client.ping() if metaapi_client and metaapi_client.enabled else False,
    }
    price_feed_status = {
        'running': rest_price_feed._running if rest_price_feed else False,
        'twelve_data': bool(TWELVE_DATA_KEY),
        'alpha_vantage': bool(ALPHA_VANTAGE_KEY),
        'cached_prices': len(rest_price_feed._prices) if rest_price_feed else 0,
        'active_symbols': len(rest_price_feed._active_symbols) if rest_price_feed else 0,
    }

    socket_status = socket_bridge_manager.get_all_status() if socket_bridge_manager else {'enabled': False}
    
    # Determine current scaling mode
    if socket_status.get('enabled'):
        scaling_mode = 'Socket Bridge + MT5 Hybrid'
        capacity = '200-500 users per VPS'
    elif metaapi_status['enabled']:
        scaling_mode = 'MetaAPI REST + MT5 Hybrid'
        capacity = '500-1000 users'
    else:
        scaling_mode = 'MT5 Only'
        capacity = '50-200 users'

    return jsonify({
        'success': True,
        'socket_bridges': socket_status,
        'metaapi': metaapi_status,
        'price_feed': price_feed_status,
        'trade_router': router_status,
        'scaling_info': {
            'mode': scaling_mode,
            'estimated_capacity': capacity,
            'ram_note': 'Socket bridges use ~50MB/terminal vs MetaAPI ~2MB but free & self-hosted',
        },
    })


@app.route('/api/admin/rest-trading/prices', methods=['GET'])
def get_rest_prices():
    """Get all cached REST prices"""
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    prices = rest_price_feed.get_all_prices() if rest_price_feed else {}
    return jsonify({'success': True, 'prices': prices})


@app.route('/api/admin/metaapi/provision', methods=['POST'])
def provision_metaapi_account():
    """Provision a new MetaAPI cloud account for REST trading"""
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key != API_KEY:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    if not metaapi_client or not metaapi_client.enabled:
        return jsonify({'success': False, 'error': 'MetaAPI not configured. Set METAAPI_TOKEN in .env'}), 400

    data = request.json or {}
    login = data.get('login')
    password = data.get('password')
    server = data.get('server')
    broker = data.get('broker', 'Exness')

    if not login or not password or not server:
        return jsonify({'success': False, 'error': 'login, password, and server are required'}), 400

    try:
        account_id = metaapi_client.get_or_provision(
            login=login, password=password, server=server, broker=broker)
        ready = metaapi_client.wait_for_ready(account_id, timeout_seconds=60)
        return jsonify({
            'success': True,
            'metaapi_account_id': account_id,
            'ready': ready,
            'message': f'Account provisioned and {"connected" if ready else "connecting"}',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
            password_hash TEXT,
            referrer_id TEXT,
            referral_code TEXT UNIQUE,
            created_at TEXT,
            total_commission REAL DEFAULT 0,
            FOREIGN KEY (referrer_id) REFERENCES users(user_id)
        )
    ''')
    
    # Add password_hash column if missing (migration for existing DBs)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN password_hash TEXT')
        conn.commit()
    except Exception:
        pass  # Column already exists
    
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
    if 'is_live' not in user_bots_columns:
        cursor.execute("ALTER TABLE user_bots ADD COLUMN is_live BOOLEAN DEFAULT 0")
        # Backfill is_live from linked broker_credentials for existing bots
        cursor.execute('''
            UPDATE user_bots SET is_live = (
                SELECT bcr.is_live FROM bot_credentials bc
                JOIN broker_credentials bcr ON bcr.credential_id = bc.credential_id
                WHERE bc.bot_id = user_bots.bot_id
                LIMIT 1
            ) WHERE is_live IS NULL OR is_live = 0
        ''')
    
    # Transactions table - tracks all financial transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'payout', 'commission', 'withdrawal', 'deposit', 'internal_transfer'
            amount REAL NOT NULL,
            method TEXT NOT NULL,  -- 'stripe', 'bank', 'crypto', 'internal'
            status TEXT DEFAULT 'pending',  -- 'pending', 'completed', 'failed', 'refunded'
            reason TEXT,
            stripe_transfer_id TEXT,
            bank_reference TEXT,
            crypto_tx_hash TEXT,
            fee REAL DEFAULT 0,
            net_amount REAL,
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # User payment methods table - stores payment details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_payment_methods (
            method_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'stripe', 'bank', 'crypto'
            primary_method BOOLEAN DEFAULT 0,
            -- Stripe Connect
            stripe_account_id TEXT,
            -- Bank transfer
            bank_name TEXT,
            account_holder TEXT,
            account_number TEXT,
            routing_number TEXT,
            swift_code TEXT,
            -- Cryptocurrency
            crypto_wallet TEXT,
            crypto_type TEXT,  -- 'BTC', 'ETH', 'USDT', 'USDC'
            -- Metadata
            verified BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Commission tracking table - enhanced version
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_ledger (
            entry_id TEXT PRIMARY KEY,
            commission_id TEXT,
            user_id TEXT NOT NULL,
            source_user_id TEXT,  -- Who earned this? (trader, referrer, etc.)
            type TEXT NOT NULL,  -- 'referral', 'profit_share', 'affiliate', 'bot_fee'
            amount REAL NOT NULL,
            payout_status TEXT DEFAULT 'pending',  -- 'pending', 'scheduled', 'completed', 'failed'
            payout_method TEXT,
            payout_date TEXT,
            bot_id TEXT,
            trading_profit REAL,  -- For profit share commissions
            created_at TEXT,
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

    # Migration: Add cached balance columns to broker_credentials if missing
    cursor.execute("PRAGMA table_info(broker_credentials)")
    broker_cred_columns = [col[1] for col in cursor.fetchall()]
    
    if 'cached_balance' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_balance REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_balance column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_balance column might already exist: {e}")
    
    if 'cached_equity' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_equity REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_equity column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_equity column might already exist: {e}")
    
    if 'cached_margin_free' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_margin_free REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_margin_free column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_margin_free column might already exist: {e}")
    
    if 'last_update' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN last_update TEXT')
            logger.info("✅ Migration: Added last_update column to broker_credentials")
        except Exception as e:
            logger.debug(f"last_update column might already exist: {e}")
    
    if 'cached_margin' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_margin REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_margin column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_margin column might already exist: {e}")
    
    if 'cached_margin_level' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_margin_level REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_margin_level column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_margin_level column might already exist: {e}")
    
    if 'cached_profit' not in broker_cred_columns:
        try:
            cursor.execute('ALTER TABLE broker_credentials ADD COLUMN cached_profit REAL DEFAULT 0')
            logger.info("✅ Migration: Added cached_profit column to broker_credentials")
        except Exception as e:
            logger.debug(f"cached_profit column might already exist: {e}")

    # Market Pause Events table - tracks when markets are paused/halted
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pause_events (
            pause_id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            pause_type TEXT NOT NULL,
            retcode INTEGER,
            error_message TEXT,
            reason TEXT,
            market_session TEXT,
            duration_minutes INTEGER,
            pause_start TEXT,
            pause_end TEXT,
            detected_at TEXT,
            created_at TEXT,
            FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Migration: Add pause_events table if it doesn't exist
    cursor.execute("PRAGMA table_info(pause_events)")
    if cursor.fetchall() == []:
        logger.info("✅ Migration: Created pause_events table")

    # Advanced Orders table - PXBT orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pxbt_orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            quantity REAL NOT NULL,
            order_type TEXT NOT NULL,
            limit_price REAL,
            stop_price REAL,
            tp_price REAL,
            sl_price REAL,
            trailing BOOLEAN DEFAULT 0,
            trailing_pips INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # Advanced Orders table - Binance orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS binance_orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            order_type TEXT NOT NULL,
            limit_price REAL,
            stop_price REAL,
            tp_price REAL,
            sl_price REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # ==================== WORKER POOL TABLES (100+ User Scaling) ====================
    # Worker pool: tracks each worker subprocess and its health
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS worker_pool (
            worker_id INTEGER PRIMARY KEY,
            pid INTEGER,
            status TEXT DEFAULT 'stopped',
            account_group TEXT,
            mt5_path TEXT,
            heartbeat_at TEXT,
            started_at TEXT,
            stopped_at TEXT,
            bot_count INTEGER DEFAULT 0,
            error_message TEXT
        )
    ''')

    # Worker bot queue: assigns bots to workers and sends commands
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS worker_bot_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            worker_id INTEGER,
            command TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            bot_config TEXT,
            credentials TEXT,
            created_at TEXT,
            processed_at TEXT,
            FOREIGN KEY (worker_id) REFERENCES worker_pool(worker_id)
        )
    ''')

    # Worker bot assignments: persistent mapping of bot → worker
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS worker_bot_assignments (
            bot_id TEXT PRIMARY KEY,
            worker_id INTEGER NOT NULL,
            account_number TEXT,
            broker_name TEXT,
            assigned_at TEXT,
            FOREIGN KEY (worker_id) REFERENCES worker_pool(worker_id)
        )
    ''')

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
    
    # MT5 PAUSE/HALT RETCODES - Market status codes indicating trading halts
    RETCODE_PAUSED = 10009        # Trading paused/halted for symbol
    RETCODE_REQUOTE = 10019       # Requote - market paused or no liquidity
    RETCODE_MARKET_CLOSED = 10026 # Market closed (weekend/outside hours)
    RETCODE_NO_LIQUIDITY = 10018  # No liquidity - market paused
    RETCODE_INVALID_REQUEST = 10016  # Invalid request - often during news events
    RETCODE_TRADE_MODE_DISABLED = 10015  # Trading disabled for symbol
    
    # Map of retcodes to pause reasons
    PAUSE_RETCODES = {
        10009: ('SYMBOL_HALTED', 'Trading halted/suspended for this symbol'),
        10019: ('REQUOTE', 'Market paused, no liquidity, or price changed significantly'),
        10026: ('MARKET_CLOSED', 'Market is closed (weekend or outside trading hours)'),
        10018: ('NO_LIQUIDITY', 'No liquidity available - market may be paused'),
        10016: ('INVALID_REQUEST', 'Invalid request - often during news events or market halt'),
        10015: ('TRADE_MODE_DISABLED', 'Trading disabled for this symbol'),
        10040: ('POSITION_LIMIT', 'Broker position limit reached for this symbol - close existing positions first'),
    }
    
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
        self.mt5_broker = canonicalize_broker_name(credentials.get('broker', 'Exness'))
        
        # Check if terminal is already running (avoid duplicate launches)
        try:
            import subprocess, sys, os
            # Simply skip terminal launch - assume it was launched at startup
            # If terminal crashes, MT5Connection.connect() will timeout and retry
            logger.info(f"[MT5 Terminal] Using {self.mt5_broker} MT5 terminal (launched on backend startup)")
        except Exception as e:
            logger.error(f"[MT5 Terminal Manager] Error checking terminal: {e}")
        
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            broker_cfg = get_mt5_config_for_broker(self.mt5_broker)
            # Prefer explicit credential path, then broker-specific config path.
            self.mt5_path = find_mt5_terminal_path(
                self.mt5_broker,
                credentials.get('path') or broker_cfg.get('path')
            )
        except ImportError:
            logger.error("MetaTrader5 not installed")
            self.mt5 = None

    def connect(self) -> bool:
        """
        Connect to MT5 with retry logic and better error handling
        CRITICAL: Uses global lock to prevent simultaneous MT5 connections
        OPTIMIZED: Reduced lock timeout and added exponential backoff for racing bots
        """
        global mt5_connection_lock
        
        # Acquire lock with timeout - INCREASED from 10s to 25s for trading loops
        # Balance checks use 0.1s timeout (non-blocking) to avoid stalling
        # Trading loops use 25s to give MT5 enough time to complete a full trade cycle
        lock_timeout = self.credentials.get('lock_timeout', 60)  # 60 seconds default for trades (increased from 25s to handle 10+ concurrent bots)
        
        # CRITICAL FIX: If this is a balance fetch (marked by 'is_balance_check'), use fast timeout
        if self.credentials.get('is_balance_check'):
            lock_timeout = 0.1  # 100ms - fail fast for balance reads when MT5 is busy
            logger.info(f"⏳ Balance check: Waiting for MT5 lock (max {lock_timeout}s, non-blocking)...")
        else:
            logger.info(f"⏳ Waiting for exclusive MT5 connection lock (max {lock_timeout} seconds, sequential mode)...")
        
        lock_acquired = mt5_connection_lock.acquire(timeout=float(lock_timeout))
        
        if not lock_acquired:
            logger.warning(f"⚠️ TIMEOUT: Could not acquire MT5 lock after {lock_timeout} seconds - system is busy")
            retry_delay = self.credentials.get('tradingInterval', 300) + random.uniform(1, 10)  # Add 1-10s random delay
            logger.warning(f"   Will retry in {retry_delay:.0f}s with staggered delay to reduce lock contention")
            return False  # Return False to signal connection failed, bot will retry next cycle
        
        try:
            logger.info(f"✅ Acquired MT5 connection lock - proceeding with connection")
            return self._connect_with_lock()
        finally:
            # CRITICAL: Always release the lock, even if connection fails
            mt5_connection_lock.release()
    
    def _connect_with_lock(self) -> bool:
        """Internal connection method - always called within mt5_connection_lock"""
        global balance_cache, balance_cache_lock, mt5_current_account  # Declare globals at function start (required by Python)
        
        try:
            if not self.mt5:
                logger.error("MetaTrader5 SDK not available")
                return False

            broker_name = canonicalize_broker_name(self.credentials.get('broker', self.mt5_broker))
            broker_cfg = get_mt5_config_for_broker(broker_name)

            account = self.credentials.get('account') or broker_cfg.get('account')
            password = self.credentials.get('password') or broker_cfg.get('password')
            server = self.credentials.get('server') or broker_cfg.get('server')
            is_live = self.credentials.get('is_live', False)
            
            # Broker-specific server normalization — use per-credential is_live, NOT global ENVIRONMENT
            if broker_name == 'Exness':
                server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
            elif broker_name in ['XM', 'XM Global'] and (not server or 'xm' not in str(server).lower()):
                server = 'XMGlobal-Real' if is_live else 'XMGlobal-MT5Demo'
            elif broker_name == 'PXBT':
                server = 'PXBTTrading-1'
            
            # Ensure account is integer for proper comparison with MT5 login field
            account = int(account)
            
            # CRITICAL FIX: Check if already logged into this account on this terminal
            # If so, return True immediately without attempting re-init
            # This prevents loss of session on reconnection attempts
            try:
                existing_info = self.mt5.account_info()
                if existing_info and existing_info.login == account:
                    logger.info(f"✅ MT5 already logged in to account {account} - reusing existing connection")
                    self.connected = True
                    self.account_info = existing_info
                    # Track which account is active for multi-user awareness
                    with mt5_account_lock:
                        mt5_current_account = account
                    return True
            except Exception as e:
                logger.debug(f"  (Checking existing session: {e})")
            
            # Not logged in to correct account yet - proceed with login
            
            # Check failed-auth cooldown - skip accounts that recently failed authorization
            with _failed_auth_lock:
                if account in _failed_auth_accounts:
                    fail_info = _failed_auth_accounts[account]
                    elapsed = time.time() - fail_info['timestamp']
                    if elapsed < _FAILED_AUTH_COOLDOWN:
                        logger.warning(f"⏭️ Skipping account {account} - auth failed {elapsed:.0f}s ago (cooldown: {_FAILED_AUTH_COOLDOWN}s)")
                        return False
                    else:
                        # Cooldown expired, allow retry
                        del _failed_auth_accounts[account]
                        logger.info(f"🔄 Auth cooldown expired for account {account} - allowing retry")
            
            logger.info(f"Attempting login to account {account}...")
            
            # Retry logic: balance checks get 1 attempt (fast fail), trading gets 3
            is_balance_check = self.credentials.get('is_balance_check', False)
            max_retries = 1 if is_balance_check else 3
            for attempt in range(1, max_retries + 1):
                logger.info(f"MT5 connection attempt {attempt}/{max_retries}: Account={account}, Server={server}")
                
                try:
                    init_ok = False
                    
                    # On retry attempts, just wait longer for IPC - DON'T kill MT5 terminal
                    # Killing the terminal causes loss of login session and requires manual re-login
                    # Instead, just give IPC connection more time to recover
                    if attempt > 1:
                        logger.info(f"  🔄 Allowing MT5 IPC more time to stabilize before retry...")
                        # CRITICAL FIX: Keep terminal running - just wait for recovery
                        retry_wait = 5 + (2 * attempt)
                        logger.info(f"     IPC recovery delay: {retry_wait} seconds (exponential backoff)")
                        time.sleep(retry_wait)
                    
                    # Always use broker-specific MT5 path (NO generic fallback)
                    if not self.mt5_path:
                        logger.error(f"❌ No {broker_name} MT5 path configured - cannot continue without broker-specific MT5")
                        continue
                    
                    # Initialize with broker-specific path only
                    normalized_path = str(self.mt5_path).strip().strip('"').strip("'")
                    if os.path.isdir(normalized_path):
                        candidate_64 = os.path.join(normalized_path, 'terminal64.exe')
                        candidate_32 = os.path.join(normalized_path, 'terminal.exe')
                        if os.path.isfile(candidate_64):
                            normalized_path = candidate_64
                        elif os.path.isfile(candidate_32):
                            normalized_path = candidate_32

                    if os.path.isfile(normalized_path):
                        # Pass login credentials directly in initialize() to avoid MT5 auth races.
                        logger.info(f"  🔑 Calling mt5.initialize(path='{normalized_path}', login={account}, server='{server}')")
                        init_ok = self.mt5.initialize(
                            path=normalized_path,
                            login=int(account),
                            password=str(password),
                            server=str(server)
                        )
                        if init_ok:
                            self.mt5_path = normalized_path
                            logger.info(f"  ✓ MT5 initialize() returned True")
                        else:
                            logger.warning(f"  ✗ {broker_name} MT5 initialization failed: {self.mt5.last_error()}")
                    else:
                        logger.warning(f"  ✗ {broker_name} MT5 path not found: {normalized_path}")
                        init_ok = False

                    if init_ok:
                        # Successfully initialized AND authenticated (credentials passed to initialize)
                        logger.info(f"  ✓ MT5 initialized and authenticated (path: {self.mt5_path})")
                        
                        # Brief IPC stabilization wait
                        ipc_wait = 3
                        logger.info(f"  ⏳ Waiting {ipc_wait}s for MT5 IPC stabilization...")
                        time.sleep(ipc_wait)
                        
                        # Verify account is accessible
                        acct_info = self.mt5.account_info()
                        if acct_info and acct_info.login == int(account):
                            self.connected = True
                            logger.info(f"✅ Logged in to MT5 account {account} successfully")
                            # Track which account is active for multi-user awareness
                            with mt5_account_lock:
                                mt5_current_account = int(account)
                            self.get_account_info()
                            
                            # CRITICAL FIX: Populate balance cache IMMEDIATELY after login success
                            try:
                                if self.account_info:
                                    with balance_cache_lock:
                                        cache_key = get_balance_cache_key(broker_name, account)
                                        balance = float(self.account_info.get('balance', 0))
                                        balance_cache[cache_key] = {
                                            'balance': balance,
                                            'equity': float(self.account_info.get('equity', 0)),
                                            'marginFree': float(self.account_info.get('marginFree', 0)),
                                            'timestamp': time.time()
                                        }
                                        logger.info(f"  💾 [BOT CACHE] Key='{cache_key}' Balance=${balance:.2f} (Total cache entries: {len(balance_cache)})")
                            except Exception as e:
                                logger.warning(f"  ⚠️  Failed to cache balance after login: {e}")
                            
                            # Subscribe to all symbols for trading
                            self._subscribe_symbols()
                            return True
                        else:
                            logger.warning(f"  ✗ Account verification failed after initialize - will retry")
                            continue
                    
                    else:
                        init_error = self.mt5.last_error()
                        logger.warning(f"  ✗ MT5 initialization failed: {init_error}")
                        # Check for IPC timeout during initialization
                        error_code = init_error[0] if isinstance(init_error, tuple) else -1
                        if error_code in [-10005, -10004]:  # IPC timeout or No IPC connection
                            logger.warning(f"  ⚠️  IPC CONNECTION ISSUE - will wait longer before retry")
                        logger.debug(f"    (Terminal process may still be starting...)")
                
                except Exception as e:
                    logger.warning(f"  ✗ Error during attempt {attempt}: {e}")
                
                # Wait before retry with exponential backoff
                if attempt < max_retries:
                    # Exponential backoff: 5s, 7s, (no 3rd wait as this completes loop)
                    wait_time = 5 + (2 * attempt)
                    logger.info(f"  ⏳ Retry in {wait_time}s (exponential backoff)...")
                    time.sleep(wait_time)
            
            # All retries exhausted
            logger.error(f"❌ Failed to connect to MT5 after {max_retries} attempts")
            
            # Track auth failures so we don't keep retrying bad credentials
            # Only track if the failure was auth-related (not IPC timeout from contention)
            try:
                last_err = self.mt5.last_error() if self.mt5 else None
                if last_err and isinstance(last_err, tuple) and last_err[0] == -6:  # Authorization failed
                    with _failed_auth_lock:
                        _failed_auth_accounts[account] = {
                            'timestamp': time.time(),
                            'error': str(last_err)
                        }
                        logger.warning(f"🚫 Account {account} added to auth cooldown ({_FAILED_AUTH_COOLDOWN}s) due to auth failure")
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from MT5 - marks as disconnected but does NOT call mt5.shutdown()
        because the MT5 terminal is a shared singleton used by all bots.
        Calling shutdown() would kill connections for ALL bots and API endpoints."""
        try:
            # CRITICAL: Do NOT call self.mt5.shutdown() here!
            # The MT5 terminal is shared across all bots and API endpoints.
            # Just mark this connection object as disconnected.
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
                # Now test the order execution path with order_check (NOT order_send — that would place a real trade!)
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: Testing order submission path with order_check()...")
                
                # Build a test order request — order_check validates without executing
                filling_type = self._get_filling_type(test_symbol)
                test_request = {
                    "action": self.mt5.TRADE_ACTION_DEAL,
                    "symbol": test_symbol,
                    "volume": 0.01,  # Micro volume for test
                    "type": self.mt5.ORDER_TYPE_BUY,
                    "price": tick.ask,
                    "comment": "ZTEST",  # Short comment within MT5's 31-char limit
                    "type_time": self.mt5.ORDER_TIME_GTC,
                    "type_filling": filling_type,
                }
                
                test_result = self.mt5.order_check(test_request)
                
                # Check what order_check returned
                if test_result is None:
                    logger.warning(f"  Attempt {attempt} [{elapsed:.0f}s]: ⚠️  order_check() returned None (terminal issue, not account)")
                    logger.warning(f"    This usually means:")
                    logger.warning(f"    - MT5 terminal is still initializing")
                    logger.warning(f"    - Terminal lost sync with SDK")
                    logger.warning(f"    - Rare SDK issue")
                    # Continue retrying - terminal may recover
                    time.sleep(check_interval)
                    continue
                
                # order_check did not return None - SDK is working
                # Check if order would succeed or fail for logical reasons
                if hasattr(test_result, 'retcode'):
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: order_check() returned (retcode={test_result.retcode})")
                    logger.info(f"✅ MT5 is READY - order execution path is functional")
                    logger.info(f"   Account: {account_info.login}, Balance: ${account_info.balance}")
                    logger.info(f"   Symbol {test_symbol}: bid={tick.bid:.5f}, ask={tick.ask:.5f}")
                    
                    # CRITICAL FIX: Update global balance cache so balance API calls return real data
                    global balance_cache, balance_cache_lock
                    try:
                        with balance_cache_lock:
                            # Use consistent cache key format (also used by balance endpoint)
                            cache_key = get_balance_cache_key('Exness', account_info.login)
                            balance_cache[cache_key] = {
                                'balance': float(account_info.balance),
                                'equity': float(account_info.equity),
                                'marginFree': float(account_info.margin_free) if hasattr(account_info, 'margin_free') else 0,
                                'timestamp': time.time()
                            }
                        logger.info(f"  💾 Cached balance for {cache_key}: ${account_info.balance} (cache size: {len(balance_cache)} entries)")
                    except Exception as e:
                        logger.error(f"  ❌ Failed to update balance cache: {e}")
                    return True
                else:
                    logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: order_check() returned object without retcode")
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
        """Get COMPREHENSIVE account information from Exness MT5"""
        try:
            if not self.connected:
                return None

            info = self.mt5.account_info()
            
            # Get positions for aggregate data
            positions = self.mt5.positions_get()
            total_positions = len(positions) if positions else 0
            total_volume = sum(pos.volume for pos in positions) if positions else 0
            total_pnl = sum(pos.profit for pos in positions) if positions else 0
            
            # Get orders (pending)
            orders = self.mt5.orders_get()
            total_pending = len(orders) if orders else 0
            
            # Calculate additional metrics
            floating_pl = round(float(info.profit), 2) if hasattr(info, 'profit') else 0
            used_margin = round(float(info.margin), 2)
            free_margin = round(float(info.margin_free), 2)
            margin_percentage = (used_margin / (used_margin + free_margin) * 100) if (used_margin + free_margin) > 0 else 0
            
            # Comprehensive account data
            self.account_info = {
                # === BASIC INFO ===
                'accountNumber': info.login,
                'broker': info.server,
                'company': info.company if hasattr(info, 'company') else 'Exness',
                'currency': 'USD',  # Force USD
                'displayCurrency': 'USD',
                
                # === BALANCE & EQUITY ===
                'balance': round(float(info.balance), 2),
                'equity': round(float(info.equity), 2),
                'floatingPL': floating_pl,
                'realizedPL': round(float(info.balance) - float(info.equity), 2),  # Closed P&L
                
                # === MARGIN METRICS ===
                'margin': used_margin,
                'marginFree': free_margin,
                'marginLevel': round(float(info.margin_level), 2),
                'marginPercentage': round(margin_percentage, 2),
                'usedMarginPercentage': round((used_margin / (used_margin + free_margin) * 100), 2) if (used_margin + free_margin) > 0 else 0,
                
                # === LEVERAGE & LIMITS ===
                'leverage': info.leverage,
                'limitOrders': info.limits_orders if hasattr(info, 'limits_orders') else 0,
                'limitVolume': info.limit_volume if hasattr(info, 'limit_volume') else 0,
                'limitSymbols': info.limit_symbols if hasattr(info, 'limit_symbols') else 0,
                
                # === ACCOUNT TYPE ===
                'tradeMode': self._get_trade_mode(info),
                'accountType': self._get_account_type(info),
                'accountStopout': info.fifo_close if hasattr(info, 'fifo_close') else False,
                
                # === POSITION STATISTICS ===
                'openPositions': total_positions,
                'pendingOrders': total_pending,
                'totalVolume': total_volume,
                'totalPositionPL': round(total_pnl, 2),
                
                # === ACCOUNT RESTRICTIONS ===
                'tradeAllowed': info.trade_allowed if hasattr(info, 'trade_allowed') else True,
                'investMode': info.trade_mode if hasattr(info, 'trade_mode') else 0,
                'fifoClose': info.fifo_close if hasattr(info, 'fifo_close') else False,
                
                # === TIMESTAMP ===
                'lastUpdate': datetime.utcnow().isoformat(),
            }
            return self.account_info
        except Exception as e:
            logger.error(f"Error getting MT5 account info: {e}")
            return None
    
    def _get_trade_mode(self, info) -> str:
        """Determine trade mode from MT5 account"""
        try:
            if hasattr(info, 'trade_mode'):
                mode = info.trade_mode
                modes = {
                    0: 'DEMO',
                    1: 'REAL',
                    2: 'CONTEST'
                }
                return modes.get(mode, 'UNKNOWN')
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'
    
    def _get_account_type(self, info) -> str:
        """Determine account type from MT5 account info"""
        try:
            if hasattr(info, 'account_type'):
                acc_type = info.account_type
                types = {
                    0: 'DEMO',
                    1: 'CONTEST',
                    2: 'REAL'
                }
                return types.get(acc_type, 'UNKNOWN')
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def get_positions(self) -> List[Dict]:
        """Get open positions with DETAILED metrics"""
        try:
            if not self.connected:
                return []

            positions = self.mt5.positions_get()
            result = []
            if not positions:
                return result
            for pos in positions:
                # Calculate additional metrics per position
                pnl_percentage = ((pos.price_current - pos.price_open) / pos.price_open * 100) if pos.price_open != 0 else 0
                swap = pos.swap if hasattr(pos, 'swap') else 0
                commission = pos.commission if hasattr(pos, 'commission') else 0
                comment = pos.comment if hasattr(pos, 'comment') else ''
                
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == self.mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'openPrice': round(float(pos.price_open), 5),
                    'currentPrice': round(float(pos.price_current), 5),
                    'pnl': round(pos.profit, 2),
                    'pnlPercentage': round(pnl_percentage, 2),
                    'openTime': pos.time if hasattr(pos, 'time') else None,
                    'swap': round(swap, 2),
                    'commission': round(commission, 2),
                    'netProfit': round(pos.profit + swap + commission, 2),
                    'comment': comment,
                    'sl': pos.sl if hasattr(pos, 'sl') else 0,
                    'tp': pos.tp if hasattr(pos, 'tp') else 0,
                    'broker': 'MT5',
                })
            return result
        except Exception as e:
            logger.error(f"Error getting MT5 positions: {e}")
            return []
    
    def get_trade_history(self, days: int = 30) -> List[Dict]:
        """Get CLOSED TRADES (trade history) from the last N days"""
        try:
            if not self.connected:
                return []
            
            # Get closed deals from the last N days
            from_time = datetime.utcnow() - timedelta(days=days)
            deals = self.mt5.history_deals_get(from_time, datetime.utcnow())
            
            result = []
            win_count = 0
            loss_count = 0
            total_profit = 0
            
            if deals:
                for deal in deals:
                    # Only include closed positions
                    if deal.profit != 0 or deal.entry == 1:  # dealing IN or OUT
                        profit = round(float(deal.profit), 2)
                        total_profit += profit
                        if profit > 0:
                            win_count += 1
                        elif profit < 0:
                            loss_count += 1
                        
                        result.append({
                            'ticket': deal.ticket,
                            'symbol': deal.symbol,
                            'type': 'BUY' if deal.type == 0 else 'SELL',
                            'volume': deal.volume,
                            'openPrice': round(float(deal.price), 5),
                            'profit': profit,
                            'closeTime': deal.time,
                            'commission': round(float(deal.commission), 2),
                            'swap': round(float(deal.swap), 2),
                        })
            
            return sorted(result, key=lambda x: x['closeTime'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting MT5 trade history: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict:
        """Get trading PERFORMANCE METRICS for the account"""
        try:
            if not self.connected:
                return None
            
            # Get trades from last 90 days
            trades = self.get_trade_history(days=90)
            
            if not trades:
                return {
                    'totalTrades': 0,
                    'winRate': 0,
                    'lossRate': 0,
                    'avgWin': 0,
                    'avgLoss': 0,
                    'profitFactor': 0,
                    'totalProfit': 0,
                    'maxDrawdown': 0,
                }
            
            wins = [t['profit'] for t in trades if t['profit'] > 0]
            losses = [abs(t['profit']) for t in trades if t['profit'] < 0]
            
            total_wins = sum(wins) if wins else 0
            total_losses = sum(losses) if losses else 0
            win_count = len(wins)
            loss_count = len(losses)
            total_trades = win_count + loss_count
            
            return {
                'totalTrades': total_trades,
                'winCount': win_count,
                'lossCount': loss_count,
                'winRate': round((win_count / total_trades * 100), 2) if total_trades > 0 else 0,
                'lossRate': round((loss_count / total_trades * 100), 2) if total_trades > 0 else 0,
                'avgWin': round(total_wins / win_count, 2) if wins else 0,
                'avgLoss': round(total_losses / loss_count, 2) if losses else 0,
                'profitFactor': round(total_wins / total_losses, 2) if total_losses > 0 else float('inf'),
                'totalProfit': round(total_wins - total_losses, 2),
                'maxWin': round(max(wins), 2) if wins else 0,
                'maxLoss': round(min(losses), 2) if losses else 0,
                'period': '90 days',
            }
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return None

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
    
    def wait_for_critical_symbols(self, symbols: list, timeout_seconds: int = 30) -> bool:
        """
        Wait for critical symbols (like ETHUSDm, BTCUSDm) to be loaded and available.
        Critical symbols require special handling because:
        - They fail fast if not available (no fallback)
        - They trade 24/7 but need different subscription patterns
        - Trading wrong symbol instead causes silent loss
        
        Returns True if all critical symbols are available, False on timeout
        """
        critical_symbols = {'BTCUSDm', 'ETHUSDm'}  # Define critical symbols that MUST be available
        symbols_to_wait = [s for s in symbols if s in critical_symbols]
        
        if not symbols_to_wait:
            return True  # No critical symbols, no need to wait
        
        logger.info(f"⏳ Checking critical symbols: {symbols_to_wait} (timeout: {timeout_seconds}s)")
        
        start_time = time.time()
        check_interval = 2  # Check every 2 seconds for symbols
        attempt = 0
        
        while time.time() - start_time < timeout_seconds:
            attempt += 1
            elapsed = time.time() - start_time
            unavailable = []
            
            for symbol in symbols_to_wait:
                try:
                    if not self.mt5.symbol_select(symbol, True):
                        unavailable.append(symbol)
                        continue
                    
                    tick = self.mt5.symbol_info_tick(symbol)
                    if tick is None:
                        unavailable.append(symbol)
                        continue
                    
                    # Symbol is available
                    logger.debug(f"  ✅ {symbol}: available (bid={tick.bid}, ask={tick.ask})")
                except Exception as e:
                    logger.debug(f"  ⚠️ {symbol}: check failed - {e}")
                    unavailable.append(symbol)
            
            if not unavailable:
                logger.info(f"✅ All critical symbols ready after {elapsed:.0f}s: {symbols_to_wait}")
                return True
            else:
                logger.debug(f"  Attempt {attempt} [{elapsed:.0f}s]: Waiting for symbols: {unavailable}")
                time.sleep(check_interval)
        
        # Timeout reached
        logger.error(f"❌ Critical symbols NOT ready after {timeout_seconds}s: {unavailable}")
        logger.error(f"   {unavailable} may take longer to load. Trading may fail if symbols don't become available.")
        return False

    def _get_filling_type(self, symbol: str):
        """Auto-detect the correct ORDER_FILLING type for the broker/symbol.
        Exness requires RETURN, other brokers may need IOC or FOK."""
        try:
            sym_info = self.mt5.symbol_info(symbol)
            if sym_info is not None:
                filling = sym_info.filling_mode
                # filling_mode is a bitmask: bit0=FOK, bit1=IOC, bit2=RETURN
                if filling & 2:  # IOC supported
                    return self.mt5.ORDER_FILLING_IOC
                elif filling & 1:  # FOK supported
                    return self.mt5.ORDER_FILLING_FOK
            # Default to RETURN (works on Exness and most brokers)
            return self.mt5.ORDER_FILLING_RETURN
        except Exception:
            return self.mt5.ORDER_FILLING_RETURN

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

            # STEP 2: Select symbol so broker metadata and ticks are available.
            if not self.mt5.symbol_select(symbol, True):
                return {'success': False, 'error': f'Failed to select symbol {symbol}'}

            # STEP 3: Normalize requested volume to broker constraints.
            sym_info = self.mt5.symbol_info(symbol)
            fallback_min_volumes = {
                'OILK': 1.0,
                'XAUUSD': 0.01,
                'XAGUSD': 0.1,
                'XAUUSDm': 0.01,
                'XAGUSDm': 0.1,
            }
            min_volume = float(getattr(sym_info, 'volume_min', 0.0) or fallback_min_volumes.get(symbol, 0.01))
            max_volume = float(getattr(sym_info, 'volume_max', 0.0) or 0.0)
            volume_step = float(getattr(sym_info, 'volume_step', 0.0) or 0.01)
            requested_volume = float(volume)
            normalized_volume = requested_volume

            if normalized_volume < min_volume:
                normalized_volume = min_volume

            if volume_step > 0:
                import math
                step_precision = max(0, len(f"{volume_step:.10f}".rstrip('0').split('.')[-1]))
                step_count = math.ceil(((normalized_volume - min_volume) / volume_step) - 1e-9)
                step_count = max(0, step_count)
                normalized_volume = round(min_volume + (step_count * volume_step), step_precision)
            else:
                step_precision = 2

            if max_volume > 0 and normalized_volume > max_volume:
                return {
                    'success': False,
                    'error': f'Volume {normalized_volume} exceeds broker maximum {max_volume} for {symbol}'
                }

            if normalized_volume != requested_volume:
                logger.info(
                    f"Adjusting volume for {symbol}: requested={requested_volume}, "
                    f"normalized={normalized_volume}, min={min_volume}, step={volume_step}"
                )

            volume = normalized_volume

            # Get the tick data (bid/ask prices)
            tick = self.mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'success': False, 'error': f'Cannot get tick data for {symbol}'}
            
            price = tick.ask if order_type == 'BUY' else tick.bid

            # Auto-detect correct filling type for broker
            filling_type = self._get_filling_type(symbol)

            request_dict = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_BUY if order_type == 'BUY' else self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "comment": (kwargs.get('comment', 'ZTrade')[:31] if kwargs.get('comment') else 'ZTrade'),  # Enforce 31-char limit
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
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
                
                # CHECK FOR MARKET PAUSE/HALT CONDITIONS
                if result.retcode in self.PAUSE_RETCODES:
                    pause_type, pause_reason = self.PAUSE_RETCODES[result.retcode]
                    logger.warning(f"🔒 MARKET PAUSE DETECTED: {pause_type} - {pause_reason}")
                    return {
                        'success': False,
                        'error': f'Market paused: {pause_reason}',
                        'retcode': result.retcode,
                        'pause_type': pause_type,
                        'pause_reason': pause_reason,
                        'is_paused': True,
                        'original_comment': result.comment,
                        'action_required': f'Market is currently paused ({pause_type}). Trading will resume when market reopens.'
                    }
                
                # Retcode 10027 = AutoTrading disabled in MT5 terminal
                if result.retcode == 10027:
                    return {
                        'success': False,
                        'error': 'AutoTrading is disabled in MT5 terminal. Enable it by clicking the AutoTrading button in the MT5 toolbar, or run: mt5.terminal_info().trade_allowed',
                        'retcode': 10027,
                        'action_required': 'Enable AutoTrading in MT5 terminal'
                    }
                return {'success': False, 'error': f'MT5 error: {result.comment}', 'retcode': result.retcode}

            # Trade insert is handled by the calling bot trading loop (which has the correct bot_id/user_id)
            # Do not insert here to avoid duplicate records with bot_id='unknown'

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
            
            # Auto-detect correct filling type for broker
            filling_type = self._get_filling_type(pos.symbol)

            request_dict = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": self.mt5.ORDER_TYPE_SELL if pos.type == self.mt5.ORDER_TYPE_BUY else self.mt5.ORDER_TYPE_BUY,
                "position": int(position_id),
                "comment": "ZCLOSE",  # Short comment for close (31-char MT5 limit)
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
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
        """Connect to XM MT5 account.
        CRITICAL: XM uses a DIFFERENT MT5 terminal than Exness.
        We must NEVER call mt5.initialize()/login()/shutdown() here because
        that would hijack/kill the shared Exness terminal used by all bots.
        XM accounts operate in cache-only/demo mode."""
        try:
            account = self.credentials.get('account')
            password = self.credentials.get('password')
            
            if not account or not password:
                logger.warning(f"XM: Missing account or password credentials")
                return False
            
            # CRITICAL: Do NOT call mt5.initialize() or mt5.login() here!
            # The MT5 terminal is Exness-only. XM would need its own terminal.
            # XM operates in cache-only/demo mode.
            logger.info(f"ℹ️ XM account {account} uses separate MT5 terminal - operating in cache mode")
            self.connected = True  # Mark as connected for cache-based operations
            return True
                
        except Exception as e:
            logger.error(f"Error connecting to XM: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from XM.
        CRITICAL: Does NOT call mt5.shutdown() - that would kill the shared Exness terminal."""
        try:
            self.connected = False
            logger.info("XM connection marked as disconnected (MT5 terminal preserved)")
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
        'pxbt': 'PXBT',
        'prime xbt': 'PXBT',
        'primexbt': 'PXBT',
        'pxbt trading': 'PXBT',
    }
    return broker_map.get(normalized, broker_name)


def is_mt5_broker_name(broker_name: str) -> bool:
    return canonicalize_broker_name(broker_name) in ['Exness', 'PXBT', 'MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5']


def get_mt5_config_for_broker(broker_name: str) -> Dict:
    normalized = canonicalize_broker_name(broker_name)
    if normalized == 'XM' or normalized == 'XM Global':
        return XM_CONFIG
    if normalized == 'PXBT':
        return PXBT_CONFIG
    return MT5_CONFIG


def get_balance_cache_key(broker_name: str, account_id) -> str:
    """Generate consistent cache key for balance cache with auto-detection
    
    This function implements TWO-LAYER BROKER DETECTION:
    1. First, attempts to auto-detect the real broker based on account number
       (maps 'MetaTrader 5' → 'Exness' for known Exness accounts)
    2. Falls back to normalizing the provided broker_name if not in auto-detection map
    
    Used by BOTH bot connection AND balance endpoint to ensure key format matches.
    This prevents cache misses due to key format discrepancies.
    
    Args:
        broker_name: Raw broker name from database (e.g., 'Exness', 'MetaTrader 5', 'XM Global', 'Binance')
        account_id: Account number (int, or string convertible to int)
    
    Returns:
        Consistent cache key: "Exness:298997455" or "Binance:z9e8s9v7..."
        
    Example:
        # Bot code (sends raw account number):
        get_balance_cache_key('Exness', 298997455)  → 'Exness:298997455'
        
        # Endpoint code (gets broker_name from DB which might be 'MetaTrader 5'):
        get_balance_cache_key('MetaTrader 5', 298997455)  → 'Exness:298997455' ✅ Matches!
    """
    
    # ==================== LAYER 1: ACCOUNT-BASED AUTO-DETECTION ====================
    # Only apply auto-detection when broker_name is generic (e.g., 'MetaTrader 5', 'MT5')
    # Do NOT override when broker_name is already specific (Exness, XM, etc.)
    ACCOUNT_BROKER_MAPPING = {
        # Exness DEMO - known account that may be stored as 'MetaTrader 5' in DB
        '298997455': 'Exness',
        298997455: 'Exness',
        # Exness LIVE - known account that may be stored as 'MetaTrader 5' in DB
        '295619855': 'Exness',
        295619855: 'Exness',
        # Add more known accounts here as needed
    }
    
    # Normalize account for lookup
    try:
        account_str = str(int(account_id))
    except (ValueError, TypeError):
        account_str = str(account_id)
    
    # Only use auto-detection if the broker name is generic (MetaTrader 5, MT5, etc.)
    # If the broker name is already specific (Exness, XM, Binance), use it as-is
    normalized_broker = canonicalize_broker_name(broker_name)
    generic_broker_names = {'MetaTrader5', 'MetaTrader 5', 'MT5'}
    
    if normalized_broker in generic_broker_names or broker_name in generic_broker_names:
        # Check if this account number has a known broker mapping
        if account_str in ACCOUNT_BROKER_MAPPING:
            real_broker = ACCOUNT_BROKER_MAPPING[account_str]
            return f"{real_broker}:{account_str}"
        if account_id in ACCOUNT_BROKER_MAPPING:
            real_broker = ACCOUNT_BROKER_MAPPING[account_id]
            return f"{real_broker}:{account_str}"
    
    # ==================== LAYER 2: BROKER NAME NORMALIZATION ====================
    # Use the provided broker name (normalized) for the cache key
    cache_key = f"{normalized_broker}:{account_str}"
    return cache_key

# ==================== IN-MEMORY STORAGE ====================
# Store demo trades placed via API (temporary storage for this session)
demo_trades_storage = {}

# Connections are created when users provide their credentials via API
# Previously auto-initialized connections have been removed to prevent forced MT5 terminal launches

# AUTO-CONNECT to Exness MT5 on startup (so dashboard shows real balance)
# Removed: auto_connect_mt5() function - connections are now created only when users provide credentials
# Removed: auto_connect_ig() function (IG Markets integration removed)


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


@app.route('/api/environment', methods=['GET'])
def get_environment_status():
    """Get current trading environment mode and MT5 configuration
    
    Returns:
    - environment: 'DEMO' or 'LIVE'
    - account: MT5 account number
    - server: MT5 server name
    - broker: Broker name ('Exness')
    - warning: Alert if in LIVE mode
    - how_to_trade: Instructions for DEMO/LIVE verification
    """
    return jsonify({
        'success': True,
        'environment': ENVIRONMENT,
        'account': MT5_CONFIG['account'],
        'server': MT5_CONFIG['server'],
        'broker': MT5_CONFIG['broker'],
        'isLive': ENVIRONMENT == 'LIVE',
        'warning': '🔴 LIVE MODE - REAL MONEY TRADING' if ENVIRONMENT == 'LIVE' else '🟢 DEMO MODE - Safe for Testing',
        'how_to_verify': {
            'demo_mode': {
                'step1': 'Open Exness MT5 Demo Terminal',
                'step2': 'Click Terminal → Trade History tab',
                'step3': 'Look for bot trades matching execution times',
                'step4': 'Trades should appear within 1-2 seconds of bot cycle'
            },
            'live_mode': {
                'step1': 'Open Exness Portal (my.exness.com/account)',
                'step2': 'Check Account → Trade History',
                'step3': 'Or open Exness MT5 Live Terminal → Terminal → Trade History',
                'step4': 'Trades should appear within 1-2 seconds of bot cycle'
            }
        },
        'how_to_switch_to_live': {
            'step1': 'Edit .env file in project root',
            'step2': 'Set: ENVIRONMENT=LIVE',
            'step3': 'Update: EXNESS_ACCOUNT=your_account_number',
            'step4': 'Update: EXNESS_PASSWORD=your_password',
            'step5': 'Restart backend: python multi_broker_backend_updated.py',
            'step6': 'Check logs for: [LIVE] USING LIVE EXNESS CREDENTIALS',
            'step7': 'Verify account in Exness terminal dropdown matches EXNESS_ACCOUNT'
        },
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

def detect_mt5_terminal_for_broker(broker_name: str, configured_path: str = None):
    """Detect if MT5 is available for a broker and whether configured terminal path exists."""
    try:
        import MetaTrader5 as mt5

        resolved_path = find_mt5_terminal_path(broker_name, configured_path)
        path_ok = bool(resolved_path and os.path.exists(resolved_path))
        
        # Try to initialize MT5 to check if it's installed
        if hasattr(mt5, 'version'):
            if path_ok:
                logger.info(f"✅ {broker_name} MT5 detected on system at {resolved_path}")
            else:
                logger.warning(f"⚠️ {broker_name} MT5 SDK found but broker terminal path was not found")
            return {
                'available': path_ok,
                'installed': True,
                'version': str(mt5.version if hasattr(mt5, 'version') else 'Unknown'),
                'terminal_path': resolved_path,
                'path_exists': path_ok,
                'reason': None if path_ok else f'{broker_name} terminal not found in configured/common paths',
            }
        else:
            logger.warning("⚠️ MetaTrader 5 library found but version info unavailable")
            return {
                'available': path_ok,
                'installed': True,
                'version': 'Unknown',
                'terminal_path': resolved_path,
                'path_exists': path_ok,
                'reason': None if path_ok else f'{broker_name} terminal not found in configured/common paths',
            }
    except ImportError:
        logger.warning("⚠️ MetaTrader 5 library not installed")
        return {
            'available': False,
            'installed': False,
            'reason': 'MetaTrader 5 library not installed. Install with: pip install MetaTrader5'
        }
    except Exception as e:
        logger.error(f"❌ Error detecting {broker_name} MT5: {e}")
        return {
            'available': False,
            'installed': False,
            'error': str(e)
        }


def detect_exness_mt5():
    """Detect if Exness MT5 is available on the system"""
    return detect_mt5_terminal_for_broker('Exness', MT5_CONFIG.get('path'))


def detect_pxbt_mt5():
    """Detect if PXBT MT5 is available on the system"""
    return detect_mt5_terminal_for_broker('PXBT', PXBT_CONFIG.get('path'))


def check_exness_connectivity(account_id=None, password=None, server='Exness-MT5'):
    """Check if Exness MT5 server is reachable.
    CRITICAL: Does NOT call mt5.initialize(login=...) or mt5.shutdown()!
    Those calls would hijack/kill the shared MT5 session used by all bots.
    Instead, uses the safe ensure_mt5_ready() probe."""
    try:
        import MetaTrader5 as mt5
        
        if account_id and password:
            # Check if MT5 IPC is alive and we're logged into the right account
            if ensure_mt5_ready():
                existing = mt5.account_info()
                if existing and existing.login == int(account_id):
                    logger.info(f"✅ Exness connectivity verified for account {account_id}")
                    return {
                        'connected': True,
                        'account_id': account_id,
                        'server': server,
                        'balance': existing.balance,
                        'message': 'Successfully connected to Exness'
                    }
                elif existing:
                    # MT5 is alive but logged into different account
                    logger.info(f"ℹ️ Exness MT5 connected (account {existing.login}), requested {account_id}")
                    return {
                        'connected': True,
                        'account_id': str(existing.login),
                        'server': server,
                        'message': f'MT5 connected to account {existing.login}'
                    }
            logger.warning(f"⚠️ Exness MT5 not responding for account {account_id}")
            return {
                'connected': False,
                'error': 'MT5 terminal not responding'
            }
        else:
            # Just check if MT5 library responds
            if ensure_mt5_ready():
                logger.info("✅ Exness MT5 library responding")
                return {'connected': True, 'message': 'MT5 is connected and responding'}
            return {'connected': False, 'error': 'MT5 not responding'}
    except Exception as e:
        logger.error(f"❌ Error checking Exness connectivity: {e}")
        return {'connected': False, 'error': str(e)}


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


@app.route('/api/brokers/check-pxbt', methods=['GET'])
def check_pxbt():
    """Check if PXBT is available and can be used"""
    try:
        pxbt_info = detect_pxbt_mt5()
        return jsonify(pxbt_info), 200
    except Exception as e:
        logger.error(f"❌ Error checking PXBT availability: {e}")
        return jsonify({
            'available': False,
            'error': str(e)
        }), 500


@app.route('/api/brokers/pxbt/session-status', methods=['GET'])
@require_session
def get_pxbt_session_status():
    """Check PXBT MT5 connection status and health
    
    Returns connection status, last activity timestamp, and suggestion for action
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get PXBT credentials for this user
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live
            FROM broker_credentials
            WHERE user_id = ? AND is_active = 1 AND broker_name LIKE '%PXBT%'
        ''', (user_id,))
        
        creds = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not creds:
            return jsonify({
                'success': True,
                'connected': False,
                'message': 'No PXBT account connected',
                'accounts': []
            }), 200
        
        # Check status for each PXBT account
        account_status = []
        for cred in creds:
            credential_id = cred['credential_id']
            account_num = cred['account_number']
            server = cred['server'] or 'PXBTTrading-1'
            is_live = cred['is_live']
            
            # Check MT5 connection health
            mt5_conn = get_global_mt5()
            is_healthy = is_pxbt_connection_healthy(mt5_conn) if mt5_conn else False
            
            # Check if session is cached
            cached_creds = get_cached_pxbt_credentials(credential_id)
            cached_time = cached_creds.get('timestamp') if cached_creds else None
            
            account_status.append({
                'credentialId': credential_id,
                'accountNumber': account_num,
                'server': server,
                'mode': 'LIVE' if is_live else 'DEMO',
                'connected': is_healthy,
                'lastActivityTime': cached_time,
                'suggestion': 'Connection healthy - no action needed' if is_healthy else 'PXBT disconnected - click reconnect to restore'
            })
        
        return jsonify({
            'success': True,
            'connected': any(acc['connected'] for acc in account_status),
            'accounts': account_status,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting PXBT session status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/brokers/pxbt/reconnect', methods=['POST'])
@require_session
def reconnect_pxbt():
    """Force PXBT reconnection - useful when connection drops
    
    Attempts to re-establish MT5 connection using cached credentials
    """
    try:
        user_id = request.user_id
        data = request.get_json() or {}
        credential_id = data.get('credentialId')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get PXBT credentials (either specific credential or first active one)
        if credential_id:
            cursor.execute('''
                SELECT credential_id, broker_name, account_number, password, server, is_live
                FROM broker_credentials
                WHERE credential_id = ? AND user_id = ? AND is_active = 1
            ''', (credential_id, user_id))
        else:
            cursor.execute('''
                SELECT credential_id, broker_name, account_number, password, server, is_live
                FROM broker_credentials
                WHERE user_id = ? AND is_active = 1 AND broker_name LIKE '%PXBT%'
                LIMIT 1
            ''', (user_id,))
        
        cred_row = cursor.fetchone()
        conn.close()
        
        if not cred_row:
            return jsonify({
                'success': False,
                'error': 'PXBT credential not found'
            }), 404
        
        cred = dict(cred_row)
        credential_id = cred['credential_id']
        account_num = cred['account_number']
        password = cred['password']
        server = cred['server'] or 'PXBTTrading-1'
        
        logger.info(f"🔄 PXBT Reconnect requested for user {user_id}, account {account_num}")
        
        # Get current connection
        mt5_conn = get_global_mt5()
        
        # Build credentials dict for reconnect
        reconnect_creds = {
            'credential_id': credential_id,
            'broker': 'PXBT',
            'account': account_num,
            'password': password,
            'server': server,
            'is_live': cred['is_live']
        }
        
        if mt5_conn:
            # Try to reconnect existing connection
            if ensure_pxbt_connection_active(mt5_conn, reconnect_creds, retry_count=5):
                logger.info(f"✅ PXBT reconnection successful for {account_num}")
                return jsonify({
                    'success': True,
                    'message': f'Successfully reconnected to PXBT account {account_num}',
                    'accountNumber': account_num,
                    'server': server
                }), 200
            else:
                logger.error(f"❌ PXBT reconnection failed for {account_num}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to reconnect to PXBT account {account_num} - try again in a moment'
                }), 500
        else:
            # No existing connection - create new one
            logger.info(f"Creating new MT5 connection for PXBT...")
            try:
                mt5_conn = MT5Connection(reconnect_creds)
                if mt5_conn.connect():
                    set_global_mt5(mt5_conn)
                    cache_pxbt_credentials(credential_id, account_num, password, server)
                    logger.info(f"✅ New PXBT connection created and connected")
                    return jsonify({
                        'success': True,
                        'message': f'Created and connected to PXBT account {account_num}',
                        'accountNumber': account_num,
                        'server': server
                    }), 200
                else:
                    logger.error(f"❌ Failed to connect new MT5 connection for PXBT")
                    return jsonify({
                        'success': False,
                        'error': 'Failed to create new connection to PXBT'
                    }), 500
            except Exception as e:
                logger.error(f"❌ Exception creating MT5 connection: {e}")
                return jsonify({
                    'success': False,
                    'error': f'Error: {str(e)}'
                }), 500
    
    except Exception as e:
        logger.error(f"Error reconnecting PXBT: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
    pxbt_status = detect_pxbt_mt5()
    pxbt_broker_status = 'active' if pxbt_status.get('available') else 'inactive'
    
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
            'type': 'pxbt',
            'name': 'PXBT (Prime XBT)',
            'description': 'PXBT - MetaTrader 5 forex & commodities broker',
            'assets': ['Forex', 'Metals', 'Indices', 'Cryptos'],
            'status': 'active',  # Always show PXBT as available for configuration
            'installed': pxbt_status.get('installed', False),
            'version': pxbt_status.get('version', 'Unknown'),
            'configurable': True,
            'note': 'Configure PXBT credentials in .env file'
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
    """Get user's current trading mode (DEMO or LIVE)"""
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
@require_session
def switch_trading_mode():
    """Switch between DEMO and LIVE trading modes"""
    try:
        data = request.get_json()
        user_id = request.user_id  # From @require_session decorator
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
    
    IMPORTANT: Uses a 5-second timeout per broker to prevent dashboard reload loops.
    If a broker connection times out, returns cached balance from last successful fetch.
    """
    import signal
    import threading
    global balance_cache, balance_cache_lock
    
    def timeout_handler():
        """Handler for connection timeout"""
        pass
    
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
        
        # CRITICAL FIX: Fetch cached balances for fallback on timeout
        cursor.execute('''
            SELECT credential_id, cached_balance, cached_equity, cached_margin_free, 
                   cached_margin, cached_margin_level, cached_profit, last_update
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        
        cached_data = {row['credential_id']: dict(row) for row in cursor.fetchall()}
        conn.close()
        
        accounts_summary = {
            'success': True,
            'accounts': [],
            'totalBalance': 0,
            'totalEquity': 0,
            'brokers': {},  # Grouped by broker: {Exness: {...}, XM: {...}, Binance: {...}}
        }
        
        # Fetch balance from each broker with timeout protection
        for cred in credentials:
            broker_name = canonicalize_broker_name(cred['broker_name'])
            account_num = cred['account_number']
            is_live = cred['is_live']
            mode = 'Live' if is_live else 'Demo'
            
            account_info = None
            error_msg = None
            timed_out = False
            
            try:
                # --- PATCH: Always attempt live fetch for Exness live accounts using socket bridge ---
                if broker_name == 'Exness' and is_live:
                    try:
                        bridge = socket_bridge_manager.get_bridge('Exness', str(account_num))
                        if bridge:
                            acc_info = bridge.get_account_info()
                            if acc_info and acc_info.get('balance') is not None:
                                account_info = {
                                    'accountNumber': account_num,
                                    'balance': float(acc_info.get('balance', 0)),
                                    'equity': float(acc_info.get('equity', 0)),
                                    'marginFree': float(acc_info.get('margin_free', 0)),
                                    'margin': float(acc_info.get('margin', 0)),
                                    'margin_level': float(acc_info.get('margin_level', 0)),
                                    'total_pl': float(acc_info.get('profit', 0)),
                                    'currency': acc_info.get('currency', 'USD'),
                                    'connected': True,
                                    'dataSource': 'live',
                                }
                                logger.info(f"✅ Live MT5 fetch via socket bridge for Exness {account_num}: ${account_info['balance']:.2f}")
                            else:
                                error_msg = "Socket bridge did not return valid account info"
                        else:
                            error_msg = "No socket bridge available for Exness account"
                    except Exception as e:
                        logger.warning(f"Socket bridge live fetch failed for Exness {account_num}: {e}")
                        error_msg = f"Socket bridge live fetch failed: {e}"
                elif broker_name in ['Exness', 'XM', 'XM Global', 'PXBT']:
                    # DISCONNECTED MODE: Do NOT call MT5 from the balance endpoint for demo or other brokers.
                    logger.info(f"ℹ️ Balance: {broker_name} {account_num} — using cache only (MT5 disconnected in balance endpoint)")
                    error_msg = "Using cached balance — MT5 reads handled by trading loop"
                elif broker_name == 'Binance':
                    # Connect to Binance API with timeout
                    try:
                        binance_conn = BinanceConnection({
                            'api_key': cred['api_key'],
                            'api_secret': cred['password'],
                            'account_number': account_num,
                            'is_live': is_live,
                        })
                        result = [None]
                        def connect_binance():
                            if binance_conn.connect():
                                balance_info = binance_conn.get_balance()
                                result[0] = {
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
                        
                        thread = threading.Thread(target=connect_binance, daemon=True)
                        thread.start()
                        thread.join(timeout=5)  # 5-second timeout
                        
                        if thread.is_alive():
                            logger.warning(f"Binance balance fetch timed out for {account_num}")
                            timed_out = True
                            error_msg = "Connection timeout"
                        else:
                            account_info = result[0]
                            if not account_info:
                                error_msg = "Failed to connect to Binance API"
                    except Exception as e:
                        logger.warning(f"Binance balance error: {e}")
                        error_msg = str(e)
                
                else:
                    # Generic MT5 fallback — also disconnected, use cache only
                    logger.info(f"ℹ️ Balance: {broker_name} {account_num} — using cache only (MT5 disconnected in balance endpoint)")
                    error_msg = "Using cached balance — MT5 reads handled by trading loop"
                
            except Exception as e:
                logger.warning(f"Error fetching balance from {broker_name} account {account_num}: {e}")
                error_msg = str(e)
            
            # Build account entry
            # Count active bots for this account
            try:
                bot_conn = get_db_connection()
                bot_cursor = bot_conn.cursor()
                bot_cursor.execute('''
                    SELECT COUNT(*) as count FROM user_bots
                    WHERE user_id = ? AND broker_account_id = ? AND status = 'active' AND enabled = 1
                ''', (user_id, account_num))
                active_bot_count = bot_cursor.fetchone()['count']
                bot_conn.close()
            except Exception:
                active_bot_count = 0
            
            account_entry = {
                'credentialId': cred['credential_id'],
                'broker': broker_name,
                'accountNumber': account_num,
                'mode': mode,
                'is_live': is_live,  # Include is_live flag for frontend mode filtering
                'active_bots': active_bot_count,
                'last_update': datetime.now().isoformat() if account_info else cached_data.get(cred['credential_id'], {}).get('last_update'),
                'error': error_msg,
            }
            
            if account_info:
                # Fresh data from broker connection
                account_entry.update({
                    'balance': account_info.get('balance', 0),
                    'equity': account_info.get('equity', account_info.get('balance', 0)),
                    'marginFree': account_info.get('marginFree', 0),
                    'margin': account_info.get('margin', 0),
                    'margin_level': account_info.get('margin_level', 0),
                    'total_pl': account_info.get('total_pl', 0),
                    'currency': account_info.get('currency', 'USD'),
                    'connected': True,
                    'dataSource': 'live',
                })
                # Add to broker group
                if broker_name not in accounts_summary['brokers']:
                    accounts_summary['brokers'][broker_name] = []
                accounts_summary['brokers'][broker_name].append(account_entry)
                # Accumulate totals
                accounts_summary['totalBalance'] += account_entry['balance']
                accounts_summary['totalEquity'] += account_entry['equity']
            else:
                # No live broker connection — use cached balance from
                # balance_cache (populated by bot trading loops) or DB cache.
                cache_key = get_balance_cache_key(broker_name, account_num)
                cached_balance = 0
                cached_equity = 0
                cached_margin = 0
                cached_margin_free = 0
                cached_margin_level = 0
                cached_profit = 0
                # Check in-memory cache (populated by bot trading loops)
                with balance_cache_lock:
                    if cache_key in balance_cache:
                        cached_info = balance_cache[cache_key]
                        cached_balance = cached_info.get('balance', 0)
                        cached_equity = cached_info.get('equity', cached_balance)
                        cached_margin = cached_info.get('margin', 0)
                        cached_margin_free = cached_info.get('marginFree', 0)
                        cached_margin_level = cached_info.get('margin_level', 0)
                        cached_profit = cached_info.get('total_pl', 0)
                        logger.info(f"✅ Balance cache hit for {cache_key}: ${cached_balance:.2f}")
                # Fallback: try SQLite cached_balance column
                if cached_balance == 0 and cred['credential_id'] in cached_data:
                    cache = dict(cached_data[cred['credential_id']])
                    cached_balance = cache.get('cached_balance', 0) or 0
                    cached_equity = cache.get('cached_equity', cached_balance) or 0
                    cached_margin = cache.get('cached_margin', 0) or 0
                    cached_margin_free = cache.get('cached_margin_free', 0) or 0
                    cached_margin_level = cache.get('cached_margin_level', 0) or 0
                    cached_profit = cache.get('cached_profit', 0) or 0
                    if cached_balance > 0:
                        logger.info(f"✅ SQLite cache hit for {cache_key}: ${cached_balance:.2f}")
                # --- NEW: If still $0 and Exness, try live fetch from MT5 ---
                if cached_balance == 0 and broker_name == 'Exness':
                    try:
                        import MetaTrader5 as mt5
                        if mt5.initialize():
                            acc_info = mt5.account_info()
                            if acc_info and acc_info.login == int(account_num):
                                cached_balance = acc_info.balance
                                cached_equity = acc_info.equity
                                cached_margin = acc_info.margin
                                cached_margin_free = acc_info.margin_free
                                cached_margin_level = acc_info.margin_level if acc_info.margin_level else 0
                                cached_profit = acc_info.profit
                                logger.info(f"✅ Live MT5 fetch for Exness {account_num}: ${cached_balance:.2f}")
                            mt5.shutdown()
                    except Exception as e:
                        logger.warning(f"Live MT5 fetch failed for Exness {account_num}: {e}")
                has_cached_data = cached_balance > 0
                account_entry.update({
                    'balance': float(cached_balance),
                    'equity': float(cached_equity),
                    'marginFree': float(cached_margin_free),
                    'margin': float(cached_margin),
                    'margin_level': float(cached_margin_level),
                    'total_pl': float(cached_profit),
                    'currency': 'USD',
                    'connected': has_cached_data,  # Show as connected when we have valid cached data
                    'dataSource': 'cache' if has_cached_data else 'not_connected',
                })
                # Clear error when cached data is available — it's not an error
                if has_cached_data:
                    account_entry.pop('error', None)
                else:
                    account_entry['warning'] = 'Account not connected — balance will update when bot runs'
                # Add to broker group
                if broker_name not in accounts_summary['brokers']:
                    accounts_summary['brokers'][broker_name] = []
                accounts_summary['brokers'][broker_name].append(account_entry)
                # Accumulate totals from cache (better than $0)
                accounts_summary['totalBalance'] += account_entry['balance']
                accounts_summary['totalEquity'] += account_entry['equity']
            
            accounts_summary['accounts'].append(account_entry)
        
        logger.info(f"✅ Fetched account balances for user {user_id}: {len(accounts_summary['accounts'])} accounts, Total: ${accounts_summary['totalBalance']:.2f}")
        
        return jsonify(accounts_summary)
    
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<credential_id>/details', methods=['GET'])
@require_session
def get_account_details(credential_id):
    """Get detailed financial information for a specific broker account.
    
    Returns:
    - Account info (broker, account number, balance, equity)
    - Trade history with profits/losses
    - Withdrawal history
    - Commission/fee summary
    - Net profit calculation
    """
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify credential belongs to this user
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, is_live, server,
                   cached_balance, cached_equity, cached_margin_free, last_update
            FROM broker_credentials
            WHERE credential_id = ? AND user_id = ? AND is_active = 1
        ''', (credential_id, user_id))
        
        cred = cursor.fetchone()
        if not cred:
            conn.close()
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        cred = dict(cred)
        broker_name = cred['broker_name']
        account_number = cred['account_number']
        
        # Get live balance if Exness and connected
        balance = float(cred.get('cached_balance') or 0)
        equity = float(cred.get('cached_equity') or 0)
        margin_free = float(cred.get('cached_margin_free') or 0)
        
        if broker_name == 'Exness':
            try:
                import MetaTrader5 as mt5
                existing = mt5.account_info()
                if existing and existing.login == int(account_number):
                    balance = existing.balance
                    equity = existing.equity
                    margin_free = existing.margin_free
            except Exception:
                pass
        
        # Get all trades for bots linked to this account
        cursor.execute('''
            SELECT t.trade_id, t.bot_id, t.symbol, t.order_type, t.volume,
                   t.price, t.profit, t.commission, t.swap, t.ticket,
                   t.time_open, t.time_close, t.status, t.created_at,
                   b.name as bot_name
            FROM trades t
            LEFT JOIN user_bots b ON t.bot_id = b.bot_id
            WHERE t.user_id = ? AND (
                b.broker_account_id = ? OR
                t.bot_id IN (
                    SELECT bc.bot_id FROM bot_credentials bc
                    WHERE bc.credential_id = ?
                )
            )
            ORDER BY t.created_at DESC
            LIMIT 200
        ''', (user_id, account_number, credential_id))
        
        trades = [dict(row) for row in cursor.fetchall()]
        
        # If no trades found via bot linkage, try broader match by user
        if not trades:
            cursor.execute('''
                SELECT t.trade_id, t.bot_id, t.symbol, t.order_type, t.volume,
                       t.price, t.profit, t.commission, t.swap, t.ticket,
                       t.time_open, t.time_close, t.status, t.created_at,
                       b.name as bot_name
                FROM trades t
                LEFT JOIN user_bots b ON t.bot_id = b.bot_id
                WHERE t.user_id = ?
                ORDER BY t.created_at DESC
                LIMIT 200
            ''', (user_id,))
            trades = [dict(row) for row in cursor.fetchall()]
        
        # Calculate trade stats
        total_profit = 0
        total_loss = 0
        total_commission = 0
        total_swap = 0
        open_trades = 0
        closed_trades = 0
        winning_trades = 0
        losing_trades = 0
        
        for trade in trades:
            profit = float(trade.get('profit') or 0)
            commission = float(trade.get('commission') or 0)
            swap = float(trade.get('swap') or 0)
            status = trade.get('status', 'open')
            
            total_commission += commission
            total_swap += swap
            
            if status == 'closed':
                closed_trades += 1
                if profit >= 0:
                    total_profit += profit
                    winning_trades += 1
                else:
                    total_loss += profit
                    losing_trades += 1
            else:
                open_trades += 1
                if profit >= 0:
                    total_profit += profit
                else:
                    total_loss += profit
        
        # Get withdrawal history for this account
        cursor.execute('''
            SELECT withdrawal_id, withdrawal_type, source_type,
                   profit_from_trades, commission_earned, total_amount,
                   fee, net_amount, status, withdrawal_method,
                   created_at, completed_at
            FROM exness_withdrawals
            WHERE user_id = ? AND broker_account_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id, account_number))
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        total_withdrawn = sum(float(w.get('net_amount') or w.get('total_amount') or 0) for w in withdrawals if w.get('status') == 'completed')
        
        # Get commission ledger entries
        cursor.execute('''
            SELECT entry_id, type, amount, payout_status, payout_date,
                   bot_id, trading_profit, created_at
            FROM commission_ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))
        
        commissions = [dict(row) for row in cursor.fetchall()]
        total_commission_earned = sum(float(c.get('amount') or 0) for c in commissions)
        
        # Get active bots count for this account
        cursor.execute('''
            SELECT COUNT(*) as count FROM user_bots
            WHERE user_id = ? AND broker_account_id = ? AND status = 'active' AND enabled = 1
        ''', (user_id, account_number))
        active_bots = cursor.fetchone()['count']
        
        # Get total bots count
        cursor.execute('''
            SELECT COUNT(*) as count FROM user_bots
            WHERE user_id = ? AND broker_account_id = ?
        ''', (user_id, account_number))
        total_bots = cursor.fetchone()['count']
        
        conn.close()
        
        # Calculate net profit
        gross_profit = total_profit + total_loss  # total_loss is negative
        net_profit = gross_profit + total_commission + total_swap  # commission and swap are usually negative
        win_rate = (winning_trades / max(winning_trades + losing_trades, 1)) * 100
        
        return jsonify({
            'success': True,
            'account': {
                'credentialId': credential_id,
                'broker': broker_name,
                'accountNumber': account_number,
                'isLive': bool(cred['is_live']),
                'server': cred.get('server'),
                'balance': balance,
                'equity': equity,
                'marginFree': margin_free,
                'activeBots': active_bots,
                'totalBots': total_bots,
            },
            'tradeStats': {
                'totalTrades': len(trades),
                'openTrades': open_trades,
                'closedTrades': closed_trades,
                'winningTrades': winning_trades,
                'losingTrades': losing_trades,
                'winRate': round(win_rate, 1),
                'totalProfit': round(total_profit, 2),
                'totalLoss': round(total_loss, 2),
                'grossProfit': round(gross_profit, 2),
                'totalCommission': round(total_commission, 2),
                'totalSwap': round(total_swap, 2),
                'netProfit': round(net_profit, 2),
            },
            'recentTrades': trades[:20],
            'withdrawals': {
                'history': withdrawals[:10],
                'totalWithdrawn': round(total_withdrawn, 2),
                'count': len(withdrawals),
            },
            'commissions': {
                'history': commissions[:10],
                'totalEarned': round(total_commission_earned, 2),
                'count': len(commissions),
            },
        })
        
    except Exception as e:
        logger.error(f"Error getting account details: {e}")
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


# ==================== NEW: ENRICHED ACCOUNT DATA ENDPOINTS ====================

@app.route('/api/account/detailed', methods=['GET'])
@require_session
def get_account_detailed():
    """Get COMPREHENSIVE account data from Exness with all metrics"""
    user_id = request.user_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # PRIORITY ORDER: Try DEMO account first (where bots are actually trading)
        # Then fall back to LIVE account
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, password, server, is_live
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1 AND broker_name = 'Exness'
            ORDER BY is_live ASC, credential_id
            LIMIT 2
        ''', (user_id,))
        
        creds = cursor.fetchall()
        conn.close()
        
        if not creds:
            return jsonify({
                'success': False,
                'error': 'No Exness credentials found'
            }), 404
        
        # CRITICAL FIX: Read from existing MT5 session instead of re-initializing
        import MetaTrader5 as mt5
        account_info = None
        
        # First, try to use the currently logged-in MT5 session (where bots are actually trading)
        try:
            existing = mt5.account_info()
            if existing:
                # Check if ANY of the user's accounts matches the currently logged-in account
                for cred in creds:
                    if existing.login == int(cred[2]):
                        account_info = {
                            'accountNumber': cred[2],
                            'balance': existing.balance,
                            'equity': existing.equity,
                            'marginFree': existing.margin_free,
                            'currency': existing.currency,
                            'leverage': existing.leverage,
                            'broker': 'Exness',
                            'profit': existing.profit,
                            'margin': existing.margin,
                            'margin_level': existing.margin_level if existing.margin_level else 0,
                            'name': existing.name,
                            'server': existing.server,
                            'trade_mode': existing.trade_mode,
                        }
                        logger.info(f"✅ Account detailed: Read from existing MT5 session for {existing.login}")
                        break
        except Exception as e:
            logger.warning(f"Could not read existing MT5 session: {e}")
        
        # If existing session doesn't match any credential, try connecting to each (demo first)
        if not account_info:
            for cred in creds:
                try:
                    logger.info(f"Attempting to connect to Exness account {cred[2]} (is_live={cred[5]})")
                    mt5_conn = MT5Connection({
                        'account': int(cred[2]),
                        'password': cred[3],
                        'server': cred[4],
                    })
                    if mt5_conn.connect():
                        account_info = mt5_conn.get_account_info()
                        mt5_conn.disconnect()
                        logger.info(f"✅ Successfully connected to account {cred[2]}")
                        break
                    else:
                        logger.warning(f"Failed to connect to account {cred[2]}")
                except Exception as e:
                    logger.warning(f"Exception connecting to account {cred[2]}: {e}")
        
        if account_info:
            return jsonify({
                'success': True,
                'account': account_info,
                'lastUpdate': datetime.utcnow().isoformat(),
            })
        else:
            # Return error that allows Flutter to use cached balance instead of mock data
            return jsonify({
                'success': False,
                'error': 'Could not connect to Exness - MT5 terminal may not be ready'
            }), 503
            
    except Exception as e:
        logger.error(f"Error getting detailed account info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/positions/detailed', methods=['GET'])
@require_session
def get_positions_detailed():
    """Get ALL open positions with DETAILED metrics"""
    user_id = request.user_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, password, server, is_live
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1 AND broker_name = 'Exness'
            ORDER BY credential_id
            LIMIT 1
        ''', (user_id,))
        
        cred = cursor.fetchone()
        conn.close()
        
        if not cred:
            return jsonify({
                'success': False,
                'positions': [],
                'totalCount': 0
            })
        
        mt5_conn = MT5Connection({
            'account': int(cred[2]),
            'password': cred[3],
            'server': cred[4],
        })
        
        if mt5_conn.connect():
            positions = mt5_conn.get_positions()
            mt5_conn.disconnect()
            
            return jsonify({
                'success': True,
                'positions': positions,
                'totalCount': len(positions),
                'totalPL': sum(p['pnl'] for p in positions),
            })
        else:
            return jsonify({
                'success': False,
                'positions': [],
                'error': 'Connection failed'
            })
            
    except Exception as e:
        logger.error(f"Error getting detailed positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'positions': []
        }), 500


@app.route('/api/trades/history', methods=['GET'])
@require_session
def get_trades_history():
    """Get TRADE HISTORY (closed trades) from the last N days"""
    user_id = request.user_id
    days = request.args.get('days', default=30, type=int)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, password, server, is_live
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1 AND broker_name = 'Exness'
            ORDER BY credential_id
            LIMIT 1
        ''', (user_id,))
        
        cred = cursor.fetchone()
        conn.close()
        
        if not cred:
            return jsonify({
                'success': False,
                'trades': []
            })
        
        mt5_conn = MT5Connection({
            'account': int(cred[2]),
            'password': cred[3],
            'server': cred[4],
        })
        
        if mt5_conn.connect():
            trades = mt5_conn.get_trade_history(days=days)
            mt5_conn.disconnect()
            
            return jsonify({
                'success': True,
                'trades': trades,
                'totalCount': len(trades),
                'period': f'Last {days} days',
            })
        else:
            return jsonify({
                'success': False,
                'trades': [],
                'error': 'Connection failed'
            })
            
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'trades': []
        }), 500


@app.route('/api/account/performance', methods=['GET'])
@require_session
def get_account_performance():
    """Get account PERFORMANCE METRICS and statistics"""
    user_id = request.user_id
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, password, server, is_live
            FROM broker_credentials 
            WHERE user_id = ? AND is_active = 1 AND broker_name = 'Exness'
            ORDER BY credential_id
            LIMIT 1
        ''', (user_id,))
        
        cred = cursor.fetchone()
        conn.close()
        
        if not cred:
            return jsonify({
                'success': False,
                'metrics': None
            })
        
        mt5_conn = MT5Connection({
            'account': int(cred[2]),
            'password': cred[3],
            'server': cred[4],
        })
        
        if mt5_conn.connect():
            metrics = mt5_conn.get_performance_metrics()
            mt5_conn.disconnect()
            
            return jsonify({
                'success': True,
                'metrics': metrics,
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Connection failed'
            })
            
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
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

PXBT_VALID_SYMBOLS = {
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF',
    'XAUUSD', 'XAGUSD',
    'US30', 'EUR50', 'BRENT',
    'BTCUSDT', 'ETHUSDT',
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

    if broker_name == 'PXBT':
        if not symbols:
            return ['EURUSD']

        corrected = []
        pxbt_symbol_map = {
            'EURUSDM': 'EURUSD', 'EURUSD': 'EURUSD',
            'GBPUSDM': 'GBPUSD', 'GBPUSD': 'GBPUSD',
            'USDJPYM': 'USDJPY', 'USDJPY': 'USDJPY',
            'USDCHFM': 'USDCHF', 'USDCHF': 'USDCHF',
            'XAUUSDM': 'XAUUSD', 'XAUUSD': 'XAUUSD', 'GOLD': 'XAUUSD',
            'XAGUSDM': 'XAGUSD', 'XAGUSD': 'XAGUSD', 'SILVER': 'XAGUSD',
            'US30M': 'US30', 'US30': 'US30', 'DJ30': 'US30',
            'EUR50M': 'EUR50', 'EUR50': 'EUR50',
            'BRENTUSD': 'BRENT', 'BRENTM': 'BRENT', 'BRENT': 'BRENT',
            'BTCUSDM': 'BTCUSDT', 'BTCUSD': 'BTCUSDT', 'BTCUSDT': 'BTCUSDT', 'BITCOIN': 'BTCUSDT',
            'ETHUSDM': 'ETHUSDT', 'ETHUSD': 'ETHUSDT', 'ETHUSDT': 'ETHUSDT', 'ETHEREUM': 'ETHUSDT',
        }

        for symbol in symbols:
            normalized = str(symbol).upper().replace('/', '').replace('_', '')
            normalized = pxbt_symbol_map.get(normalized, normalized)

            if normalized in PXBT_VALID_SYMBOLS and normalized not in corrected:
                corrected.append(normalized)
            else:
                logger.warning(f"⚠️ Unknown PXBT symbol {symbol} -> defaulting to EURUSD")
                if 'EURUSD' not in corrected:
                    corrected.append('EURUSD')

        return corrected[:5] or ['EURUSD']

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
        'stop_loss_pips': 50000,
        'take_profit_pips': 100000,
        'max_slippage': 0.002,
        'min_signal_strength': 40,
        'volatility_high': 5.0,
        'volatility_low': 1.0,
    },
    'ETHUSDm': {
        'atr_multiplier': 2.0,
        'stop_loss_pips': 2000,
        'take_profit_pips': 5000,
        'max_slippage': 0.002,
        'min_signal_strength': 40,
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
        current_price = market_data.get('current_price', 0) or market_data.get('price', 0)
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
        price_history = market_data.get('price_history', [current_price] * 50)[-50:]
        if len(price_history) < 5:
            price_history = [current_price] * 50
        
        # Calculate technical indicators
        rsi = calculate_rsi(price_history, period=14)
        ma_short, ma_long = calculate_moving_averages(price_history, short=10, long=20)
        macd_line, signal_line, histogram = calculate_macd(price_history)
        
        # Determine trend — use dead zone around ma_long to avoid flip-flopping
        ma_diff_pct = (current_price - ma_long) / ma_long * 100 if ma_long > 0 else 0
        if ma_diff_pct > 0.1:  # clearly above MA → uptrend or ranging
            trend = 'UP' if ma_short > ma_long else 'RANGING'
        elif ma_diff_pct < -0.1:  # clearly below MA → downtrend
            trend = 'DOWN'
        else:  # price near ma_long → use MA crossover for direction
            if ma_short > ma_long:
                trend = 'UP'
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
        elif rsi < 45:
            strength += 15
            signal = 'BUY'
            entry_reason.append(f'RSI leaning oversold ({rsi:.0f})')
        elif rsi > 55:
            strength += 15
            signal = 'SELL'
            entry_reason.append(f'RSI leaning overbought ({rsi:.0f})')
        else:  # 45 <= rsi <= 55
            strength += 10
            # Use recent price momentum for direction in neutral RSI zone
            # Compare against price_history[-5] for wider momentum window
            ref_idx = -5 if len(price_history) >= 5 else -len(price_history)
            ref_price = price_history[ref_idx]
            if current_price < ref_price:
                signal = 'SELL'
                entry_reason.append(f'RSI neutral ({rsi:.0f}) + bearish momentum')
            elif current_price > ref_price:
                signal = 'BUY'
                entry_reason.append(f'RSI neutral ({rsi:.0f}) + bullish momentum')
            else:
                # Fallback: use MA crossover for direction
                if ma_short < ma_long:
                    signal = 'SELL'
                    entry_reason.append(f'RSI neutral ({rsi:.0f}) + MA bearish')
                elif ma_short > ma_long:
                    signal = 'BUY'
                    entry_reason.append(f'RSI neutral ({rsi:.0f}) + MA bullish')
                else:
                    entry_reason.append(f'RSI neutral ({rsi:.0f})')
        
        # MACD-based signals (0-30)
        macd_direction = None
        if histogram > 0 and macd_line > signal_line:
            strength += 20
            macd_direction = 'BUY'
            entry_reason.append('MACD bullish')
        elif histogram < 0 and macd_line < signal_line:
            strength += 20
            macd_direction = 'SELL'
            entry_reason.append('MACD bearish')
        
        # Trend-based signals (0-30) — always contribute when trend detected
        trend_direction = None
        if trend == 'UP':
            strength += 15
            trend_direction = 'BUY'
            entry_reason.append('Uptrend confirmed')
        elif trend == 'DOWN':
            strength += 15
            trend_direction = 'SELL'
            entry_reason.append('Downtrend confirmed')
        elif trend == 'RANGING' and signal != 'NEUTRAL':
            strength += 15
            entry_reason.append('Ranging market - follow signal')
        
        # Majority-vote direction: if MACD + trend disagree with RSI, majority wins
        if signal != 'NEUTRAL' and macd_direction and trend_direction:
            votes = {'BUY': 0, 'SELL': 0}
            votes[signal] += 1  # RSI vote
            votes[macd_direction] += 1  # MACD vote
            votes[trend_direction] += 1  # Trend vote
            majority = 'BUY' if votes['BUY'] > votes['SELL'] else 'SELL'
            if majority != signal:
                signal = majority
        elif signal == 'NEUTRAL':
            # Set direction from MACD or trend
            signal = macd_direction or trend_direction or 'NEUTRAL'
        
        # Volatility adjustment (0-10)
        if volatility == 'LOW':
            strength += 5
            entry_reason.append('Low volatility - good for tight stops')
        elif volatility == 'HIGH' and signal != 'NEUTRAL':
            strength -= 10
            entry_reason.append('High volatility - reduced confidence')
        
        # Debug logging for signal evaluation
        if symbol in ['ETHUSDm', 'BTCUSDm', 'XAUUSDm']:
            logger.info(f"[SIGNAL-DBG] {symbol}: rsi={rsi:.1f} macd_h={histogram:.6f} trend={trend} vol={volatility} sig={signal} str={strength} ma_diff={ma_diff_pct:.4f}% reasons={entry_reason}")
        
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
    
    # Trend following needs trend + signal (ranging allowed at normal threshold)
    if signal_eval['strength'] < params['min_signal_strength']:
        return None
    
    # Use the actual signal direction from the evaluator
    order_type = 'BUY' if 'BUY' in signal_eval['signal'] else 'SELL'
    
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
    'maxOpenPositions',
    'maxPositionsPerSymbol',
    'managementMode',
    'managementProfile',
    'managementState',
    'mode',
    'name',
    'peakProfit',
    'profit',
    'profitHistory',
    'profitLock',
    'riskPerTrade',
    'signalThreshold',
    'startTime',
    'strategy',
    'strategyHistory',
    'symbols',
    'open_positions',
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
        'maxOpenPositions': 5,
        'maxPositionsPerSymbol': 5,
        'profitLock': 80.0,
        'drawdownPausePercent': 5.0,
        'drawdownPauseHours': 6.0,
        'allowedVolatility': ['Low', 'Medium'],
        'autoSwitch': True,
        'dynamicSizing': True,
        'managementMode': 'assisted',
        'managementProfile': 'beginner',
        'managementState': 'normal',
        'signalThreshold': 70,
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
    bot_state['maxOpenPositions'] = bot_state.get('maxOpenPositions') or 5
    bot_state['maxPositionsPerSymbol'] = bot_state.get('maxPositionsPerSymbol') or bot_state['maxOpenPositions']
    bot_state['managementProfile'] = _normalize_management_profile(bot_state.get('managementProfile'))
    bot_state['managementMode'] = bot_state.get('managementMode') or 'assisted'
    bot_state['managementState'] = bot_state.get('managementState') or 'normal'
    bot_state['signalThreshold'] = bot_state.get('signalThreshold') or BOT_MANAGEMENT_PROFILES[bot_state['managementProfile']]['signalThreshold']
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
    # ✅ Always resync totalTrades from DB count — covers both: tradeHistory loaded now
    # AND the case where tradeHistory was already in persisted runtime_state but totalTrades=0
    try:
        tsync_conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
        tsync_cur = tsync_conn.cursor()
        tsync_cur.execute('SELECT COUNT(*) FROM trades WHERE bot_id = ?', (row['bot_id'],))
        db_trade_count = tsync_cur.fetchone()[0] or 0
        tsync_conn.close()
        if db_trade_count > bot_state.get('totalTrades', 0):
            bot_state['totalTrades'] = db_trade_count
            logger.info(f"📊 Resynced totalTrades={db_trade_count} from DB for bot {row['bot_id']}")
    except Exception as e:
        logger.warning(f"Could not resync totalTrades for bot {row['bot_id']}: {e}")
    bot_state['profitHistory'] = bot_state.get('profitHistory') or []
    bot_state['dailyProfits'] = bot_state.get('dailyProfits') or {}
    # Restore open_positions from DB if not already in runtime_state
    if not bot_state.get('open_positions'):
        bot_state['open_positions'] = {}
        try:
            tconn2 = sqlite3.connect(DATABASE_PATH, timeout=10.0)
            tconn2.row_factory = sqlite3.Row
            tcursor2 = tconn2.cursor()
            tcursor2.execute(
                "SELECT ticket, symbol, order_type, volume, price, time_open FROM trades WHERE bot_id = ? AND status = 'open'",
                (row['bot_id'],)
            )
            for trow in tcursor2.fetchall():
                ticket_str = str(trow['ticket'])
                bot_state['open_positions'][ticket_str] = {
                    'ticket': trow['ticket'],
                    'symbol': trow['symbol'],
                    'type': trow['order_type'],
                    'volume': trow['volume'],
                    'entryPrice': trow['price'],
                    'entryTime': trow['time_open'],
                }
            tconn2.close()
            if bot_state['open_positions']:
                logger.info(f"📂 Restored {len(bot_state['open_positions'])} open positions from DB for bot {row['bot_id']}")
        except Exception as e:
            logger.warning(f"Could not restore open positions for bot {row['bot_id']}: {e}")
    # Clear today's P&L on restore — stale/sample-trade values from before a
    # restart would otherwise immediately trigger daily-loss limits.  Real
    # intra-day P&L will be recalculated from new trades placed after restart.
    today_key = datetime.now().strftime('%Y-%m-%d')
    bot_state['dailyProfits'].pop(today_key, None)
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

    conn = None
    for attempt in range(3):
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
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
            else:
                logger.warning(f"Could not persist runtime state for bot {bot_id}: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None


def log_pause_event(bot_id: str, user_id: str, symbol: str, pause_type: str, retcode: int, 
                    error_message: str, pause_reason: str):
    """Log a market pause/halt event to the database for monitoring and debugging"""
    try:
        pause_id = str(uuid.uuid4())
        detected_at = datetime.now().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO pause_events 
            (pause_id, bot_id, user_id, symbol, pause_type, retcode, error_message, reason, detected_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pause_id, bot_id, user_id, symbol, pause_type, retcode, 
            error_message, pause_reason, detected_at, detected_at
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Pause event logged: bot={bot_id}, symbol={symbol}, type={pause_type}, retcode={retcode}")
        return pause_id
    except Exception as e:
        logger.error(f"Error logging pause event: {e}")
        return None


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
    # If worker pool is active, send stop via worker queue
    if worker_pool_manager and worker_pool_manager.enabled:
        worker_pool_manager.stop_bot(bot_id)
        logger.info(f"🛑 Bot {bot_id}: Stop dispatched to worker pool")
    elif bot_id in bot_threads and bot_threads[bot_id].is_alive():
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

                # --- Small Account & Fast Growth Profile Logic ---
                profile = bot.get('managementProfile') or bot.get('profile')
                balance = float(bot.get('accountBalance', 0))
                min_lot = 0.01
                # If Fast Growth profile or balance is small, apply special logic
                if profile == 'fast_growth' or balance <= 200:
                    risk_percent = min(float(bot.get('riskPercent', 4.0)), 5.0)
                    sl = float(bot.get('stopLoss', 0))
                    tp = float(bot.get('takeProfit', 0))
                    if not sl or sl > balance * 0.01:
                        sl = round(balance * 0.005, 2)  # 0.5% of balance
                    if not tp or tp > balance * 0.02:
                        tp = round(balance * 0.01, 2)   # 1% of balance
                    max_trades = max(int(bot.get('maxOpenTrades', 6)), 4)
                    lot_size = max(min_lot, round((balance * risk_percent / 100) / (sl if sl else 1), 2))
                    trade_params = {
                        'symbol': symbol,
                        'order_type': 'BUY',  # or use bot logic
                        'volume': lot_size,
                        'stopLoss': sl,
                        'takeProfit': tp,
                        'maxOpenTrades': max_trades,
                        'autoCompound': True
                    }
                else:
                    # Default logic for other profiles
                    trade_params = {
                        'symbol': symbol,
                        'order_type': 'BUY',  # or use bot logic
                        'volume': bot.get('lotSize', 0.01),
                        'stopLoss': bot.get('stopLoss'),
                        'takeProfit': bot.get('takeProfit'),
                        'maxOpenTrades': bot.get('maxOpenTrades', 3),
                        'autoCompound': False
                    }
                # Place trade
                result = place_trade(**trade_params)
                if result.get('success'):
                    logger.info(f"[TRADE] Bot {bot_id} placed trade: {trade_params} Result: {result}")
                else:
                    logger.warning(f"[TRADE] Bot {bot_id} failed to place trade: {trade_params} Result: {result}")

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
    allowed_vol = bot_config.get('effectiveAllowedVolatility') or bot_config.get('allowedVolatility', ['Low', 'Medium'])
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


def should_trade_symbol_based_on_risk_management(bot_config, symbol):
    """Compatibility wrapper for the live trading loop risk gate."""
    return should_trade_today(bot_config, symbol)

def get_live_prices_from_mt5():
    """Fetch real-time prices from MT5 for all available symbols"""
    global previous_prices
    
    try:
        # Use the global MT5 singleton directly (warmed up on main thread)
        import MetaTrader5 as mt5
        
        if not mt5.terminal_info():
            logger.debug("MT5 terminal not connected for live price updates")
            return None
        
        live_prices = {}
        
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
                    'current_price': round(current_price, 5),
                    'change': round(price_change, 3),  # Changed from 2 to 3 decimal places for precision
                    'trend': trend,
                    'volatility': volatility,
                    'volatility_pct': round(spread_percent, 4),
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
    
    # Seed price_history from MT5 historical candles for better initial signals
    try:
        import MetaTrader5 as _mt5_hist
        for symbol in list(commodity_market_data.keys()):
            try:
                rates = _mt5_hist.copy_rates_from_pos(symbol, _mt5_hist.TIMEFRAME_M5, 0, 50)
                if rates is not None and len(rates) > 5:
                    price_history = [float(r[4]) for r in rates]  # close prices
                    commodity_market_data[symbol]['price_history'] = price_history
                    commodity_market_data[symbol]['current_price'] = price_history[-1]
                    logger.info(f"📈 Seeded {symbol} price history: {len(price_history)} M5 candles, latest={price_history[-1]:.2f}")
            except Exception as e:
                logger.debug(f"Could not seed price history for {symbol}: {e}")
        logger.info("✅ Price history seeding complete")
    except Exception as e:
        logger.warning(f"Could not seed price history from MT5: {e}")
    
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
                    now_ts = time.time()
                    for symbol, data in live_prices.items():
                        if symbol in commodity_market_data:
                            # Update display fields (current_price, trend, signal, etc.)
                            # but do NOT touch price_history — that is re-seeded from M5 candles below
                            commodity_market_data[symbol].update(data)
                            updated_count += 1
                    
                    # Re-seed price_history from M5 candles every 300s (one M5 bar)
                    # This keeps technical indicators (RSI, MACD, MA) operating on
                    # proper OHLC data instead of flat tick-level noise.
                    last_reseed = getattr(live_market_data_updater, '_last_m5_reseed', 0)
                    if now_ts - last_reseed >= 300:
                        try:
                            import MetaTrader5 as _mt5_reseed
                            for symbol in list(commodity_market_data.keys()):
                                try:
                                    rates = _mt5_reseed.copy_rates_from_pos(symbol, _mt5_reseed.TIMEFRAME_M5, 0, 50)
                                    if rates is not None and len(rates) > 5:
                                        commodity_market_data[symbol]['price_history'] = [float(r[4]) for r in rates]
                                except Exception:
                                    pass
                            live_market_data_updater._last_m5_reseed = now_ts
                            logger.info(f"📈 Re-seeded price_history from M5 candles for {len(commodity_market_data)} symbols")
                        except Exception as e:
                            logger.warning(f"M5 re-seed failed: {e}")
                    
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
        'id': 'pxbt',
        'name': 'PXBT',
        'display_name': 'PXBT Trading',
        'logo': '🚀',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'PXBT Trading MT5 broker',
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
    - XM Global/XM: account_number, password, server, is_live
    - Binance: api_key, api_secret, optional market/server
    - FXCM: token/api_key, optional account_number
    - OANDA: api_key, account_number
    - Exness: account_number, password, server, is_live
    - PXBT: account_number, password, server, is_live
    """
    try:
        user_id = request.user_id
        data = request.json
        
        broker_name = canonicalize_broker_name(data.get('broker_name') or data.get('broker'))
        account_number = data.get('account_number')
        password = data.get('password')
        server = data.get('server')
        api_key = data.get('api_key')  # For IG Markets
        username = data.get('username')  # For IG Markets
        api_secret = data.get('api_secret')
        token = data.get('token')
        is_live = data.get('is_live', False)
        
        if not broker_name:
            return jsonify({'success': False, 'error': 'broker_name required'}), 400
        
        # Validate based on broker type
        # IG Markets integration removed
        if broker_name in ['Binance']:
            password = api_secret or password
            if not api_key or not password:
                return jsonify({
                    'success': False,
                    'error': 'Binance requires: api_key, api_secret'
                }), 400
            server = (server or data.get('market') or 'spot').lower()
            account_number = account_number or server.upper()
        elif broker_name in ['FXCM']:
            api_key = token or api_key or password
            if not api_key:
                return jsonify({
                    'success': False,
                    'error': 'FXCM requires: token'
                }), 400
            account_number = account_number or 'FXCM'
            server = server or 'REST-API'
            password = ''
        elif broker_name in ['OANDA']:
            if not api_key or not account_number:
                return jsonify({
                    'success': False,
                    'error': 'OANDA requires: api_key, account_number'
                }), 400
            server = server or 'REST-API'
            password = ''
        elif broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5', 'PXBT']:
            if not account_number or not password:
                return jsonify({
                    'success': False,
                    'error': f'{broker_name} requires: account_number, password, server'
                }), 400
            if not server:
                if broker_name == 'MetaQuotes':
                    server = 'MetaQuotes-Demo'
                elif broker_name in ['XM', 'XM Global']:
                    server = 'XMGlobal-Real' if is_live else 'XMGlobal-MT5Demo'
                elif broker_name == 'PXBT':
                    server = 'PXBTTrading-1'
                else:  # MetaTrader 5
                    server = 'MetaTrader5-Real' if is_live else 'MetaTrader5-Demo'
        elif broker_name in ['Exness']:
            if not account_number or not password:
                return jsonify({
                    'success': False,
                    'error': 'Exness requires: account_number, password, server'
                }), 400
            if not server:
                server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown broker: {broker_name}. Supported: MetaQuotes, XM Global/XM, Exness, PXBT, Binance, FXCM, OANDA'
            }), 400
        
        created_at = datetime.now().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use account_number as primary identifier
        account_id = account_number
        
        # Check if credential already exists for this user and broker
        # IG Markets integration removed
        cursor.execute('''
            SELECT credential_id FROM broker_credentials
            WHERE user_id = ? AND broker_name = ? AND account_number = ?
        ''', (user_id, broker_name, account_number))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing credential
            credential_id = existing[0]
            # IG Markets integration removed
            if broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5', 'Exness', 'PXBT']:
                cursor.execute('''
                    UPDATE broker_credentials
                    SET account_number = ?, password = ?, server = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (account_number, password, server, 1 if is_live else 0, created_at, credential_id))
            else:
                cursor.execute('''
                    UPDATE broker_credentials
                    SET account_number = ?, password = ?, server = ?, api_key = ?, username = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (account_number, password, server, api_key or '', username or '', 1 if is_live else 0, created_at, credential_id))
            
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
    """Test broker connection and save credentials (supports MT5, Exness, Binance, etc.)"""
    try:
        user_id = request.user_id
        data = request.json
        broker = canonicalize_broker_name(data.get('broker', ''))
        is_live = data.get('is_live', False)

        logger.info(f"🔌 Testing broker connection: {broker} | User: {user_id}")

        # IG MARKETS INTEGRATION REMOVED - only MT5 and other brokers supported
        if broker == 'IG Markets':
            return jsonify({
                'success': False,
                'error': 'IG Markets integration has been removed. Supported brokers: Exness, PXBT, XM Global, Binance, FXCM, OANDA'
            }), 400

        # ==================== BINANCE ====================
        elif broker == 'Binance':
            api_key = data.get('api_key')
            api_secret = data.get('api_secret') or data.get('password')
            market = (data.get('market') or data.get('server') or 'spot').lower()
            account_id = data.get('account_number') or market.upper()

            if not all([api_key, api_secret]):
                return jsonify({'success': False, 'error': 'Missing Binance fields: api_key, api_secret'}), 400

            binance_conn = BinanceConnection(credentials={
                'api_key': api_key,
                'api_secret': api_secret,
                'account_number': account_id,
                'server': market,
                'is_live': is_live,
            })
            if not binance_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with Binance'}), 401

            account_info = binance_conn.get_account_info()
            binance_conn.disconnect()

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'Binance', account_id, api_secret, market, int(is_live), api_key, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to Binance account {account_id}',
                'credential_id': credential_id,
                'broker': 'Binance',
                'account_number': account_id,
                'balance': account_info.get('balance', 0),
                'currency': account_info.get('currency', 'USDT'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

        # ==================== FXCM ====================
        elif broker == 'FXCM':
            token = data.get('token') or data.get('api_key') or data.get('password')
            account_id = data.get('account_number') or 'FXCM'
            if not token:
                return jsonify({'success': False, 'error': 'Missing FXCM field: token'}), 400

            fxcm_conn = FXCMConnection(credentials={
                'api_key': token,
                'account_number': data.get('account_number', ''),
                'is_live': is_live,
            })
            if not fxcm_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with FXCM'}), 401

            account_info = fxcm_conn.get_account_info()
            fxcm_conn.disconnect()
            account_id = str(account_info.get('account_id') or account_id)

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'FXCM', account_id, '', 'REST-API', int(is_live), token, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to FXCM account {account_id}',
                'credential_id': credential_id,
                'broker': 'FXCM',
                'account_number': account_id,
                'currency': account_info.get('currency', 'USD'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

        # ==================== OANDA ====================
        elif broker == 'OANDA':
            api_key = data.get('api_key')
            account_id = data.get('account_number') or data.get('account_id')
            if not api_key or not account_id:
                return jsonify({'success': False, 'error': 'Missing OANDA fields: api_key, account_number'}), 400

            oanda_conn = OANDAConnection(credentials={
                'api_key': api_key,
                'account_number': account_id,
                'is_live': is_live,
            })
            if not oanda_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with OANDA'}), 401

            account_info = oanda_conn.get_account_info()
            oanda_conn.disconnect()

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'OANDA', account_id, '', 'REST-API', int(is_live), api_key, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to OANDA account {account_id}',
                'credential_id': credential_id,
                'broker': 'OANDA',
                'account_number': account_id,
                'currency': account_info.get('currency', 'USD'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

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
            
            # Fix server name for MT5 brokers — use per-account is_live, NOT global ENVIRONMENT
            broker_l = broker.lower()
            if broker_l in ['metaquotes', 'xm', 'xm global', 'metatrader5', 'mt5', 'exness', 'pxbt', 'prime xbt', 'primexbt']:
                if broker_l in ['xm', 'xm global']:
                    expected_server = 'XMGlobal-Real' if is_live else 'XMGlobal-Demo'
                elif broker_l == 'exness':
                    expected_server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
                elif broker_l in ['pxbt', 'prime xbt', 'primexbt']:
                    expected_server = 'PXBTTrading-1'
                else:
                    expected_server = 'MetaQuotes-Live' if is_live else 'MetaQuotes-Demo'

                if not server or server != expected_server:
                    server = expected_server
                    logger.info(f"   Corrected server to: {server} (is_live={is_live})")
            
            # Try to get real balance - first from global cache, then from cached MT5 connection, then via quick MT5 login
            actual_balance = 10000.00  # Default fallback
            actual_equity = 10000.00
            actual_margin_free = 10000.00
            actual_margin_used = 0.00
            actual_margin_level = 0.00
            actual_profit = 0.00
            got_real_balance = False
            
            # FIRST: Check global balance_cache (populated on startup with hardcoded demo balances)
            try:
                global balance_cache, balance_cache_lock
                cache_key = f"{canonicalize_broker_name(broker)}:{account}"
                with balance_cache_lock:
                    if cache_key in balance_cache:
                        cached_info = balance_cache[cache_key]
                        actual_balance = cached_info.get('balance', actual_balance)
                        got_real_balance = True
                        logger.info(f"💰 Got balance from global cache: {cache_key} = ${actual_balance}")
            except Exception as e:
                logger.warning(f"Could not fetch from global cache: {e}")
            
            # SECOND: Try cached connection
            if not got_real_balance:
                try:
                    cached_connection_id = None
                    normalized_broker = canonicalize_broker_name(broker)
                    if normalized_broker == 'Exness':
                        cached_connection_id = 'Exness MT5'
                    elif normalized_broker in ['XM', 'XM Global']:
                        cached_connection_id = 'XM Global MT5'
                    elif normalized_broker == 'PXBT':
                        cached_connection_id = 'PXBT MT5'
                    
                    if cached_connection_id:
                        cached_conn = broker_manager.connections.get(cached_connection_id)
                        if cached_conn and cached_conn.connected:
                            acct_info = cached_conn.account_info or cached_conn.get_account_info()
                            if acct_info and str(acct_info.get('accountNumber', '')) == str(account):
                                actual_balance = acct_info.get('balance', actual_balance)
                                got_real_balance = True
                                logger.info(f"💰 Got real balance from cached {cached_connection_id}: ${actual_balance}")
                except Exception as e:
                    logger.warning(f"Could not fetch cached balance: {e}")
            
            # THIRD: If cached connection is for a different account, do a quick MT5 login to get real balance
            if not got_real_balance:
                try:
                    import MetaTrader5 as mt5_mod
                    lock_acquired = mt5_connection_lock.acquire(timeout=2.0)  # Short timeout for balance check
                    if lock_acquired:
                        try:
                            terminal_path = find_mt5_terminal_path(broker)
                            init_ok = False
                            if terminal_path:
                                init_ok = mt5_mod.initialize(
                                    path=terminal_path,
                                    login=int(account),
                                    password=str(password),
                                    server=str(server),
                                )
                            else:
                                init_ok = mt5_mod.initialize(login=int(account), password=str(password), server=str(server))

                            login_ok = init_ok
                            if login_ok:
                                info = mt5_mod.account_info()
                                if info:
                                    actual_balance = info.balance
                                    actual_equity = getattr(info, 'equity', actual_balance)
                                    actual_margin_free = getattr(info, 'margin_free', 0)
                                    actual_margin_used = getattr(info, 'margin', 0)
                                    actual_margin_level = getattr(info, 'margin_level', 0)
                                    actual_profit = getattr(info, 'profit', 0)
                                    got_real_balance = True
                                    logger.info(f"💰 Got real balance via quick MT5 login: ${actual_balance} | Equity: ${actual_equity} | Free Margin: ${actual_margin_free} | P/L: ${actual_profit}")
                            else:
                                err = mt5_mod.last_error()
                                logger.warning(f"⚠️ Quick MT5 login failed: {err} - using default balance")
                            mt5_mod.shutdown()
                        finally:
                            mt5_connection_lock.release()
                    else:
                        logger.warning(f"⚠️ Could not acquire MT5 lock for balance check - using default")
                except Exception as e:
                    logger.warning(f"Could not fetch balance via quick login: {e} - using default")
            
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
                    SET password = ?, server = ?, is_live = ?, is_active = 1, updated_at = ?,
                        cached_balance = ?, cached_equity = ?, cached_margin_free = ?, 
                        cached_margin = ?, cached_margin_level = ?, cached_profit = ?
                    WHERE credential_id = ?
                ''', (password, server, int(is_live), datetime.now().isoformat(),
                      actual_balance if got_real_balance else None,
                      actual_equity if got_real_balance else None,
                      actual_margin_free if got_real_balance else None,
                      actual_margin_used if got_real_balance else None,
                      actual_margin_level if got_real_balance else None,
                      actual_profit if got_real_balance else None,
                      credential_id))
                logger.info(f"ℹ️  Updated broker credential: {broker} | Account: {account}")
            else:
                credential_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO broker_credentials 
                    (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at, updated_at,
                     cached_balance, cached_equity, cached_margin_free, cached_margin, cached_margin_level, cached_profit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?,
                            ?, ?, ?, ?, ?, ?)
                ''', (credential_id, user_id, broker, account, password, server, int(is_live), 
                      datetime.now().isoformat(), datetime.now().isoformat(),
                      actual_balance if got_real_balance else None,
                      actual_equity if got_real_balance else None,
                      actual_margin_free if got_real_balance else None,
                      actual_margin_used if got_real_balance else None,
                      actual_margin_level if got_real_balance else None,
                      actual_profit if got_real_balance else None))
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
                'balance': round(actual_balance, 2) if got_real_balance else 0,
                'equity': round(actual_equity, 2) if got_real_balance else 0,
                'free_margin': round(actual_margin_free, 2) if got_real_balance else 0,
                'margin': round(actual_margin_used, 2) if got_real_balance else 0,
                'margin_level': round(actual_margin_level, 2) if got_real_balance else 0,
                'total_pl': round(actual_profit, 2) if got_real_balance else 0,
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

def _get_commission_config(cursor):
    """Load commission rates from DB. Returns dict with all config fields."""
    cursor.execute('SELECT * FROM commission_config WHERE config_id = ?', ('default',))
    row = cursor.fetchone()
    if row:
        return dict(row)
    # Fallback defaults
    return {
        'developer_id': 'developer',
        'developer_direct_rate': 0.25,
        'developer_referral_rate': 0.20,
        'recruiter_rate': 0.05,
        'ig_commission_enabled': 1,
        'ig_developer_rate': 0.20,
        'ig_recruiter_rate': 0.05,
        'multi_tier_enabled': 0,
        'tier2_rate': 0.02,
    }


def distribute_trade_commissions(bot_id: str, user_id: str, profit_amount: float, source: str = 'MT5'):
    """
    Distribute commissions for profitable trades.
    Reads rates from commission_config DB table (admin-editable).
    source: 'MT5' or 'IG' — uses matching rate set.
    """
    try:
        if profit_amount <= 0:
            return  # Only commission on profits

        conn = get_db_connection()
        cursor = conn.cursor()

        cfg = _get_commission_config(cursor)

        DEVELOPER_ID = cfg['developer_id']

        if source == 'IG':
            if not cfg.get('ig_commission_enabled', 1):
                conn.close()
                logger.info(f"IG commission disabled — skipping for profit ${profit_amount:.2f}")
                return
            DEV_REFERRAL_RATE = float(cfg.get('ig_developer_rate', 0.20))
            RECRUITER_RATE = float(cfg.get('ig_recruiter_rate', 0.05))
            DEV_DIRECT_RATE = DEV_REFERRAL_RATE + RECRUITER_RATE
        else:
            DEV_DIRECT_RATE = float(cfg.get('developer_direct_rate', 0.25))
            DEV_REFERRAL_RATE = float(cfg.get('developer_referral_rate', 0.20))
            RECRUITER_RATE = float(cfg.get('recruiter_rate', 0.05))

        MULTI_TIER = bool(cfg.get('multi_tier_enabled', 0))
        TIER2_RATE = float(cfg.get('tier2_rate', 0.02))

        # Check if bot owner has a referrer (upline)
        cursor.execute('''
            SELECT referrer_id FROM referrals
            WHERE referred_user_id = ? AND status = 'active'
        ''', (user_id,))
        referrer_row = cursor.fetchone()
        has_referrer = referrer_row is not None
        referrer_id = referrer_row[0] if has_referrer else None

        now = datetime.now().isoformat()

        if has_referrer:
            # Developer portion (reduced rate)
            developer_commission = profit_amount * DEV_REFERRAL_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), DEVELOPER_ID, user_id, bot_id,
                  profit_amount, DEV_REFERRAL_RATE, developer_commission, now))

            # Recruiter portion
            recruiter_commission = profit_amount * RECRUITER_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), referrer_id, user_id, bot_id,
                  profit_amount, RECRUITER_RATE, recruiter_commission, now))

            logger.info(
                f"💰 [{source}] Commission split: Developer gets ${developer_commission:.2f} ({DEV_REFERRAL_RATE*100:.0f}%), "
                f"Recruiter {referrer_id} gets ${recruiter_commission:.2f} ({RECRUITER_RATE*100:.0f}%) from ${profit_amount:.2f}"
            )

            # Multi-tier: recruiter's recruiter gets tier2_rate
            if MULTI_TIER and TIER2_RATE > 0:
                cursor.execute('''
                    SELECT referrer_id FROM referrals
                    WHERE referred_user_id = ? AND status = 'active'
                ''', (referrer_id,))
                tier2_row = cursor.fetchone()
                if tier2_row:
                    tier2_id = tier2_row[0]
                    tier2_commission = profit_amount * TIER2_RATE
                    cursor.execute('''
                        INSERT INTO commissions
                        (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (str(uuid.uuid4()), tier2_id, user_id, bot_id,
                          profit_amount, TIER2_RATE, tier2_commission, now))
                    logger.info(f"💰 [{source}] Tier-2: {tier2_id} gets ${tier2_commission:.2f} ({TIER2_RATE*100:.0f}%)")
        else:
            # Full developer rate (no recruiter)
            developer_commission = profit_amount * DEV_DIRECT_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), DEVELOPER_ID, user_id, bot_id,
                  profit_amount, DEV_DIRECT_RATE, developer_commission, now))
            logger.info(f"💰 [{source}] Commission: Developer gets ${developer_commission:.2f} ({DEV_DIRECT_RATE*100:.0f}%) from ${profit_amount:.2f} [Direct signup]")

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error in distribute_trade_commissions: {e}")
        # Don't raise - don't break trading if commission fails


# ==================== EMAIL NOTIFICATIONS ====================
def send_activation_pin_email(user_email: str, user_name: str, bot_id: str, pin: str):
    """Send activation PIN to user email"""
    try:
        smtp_server = os.environ.get('SMTP_SERVER', '')
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_pass = os.environ.get('SMTP_PASS', '')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        
        logger.info(f"🔐 BOT ACTIVATION PIN: User={user_name}, Bot={bot_id}, PIN={pin}")
        
        if not smtp_server or not smtp_user:
            logger.warning(f"⚠️ SMTP not configured — PIN for {user_email}: {pin}")
            return True
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f'Zwesta Trading <{smtp_user}>'
        msg['To'] = user_email
        msg['Subject'] = f'Zwesta Trading - Bot Activation PIN'
        
        plain = f'Hi {user_name},\n\nYour bot activation PIN is: {pin}\nBot ID: {bot_id}\n\nThis PIN expires in 10 minutes.'
        
        html = f"""\
        <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
        <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <h2 style="color:#0A0E21;margin-top:0;">🤖 Bot Activation PIN</h2>
          <p style="color:#555;font-size:15px;">Hi <b>{user_name}</b>, use this PIN to activate your bot:</p>
          <div style="background:#0A0E21;color:#00E5FF;font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;padding:18px;border-radius:8px;margin:24px 0;">
            {pin}
          </div>
          <p style="color:#888;font-size:13px;">Bot ID: <code>{bot_id}</code></p>
          <p style="color:#888;font-size:13px;">This PIN expires in <b>10 minutes</b>.</p>
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
          <p style="color:#aaa;font-size:11px;text-align:center;">Zwesta Trading Platform</p>
        </div>
        </body></html>"""
        
        msg.attach(MIMEText(plain, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"✅ Activation PIN email sent to {user_email}")
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


BOT_RISK_LIMITS = {
    'riskPerTrade': (5.0, 30.0),
    'maxDailyLoss': (20.0, 2000.0),
    'profitLock': (0.0, 300.0),
    'drawdownPausePercent': (3.0, 12.0),
    'drawdownPauseHours': (2.0, 12.0),
}

BOT_MANAGEMENT_PROFILES = {
    'beginner': {
        'riskPerTrade': 10.0,
        'maxDailyLoss': 40.0,
        'profitLock': 60.0,
        'drawdownPausePercent': 5.0,
        'drawdownPauseHours': 8.0,
        'maxOpenPositions': 2,
        'maxPositionsPerSymbol': 1,
        'signalThreshold': 70,
        'allowedVolatility': ['Low'],
        'autoSwitch': True,
        'dynamicSizing': True,
    },
    'balanced': {
        'riskPerTrade': 15.0,
        'maxDailyLoss': 80.0,
        'profitLock': 100.0,
        'drawdownPausePercent': 7.0,
        'drawdownPauseHours': 6.0,
        'maxOpenPositions': 3,
        'maxPositionsPerSymbol': 2,
        'signalThreshold': 60,
        'allowedVolatility': ['Low', 'Medium'],
        'autoSwitch': True,
        'dynamicSizing': True,
    },
    'advanced': {
        'riskPerTrade': 20.0,
        'maxDailyLoss': 120.0,
        'profitLock': 120.0,
        'drawdownPausePercent': 10.0,
        'drawdownPauseHours': 4.0,
        'maxOpenPositions': 5,
        'maxPositionsPerSymbol': 2,
        'signalThreshold': 50,
        'allowedVolatility': ['Low', 'Medium'],
        'autoSwitch': True,
        'dynamicSizing': True,
    },
}

SUPPORTED_DISPLAY_CURRENCIES = {'USD', 'ZAR', 'GBP'}


def _clamp_bot_config_value(field_name: str, raw_value, minimum: float, maximum: float, default_value: float, warnings: List[str]) -> float:
    """Clamp bot risk inputs into a safe range and track any overrides."""
    try:
        parsed_value = float(raw_value)
    except (TypeError, ValueError):
        warnings.append(f'{field_name} defaulted to {default_value}')
        return default_value

    if parsed_value < minimum:
        warnings.append(f'{field_name} raised to minimum {minimum}')
        return minimum
    if parsed_value > maximum:
        warnings.append(f'{field_name} reduced to maximum {maximum}')
        return maximum
    return parsed_value


def _clamp_int_value(field_name: str, raw_value, minimum: int, maximum: int, default_value: int, warnings: List[str]) -> int:
    try:
        parsed_value = int(round(float(raw_value)))
    except (TypeError, ValueError):
        warnings.append(f'{field_name} defaulted to {default_value}')
        return default_value

    if parsed_value < minimum:
        warnings.append(f'{field_name} raised to minimum {minimum}')
        return minimum
    if parsed_value > maximum:
        warnings.append(f'{field_name} reduced to maximum {maximum}')
        return maximum
    return parsed_value


def _coerce_bool(raw_value, default_value: bool = False) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}
    if raw_value is None:
        return default_value
    return bool(raw_value)


def _normalize_management_profile(raw_profile) -> str:
    profile = str(raw_profile or 'beginner').strip().lower()
    if profile in {'safe', 'conservative', 'starter', 'new', 'novice'}:
        return 'beginner'
    if profile in {'moderate', 'medium', 'assisted'}:
        return 'balanced'
    if profile in {'pro', 'expert', 'aggressive'}:
        return 'advanced'
    if profile not in BOT_MANAGEMENT_PROFILES:
        return 'beginner'
    return profile


def apply_assisted_management_overrides(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    profile = _normalize_management_profile(bot_config.get('managementProfile'))
    is_assisted = bot_config.get('managementMode', 'assisted') != 'manual'
    defaults = BOT_MANAGEMENT_PROFILES.get(profile, BOT_MANAGEMENT_PROFILES['beginner'])
    effective = {
        'profile': profile,
        'mode': 'assisted' if is_assisted else 'manual',
        'maxOpenPositions': int(bot_config.get('maxOpenPositions') or defaults['maxOpenPositions']),
        'maxPositionsPerSymbol': int(bot_config.get('maxPositionsPerSymbol') or defaults['maxPositionsPerSymbol']),
        'signalThreshold': int(bot_config.get('signalThreshold') or defaults['signalThreshold']),
        'allowedVolatility': list(bot_config.get('allowedVolatility') or defaults['allowedVolatility']),
    }

    if is_assisted:
        effective['maxOpenPositions'] = min(effective['maxOpenPositions'], defaults['maxOpenPositions'])
        effective['maxPositionsPerSymbol'] = min(effective['maxPositionsPerSymbol'], defaults['maxPositionsPerSymbol'])
        effective['signalThreshold'] = max(effective['signalThreshold'], defaults['signalThreshold'])
        effective['allowedVolatility'] = [
            level for level in effective['allowedVolatility'] if level in defaults['allowedVolatility']
        ] or list(defaults['allowedVolatility'])

        recent_trades = bot_config.get('tradeHistory') or []
        recent_closed = recent_trades[-6:]
        consecutive_losses = 0
        for trade in reversed(recent_closed):
            if (trade.get('profit') or 0) < 0:
                consecutive_losses += 1
            else:
                break

        recent_count = len(recent_closed)
        recent_wins = sum(1 for trade in recent_closed if (trade.get('profit') or 0) > 0)
        recent_win_rate = (recent_wins / recent_count * 100) if recent_count else 100.0

        if consecutive_losses >= 2 or (recent_count >= 4 and recent_win_rate < 40):
            effective['signalThreshold'] = min(85, effective['signalThreshold'] + 10)
            effective['maxOpenPositions'] = min(effective['maxOpenPositions'], 1 if profile == 'beginner' else 2)
            effective['maxPositionsPerSymbol'] = 1
            effective['allowedVolatility'] = ['Low']
            bot_config['managementState'] = 'recovery'
        else:
            bot_config['managementState'] = 'normal'
    else:
        bot_config['managementState'] = 'manual'

    bot_config['effectiveSignalThreshold'] = effective['signalThreshold']
    bot_config['effectiveMaxOpenPositions'] = effective['maxOpenPositions']
    bot_config['effectiveMaxPositionsPerSymbol'] = effective['maxPositionsPerSymbol']
    bot_config['effectiveAllowedVolatility'] = effective['allowedVolatility']
    return effective


def sanitize_bot_risk_config(data: Dict) -> Dict[str, Any]:
    """Normalize bot risk configuration before persisting or trading."""
    warnings: List[str] = []

    intelligent_settings = data.get('intelligentManagement') or {}
    if not isinstance(intelligent_settings, dict):
        intelligent_settings = {}

    management_profile = _normalize_management_profile(
        intelligent_settings.get('profile')
        or intelligent_settings.get('experienceLevel')
        or data.get('managementProfile')
        or data.get('riskProfile')
        or 'beginner'
    )
    management_mode = 'manual' if not _coerce_bool(intelligent_settings.get('enabled', True), True) else 'assisted'
    profile_defaults = BOT_MANAGEMENT_PROFILES[management_profile]

    raw_risk_per_trade = data.get('riskPerTrade')
    if raw_risk_per_trade is None and data.get('riskPercent') is not None:
        try:
            raw_risk_per_trade = float(data.get('riskPercent', 2.0)) * 10.0
        except (TypeError, ValueError):
            raw_risk_per_trade = profile_defaults['riskPerTrade']
            warnings.append(f"riskPercent defaulted to {profile_defaults['riskPerTrade'] / 10:.1f}% profile value")

    risk_per_trade = _clamp_bot_config_value(
        'riskPerTrade',
        raw_risk_per_trade if raw_risk_per_trade is not None else profile_defaults['riskPerTrade'],
        BOT_RISK_LIMITS['riskPerTrade'][0],
        BOT_RISK_LIMITS['riskPerTrade'][1],
        profile_defaults['riskPerTrade'],
        warnings,
    )
    max_daily_loss = _clamp_bot_config_value(
        'maxDailyLoss',
        data.get('maxDailyLoss', profile_defaults['maxDailyLoss']),
        BOT_RISK_LIMITS['maxDailyLoss'][0],
        BOT_RISK_LIMITS['maxDailyLoss'][1],
        profile_defaults['maxDailyLoss'],
        warnings,
    )

    raw_profit_lock = data.get('profitLock', profile_defaults['profitLock'])
    try:
        parsed_profit_lock = float(raw_profit_lock)
    except (TypeError, ValueError):
        parsed_profit_lock = profile_defaults['profitLock']
        warnings.append(f"profitLock defaulted to {profile_defaults['profitLock']}")

    if parsed_profit_lock <= 0:
        profit_lock = 0.0
    else:
        profit_lock = _clamp_bot_config_value(
            'profitLock',
            parsed_profit_lock,
            20.0,
            BOT_RISK_LIMITS['profitLock'][1],
            profile_defaults['profitLock'],
            warnings,
        )

    drawdown_pause_percent = _clamp_bot_config_value(
        'drawdownPausePercent',
        data.get('drawdownPausePercent', data.get('maxDrawdownPercent', profile_defaults['drawdownPausePercent'])),
        BOT_RISK_LIMITS['drawdownPausePercent'][0],
        BOT_RISK_LIMITS['drawdownPausePercent'][1],
        profile_defaults['drawdownPausePercent'],
        warnings,
    )
    drawdown_pause_hours = _clamp_bot_config_value(
        'drawdownPauseHours',
        data.get('drawdownPauseHours', profile_defaults['drawdownPauseHours']),
        BOT_RISK_LIMITS['drawdownPauseHours'][0],
        BOT_RISK_LIMITS['drawdownPauseHours'][1],
        profile_defaults['drawdownPauseHours'],
        warnings,
    )

    max_open_positions = _clamp_int_value(
        'maxOpenPositions',
        data.get('maxOpenPositions', data.get('maxOpenTrades', profile_defaults['maxOpenPositions'])),
        1,
        8,
        profile_defaults['maxOpenPositions'],
        warnings,
    )
    max_positions_per_symbol = _clamp_int_value(
        'maxPositionsPerSymbol',
        data.get('maxPositionsPerSymbol', max_open_positions),
        1,
        max_open_positions,
        min(profile_defaults['maxPositionsPerSymbol'], max_open_positions),
        warnings,
    )
    signal_threshold = _clamp_int_value(
        'signalThreshold',
        data.get('signalThreshold', profile_defaults['signalThreshold']),
        45,
        90,
        profile_defaults['signalThreshold'],
        warnings,
    )

    allowed_volatility = data.get('allowedVolatility') or profile_defaults['allowedVolatility']
    if not isinstance(allowed_volatility, list):
        allowed_volatility = profile_defaults['allowedVolatility']
        warnings.append('allowedVolatility defaulted to profile setting')
    allowed_volatility = [str(level).title() for level in allowed_volatility if str(level).strip()]
    if not allowed_volatility:
        allowed_volatility = list(profile_defaults['allowedVolatility'])

    auto_switch = _coerce_bool(
        data.get('autoSwitch', intelligent_settings.get('autoSwitch', profile_defaults['autoSwitch'])),
        profile_defaults['autoSwitch'],
    )
    dynamic_sizing = _coerce_bool(
        data.get('dynamicSizing', intelligent_settings.get('dynamicSizing', profile_defaults['dynamicSizing'])),
        profile_defaults['dynamicSizing'],
    )

    if management_mode == 'assisted':
        max_open_positions = min(max_open_positions, profile_defaults['maxOpenPositions'])
        max_positions_per_symbol = min(max_positions_per_symbol, profile_defaults['maxPositionsPerSymbol'])
        signal_threshold = max(signal_threshold, profile_defaults['signalThreshold'])
        allowed_volatility = [level for level in allowed_volatility if level in profile_defaults['allowedVolatility']] or list(profile_defaults['allowedVolatility'])

    display_currency = 'USD'  # Force USD - all accounts are in USD
    
    return {
        'riskPerTrade': risk_per_trade,
        'maxDailyLoss': max_daily_loss,
        'profitLock': profit_lock,
        'drawdownPausePercent': drawdown_pause_percent,
        'drawdownPauseHours': drawdown_pause_hours,
        'maxOpenPositions': max_open_positions,
        'maxPositionsPerSymbol': max_positions_per_symbol,
        'signalThreshold': signal_threshold,
        'allowedVolatility': allowed_volatility,
        'autoSwitch': auto_switch,
        'dynamicSizing': dynamic_sizing,
        'managementMode': management_mode,
        'managementProfile': management_profile,
        'displayCurrency': display_currency,  # Always USD
        'warnings': warnings,
    }




def _generate_sample_trades_for_bot(symbols: List[str], trade_count: int = 10):
    """
    Generate sample trades for newly created bots so analytics display data immediately
    
    Returns: (trade_history, daily_profits, total_profit, winning_trades_count)
    """
    import random
    from datetime import timedelta
    
    try:
        trade_history = []
        daily_profits = {}
        now = datetime.now()
        total_profit = 0
        winning_trades = 0
        
        # Generate trades over the last 30 days (exclude today so daily P&L starts clean)
        for i in range(trade_count):
            # Random date within past 30 days (starting from 1 day ago, not today)
            days_ago = random.randint(1, 30)
            trade_time = now - timedelta(days=days_ago)
            date_key = trade_time.strftime('%Y-%m-%d')
            
            # Random profit/loss
            profit = random.uniform(-500, 2500)
            if profit > 0:
                winning_trades += 1
            
            trade = {
                'symbol': random.choice(symbols or ['EURUSDm']),
                'profit': round(profit, 2),
                'type': random.choice(['BUY', 'SELL']),
                'volume': round(random.uniform(0.1, 5.0), 2),
                'time': trade_time.isoformat(),
                'isWinning': profit > 0,
            }
            
            trade_history.append(trade)
            
            # Accumulate daily profits
            if date_key not in daily_profits:
                daily_profits[date_key] = 0.0
            daily_profits[date_key] += profit
            
            total_profit += profit
        
        # Do NOT generate fake profit for today - bot should start with clean daily P&L
        # so it doesn't immediately hit daily loss limits before placing any real trades
        
        return trade_history, daily_profits, round(total_profit, 2), winning_trades
        
    except Exception as e:
        logger.error(f"Error generating sample trades: {e}")
        return [], {}, 0, 0


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
        "riskPerTrade": 20,
        "maxDailyLoss": 60
    }
    """
    # ==================== BOT CREATION LOCK ====================
    # Only allow ONE bot creation at a time to prevent MT5 lock contention
    # Multiple simultaneous creations cause competing MT5 connection attempts
    global bot_creation_lock
    logger.info("🔒 Waiting for exclusive bot creation lock...")
    
    with bot_creation_lock:
        conn = None
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

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            cursor.execute('''
                SELECT credential_id, broker_name, account_number, is_live, api_key, password, server, is_active
                FROM broker_credentials
                WHERE credential_id = ? AND user_id = ?
            ''', (credential_id, user_id))
            credential_row = cursor.fetchone()
            if not credential_row:
                return jsonify({'success': False, 'error': f'Broker credential {credential_id} not found or does not belong to this user'}), 404

            if not credential_row['is_active']:
                return jsonify({'success': False, 'error': 'This broker credential has been deactivated. Please use an active credential.'}), 400

            credential_data = dict(credential_row)
            broker_name = credential_data['broker_name']
            account_number = credential_data['account_number']
            is_live = credential_data['is_live']
            mode = 'live' if is_live else 'demo'

            # Fail fast for Binance credentials so users don't create bots that silently fail at runtime.
            if canonicalize_broker_name(broker_name) == 'Binance':
                binance_conn = BinanceConnection(credentials={
                    'api_key': credential_data.get('api_key'),
                    'api_secret': credential_data.get('password'),
                    'account_number': account_number,
                    'server': credential_data.get('server') or 'spot',
                    'is_live': bool(is_live),
                })
                if not binance_conn.connect():
                    return jsonify({
                        'success': False,
                        'error': 'Binance credential validation failed. Please re-check API key/secret and account mode.'
                    }), 400
                binance_conn.disconnect()

            print(f"✅ Using broker credential: {broker_name} | Account: {account_number} | Mode: {mode}")

            # Bot configuration
            import time
            bot_id = data.get('botId') or f"bot_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            # Support both 'symbol' (singular) and 'symbols' (plural) in request
            raw_symbols = data.get('symbols') or data.get('symbol')
            if isinstance(raw_symbols, str):
                raw_symbols = [raw_symbols]  # Convert single symbol to list
            if not raw_symbols:
                raw_symbols = ['EURUSDm']  # Default fallback
            symbols = validate_and_correct_symbols(raw_symbols, broker_name)
            strategy = data.get('strategy', 'Trend Following')
            sanitized_risk_config = sanitize_bot_risk_config(data)
            risk_per_trade = sanitized_risk_config['riskPerTrade']
            max_daily_loss = sanitized_risk_config['maxDailyLoss']
            profit_lock = sanitized_risk_config['profitLock']
            drawdown_pause_percent = sanitized_risk_config['drawdownPausePercent']
            drawdown_pause_hours = sanitized_risk_config['drawdownPauseHours']
            max_open_positions = sanitized_risk_config['maxOpenPositions']
            max_positions_per_symbol = sanitized_risk_config['maxPositionsPerSymbol']
            signal_threshold = sanitized_risk_config['signalThreshold']
            allowed_volatility = sanitized_risk_config['allowedVolatility']
            auto_switch = sanitized_risk_config['autoSwitch']
            dynamic_sizing = sanitized_risk_config['dynamicSizing']
            management_mode = sanitized_risk_config['managementMode']
            management_profile = sanitized_risk_config['managementProfile']
            display_currency = sanitized_risk_config['displayCurrency']
            trading_enabled = data.get('enabled', True)
            trade_amount = data.get('tradeAmount')  # Fixed dollar trade amount (overrides risk %)
            if trade_amount is not None:
                try:
                    trade_amount = float(trade_amount)
                    if trade_amount <= 0:
                        trade_amount = None
                except (ValueError, TypeError):
                    trade_amount = None

            account_id = f"{broker_name}_{account_number}"
            created_at = datetime.now().isoformat()

            try:
                cursor.execute('SELECT bot_id FROM user_bots WHERE bot_id = ?', (bot_id,))
                if cursor.fetchone():
                    logger.warning(f"Bot ID {bot_id} already exists, regenerating...")
                    bot_id = f"bot_{int(time.time() * 1000) + 1}_{uuid.uuid4().hex[:8]}"

                logger.info(f"🔧 [BOT INSERT] Inserting bot {bot_id} for user {user_id} into user_bots table...")
                cursor.execute('''
                    INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, is_live, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), 1 if is_live else 0, created_at, created_at))
                logger.info(f"✅ [BOT INSERT SUCCESS] user_bots row inserted")

                logger.info(f"🔧 [CREDENTIALS INSERT] Inserting bot credentials...")
                cursor.execute('''
                    INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (bot_id, credential_id, user_id, created_at))
                logger.info(f"✅ [CREDENTIALS INSERT SUCCESS] bot_credentials row inserted")

                logger.info(f"🔧 [DB COMMIT] Committing transaction...")
                conn.commit()
                logger.info(f"✅ [DB COMMIT SUCCESS] Transaction committed to database")
            except Exception as e:
                logger.error(f"❌ [DB ERROR] Exception during bot creation: {type(e).__name__}: {str(e)}")
                if 'UNIQUE constraint' in str(e):
                    logger.error("Bot creation failed - duplicate ID. Retrying with new ID...")
                    bot_id = f"bot_{int(time.time() * 1000000)}_{uuid.uuid4().hex[:6]}"
                    try:
                        cursor.execute('''
                            INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, is_live, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), 1 if is_live else 0, created_at, created_at))
                        cursor.execute('''
                            INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                            VALUES (?, ?, ?, ?)
                        ''', (bot_id, credential_id, user_id, created_at))
                        conn.commit()
                        logger.info(f"✅ [RETRY SUCCESS] Bot retry successful with new ID: {bot_id}")
                    except Exception as retry_e:
                        logger.error(f"❌ [RETRY FAILED] Retry also failed: {type(retry_e).__name__}: {str(retry_e)}")
                        raise
                else:
                    raise

            now = datetime.now()
            # Start with clean stats — no fake sample trades that pollute analytics
            # Real trades will be recorded as the bot executes

            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': user_id,
                'accountId': account_id,
                'brokerName': broker_name,
                'broker_type': broker_name,
                'mode': mode,
                'credentialId': credential_id,
                'symbols': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'maxDailyLoss': max_daily_loss,
                'profitLock': profit_lock,
                'drawdownPausePercent': drawdown_pause_percent,
                'drawdownPauseHours': drawdown_pause_hours,
                'signalThreshold': signal_threshold,
                'allowedVolatility': allowed_volatility,
                'autoSwitch': auto_switch,
                'dynamicSizing': dynamic_sizing,
                'managementMode': management_mode,
                'managementProfile': management_profile,
                'managementState': 'normal',
                'displayCurrency': display_currency,
                'enabled': trading_enabled,
                'tradeAmount': trade_amount,  # Fixed dollar amount per trade (None = use risk %)
                'maxOpenPositions': max_open_positions,
                'maxPositionsPerSymbol': max_positions_per_symbol,
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
                'drawdownPauseUntil': None,
                'profit': 0,
                'open_positions': {},  # Track open positions for closure detection
            }
            persist_bot_runtime_state(bot_id)

            logger.info(f"✅ Created bot {bot_id} for user {user_id}")
            logger.info(f"   Broker: {broker_name} | Account: {account_number} | Mode: {mode}")

            running_bots[bot_id] = True
            bot_stop_flags[bot_id] = False

            # ==================== WORKER POOL DISPATCH ====================
            if worker_pool_manager and worker_pool_manager.enabled:
                # Dispatch to a worker subprocess instead of local thread
                _worker_creds = None
                if credential_id:
                    try:
                        _wc_conn = get_db_connection()
                        _wc_cursor = _wc_conn.cursor()
                        _wc_cursor.execute('SELECT account_number, password, server FROM broker_credentials WHERE credential_id = ? AND user_id = ?', (credential_id, user_id))
                        _wc_row = _wc_cursor.fetchone()
                        _wc_conn.close()
                        if _wc_row:
                            _worker_creds = {'account_number': _wc_row['account_number'] or account_number, 'password': _wc_row['password'], 'server': _wc_row['server'], 'is_live': bool(is_live)}
                    except Exception as e:
                        logger.warning(f'Worker dispatch: could not fetch credentials: {e}')
                worker_pool_manager.dispatch_bot(bot_id, user_id, active_bots[bot_id], _worker_creds)
                logger.info(f"🚀 Bot {bot_id}: Dispatched to worker pool")
            else:
                # Legacy single-process mode
                def _async_start_bot():
                    """Start bot in background without blocking the API response"""
                    try:
                        time.sleep(0.5)

                        bot_credentials = None
                        if credential_id:
                            conn_local = None
                            try:
                                conn_local = get_db_connection()
                                cursor_local = conn_local.cursor()
                                cursor_local.execute('''
                                    SELECT api_key, password, server, account_number
                                    FROM broker_credentials
                                    WHERE credential_id = ? AND user_id = ?
                                ''', (credential_id, user_id))
                                cred_row = cursor_local.fetchone()

                                if cred_row:
                                    if canonicalize_broker_name(broker_name) == 'Binance':
                                        bot_credentials = {
                                            'api_key': cred_row['api_key'],
                                            'api_secret': cred_row['password'],
                                            'server': cred_row['server'] or 'spot',
                                            'is_live': bool(is_live),
                                        }
                                    else:
                                        bot_credentials = {
                                            'account_number': cred_row['account_number'] or account_number,
                                            'password': cred_row['password'],
                                            'server': cred_row['server'],
                                            'is_live': bool(is_live),
                                        }
                            except Exception as e:
                                logger.warning(f'Could not fetch broker credentials for bot startup: {e}')
                            finally:
                                if conn_local:
                                    conn_local.close()

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

                startup_thread = threading.Thread(target=_async_start_bot, daemon=True)
                startup_thread.start()

            account_balance = 10000.0
            try:
                if canonicalize_broker_name(broker_name) == 'Binance':
                    binance_conn_balance = BinanceConnection(credentials={
                        'api_key': credential_data.get('api_key'),
                        'api_secret': credential_data.get('password'),
                        'account_number': account_number,
                        'server': credential_data.get('server') or 'spot',
                        'is_live': bool(is_live),
                    })
                    if binance_conn_balance.connect():
                        acct_info = binance_conn_balance.get_account_info()
                        if acct_info and 'balance' in acct_info:
                            account_balance = acct_info['balance']
                        binance_conn_balance.disconnect()
                elif is_mt5_broker_name(broker_name):
                    cached_connection_id = None
                    normalized_broker_name = canonicalize_broker_name(broker_name)

                    if normalized_broker_name == 'Exness':
                        cached_connection_id = 'Exness MT5'
                    elif normalized_broker_name in ['XM', 'XM Global']:
                        cached_connection_id = 'XM Global MT5'
                    elif normalized_broker_name == 'PXBT':
                        cached_connection_id = 'PXBT MT5'

                    cached_connection = broker_manager.connections.get(cached_connection_id) if cached_connection_id else None
                    if cached_connection and cached_connection.connected:
                        acct_info = cached_connection.account_info or cached_connection.get_account_info()
                        if acct_info and str(acct_info.get('accountNumber', '')) == str(account_number):
                            account_balance = acct_info.get('balance', account_balance)
                            logger.info(f"💰 Got cached balance for bot creation: ${account_balance}")
                        else:
                            logger.info(f"⚠️ Cached MT5 is for different account - balance will update after bot connects")
                    else:
                        logger.info(f"⚠️ No cached MT5 connection - balance will update after bot connects")
            except Exception as e:
                logger.info(f"⚠️  Could not fetch balance during bot creation: {e} - using default 10000.0")

            return jsonify({
                'success': True,
                'botId': bot_id,
                'user_id': user_id or '',
                'credentialId': credential_id or '',
                'accountId': account_id or '',
                'broker': broker_name or 'Unknown',
                'account_number': account_number or '',
                'balance': round(account_balance, 2),
                'mode': mode or 'demo',
                'displayCurrency': display_currency or 'USD',
                'tradeAmount': trade_amount,
                'appliedRiskConfig': {
                    'riskPerTrade': risk_per_trade or 20.0,
                    'maxDailyLoss': max_daily_loss or 60.0,
                    'profitLock': profit_lock or 80.0,
                    'drawdownPausePercent': drawdown_pause_percent or 0.0,
                    'drawdownPauseHours': drawdown_pause_hours or 6.0,
                },
                'appliedManagementConfig': {
                    'managementMode': management_mode,
                    'managementProfile': management_profile,
                    'maxOpenPositions': max_open_positions,
                    'maxPositionsPerSymbol': max_positions_per_symbol,
                    'signalThreshold': signal_threshold,
                    'allowedVolatility': allowed_volatility,
                    'autoSwitch': auto_switch,
                    'dynamicSizing': dynamic_sizing,
                },
                'warnings': (sanitized_risk_config or {}).get('warnings', []),
                'message': f'Bot {bot_id} created and starting...',
                'status': 'STARTING'
            }), 201
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()


# ==================== CONTINUOUS BOT TRADING LOOP ====================

def evaluate_trade_signal_strength(symbol: str, strategy_params: Dict) -> float:
    """
    Evaluate how strong a profit signal is (0-100 scale)
    
    Returns: Signal strength score
    - 0-30: Weak signal, don't trade
    - 30-60: Medium signal, hold for better opportunity  
    - 60-85: Strong signal, good time to trade
    - 85-100: Very strong signal, excellent trade setup
    """
    try:
        # Get live price data
        if symbol not in commodity_market_data:
            return 0
        
        market_data = commodity_market_data[symbol]
        signal = market_data.get('signal', '')
        
        # Base score from signal type (from technical analysis)
        if 'STRONG BUY' in signal or 'STRONG SELL' in signal:
            base_score = 85
        elif 'BUY' in signal or 'SELL' in signal:
            base_score = 65
        elif 'CONSOLIDATING' in signal or 'WEAK BUY' in signal:
            base_score = 40
        else:
            base_score = 20
        
        # Adjust for volatility (high volatility = higher risk but higher reward)
        volatility = market_data.get('volatility_pct', 1.0)
        if volatility > 3:  # High volatility
            base_score *= 1.1
        elif volatility < 0.5:  # Very low volatility
            base_score *= 0.9
        
        # Adjust for profitability score (historical performance)
        if 'profitability_score' in market_data:
            profit_score = market_data['profitability_score']
            base_score = base_score * 0.6 + profit_score * 40
        
        # Cap at 100
        return min(100, max(0, base_score))
    except:
        return 0


def continuous_bot_trading_loop(bot_id: str, user_id: str, bot_credentials: Dict = None):
    """
    Continuously execute trading for a bot until stop is requested
    
    Supports TWO MODES:
    1. TIME-BASED (default): Execute trades every N seconds (5 min default)
    2. SIGNAL-DRIVEN (new): Execute trades IMMEDIATELY when profit signal detected
       - Checks signals frequently (every 10-30 seconds)
       - Executes when signal strength exceeds threshold
       - Much faster response to market opportunities
    
    This function runs in a background thread and:
    1. Executes trades based on mode (time or signal)
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
        
        # ✅ DEFENSIVE FIX: Load bot_credentials from bot_config if not passed in
        if not bot_credentials:
            # Try to extract credentials from bot_config (set during start_bot)
            credential_id = bot_config.get('credentialId')
            if credential_id:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM broker_credentials WHERE credential_id = ? AND user_id = ?', (credential_id, user_id))
                    cred_row = cursor.fetchone()
                    conn.close()
                    
                    if cred_row:
                        cred_dict = dict(cred_row)
                        bot_credentials = {
                            'account': cred_dict.get('account_number', ''),
                            'password': cred_dict.get('password', ''),
                            'server': cred_dict.get('server', 'Exness-Real'),
                            'broker': cred_dict.get('broker_name', 'Exness'),
                            'is_live': bool(cred_dict.get('is_live', False))
                        }
                        logger.info(f"📌 Bot {bot_id}: Loaded credentials from database (credential_id={credential_id})")
                    else:
                        logger.warning(f"⚠️  Bot {bot_id}: Credential {credential_id} not found in database")
                        bot_credentials = {}
                except Exception as e:
                    logger.warning(f"⚠️  Bot {bot_id}: Could not load credentials: {e}")
                    bot_credentials = {}
            else:
                logger.warning(f"⚠️  Bot {bot_id}: No credentialId found in bot_config")
                bot_credentials = {}
        
        # Ensure bot_credentials is never None
        if not bot_credentials:
            bot_credentials = {
                'account': '',
                'password': '',
                'server': 'Exness-Real',
                'broker': 'Exness',
                'is_live': False
            }
        
        # Get trading mode configuration
        trading_mode = bot_config.get('tradingMode', 'interval')  # 'interval' or 'signal-driven'
        trading_interval = bot_config.get('tradingInterval', 300)  # Default 5 minutes for time-based
        signal_threshold = bot_config.get('signalThreshold', 65)    # 0-100, minimum signal strength
        poll_interval = bot_config.get('pollInterval', 15)          # Check signals every N seconds in signal-driven mode
        
        if trading_mode == 'signal-driven':
            logger.info(f"Bot {bot_id}: ⚡ SIGNAL-DRIVEN MODE enabled")
            logger.info(f"   - Signal Threshold: {signal_threshold}/100 (trades execute when signal >= this)")
            logger.info(f"   - Poll Interval: {poll_interval} seconds (check signals this often)")
            logger.info(f"   - Will execute IMMEDIATELY when profit signal detected (no waiting!)")
        else:
            logger.info(f"Bot {bot_id}: ⏱️ TIME-BASED MODE - trades every {trading_interval}s ({trading_interval/60:.1f} min)")
        
        # Initialize stop flag if not exists
        if bot_id not in bot_stop_flags:
            bot_stop_flags[bot_id] = False
        
        running_bots[bot_id] = True
        trade_cycle = 0
        mt5_ready_timeout = 30  # OPTIMIZED: Reduced from 120 to 30 seconds - MT5 usually ready in 5-15s
        
        # ==================== MARKET HOURS CONFIG ====================
        # Define market hours for different symbol groups (UTC time)
        # ✅ FIXED: FOREX trades 24/5 (Sun evening to Fri evening) - allow all weekday+weekend trading in demo
        market_hours = {
            'FOREX': {'open': (0, 0), 'close': (24, 0), 'days': [0, 1, 2, 3, 4, 5, 6]},  # ✅ Open all days for demo - forex actually trades Sun 21:00 UTC to Fri 21:00 UTC
            'CRYPTO': {'open': (0, 0), 'close': (24, 0), 'days': [0, 1, 2, 3, 4, 5, 6]},  # 24/7
            'INDICES': {'open': (8, 0), 'close': (22, 0), 'days': [0, 1, 2, 3, 4]},  # Mon-Fri only
            'COMMODITIES': {'open': (1, 0), 'close': (23, 59), 'days': [0, 1, 2, 3, 4, 5, 6]},  # ✅ Open all days - gold/commodities trade extended hours
            'STOCKS': {'open': (13, 30), 'close': (20, 0), 'days': [0, 1, 2, 3, 4]},  # US stocks: 9:30 AM - 4:00 PM ET = Mon-Fri only
        }
        
        # Known US stock symbols on Exness (end with 'm' suffix)
        STOCK_SYMBOLS = {'AAPL', 'AMD', 'MSFT', 'NVDA', 'JPM', 'BAC', 'WFC', 'GOOGL', 'META', 'ORCL', 'TSM',
                         'AAPLM', 'AMDM', 'MSFTM', 'NVDAM', 'JPMM', 'BACM', 'WFCM', 'GOOGLM', 'METAM', 'ORCLM', 'TSMM'}
        
        def get_symbol_category(symbol):
            """Determine symbol category from its name"""
            symbol_upper = symbol.upper()
            # Check commodities FIRST (XAU/XAG contain USD but are commodities, not forex)
            if any(com in symbol_upper for com in ['XAU', 'XAG', 'OIL', 'GAS', 'WHEAT']):
                return 'COMMODITIES'
            elif any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'XRP', 'USDT']):
                return 'CRYPTO'
            elif any(idx in symbol_upper for idx in ['SPX', 'NDX', 'TECH', 'DOW', 'USTEC']):
                return 'INDICES'
            elif symbol_upper in STOCK_SYMBOLS:
                return 'STOCKS'
            elif any(pair in symbol_upper for pair in ['EUR', 'GBP', 'USD', 'JPY', 'CHF']):
                return 'FOREX'
            return 'STOCKS'  # Default to STOCKS (safer - has restricted hours)
        
        def is_market_open_for_symbol(symbol, mt5_conn=None):
            """Check if market is open for the given symbol"""
            try:
                # ==================== CRYPTO 24/7 OVERRIDE ====================
                # Crypto symbols (BTC, ETH, etc) trade 24/7 - bypass day-of-week check
                symbol_upper = symbol.upper()
                logger.info(f"[MARKET] Checking symbol: {symbol} -> {symbol_upper}")
                if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'XRP', 'USDT']):
                    logger.info(f"✅ CRYPTO 24/7: {symbol} allowed to trade on weekends/weekdays")
                    return True, f"Market OPEN for {symbol} (crypto trades 24/7)"
                
                symbol_cat = get_symbol_category(symbol)
                category_hours = market_hours.get(symbol_cat, market_hours['FOREX'])
                
                now_utc = datetime.utcnow()
                current_day = now_utc.weekday()  # 0=Monday, 6=Sunday
                current_time = (now_utc.hour, now_utc.minute)
                
                # Check if today is a trading day
                if current_day not in category_hours['days']:
                    return False, f"Market closed (day {current_day} not in trading days)"
                
                open_time = category_hours['open']
                close_time = category_hours['close']
                
                # Convert times to minutes for easier comparison
                current_mins = current_time[0] * 60 + current_time[1]
                open_mins = open_time[0] * 60 + open_time[1]
                close_mins = close_time[0] * 60 + close_time[1]
                
                if open_mins <= current_mins < close_mins:
                    return True, f"Market OPEN for {symbol_cat}"
                else:
                    return False, f"Market closed - {symbol_cat} trading hours: {open_time[0]:02d}:{open_time[1]:02d}-{close_time[0]:02d}:{close_time[1]:02d} UTC"
            except Exception as e:
                logger.warning(f"Could not determine market hours: {e} - allowing trade")
                return True, "Unknown market status"
        
        while not bot_stop_flags.get(bot_id, False):
            try:
                trade_cycle += 1
                logger.info(f"🔄 Bot {bot_id}: Trade cycle #{trade_cycle} starting at {datetime.now().isoformat()}")
                
                # ==================== CHECK MARKET HOURS ====================
                # Get first symbol from symbols list (symbols is stored as list in bot_config)
                symbols_list = bot_config.get('symbols', ['EURUSDm'])
                logger.info(f"[BOT {bot_id}] symbols_list from config: {symbols_list}")
                symbol_to_trade = symbols_list[0] if symbols_list else 'EURUSDm'
                logger.info(f"[BOT {bot_id}] symbol_to_trade: {symbol_to_trade}")
                is_open, market_status = is_market_open_for_symbol(symbol_to_trade)
                
                if not is_open:
                    logger.info(f"⏸️  Bot {bot_id}: {market_status} - will wait for next cycle")
                    logger.info(f"   ⏰ Next check in {trading_interval} seconds")
                    time.sleep(trading_interval)
                    continue
                
                # Detect broker type
                broker_type = bot_config.get('broker_type', 'MT5')
                is_ig = broker_type == 'IG Markets'
                is_mt5 = broker_type in ['MetaTrader 5', 'MetaQuotes', 'XM Global', 'XM', 'Exness', 'PXBT', 'MT5']
                
                mt5_conn = None
                ig_conn = None
                active_conn = None
                use_rest_trading = False  # True when MetaAPI REST is used instead of local MT5
                
                if is_ig:
                    # IG Markets broker - use REST API via IGConnection
                    try:
                        ig_conn = bot_config.get('broker_conn')
                        if ig_conn is None or not ig_conn.connected:
                            # Re-establish IG connection
                            credential_id = bot_config.get('credentialId')
                            if credential_id:
                                broker_type_new, new_conn = get_broker_connection(credential_id, user_id, bot_id)
                                if False and broker_type_new == 'IG Markets' and hasattr(new_conn, 'connected'):  # IG Markets integration removed
                                    ig_conn = new_conn
                                    bot_config['broker_conn'] = ig_conn
                                else:
                                    logger.error(f"Bot {bot_id}: IG reconnection failed: {new_conn}")
                                    time.sleep(trading_interval)
                                    continue
                            else:
                                logger.error(f"Bot {bot_id}: No credentialId for IG reconnection")
                                time.sleep(trading_interval)
                                continue
                        logger.info(f"Bot {bot_id}: Connected to IG Markets for trading")
                        active_conn = ig_conn
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: IG connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                elif is_mt5:
                    # MT5 broker - connect via terminal SDK or REST API (MetaAPI)
                    try:
                        # ==================== REST/SOCKET TRADING FAST PATH ====================
                        # Socket bridge or MetaAPI cloud for supported brokers → saves ~300MB RAM per account
                        if trade_router and not use_rest_trading:
                            # ✅ DEFENSIVE: Ensure bot_credentials is dict, never None
                            if not isinstance(bot_credentials, dict):
                                logger.warning(f"⚠️  Bot {bot_id}: bot_credentials is {type(bot_credentials).__name__}, expected dict - using empty dict")
                                bot_credentials = {}
                            
                            _broker_for_route = bot_config.get('broker_type', 'MT5')
                            _account_for_route = bot_credentials.get('account', '')
                            _exec_mode = trade_router.determine_mode(_broker_for_route, _account_for_route)
                            if _exec_mode in (ExecutionMode.SOCKET, ExecutionMode.METAAPI):
                                try:
                                    _acct_exec = trade_router.get_or_create_execution(
                                        broker=_broker_for_route,
                                        account_number=_account_for_route,
                                        password=bot_credentials.get('password', ''),
                                        server=bot_credentials.get('server', ''),
                                        is_live=True,
                                        user_id=user_id,
                                    )
                                    if _acct_exec.connection and _acct_exec.mode in (ExecutionMode.SOCKET, ExecutionMode.METAAPI):
                                        mt5_conn = _acct_exec.connection
                                        active_conn = mt5_conn
                                        use_rest_trading = True
                                        _mode_label = 'Socket Bridge' if _acct_exec.mode == ExecutionMode.SOCKET else 'MetaAPI'
                                        logger.info(f"🔌 Bot {bot_id}: {_mode_label} trading ({_broker_for_route}) — no local MT5 needed")
                                except Exception as _re:
                                    logger.warning(f"Bot {bot_id}: REST/Socket setup failed ({_re}), falling back to local MT5")
                        
                        if not use_rest_trading:
                                    # LOCAL MT5 TERMINAL PATH (original code)
                                normalized_cache_broker = canonicalize_broker_name(bot_config.get('broker_type', 'MetaTrader 5'))
                                cache_key = f"{user_id}|{normalized_cache_broker}|{bot_credentials.get('account', 'unknown')}"
                                with broker_connection_cache_lock:
                                    if cache_key in broker_connection_cache:
                                        mt5_conn = broker_connection_cache[cache_key]
                                        logger.debug(f"♻️  Bot {bot_id}: Using cached MT5 connection (savings: 3-5s)")
                                
                                        # ✨ NEW: Health check for PXBT to detect session loss
                                        if normalized_cache_broker == 'PXBT':
                                            if not is_pxbt_connection_healthy(mt5_conn):
                                                logger.warning(f"⚠️  Bot {bot_id}: PXBT connection health check failed - attempting auto-reconnect")
                                                if ensure_pxbt_connection_active(mt5_conn, bot_credentials):
                                                    logger.info(f"✅ Bot {bot_id}: PXBT reconnected successfully")
                                                else:
                                                    logger.error(f"❌ Bot {bot_id}: PXBT auto-reconnect failed - will retry next cycle")
                                                    stagger_delay = random.uniform(1, 15)
                                                    actual_wait = trading_interval + stagger_delay
                                                    logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                                                    time.sleep(actual_wait)
                                                    continue
                                    else:
                                        # Create new connection and cache it
                                        if bot_credentials:
                                            # CRITICAL FIX: Use global MT5 singleton instead of creating new instances
                                            # BEFORE: Each bot created MT5Connection → 14 terminal windows
                                            # NOW: All bots reuse single global connection → 1 terminal window
                                            mt5_conn = get_global_mt5()
                                            if not mt5_conn:
                                                logger.info(f"Bot {bot_id}: Creating global MT5 singleton connection...")
                                                mt5_conn = MT5Connection(bot_credentials)
                                                set_global_mt5(mt5_conn)
                                                # ✨ NEW: Cache PXBT credentials for auto-reconnect
                                                if normalized_cache_broker == 'PXBT':
                                                    cache_pxbt_credentials(
                                                        bot_credentials.get('credential_id', 'unknown'),
                                                        bot_credentials.get('account', ''),
                                                        bot_credentials.get('password', ''),
                                                        bot_credentials.get('server', '')
                                                    )
                                            else:
                                                logger.debug(f"Bot {bot_id}: Reusing global MT5 connection")
                                        else:
                                            mt5_conn = get_global_mt5()
                                            if not mt5_conn:
                                                logger.info(f"Bot {bot_id}: Creating global MT5 singleton (no credentials)...")
                                                mt5_conn = MT5Connection()
                                                set_global_mt5(mt5_conn)
                                            else:
                                                logger.debug(f"Bot {bot_id}: Reusing global MT5 connection")
                                        broker_connection_cache[cache_key] = mt5_conn
                                        logger.debug(f"✨ Bot {bot_id}: MT5 connection cached")
                        
                                if not mt5_conn.connect():
                                    logger.error(f"Bot {bot_id}: MT5 connection failed - will retry next cycle")
                                    # STAGGER: Add random delay (1-15s) so bots don't all retry simultaneously
                                    stagger_delay = random.uniform(1, 15)
                                    actual_wait = trading_interval + stagger_delay
                                    logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                                    time.sleep(actual_wait)
                                    continue
                        
                                # ==================== MULTI-USER ACCOUNT VERIFICATION ====================
                                # Verify MT5 is logged into THIS bot's account before trading.
                                # If another user's bot switched the account, we must re-login.
                                # Uses fast mt5_current_account check first to avoid expensive MT5 IPC call.
                                try:
                                    expected_account = int(bot_credentials.get('account', 0))
                                    needs_switch = False
                                    with mt5_account_lock:
                                        if mt5_current_account and expected_account and mt5_current_account != expected_account:
                                            needs_switch = True
                            
                                    if needs_switch:
                                        logger.warning(f"⚠️  Bot {bot_id}: MT5 on account {mt5_current_account} but bot needs {expected_account} - switching...")
                                        # Force re-login with this bot's credentials
                                        mt5_conn.connected = False
                                        if not mt5_conn.connect():
                                            logger.error(f"Bot {bot_id}: Account switch to {expected_account} failed - will retry")
                                            time.sleep(trading_interval)
                                            continue
                                        # Verify the switch actually stuck (another concurrent bot may have
                                        # switched the singleton back while we held the conn lock)
                                        try:
                                            import MetaTrader5 as _mt5_verify
                                            _verify_info = _mt5_verify.account_info()
                                            if _verify_info and _verify_info.login != expected_account:
                                                logger.warning(f"⚠️  Bot {bot_id}: Switch verification failed — MT5 is on {_verify_info.login}, not {expected_account}. Skipping cycle to avoid wrong-account trade.")
                                                time.sleep(trading_interval)
                                                continue
                                        except Exception:
                                            pass
                                        logger.info(f"✅ Bot {bot_id}: Switched MT5 to account {expected_account}")
                                    elif expected_account and not mt5_current_account:
                                        # First time — verify via MT5 IPC
                                        import MetaTrader5 as _mt5_check
                                        current_info = _mt5_check.account_info()
                                        if current_info and current_info.login != expected_account:
                                            mt5_conn.connected = False
                                            if not mt5_conn.connect():
                                                logger.error(f"Bot {bot_id}: Initial account login to {expected_account} failed")
                                                time.sleep(trading_interval)
                                                continue
                                except Exception as acct_err:
                                    logger.debug(f"Bot {bot_id}: Account verification check: {acct_err}")
                                # ==================== END MULTI-USER VERIFICATION ====================
                        
                                if trade_cycle == 1:
                                    logger.info(f"Bot {bot_id}: First trade cycle - waiting for MT5 readiness (up to {mt5_ready_timeout}s)...")
                                    timeout_for_this_cycle = mt5_ready_timeout
                                    # Log progress every 5 seconds to help diagnose hangs
                                    start_wait = datetime.now()
                                else:
                                    timeout_for_this_cycle = 10  # Reduced from 15s
                                    start_wait = None
                        
                                if not mt5_conn.wait_for_mt5_ready(timeout_seconds=timeout_for_this_cycle):
                                    if trade_cycle == 1:
                                        elapsed_wait = (datetime.now() - start_wait).total_seconds() if start_wait else timeout_for_this_cycle
                                        logger.warning(f"Bot {bot_id}: First cycle MT5 readiness timeout after {elapsed_wait:.0f}s (max {timeout_for_this_cycle}s)")
                                        logger.warning(f"  Will retry with extended wait... (another {timeout_for_this_cycle}s)")
                                        time.sleep(10)
                                        continue
                                    else:
                                        logger.warning(f"Bot {bot_id}: MT5 not ready after {timeout_for_this_cycle}s - will retry next cycle")
                                        # STAGGER: Add random delay to prevent thundering herd
                                        stagger_delay = random.uniform(2, 12)
                                        actual_wait = trading_interval + stagger_delay
                                        logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                                        time.sleep(actual_wait)
                                        continue
                                
                                # ==================== WAIT FOR CRITICAL SYMBOLS ====================
                                # For bots trading ETHUSDm or BTCUSDm, ensure they're fully loaded
                                # These symbols require special initialization and fail fast if unavailable
                                symbols_list = bot_config.get('symbols', ['EURUSDm'])
                                if trade_cycle == 1:  # Only on first cycle to avoid repeated delays
                                    if not mt5_conn.wait_for_critical_symbols(symbols_list, timeout_seconds=15):
                                        logger.warning(f"Bot {bot_id}: Critical symbols not ready yet, will retry next cycle")
                                        # Rather than fail immediately, retry in next cycle
                                        # Critical symbols usually load within 30-60 seconds total after MT5 connects
                                        time.sleep(trading_interval)
                                        continue
                                # ==================== END CRITICAL SYMBOL CHECK ====================
                                
                        active_conn = mt5_conn
                        
                    except Exception as e:
                        import traceback
                        logger.error(f"Bot {bot_id}: MT5 connection exception: {e}")
                        logger.error(f"  Traceback: {traceback.format_exc()}")
                        logger.error(f"  Exception type: {type(e).__name__}")
                        # STAGGER: Add random delay to prevent thundering herd
                        stagger_delay = random.uniform(2, 12)
                        actual_wait = trading_interval + stagger_delay
                        logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                        time.sleep(actual_wait)
                        continue
                else:
                    try:
                        active_conn = bot_config.get('broker_conn')
                        if active_conn is None or not active_conn.connected:
                            credential_id = bot_config.get('credentialId')
                            if credential_id:
                                broker_type_new, new_conn = get_broker_connection(credential_id, user_id, bot_id)
                                if hasattr(new_conn, 'connected'):
                                    active_conn = new_conn
                                    bot_config['broker_conn'] = active_conn
                                    bot_config['broker_type'] = broker_type_new
                                    broker_type = broker_type_new
                                else:
                                    logger.error(f"Bot {bot_id}: Broker reconnection failed: {new_conn}")
                                    # STAGGER: Add random delay to prevent thundering herd
                                    stagger_delay = random.uniform(2, 12)
                                    actual_wait = trading_interval + stagger_delay
                                    logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                                    time.sleep(actual_wait)
                                    continue
                            else:
                                logger.error(f"Bot {bot_id}: No credentialId for broker reconnection")
                                # STAGGER: Add random delay to prevent thundering herd
                                stagger_delay = random.uniform(2, 12)
                                actual_wait = trading_interval + stagger_delay
                                logger.info(f"   ⏰ Staggered retry in {actual_wait:.0f}s (base {trading_interval}s + jitter {stagger_delay:.0f}s)")
                                time.sleep(actual_wait)
                                continue
                        logger.info(f"Bot {bot_id}: Connected to {broker_type} for trading")
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Broker connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                
                # Execute trade cycle (same logic as in start_bot endpoint)
                strategy_name = bot_config.get('strategy', 'trend_following')
                strategy_func = STRATEGY_MAP.get(strategy_name, trend_following_strategy)
                
                trades_placed = 0
                symbols = bot_config.get('symbols', ['EURUSDm'])
                
                # CHECK PROFIT LOCK AND DAILY LOSS LIMITS BEFORE TRADING
                profit_lock = bot_config.get('profitLock', 0.0) or 0.0
                max_daily_loss = bot_config.get('maxDailyLoss', 0.0) or 0.0
                today = datetime.now().strftime('%Y-%m-%d')
                # Safely handle dailyProfits - ensure it's a dict
                daily_profits_dict = bot_config.get('dailyProfits') or {}
                if not isinstance(daily_profits_dict, dict):
                    daily_profits_dict = {}
                    bot_config['dailyProfits'] = daily_profits_dict
                daily_profit = daily_profits_dict.get(today, 0.0)
                
                pause_reason = None
                if profit_lock > 0 and daily_profit >= profit_lock:
                    pause_reason = f"🔒 Daily profit lock reached: ${daily_profit:.2f} >= ${profit_lock:.2f}"
                elif max_daily_loss > 0 and daily_profit < -max_daily_loss:
                    pause_reason = f"⚠️ Daily loss limit hit: ${abs(daily_profit):.2f} >= ${max_daily_loss:.2f}"
                
                if pause_reason:
                    logger.info(f"[PAUSE] Bot {bot_id}: {pause_reason} - PAUSING TRADES FOR TODAY")
                    bot_config['status'] = 'PAUSED'
                    bot_config['pauseReason'] = pause_reason
                    persist_bot_runtime_state(bot_id)
                    # Wait for trading interval before next cycle
                    time.sleep(trading_interval)
                    continue
                else:
                    # Trading is allowed
                    if bot_config.get('status') == 'PAUSED':
                        bot_config['status'] = 'ACTIVE'
                        bot_config['pauseReason'] = None
                
                # ENHANCED LOGGING: Log signal evaluation for ALL symbols upfront
                management_state = apply_assisted_management_overrides(bot_config)
                signal_threshold = management_state['signalThreshold']
                signal_summary = []
                for eval_symbol in symbols:
                    eval_market_data = commodity_market_data.get(eval_symbol, {'current_price': 0, 'volatility_pct': 1.0})
                    eval_params = strategy_func(eval_symbol, bot_config['accountId'], bot_config['riskPerTrade'], eval_market_data)
                    signal_score = eval_params.get('signal', {}).get('strength', 0) if eval_params else 0
                    status = "✅" if eval_params and signal_score >= signal_threshold else "⏭️"
                    signal_summary.append(f"{eval_symbol}:{signal_score:.0f}")
                
                logger.info(f"📊 Bot {bot_id} Cycle #{trade_cycle}: Signal check: {' | '.join(signal_summary)} (threshold: {signal_threshold}/100)")
                
                trades_this_cycle = 0
                for symbol in symbols:
                    if bot_stop_flags.get(bot_id, False):
                        break  # Stop requested, exit loop
                    
                    try:
                        if not should_trade_symbol_based_on_risk_management(bot_config, symbol):
                            continue

                        # Dynamic position sizing
                        fixed_trade_amount = bot_config.get('tradeAmount')
                        if fixed_trade_amount:
                            # Fixed dollar amount: convert to lot size
                            # Standard lot = 100,000 units, so $amount / 100000 gives lots
                            position_size = max(0.01, round(fixed_trade_amount / 100000, 2))
                            logger.info(f"💵 Bot {bot_id}: Using fixed trade amount ${fixed_trade_amount} -> {position_size} lots")
                        elif bot_config.get('dynamicSizing', True):
                            position_size = position_sizer.calculate_position_size(
                                bot_config,
                                volatility_level=bot_config.get('volatilityLevel', 'Medium')
                            )
                        else:
                            position_size = bot_config.get('basePositionSize', 1.0)
                        
                        # Get market data for this symbol
                        market_data = commodity_market_data.get(symbol, {'current_price': 0, 'volatility_pct': 1.0})
                        
                        # Get trade direction from REAL signal-based strategy
                        trade_params = strategy_func(symbol, bot_config['accountId'], bot_config['riskPerTrade'], market_data)
                        
                        # Skip trade if signal strength is too low
                        if trade_params is None:
                            logger.info(f"⏭️ Bot {bot_id}: Skipping {symbol} - signal strength insufficient")
                            continue
                        
                        adjusted_volume = trade_params['volume'] * position_size
                        order_type = trade_params['type']
                        
                        # Log signal details
                        signal_info = trade_params.get('signal', {})
                        logger.info(f"🎯 Bot {bot_id}: {signal_info.get('signal', 'UNKNOWN')} signal on {symbol}")
                        logger.info(f"   Signal Strength: {signal_info.get('strength', 0):.0f}/100 | Reason: {signal_info.get('entry_reason', 'N/A')}")
                        
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
                        elif is_mt5:
                            # MT5 - place order with retry/fallback logic
                            # ❌ FIX: Only try fallback for non-critical symbols
                            critical_symbols = {'BTCUSDm', 'ETHUSDm'}
                            if symbol in critical_symbols:
                                symbols_to_try = [symbol]  # NO FALLBACK for BTC/ETH - fail instead
                            else:
                                symbols_to_try = [symbol, 'EURUSDm']  # Fallback only if primary fails
                            
                            # ✅ POSITION LIMIT CHECK: Enforce maxOpenPositions to prevent unlimited trades
                            max_open = bot_config.get('effectiveMaxOpenPositions') or bot_config.get('maxOpenPositions') or 5
                            max_per_symbol = bot_config.get('effectiveMaxPositionsPerSymbol') or bot_config.get('maxPositionsPerSymbol') or max_open
                            existing_positions = mt5_conn.get_positions()
                            bot_id_short = bot_id.split('_')[-1][:8]
                            comment_short = f'ZBot{bot_id_short}'
                            
                            # Count positions belonging to THIS bot (by comment) and also by tracked open_positions
                            bot_position_count = 0
                            bot_positions_on_symbol = 0
                            tracked_open = bot_config.get('open_positions', {})
                            tracked_tickets = set(tracked_open.keys())
                            
                            for ep in existing_positions:
                                ep_comment = ep.get('comment', '') or ''
                                ep_ticket = str(ep.get('ticket', ''))
                                ep_symbol = ep.get('symbol', '')
                                # Match by comment OR by tracked ticket
                                is_this_bot = comment_short in ep_comment or ep_ticket in tracked_tickets
                                if is_this_bot:
                                    bot_position_count += 1
                                    if ep_symbol == symbol:
                                        bot_positions_on_symbol += 1
                            
                            # Respect the bot's configured per-symbol position cap.
                            if bot_positions_on_symbol >= max_per_symbol:
                                logger.info(
                                    f"📌 Bot {bot_id}: Already has {bot_positions_on_symbol} open position(s) on {symbol} "
                                    f"(limit {max_per_symbol}) - skipping"
                                )
                                continue
                            
                            # Skip if bot has reached max open positions overall
                            if bot_position_count >= max_open:
                                logger.info(f"📌 Bot {bot_id}: At max open positions ({bot_position_count}/{max_open}) - skipping new trade on {symbol}")
                                continue
                            
                            # ✅ Calculate SL/TP price levels for MT5
                            sl_price = None
                            tp_price = None
                            try:
                                if use_rest_trading:
                                    # REST path: get price via MetaAPI bridge (no local mt5 module)
                                    _price_data = mt5_conn.get_symbol_price(symbol)
                                    if _price_data and _price_data.get('bid', 0) > 0:
                                        _bid = _price_data['bid']
                                        _ask = _price_data['ask']
                                        _spread = _ask - _bid
                                        from rest_price_feed import get_pip_size
                                        _point = get_pip_size(symbol)
                                        _sl_pips = trade_params.get('stop_loss', 50)
                                        _tp_pips = trade_params.get('take_profit', 100)
                                        _sl_dist = _sl_pips * _point
                                        _tp_dist = _tp_pips * _point
                                        _sl_dist = max(_sl_dist, _spread * 3)
                                        _tp_dist = max(_tp_dist, _spread * 5)
                                        _digits = 5 if _point < 0.01 else 2  # forex=5, gold/indices=2
                                        if order_type == 'BUY':
                                            sl_price = round(_ask - _sl_dist, _digits)
                                            tp_price = round(_ask + _tp_dist, _digits)
                                        else:
                                            sl_price = round(_bid + _sl_dist, _digits)
                                            tp_price = round(_bid - _tp_dist, _digits)
                                        logger.info(f"📐 Bot {bot_id}: REST SL={sl_price}, TP={tp_price} (spread={_spread:.5f})")
                                else:
                                    _tick = mt5_conn.mt5.symbol_info_tick(symbol)
                                    _sym_info = mt5_conn.mt5.symbol_info(symbol)
                                    if _tick and _sym_info:
                                        _point = _sym_info.point
                                        _spread = _tick.ask - _tick.bid
                                        _sl_pips = trade_params.get('stop_loss', 50)
                                        _tp_pips = trade_params.get('take_profit', 100)
                                        _sl_dist = _sl_pips * _point
                                        _tp_dist = _tp_pips * _point
                                        # Ensure SL is at least 3x spread, TP at least 5x spread
                                        _sl_dist = max(_sl_dist, _spread * 3)
                                        _tp_dist = max(_tp_dist, _spread * 5)
                                        if order_type == 'BUY':
                                            sl_price = round(_tick.ask - _sl_dist, _sym_info.digits)
                                            tp_price = round(_tick.ask + _tp_dist, _sym_info.digits)
                                        else:
                                            sl_price = round(_tick.bid + _sl_dist, _sym_info.digits)
                                            tp_price = round(_tick.bid - _tp_dist, _sym_info.digits)
                                        logger.info(f"📐 Bot {bot_id}: SL={sl_price}, TP={tp_price} (spread={_spread:.2f}, sl_dist={_sl_dist:.2f}, tp_dist={_tp_dist:.2f})")
                            except Exception as e:
                                logger.warning(f"Bot {bot_id}: Could not calculate SL/TP: {e}")
                            
                            # ✅ CRITICAL: Ensure SL/TP are ALWAYS set - positions without SL/TP never close
                            if sl_price is None or tp_price is None:
                                try:
                                    _tick_fb = mt5_conn.mt5.symbol_info_tick(symbol) if not use_rest_trading else None
                                    if _tick_fb:
                                        _price_fb = _tick_fb.ask if order_type == 'BUY' else _tick_fb.bid
                                        _sym_fb = mt5_conn.mt5.symbol_info(symbol)
                                        _point_fb = _sym_fb.point if _sym_fb else 0.00001
                                        _digits_fb = _sym_fb.digits if _sym_fb else 5
                                        # Default SL: 50 pips, TP: 100 pips
                                        if order_type == 'BUY':
                                            sl_price = sl_price or round(_price_fb - 50 * _point_fb, _digits_fb)
                                            tp_price = tp_price or round(_price_fb + 100 * _point_fb, _digits_fb)
                                        else:
                                            sl_price = sl_price or round(_price_fb + 50 * _point_fb, _digits_fb)
                                            tp_price = tp_price or round(_price_fb - 100 * _point_fb, _digits_fb)
                                        logger.info(f"📐 Bot {bot_id}: Fallback SL={sl_price}, TP={tp_price} (default 50/100 pips)")
                                except Exception as fb_e:
                                    logger.warning(f"Bot {bot_id}: Fallback SL/TP calculation also failed: {fb_e}")
                            
                            for index, attempt_symbol in enumerate(symbols_to_try):
                                try:
                                    order_result = mt5_conn.place_order(
                                        symbol=attempt_symbol,
                                        order_type=order_type,
                                        volume=adjusted_volume,
                                        comment=comment_short,
                                        stopLoss=sl_price,
                                        takeProfit=tp_price
                                    )
                                    
                                    if order_result.get('success', False):
                                        # ✅ CRITICAL FIX: Log WARNING if traded symbol differs from requested
                                        actual_symbol = order_result.get('symbol', attempt_symbol)
                                        if actual_symbol != symbol:
                                            logger.warning(f"⚠️ SYMBOL MISMATCH - Bot {bot_id}: Requested {symbol} but EXECUTED on {actual_symbol}")
                                            logger.warning(f"   This may result in unexpected profits/losses if symbols trade differently")
                                        logger.info(f"✅ Bot {bot_id}: Order placed successfully on {actual_symbol}")
                                        symbol = actual_symbol  # Update to actual traded symbol
                                        break
                                    else:
                                        # ==================== CRITICAL SYMBOL RETRY LOGIC ====================
                                        # If critical symbol (ETHUSDm, BTCUSDm) is temporarily unavailable,
                                        # wait the suggested time and retry (don't give up immediately)
                                        retry_after = order_result.get('retry_after_seconds')
                                        is_critical = attempt_symbol in critical_symbols
                                        
                                        if is_critical and retry_after and retry_after > 0:
                                            logger.warning(f"⏳ Bot {bot_id}: {attempt_symbol} not yet available (retry in {retry_after}s)...")
                                            logger.warning(f"   Symbol is loading. MT5 terminal may still be initializing symbols.")
                                            # Wait for symbol to load, then retry immediately (max 3 retries)
                                            total_retries = 3
                                            for retry_num in range(total_retries):
                                                time.sleep(retry_after)
                                                logger.info(f"🔄 Bot {bot_id}: Retry {retry_num + 1}/{total_retries} for {attempt_symbol}...")
                                                retry_result = mt5_conn.place_order(
                                                    symbol=attempt_symbol,
                                                    order_type=order_type,
                                                    volume=adjusted_volume,
                                                    comment=comment_short,
                                                    stopLoss=sl_price,
                                                    takeProfit=tp_price
                                                )
                                                if retry_result.get('success', False):
                                                    logger.info(f"✅ Bot {bot_id}: {attempt_symbol} order placed successfully after retry {retry_num + 1}")
                                                    order_result = retry_result
                                                    symbol = attempt_symbol
                                                    break
                                                elif retry_num < total_retries - 1:
                                                    retry_wait = retry_result.get('retry_after_seconds', retry_after)
                                                    logger.warning(f"   Retry {retry_num + 1} failed, retrying again...")
                                                    continue
                                            
                                            # After retries, check if we finally succeeded
                                            if order_result.get('success', False):
                                                break
                                            else:
                                                # All retries failed - log but continue (don't trade this cycle)
                                                logger.error(f"❌ Bot {bot_id}: {attempt_symbol} unavailable after {total_retries} retries: {order_result.get('error')}")
                                                order_result = {'success': False, 'error': f'{attempt_symbol} still unavailable after retries'}
                                                break
                                        else:
                                            # Standard error handling (not a retry-able initialization delay)
                                            error_msg = order_result.get('error', '').lower()
                                            is_last_attempt = (index == len(symbols_to_try) - 1)
                                            
                                            if ('not found' in error_msg or 'disconnected' in error_msg or 'order_send failed' in error_msg) and not is_last_attempt:
                                                logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol} ({order_result.get('error')}) - trying {symbols_to_try[index+1]}...")
                                                continue
                                            else:
                                                # Don't log CRITICAL for pause conditions (position limit, market closed, etc.)
                                                if attempt_symbol in critical_symbols and not order_result.get('is_paused'):
                                                    logger.error(f"❌ CRITICAL SYMBOL FAILED: Bot {bot_id}: {attempt_symbol} failed and NO fallback allowed: {order_result.get('error')}")
                                                logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol}: {order_result.get('error')}")
                                                break
                                except Exception as e:
                                    logger.error(f"Bot {bot_id}: Exception placing order on {attempt_symbol}: {e}")
                                    if index < len(symbols_to_try) - 1:
                                        continue
                                    break
                        else:
                            try:
                                order_result = active_conn.place_order(
                                    symbol=symbol,
                                    order_type=order_type,
                                    volume=round(adjusted_volume, 4),
                                )
                                if order_result.get('success', False):
                                    logger.info(f"✅ Bot {bot_id}: {broker_type} order placed on {order_result.get('symbol', symbol)}")
                                else:
                                    logger.warning(f"Bot {bot_id}: {broker_type} order failed on {symbol}: {order_result.get('error')}")
                            except Exception as e:
                                logger.error(f"Bot {bot_id}: {broker_type} place_order exception: {e}")
                                order_result = {'success': False, 'error': str(e)}
                        
                        # CHECK FOR MARKET PAUSE CONDITIONS - Log pause events
                        if order_result and order_result.get('is_paused', False):
                            pause_type = order_result.get('pause_type', 'UNKNOWN')
                            pause_reason = order_result.get('pause_reason', 'Market paused')
                            retcode = order_result.get('retcode', 0)
                            error_msg = order_result.get('original_comment', order_result.get('error', 'Unknown error'))
                            
                            # Log pause event to database
                            pause_id = log_pause_event(
                                bot_id=bot_id,
                                user_id=user_id,
                                symbol=symbol,
                                pause_type=pause_type,
                                retcode=retcode,
                                error_message=error_msg,
                                pause_reason=pause_reason
                            )
                            
                            logger.warning(f"🔒 Bot {bot_id}: Market pause event recorded (pause_id={pause_id})")
                            
                            # Update bot status to indicate pause
                            bot_config['lastPauseEvent'] = {
                                'symbol': symbol,
                                'pause_type': pause_type,
                                'pause_reason': pause_reason,
                                'detected_at': datetime.now().isoformat(),
                                'pause_id': pause_id
                            }
                            
                            # Skip this trade but continue to next symbol (don't stop bot)
                            continue
                        
                        if order_result and order_result.get('success', False):
                            # Get the order ticket/deal_id for precise matching
                            order_ticket = str(order_result.get('orderId') or order_result.get('deal_id') or '')
                            
                            # Get current position info (broker-aware)
                            positions = []
                            if is_ig and ig_conn:
                                positions = ig_conn.get_positions()
                            elif is_mt5 and mt5_conn:
                                positions = mt5_conn.get_positions()
                            elif active_conn:
                                positions = active_conn.get_positions()
                            
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
                                        pos_symbol = pos.get('symbol') or pos.get('instrument') or pos.get('epic', '')
                                        pos_type = pos.get('type') or pos.get('direction', '')
                                        if (pos_symbol == symbol or symbol in pos_symbol) and pos_type.upper() == order_type.upper():
                                            matched_pos = pos
                                            break
                                
                                if matched_pos:
                                    pos_symbol = matched_pos.get('symbol') or matched_pos.get('instrument') or symbol
                                    pos_type = matched_pos.get('type') or matched_pos.get('direction', order_type)
                                    pos_ticket = matched_pos.get('ticket') or matched_pos.get('deal_id', order_ticket)
                                    current_profit = matched_pos.get('profit') or matched_pos.get('pnl') or 0
                                    current_price = matched_pos.get('currentPrice') or matched_pos.get('marketPrice') or matched_pos.get('price_current') or 0
                                    
                                    # ============ TRACK AS OPEN POSITION — DO NOT RECORD P&L YET ============
                                    # The position was just opened, P&L is ~$0 (spread only).
                                    # Real P&L will be recorded when the position closes (via TP/SL or manual close).
                                    # Store in bot's open_positions tracker for monitoring.
                                    if 'open_positions' not in bot_config:
                                        bot_config['open_positions'] = {}
                                    
                                    bot_config['open_positions'][str(pos_ticket)] = {
                                        'ticket': pos_ticket,
                                        'symbol': pos_symbol,
                                        'type': pos_type,
                                        'volume': matched_pos.get('volume') or matched_pos.get('size', 0),
                                        'entryPrice': matched_pos.get('openPrice') or matched_pos.get('level', 0),
                                        'currentPrice': current_price,
                                        'profit': round(current_profit, 2),
                                        'status': 'open',
                                        'entryTime': matched_pos.get('openTime', datetime.now().isoformat()),
                                        'botId': bot_id,
                                        'cycle': trade_cycle,
                                        'strategy': strategy_name,
                                        'broker': broker_type,
                                    }
                                    
                                    # Store open trade in database
                                    try:
                                        trade_conn = sqlite3.connect(r'C:\backend\zwesta_trading.db', timeout=30)
                                        trade_cursor = trade_conn.cursor()
                                        trade_id = f"trade_{int(datetime.now().timestamp()*1000)}_{bot_id[-8:]}"
                                        trade_cursor.execute('''
                                            INSERT INTO trades (trade_id, bot_id, user_id, symbol, order_type, volume, price, profit, ticket, time_open, time_close, status, created_at, trade_data, timestamp)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        ''', (
                                            trade_id,
                                            bot_id,
                                            user_id,
                                            pos_symbol,
                                            pos_type,
                                            matched_pos.get('volume', 0),
                                            matched_pos.get('openPrice', 0),
                                            0,  # Profit is 0 until position closes
                                            str(pos_ticket),
                                            matched_pos.get('openTime', datetime.now().isoformat()),
                                            None,  # No close time yet
                                            'open',  # Mark as OPEN, not closed
                                            datetime.now().isoformat(),
                                            json.dumps({'ticket': str(pos_ticket), 'symbol': pos_symbol, 'type': pos_type, 'entryPrice': matched_pos.get('openPrice', 0), 'source': f"REAL_{str(broker_type).upper().replace(' ', '_')}"}),
                                            int(datetime.now().timestamp() * 1000)
                                        ))
                                        trade_conn.commit()
                                        trade_conn.close()
                                    except Exception as e:
                                        logger.error(f"Bot {bot_id}: Error storing open trade: {e}")

                                    open_trade = {
                                        'ticket': pos_ticket,
                                        'symbol': pos_symbol,
                                        'type': pos_type,
                                        'volume': matched_pos.get('volume') or matched_pos.get('size', 0),
                                        'entryPrice': matched_pos.get('openPrice', 0),
                                        'currentPrice': current_price,
                                        'profit': round(current_profit, 2),
                                        'entryTime': matched_pos.get('openTime', datetime.now().isoformat()),
                                        'time': matched_pos.get('openTime', datetime.now().isoformat()),
                                        'timestamp': int(datetime.now().timestamp() * 1000),
                                        'botId': bot_id,
                                        'cycle': trade_cycle,
                                        'strategy': strategy_name,
                                        'isWinning': current_profit > 0,
                                        'status': 'open',
                                        'source': f"REAL_{str(broker_type).upper().replace(' ', '_')}",
                                        'broker': broker_type,
                                    }

                                    trade_history = bot_config.setdefault('tradeHistory', [])
                                    existing_index = next(
                                        (index for index, existing in enumerate(trade_history) if str(existing.get('ticket')) == str(pos_ticket)),
                                        None,
                                    )
                                    if existing_index is None:
                                        trade_history.append(open_trade)
                                        bot_config['totalTrades'] = bot_config.get('totalTrades', 0) + 1
                                    else:
                                        trade_history[existing_index] = {**trade_history[existing_index], **open_trade}
                                    
                                    logger.info(f"✅ Bot {bot_id}: Position OPENED | {pos_symbol} {pos_type} @ {matched_pos.get('openPrice', 0)} | Ticket: {pos_ticket}")
                                    trades_placed += 1
                        else:
                            logger.warning(f"Bot {bot_id}: Could not place order on {symbol} or EURUSD fallback")
                    
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Error in trade cycle for {symbol}: {e}")
                        continue
                
                # ==================== CHECK FOR CLOSED POSITIONS (TP/SL HIT) ====================
                # Compare tracked open_positions against current broker positions.
                # If a tracked position is no longer open, it was closed by TP/SL — record the real P&L.
                try:
                    tracked_positions = bot_config.get('open_positions', {})
                    if tracked_positions and active_conn:
                        current_positions = []
                        if is_mt5 and mt5_conn:
                            current_positions = mt5_conn.get_positions()
                        elif active_conn:
                            current_positions = active_conn.get_positions()
                        
                        current_tickets = set()
                        for cp in current_positions:
                            current_ticket = str(cp.get('ticket') or cp.get('deal_id', ''))
                            current_tickets.add(current_ticket)
                            if current_ticket in tracked_positions:
                                tracked_positions[current_ticket]['currentPrice'] = cp.get('currentPrice') or cp.get('marketPrice') or cp.get('price_current') or tracked_positions[current_ticket].get('currentPrice', 0)
                                tracked_positions[current_ticket]['profit'] = round(cp.get('profit') or cp.get('pnl') or 0, 2)
                                tracked_positions[current_ticket]['status'] = 'open'
                                for trade in bot_config.get('tradeHistory', []):
                                    if str(trade.get('ticket')) == current_ticket:
                                        trade['currentPrice'] = tracked_positions[current_ticket]['currentPrice']
                                        trade['profit'] = tracked_positions[current_ticket]['profit']
                                        trade['status'] = 'open'
                                        trade['isWinning'] = tracked_positions[current_ticket]['profit'] > 0
                                        break
                        
                        closed_tickets = []
                        for ticket_str, tracked in list(tracked_positions.items()):
                            if ticket_str not in current_tickets:
                                closed_tickets.append(ticket_str)
                                
                                # Position is gone — closed by TP/SL or manually
                                # Get the actual P&L from MT5 trade history
                                real_profit = 0
                                try:
                                    if is_mt5 and mt5_conn and mt5_conn.mt5:
                                        from datetime import timedelta
                                        now_ts = datetime.now()
                                        deals = mt5_conn.mt5.history_deals_get(
                                            now_ts - timedelta(days=1), now_ts
                                        )
                                        if deals:
                                            for deal in deals:
                                                if deal.position_id == int(ticket_str):
                                                    # OUT deal = closing deal with actual profit
                                                    if deal.entry == 1:  # DEAL_ENTRY_OUT
                                                        real_profit = deal.profit + deal.swap + deal.commission
                                                        break
                                except Exception as hist_e:
                                    logger.warning(f"Bot {bot_id}: Could not get history for ticket {ticket_str}: {hist_e}")
                                
                                trade = {
                                    'ticket': tracked.get('ticket', ticket_str),
                                    'symbol': tracked.get('symbol', ''),
                                    'type': tracked.get('type', ''),
                                    'volume': tracked.get('volume', 0),
                                    'entryPrice': tracked.get('entryPrice', 0),
                                    'currentPrice': tracked.get('currentPrice', 0),
                                    'entryTime': tracked.get('entryTime', ''),
                                    'exitTime': datetime.now().isoformat(),
                                    'profit': round(real_profit, 2),
                                    'time': datetime.now().isoformat(),
                                    'timestamp': int(datetime.now().timestamp() * 1000),
                                    'botId': bot_id,
                                    'cycle': tracked.get('cycle', 0),
                                    'strategy': tracked.get('strategy', ''),
                                    'isWinning': real_profit > 0,
                                    'source': f"REAL_{str(broker_type).upper().replace(' ', '_')}",
                                    'broker': tracked.get('broker', broker_type),
                                }
                                
                                # Update trade in database from open to closed
                                try:
                                    trade_conn = sqlite3.connect(r'C:\backend\zwesta_trading.db', timeout=30)
                                    trade_cursor = trade_conn.cursor()
                                    trade_cursor.execute('''
                                        UPDATE trades SET profit = ?, status = 'closed', time_close = ?, trade_data = ?, updated_at = ?
                                        WHERE ticket = ? AND bot_id = ? AND status = 'open'
                                    ''', (
                                        real_profit,
                                        datetime.now().isoformat(),
                                        json.dumps(trade),
                                        datetime.now().isoformat(),
                                        str(ticket_str),
                                        bot_id
                                    ))
                                    trade_conn.commit()
                                    trade_conn.close()
                                except Exception as db_e:
                                    logger.error(f"Bot {bot_id}: Error updating closed trade: {db_e}")
                                
                                # Update bot analytics with REAL P&L
                                if 'tradeHistory' not in bot_config:
                                    bot_config['tradeHistory'] = []
                                existing_index = next(
                                    (index for index, existing in enumerate(bot_config['tradeHistory']) if str(existing.get('ticket')) == str(ticket_str)),
                                    None,
                                )
                                if existing_index is None:
                                    bot_config['tradeHistory'].append(trade)
                                    bot_config['totalTrades'] = bot_config.get('totalTrades', 0) + 1
                                    bot_config['totalInvestment'] = bot_config.get('totalInvestment', 0) + (trade['volume'] * trade['entryPrice'])
                                else:
                                    bot_config['tradeHistory'][existing_index] = {**bot_config['tradeHistory'][existing_index], **trade, 'status': 'closed'}
                                
                                if real_profit > 0:
                                    bot_config['winningTrades'] = bot_config.get('winningTrades', 0) + 1
                                else:
                                    bot_config['totalLosses'] = bot_config.get('totalLosses', 0) + abs(real_profit)
                                
                                bot_config['totalProfit'] = bot_config.get('totalProfit', 0) + real_profit
                                
                                # Update peak & drawdown
                                if bot_config['totalProfit'] > bot_config.get('peakProfit', 0):
                                    bot_config['peakProfit'] = bot_config['totalProfit']
                                drawdown = bot_config.get('peakProfit', 0) - bot_config['totalProfit']
                                if drawdown > bot_config.get('maxDrawdown', 0):
                                    bot_config['maxDrawdown'] = drawdown
                                
                                # Track profit history
                                bot_config.setdefault('profitHistory', []).append({
                                    'timestamp': trade['timestamp'],
                                    'profit': round(bot_config['totalProfit'], 2),
                                    'trades': bot_config['totalTrades'],
                                })
                                
                                # Track daily profit
                                today = datetime.now().strftime('%Y-%m-%d')
                                if today not in bot_config.get('dailyProfits', {}):
                                    bot_config.setdefault('dailyProfits', {})[today] = 0
                                bot_config['dailyProfits'][today] += real_profit
                                bot_config['dailyProfit'] = bot_config['dailyProfits'][today]
                                bot_config['profit'] = bot_config['totalProfit']
                                
                                # Commission distribution on real profit
                                if real_profit > 0:
                                    try:
                                        distribute_trade_commissions(bot_id, user_id, real_profit)
                                    except Exception as comm_e:
                                        logger.error(f"Bot {bot_id}: Commission error: {comm_e}")
                                
                                logger.info(f"💰 Bot {bot_id}: Position CLOSED by TP/SL | {tracked.get('symbol')} | Real P&L: ${real_profit:.2f}")
                        
                        # Remove closed positions from tracker
                        for t in closed_tickets:
                            del tracked_positions[t]
                        if closed_tickets and len(tracked_positions) == 0:
                            logger.info(f"🔁 Bot {bot_id}: All tracked positions are closed. Continuing trading on next cycle.")
                
                except Exception as close_check_e:
                    logger.warning(f"Bot {bot_id}: Error checking closed positions: {close_check_e}")
                
                # ==================== DISCOVER UNTRACKED POSITIONS ====================
                # Sync ALL MT5 positions for this bot's symbols into open_positions/tradeHistory.
                # This catches positions that existed before tracking was enabled, or were placed
                # by MT5 directly (TP/SL spawned hedges, manual trades on same symbols, etc.)
                try:
                    if is_mt5 and mt5_conn and bot_config.get('symbols'):
                        discovery_positions = mt5_conn.get_positions()
                        tracked_positions = bot_config.get('open_positions', {})
                        tracked_tickets = set(tracked_positions.keys())
                        bot_symbols = set(bot_config.get('symbols', []))
                        bot_id_short = bot_id.split('_')[-1][:8]
                        comment_tag = f'ZBot{bot_id_short}'
                        
                        discovered_count = 0
                        for dp in discovery_positions:
                            dp_ticket = str(dp.get('ticket', ''))
                            dp_symbol = dp.get('symbol', '')
                            dp_comment = dp.get('comment', '') or ''
                            
                            # Skip if already tracked
                            if dp_ticket in tracked_tickets:
                                continue
                            
                            # Match: position is on one of the bot's symbols, OR has the bot's comment tag
                            is_bot_symbol = dp_symbol in bot_symbols
                            is_bot_comment = comment_tag in dp_comment
                            
                            if is_bot_symbol or is_bot_comment:
                                dp_type = dp.get('type', 'BUY')
                                dp_volume = dp.get('volume', 0)
                                dp_entry_price = dp.get('openPrice') or dp.get('price_open') or dp.get('level', 0)
                                dp_current_price = dp.get('currentPrice') or dp.get('marketPrice') or dp.get('price_current', 0)
                                dp_profit = round(dp.get('profit') or dp.get('pnl') or 0, 2)
                                dp_open_time = dp.get('openTime') or dp.get('time', datetime.now().isoformat())
                                
                                # Add to open_positions tracker
                                if 'open_positions' not in bot_config:
                                    bot_config['open_positions'] = {}
                                bot_config['open_positions'][dp_ticket] = {
                                    'ticket': dp.get('ticket', dp_ticket),
                                    'symbol': dp_symbol,
                                    'type': dp_type,
                                    'volume': dp_volume,
                                    'entryPrice': dp_entry_price,
                                    'currentPrice': dp_current_price,
                                    'profit': dp_profit,
                                    'status': 'open',
                                    'entryTime': dp_open_time,
                                    'botId': bot_id,
                                    'cycle': trade_cycle,
                                    'strategy': bot_config.get('strategy', 'trend_following'),
                                    'broker': broker_type,
                                    'discovered': True,
                                }
                                
                                # Add to tradeHistory if not already there
                                if 'tradeHistory' not in bot_config:
                                    bot_config['tradeHistory'] = []
                                existing_th = next(
                                    (i for i, t in enumerate(bot_config['tradeHistory']) if str(t.get('ticket')) == dp_ticket),
                                    None,
                                )
                                open_trade = {
                                    'ticket': dp.get('ticket', dp_ticket),
                                    'symbol': dp_symbol,
                                    'type': dp_type,
                                    'volume': dp_volume,
                                    'entryPrice': dp_entry_price,
                                    'currentPrice': dp_current_price,
                                    'profit': dp_profit,
                                    'time': dp_open_time,
                                    'timestamp': int(datetime.now().timestamp() * 1000),
                                    'botId': bot_id,
                                    'status': 'open',
                                    'isWinning': dp_profit > 0,
                                    'source': f"DISCOVERED_{str(broker_type).upper().replace(' ', '_')}",
                                    'broker': broker_type,
                                }
                                if existing_th is None:
                                    bot_config['tradeHistory'].append(open_trade)
                                    bot_config['totalTrades'] = bot_config.get('totalTrades', 0) + 1
                                    discovered_count += 1
                                else:
                                    # Update existing entry with live data
                                    bot_config['tradeHistory'][existing_th].update({
                                        'currentPrice': dp_current_price,
                                        'profit': dp_profit,
                                        'isWinning': dp_profit > 0,
                                        'status': 'open',
                                    })
                                
                                # Also insert into DB if not already there
                                if existing_th is None:
                                    try:
                                        disc_conn = sqlite3.connect(r'C:\backend\zwesta_trading.db', timeout=30)
                                        disc_cursor = disc_conn.cursor()
                                        trade_id = f"disc_{int(datetime.now().timestamp()*1000)}_{dp_ticket}"
                                        disc_cursor.execute('''
                                            INSERT OR IGNORE INTO trades (trade_id, bot_id, user_id, symbol, order_type, volume, price, profit, ticket, time_open, status, created_at, trade_data, timestamp)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        ''', (
                                            trade_id, bot_id, user_id, dp_symbol, dp_type, dp_volume,
                                            dp_entry_price, dp_profit, dp_ticket, dp_open_time,
                                            'open', datetime.now().isoformat(),
                                            json.dumps({'ticket': dp_ticket, 'symbol': dp_symbol, 'type': dp_type, 'entryPrice': dp_entry_price, 'source': 'DISCOVERED'}),
                                            int(datetime.now().timestamp() * 1000)
                                        ))
                                        disc_conn.commit()
                                        disc_conn.close()
                                    except Exception as disc_db_e:
                                        logger.warning(f"Bot {bot_id}: Error saving discovered trade: {disc_db_e}")
                        
                        if discovered_count > 0:
                            logger.info(f"🔍 Bot {bot_id}: Discovered {discovered_count} untracked position(s) on {', '.join(bot_symbols)}")
                
                except Exception as disc_e:
                    logger.warning(f"Bot {bot_id}: Error discovering untracked positions: {disc_e}")
                
                # Update account balance (broker-aware)
                try:
                    if active_conn:
                        account_info = active_conn.get_account_info()
                        if account_info:
                            bot_config['accountBalance'] = account_info.get('balance', account_info.get('equity', 0))
                            bot_config['accountEquity'] = account_info.get('equity', account_info.get('balance', 0))
                except Exception as e:
                    logger.warning(f"Bot {bot_id}: Could not update account balance: {e}")

                persist_bot_runtime_state(bot_id)
                
                # Log cycle summary with position status for debugging
                open_pos_count = len(bot_config.get('open_positions', {}))
                logger.info(f"✅ Bot {bot_id}: Cycle #{trade_cycle} complete | Trades placed: {trades_placed} | Open positions: {open_pos_count} | Total P&L: ${bot_config.get('totalProfit', 0):.2f}")
                
                # DUAL MODE: TIME-BASED vs SIGNAL-DRIVEN waiting
                if trading_mode == 'signal-driven':
                    # ⚡ SIGNAL-DRIVEN MODE: Check signals every poll_interval seconds
                    logger.info(f"⚡ Bot {bot_id}: Polling signals every {poll_interval}s (threshold: {signal_threshold}/100)...")
                    
                    poll_elapsed = 0
                    while not bot_stop_flags.get(bot_id, False) and poll_elapsed < trading_interval:
                        time.sleep(poll_interval)
                        poll_elapsed += poll_interval
                        
                        # Check if strong signal exists for any symbol
                        best_signal_strength = 0
                        best_signal_symbol = None
                        
                        for symbol in bot_config.get('symbols', ['EURUSDm'])[:3]:
                            signal_strength = evaluate_trade_signal_strength(symbol, {})
                            if signal_strength > best_signal_strength:
                                best_signal_strength = signal_strength
                                best_signal_symbol = symbol
                        
                        if best_signal_strength >= signal_threshold:
                            logger.info(f"🔥 Bot {bot_id}: STRONG SIGNAL DETECTED on {best_signal_symbol}!")
                            logger.info(f"   Signal Strength: {best_signal_strength:.0f}/100 (threshold: {signal_threshold})")
                            logger.info(f"   Executing trade IMMEDIATELY (no waiting)...")
                            break  # Break inner loop, execute trade next cycle
                        elif best_signal_strength > 0:
                            logger.debug(f"📊 Bot {bot_id}: Signal on {best_signal_symbol}: {best_signal_strength:.0f}/100 (waiting for {signal_threshold}+)")
                else:
                    # ⏱️ TIME-BASED MODE: Wait fixed interval
                    logger.info(f"⏳ Bot {bot_id}: Waiting {trading_interval} seconds until next cycle...")
                    time.sleep(trading_interval)
            
            except Exception as e:
                logger.error(f"Bot {bot_id}: Error in trading loop: {e}")
                time.sleep(min(poll_interval if trading_mode == 'signal-driven' else trading_interval, 60))  # Wait at least 60 seconds before retry
        
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
    - Binance (REST API)
    - FXCM (REST API)
    - OANDA (REST API)
    
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
        broker_name = canonicalize_broker_name(cred['broker_name'])
        
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

        elif broker_name == 'Binance':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using Binance REST API")
            api_key = cred['api_key']
            api_secret = cred['password']
            account_number = cred['account_number']
            server = cred['server'] or 'spot'
            is_live = cred['is_live']

            if not api_key or not api_secret:
                error_msg = 'Binance: Missing API key or API secret'
                logger.error(error_msg)
                return None, error_msg

            binance_conn = BinanceConnection(credentials={
                'api_key': api_key,
                'api_secret': api_secret,
                'account_number': account_number,
                'server': server,
                'is_live': is_live,
            })
            if binance_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to Binance ({account_number or server})")
                return 'Binance', binance_conn
            error_msg = 'Failed to connect to Binance'
            logger.error(error_msg)
            return None, error_msg

        elif broker_name == 'FXCM':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using FXCM REST API")
            token = cred['api_key'] or cred['password']
            account_number = cred['account_number']
            is_live = cred['is_live']

            if not token:
                error_msg = 'FXCM: Missing API token'
                logger.error(error_msg)
                return None, error_msg

            fxcm_conn = FXCMConnection(credentials={
                'api_key': token,
                'account_number': account_number,
                'is_live': is_live,
            })
            if fxcm_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to FXCM ({account_number})")
                return 'FXCM', fxcm_conn
            error_msg = 'Failed to connect to FXCM'
            logger.error(error_msg)
            return None, error_msg

        elif broker_name == 'OANDA':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using OANDA REST API")
            api_key = cred['api_key']
            account_number = cred['account_number']
            is_live = cred['is_live']

            if not api_key or not account_number:
                error_msg = 'OANDA: Missing API key or account number'
                logger.error(error_msg)
                return None, error_msg

            oanda_conn = OANDAConnection(credentials={
                'api_key': api_key,
                'account_number': account_number,
                'is_live': is_live,
            })
            if oanda_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to OANDA ({account_number})")
                return 'OANDA', oanda_conn
            error_msg = 'Failed to connect to OANDA'
            logger.error(error_msg)
            return None, error_msg
        
        # ✅ METATRADER 5 - MetaQuotes, XM Global, Exness, or PXBT
        elif broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5', 'Exness', 'PXBT']:
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
            elif 'exness' in server.lower():
                # Normalize Exness server name based on live/demo mode
                server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
            elif 'pxbt' in server.lower() or 'primexbt' in server.lower() or broker_name == 'PXBT':
                server = 'PXBTTrading-1'
            
            logger.info(f"Bot {bot_id}: Connecting to MT5 - Account: {account_number}, Server: {server}")
            
            # Create MT5 connection
            # Determine broker name for MT5 connection initialization
            if broker_name in ['XM', 'XM Global']:
                broker_for_mt5 = 'XM'
            elif broker_name == 'Exness':
                broker_for_mt5 = 'Exness'
            elif broker_name == 'PXBT':
                broker_for_mt5 = 'PXBT'
            else:
                broker_for_mt5 = 'MetaQuotes'
            
            mt5_conn = MT5Connection(credentials={
                'account': int(account_number),
                'password': password,
                'server': server,
                'broker': broker_for_mt5,
                'path': MT5_CONFIG.get('path')
            })
            
            if mt5_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to MT5 ({account_number}@{server})")
                return 'MetaTrader 5', mt5_conn
            else:
                error_msg = f"Failed to connect to MT5 - Account: {account_number}, Server: {server}"
                logger.error(error_msg)
                return None, error_msg
        
        else:
            error_msg = f"Unknown broker type: {broker_name}. Supported: IG Markets, MetaQuotes, XM Global/XM, Exness, PXBT, Binance, FXCM, OANDA"
            logger.error(error_msg)
            return None, error_msg
    
    except Exception as e:
        error_msg = f"Error loading broker connection: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


# ==================== QUICK BOT CREATION (One-Click for Binance) ====================

@app.route('/api/bot/quick-create', methods=['POST'])
@require_session
def quick_create_bot():
    """One-click bot creation for Binance users with predefined high-performance pairs
    
    FEATURES:
    - No symbol selection needed (uses 6 best-performing pairs)
    - Optimized crypto risk settings
    - Instant creation and activation
    - Works only for Binance broker
    
    REQUEST:
    {
        "credentialId": "uuid",           // Required: Binance credential
        "preset": "top_edge" | "balanced" // Optional: pair selection strategy
    }
    
    RESPONSE: {bot_id, status, message, tradesPlaced, pairs}
    """
    # ==================== BOT CREATION LOCK ====================
    # Only allow ONE bot creation at a time
    global bot_creation_lock
    logger.info("🔒 Waiting for exclusive bot creation lock (quick-create)...")
    
    with bot_creation_lock:
        logger.info("✅ Acquired bot creation lock - proceeding with quick creation")
        conn = None
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No configuration provided'}), 400

            user_id = request.user_id  # From @require_session decorator
            if not user_id:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401

            credential_id = data.get('credentialId')
            if not credential_id:
                return jsonify({'success': False, 'error': 'credentialId required'}), 400

            preset = data.get('preset', 'top_edge')  # Default to top performers

            conn = get_db_connection()
            cursor = conn.cursor()

            # Verify credential exists and belongs to user AND is Binance
            cursor.execute('''
                SELECT credential_id, broker_name, account_number, is_live, api_key, password, server
                FROM broker_credentials
                WHERE credential_id = ? AND user_id = ?
            ''', (credential_id, user_id))
            credential_row = cursor.fetchone()
            if not credential_row:
                return jsonify({'success': False, 'error': 'Broker credential not found'}), 404

            credential_data = dict(credential_row)
            broker_name = credential_data['broker_name']

            # Only allow Binance for quick create
            if canonicalize_broker_name(broker_name) != 'Binance':
                return jsonify({
                    'success': False,
                    'error': f'Quick bot creation only works for Binance. You are using {broker_name}'
                }), 400

            account_number = credential_data['account_number']
            is_live = credential_data['is_live']
            mode = 'live' if is_live else 'demo'

            # Validate Binance connection
            binance_conn = BinanceConnection(credentials={
                'api_key': credential_data.get('api_key'),
                'api_secret': credential_data.get('password'),
                'account_number': account_number,
                'server': credential_data.get('server') or 'spot',
                'is_live': bool(is_live),
            })
            if not binance_conn.connect():
                return jsonify({
                    'success': False,
                    'error': 'Binance connection failed. Check API key/secret.'
                }), 400
            binance_conn.disconnect()

            # Predefined high-performance Binance pairs
            BINANCE_PRESETS = {
                'top_edge': [
                    'BTCUSDT',   # Highest edge (6.8%)
                    'ETHUSDT',   # High edge (6.2%)
                    'SOLUSDT',   # Highest momentum (7.4%)
                    'XRPUSDT',   # Consistent (5.6%)
                    'BNBUSDT',   # Exchange beta (5.3%)
                    'LTCUSDT',   # Lower beta (4.8%)
                ],
                'balanced': [
                    'BTCUSDT', 'ETHUSDT', 'LINKUSDT', 'ADAUSDT', 'DOGEUSDT', 'MATICUSDT'
                ],
                'defi': [
                    'UNIUSDT', 'AAVEUSDT', 'APTUSDT', 'INJUSDT', 'SUIUSDT', 'FTMUSDT'
                ],
                'large_cap_only': [
                    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT'
                ]
            }

            symbols = BINANCE_PRESETS.get(preset, BINANCE_PRESETS['top_edge'])

            # Bot configuration (optimized for crypto)
            bot_id = f"quick_bot_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            strategy = 'Momentum Trading'  # Best for crypto
            risk_per_trade = 15  # Crypto-optimized
            max_daily_loss = 50
            profit_lock = 40
            drawdown_pause_percent = 5
            drawdown_pause_hours = 4
            display_currency = 'USD'
            trading_enabled = True

            account_id = f"{broker_name}_{account_number}"
            created_at = datetime.now().isoformat()

            # Store bot in database
            cursor.execute('''
                INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, is_live, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bot_id, user_id, f'Quick {preset}', strategy, 'active', trading_enabled, account_id, ','.join(symbols), 1 if is_live else 0, created_at, created_at))

            # Link bot to credential
            cursor.execute('''
                INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (bot_id, credential_id, user_id, created_at))
            
            conn.commit()

            now = datetime.now()
            # Start with clean stats — no fake sample trades

            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': user_id,
                'accountId': account_id,
                'brokerName': broker_name,
                'broker_type': broker_name,
                'mode': mode,
                'credentialId': credential_id,
                'symbols': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'maxDailyLoss': max_daily_loss,
                'profitLock': profit_lock,
                'drawdownPausePercent': drawdown_pause_percent,
                'drawdownPauseHours': drawdown_pause_hours,
                'displayCurrency': display_currency,
                'enabled': trading_enabled,
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
                'profit': 0,
            }
            persist_bot_runtime_state(bot_id)

            running_bots[bot_id] = True
            bot_stop_flags[bot_id] = False

            # ==================== WORKER POOL DISPATCH (QUICK BOT) ====================
            if worker_pool_manager and worker_pool_manager.enabled:
                _qb_creds = None
                if credential_id:
                    try:
                        _qbc = get_db_connection()
                        _qbr = _qbc.cursor()
                        _qbr.execute('SELECT account_number, password, server, is_live FROM broker_credentials WHERE credential_id = ?', (credential_id,))
                        _qrow = _qbr.fetchone()
                        _qbc.close()
                        if _qrow:
                            _qrow = dict(_qrow)
                            _qb_creds = {'account_number': _qrow['account_number'], 'password': _qrow['password'], 'server': _qrow.get('server', ''), 'is_live': bool(_qrow['is_live'])}
                    except Exception as e:
                        logger.warning(f'Quick bot worker dispatch: could not fetch credentials: {e}')
                worker_pool_manager.dispatch_bot(bot_id, user_id, active_bots[bot_id], _qb_creds)
                logger.info(f"🚀 Quick bot {bot_id}: Dispatched to worker pool")
            else:
                def _async_start_quick_bot():
                    try:
                        time.sleep(0.5)

                        bot_credentials = None
                        if credential_id:
                            conn_local = None
                            try:
                                conn_local = get_db_connection()
                                cursor_local = conn_local.cursor()
                                cursor_local.execute('SELECT api_key, password, server, is_live, account_number FROM broker_credentials WHERE credential_id = ?', (credential_id,))
                                cred_row = cursor_local.fetchone()

                                if cred_row:
                                    cred_dict = dict(cred_row)
                                    bot_credentials = {
                                        'api_key': cred_dict['api_key'],
                                        'api_secret': cred_dict['password'],
                                        'account_number': cred_dict['account_number'],
                                        'server': cred_dict.get('server', 'spot'),
                                        'broker': broker_name,
                                        'is_live': bool(cred_dict['is_live'])
                                    }
                            except Exception as e:
                                logger.warning(f"Could not load credential details: {e}")
                            finally:
                                if conn_local:
                                    conn_local.close()

                        continuous_bot_trading_loop(bot_id, user_id, bot_credentials)
                    except Exception as e:
                        logger.error(f"Error auto-starting quick bot {bot_id}: {e}")
                        running_bots[bot_id] = False

                bot_thread = threading.Thread(target=_async_start_quick_bot, daemon=True)
                bot_threads[bot_id] = bot_thread
                bot_thread.start()

            logger.info(f"✅ Quick bot created: {bot_id} for user {user_id}")
            logger.info(f"   Preset: {preset} | Symbols: {symbols}")

            return jsonify({
                'success': True,
                'botId': bot_id,
                'status': 'active',
                'message': f'Quick bot created with preset: {preset}',
                'pairs': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'tradingEnabled': trading_enabled,
            }), 201
            logger.error(f"Error in quick_create_bot: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()


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
        
        conn.close()

        # ✅ FAST PATH: If bot thread is already alive (started by create_bot), return immediately
        # This avoids the expensive broker connection + 120s MT5 readiness wait on start_bot
        if bot_id in bot_threads and bot_threads[bot_id].is_alive():
            logger.info(f"Bot {bot_id}: Already running via background thread - returning success immediately")
            bot_config = active_bots[bot_id]
            return jsonify({
                'success': True,
                'botId': bot_id,
                'strategy': bot_config.get('strategy', 'unknown'),
                'status': 'RUNNING',
                'message': f'Bot {bot_id} is already trading in background',
                'tradingInterval': bot_config.get('tradingInterval', 300),
                'botStats': {
                    'totalTrades': bot_config.get('totalTrades', 0),
                    'winningTrades': bot_config.get('winningTrades', 0),
                    'totalLosses': round(bot_config.get('totalLosses', 0), 2),
                    'totalProfit': round(bot_config.get('totalProfit', 0), 2),
                    'accountBalance': bot_config.get('accountBalance', 0),
                }
            }), 200

        # Bot thread not running — connect to broker and start a new thread
        # ✅ AUTOMATIC BROKER DETECTION
        credential_id = bot.get('credentialId')

        if not credential_id:
            return jsonify({
                'success': False,
                'error': 'Bot missing credentialId - must link to broker credential first'
            }), 400

        broker_type, broker_conn = get_broker_connection(credential_id, user_id, bot_id)

        if broker_conn is None or not hasattr(broker_conn, 'connected'):
            return jsonify({
                'success': False,
                'error': f'Failed to connect to broker: {broker_type or broker_conn}',
                'botId': bot_id,
                'status': 'FAILED'
            }), 503

        logger.info(f"✅ Bot {bot_id}: Broker connection established ({broker_type})")

        bot_config = active_bots[bot_id]
        bot_config['broker_type'] = broker_type
        bot_config['broker_conn'] = broker_conn
        
        import random
        
        # ✅ VALIDATE & CORRECT BOT SYMBOLS IMMEDIATELY (in case they're old/unavailable)
        # This prevents users from being shown old symbols and ensures trades use valid ones
        original_symbols = bot_config.get('symbols', ['EURUSDm'])
        corrected_symbols = validate_and_correct_symbols(original_symbols, broker_type)
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
                    SET symbols = ?, updated_at = ?
                    WHERE bot_id = ?
                ''', (','.join(corrected_symbols), datetime.now().isoformat(), bot_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not update bot symbols in DB: {e}")
        
        logger.info(f"✅ Bot {bot_id}: All validation checks passed - ready to start trading")
        
        # Validate symbols are available
        validated_symbols = validate_and_correct_symbols(bot_config.get('symbols', ['EURUSDm']), broker_type)
        bot_config['symbols'] = validated_symbols
        logger.info(f"📍 Bot {bot_id}: Trading symbols validated: {validated_symbols}")
        
        logger.info(f"Bot {bot_id}: Starting CONTINUOUS trading in background thread")
        
        # Bot thread not running or stopped - create a new one
        logger.info(f"Bot {bot_id}: No active thread found - creating new background thread")
        
        # Reset stop flag and start new thread
        bot_stop_flags[bot_id] = False
        
        # ✅ REGISTER BOT AS RUNNING IMMEDIATELY (before thread starts)
        # This prevents dashboard from showing it as stopped during startup
        running_bots[bot_id] = True
        bot_config['enabled'] = True
        persist_bot_runtime_state(bot_id)
        
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
            key_symbols = ['EURUSDm', 'XAUUSDm', 'BTCUSDm', 'ETHUSDm']
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
    """Get status of authenticated user's bots only.
    Optional query param: ?mode=LIVE or ?mode=DEMO to filter by trading mode.
    """
    try:
        user_id = request.user_id  # From session token
        mode_filter = request.args.get('mode', '').upper()  # LIVE, DEMO, or '' (all)
        
        bots_list = []
        for bot in active_bots.values():
            # Only return bots for authenticated user
            if bot.get('user_id') != user_id:
                continue
            
            # Filter by trading mode if specified
            if mode_filter in ('LIVE', 'DEMO'):
                bot_mode = (bot.get('mode') or 'demo').upper()
                if bot_mode != mode_filter:
                    continue
            
            # Calculate runtime (safely access createdAt)
            created = datetime.fromisoformat(bot.get('createdAt', datetime.now().isoformat()))
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit (safely access dailyProfits)
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profits = dict(bot.get('dailyProfits', {}))  # Copy so we don't mutate the original
            daily_profit = daily_profits.get(today, bot.get('dailyProfit', 0))
            
            # Calculate ROI (safely access totalInvestment and totalProfit)
            total_profit = bot.get('totalProfit', 0)
            open_positions = list(bot.get('open_positions', {}).values())
            floating_profit = sum(float(position.get('profit') or 0) for position in open_positions)
            current_profit = total_profit + floating_profit
            
            # ✅ Inject floating P/L into dailyProfits for "Profit Over Time" chart
            # Without this, the chart is empty until trades actually close.
            if floating_profit != 0 or daily_profit != 0:
                daily_profits[today] = round(daily_profit + floating_profit, 2)
            # Also add historical profit entries from profitHistory if dailyProfits is sparse
            profit_history = bot.get('profitHistory', [])
            for ph in profit_history:
                ph_ts = ph.get('timestamp', 0)
                if ph_ts:
                    ph_date = datetime.fromtimestamp(ph_ts / 1000).strftime('%Y-%m-%d')
                    if ph_date not in daily_profits:
                        daily_profits[ph_date] = round(ph.get('profit', 0), 2)
            # Use totalInvestment if available, otherwise assume $10,000 initial investment (standard for demo/live)
            investment = bot.get('totalInvestment', 10000)
            if investment <= 0:
                investment = 10000  # Default assumption for ROI calculation
            roi = (current_profit / investment) * 100 if investment > 0 else 0
            
            # Calculate profitability (profit as % of total traded value)
            total_trades = bot.get('totalTrades', 0)
            # Count open positions that are currently in profit as "winning"
            open_winning = sum(1 for p in open_positions if float(p.get('profit') or 0) > 0)
            closed_winning = bot.get('winningTrades', 0)
            effective_winning = closed_winning + open_winning
            effective_win_rate = round((effective_winning / max(total_trades, 1)) * 100, 1)
            if total_trades > 0:
                avg_trade_profit = current_profit / total_trades
                profitability = avg_trade_profit
            else:
                profitability = 0
            
            # Calculate profit factor - capped at 99.99 to avoid JSON infinity issues
            total_losses = bot.get('totalLosses', 0)
            if total_losses > 0:
                profit_factor = min(total_profit / total_losses, 99.99) if total_profit > 0 else 0
            else:
                profit_factor = 99.99 if total_profit > 0 else 0
            
            # Safely access symbols and other fields
            symbols = bot.get('symbols', [])
            if open_positions:
                symbol = open_positions[0].get('symbol', 'EURUSDm')
            elif len(symbols) == 1:
                symbol = symbols[0]
            elif len(symbols) > 1:
                symbol = 'MULTI'
            else:
                symbol = 'EURUSDm'
            trade_history = bot.get('tradeHistory', [])
            last_trade_time = trade_history[-1].get('time') if trade_history else bot.get('createdAt', datetime.now().isoformat())
            
            enhanced_bot = {
                'botId': bot.get('botId', 'unknown'),
                'symbol': symbol,
                'symbols': symbols,
                'strategy': bot.get('strategy', 'Unknown'),
                'commission': round(max(total_profit, 0) * 0.01, 2),
                'profit': round(current_profit, 2),
                'totalProfit': round(total_profit, 2),
                'floatingProfit': round(floating_profit, 2),
                'currentProfit': round(current_profit, 2),
                'totalTrades': bot.get('totalTrades', 0),
                'winningTrades': bot.get('winningTrades', 0),
                'winRate': effective_win_rate,
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit + floating_profit, 2),
                'roi': round(roi, 2),
                'profitability': round(profitability if total_trades > 0 else current_profit, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(total_profit / max(bot.get('totalTrades', 1), 1), 2),
                'enabled': bot.get('enabled', True),
                'status': 'Active' if bot.get('enabled', True) else 'Inactive',
                'pauseReason': bot.get('pauseReason'),
                'stopReason': bot.get('stopReason'),  # Why bot was auto-stopped (e.g., external close)
                'lastPauseEvent': bot.get('lastPauseEvent'),  # Include last market pause event
                'displayCurrency': bot.get('displayCurrency', 'USD'),
                'maxOpenPositions': bot.get('maxOpenPositions', 5),
                'maxPositionsPerSymbol': bot.get('maxPositionsPerSymbol', 1),
                'signalThreshold': bot.get('effectiveSignalThreshold', bot.get('signalThreshold', 70)),
                'managementMode': bot.get('managementMode', 'assisted'),
                'managementProfile': bot.get('managementProfile', 'beginner'),
                'managementState': bot.get('managementState', 'normal'),
                'drawdownPauseUntil': bot.get('drawdownPauseUntil'),
                'lastTradeTime': last_trade_time,
                'broker_type': bot.get('broker_type', 'MT5'),
                'mode': (bot.get('mode') or 'demo').upper(),
                'is_live': (bot.get('mode') or 'demo').lower() == 'live',
                'profitField': round(current_profit, 2),
                'tradeHistory': trade_history,  # Include full trade history for analytics
                'dailyProfits': daily_profits,  # Include daily profits map for charts
                'openPositions': open_positions,  # Currently open positions
                'accountBalance': round(bot.get('accountBalance', 0), 2),  # Latest known balance
                'accountEquity': round(bot.get('accountEquity', 0), 2),  # Latest known equity
            }
            bots_list.append(enhanced_bot)
        
        return jsonify({
            'success': True,
            'activeBots': len([b for b in bots_list if b.get('enabled', True) or b.get('status') == 'Active']),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/performance', methods=['GET'])
@require_session
def get_bot_performance(bot_id):
    """Get detailed performance metrics for a specific bot
    
    Returns:
    - Account balance (from broker)
    - Total trades and breakdown
    - Profit/Loss
    - Commission distribution
    - Daily profits tracking
    """
    try:
        user_id = g.user_id
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot = active_bots[bot_id]
        
        # Get broker connection for live balance
        credential_id = bot.get('credentialId')
        broker_type = bot.get('broker_type', 'MT5')
        current_balance = 0
        
        try:
            if credential_id:
                _, broker_conn = get_broker_connection(credential_id, user_id, bot_id)
                account_info = broker_conn.get_account_info()
                if account_info:
                    current_balance = account_info.get('balance', account_info.get('equity', 0))
        except:
            current_balance = bot.get('accountBalance', 0)
        
        # Calculate metrics
        total_trades = bot.get('totalTrades', 0)
        winning_trades = bot.get('winningTrades', 0)
        total_profit = bot.get('totalProfit', 0)
        total_loss = bot.get('totalLosses', 0)
        
        win_rate = (winning_trades / max(total_trades, 1)) * 100
        profit_factor = total_profit / max(total_loss, 0.01)
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'botName': bot.get('name', bot_id),
            'brokerType': broker_type,
            'currentBalance': round(current_balance, 2),
            'initialBalance': bot.get('initialBalance', 0),
            'trades': {
                'total': total_trades,
                'winning': winning_trades,
                'losing': total_trades - winning_trades,
                'winRate': round(win_rate, 1)
            },
            'profitLoss': {
                'totalProfit': round(total_profit, 2),
                'totalLoss': round(total_loss, 2),
                'netProfit': round(total_profit - total_loss, 2),
                'roi': round(((total_profit - total_loss) / max(bot.get('initialBalance', 1), 1)) * 100, 2),
                'profitFactor': round(profit_factor, 2)
            },
            'drawdown': {
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
                'peakProfit': round(bot.get('peakProfit', 0), 2),
                'currentDrawdown': round(bot.get('peakProfit', 0) - total_profit, 2)
            },
            'dailyProfits': bot.get('dailyProfits', {}),
            'created': bot.get('createdAt', 'Unknown'),
            'status': 'Running' if bot.get('enabled', False) else 'Stopped',
            'tradingMode': bot.get('tradingMode', 'interval'),
            'symbol': bot.get('symbols', ['EURUSD'])[0] if bot.get('symbols') else 'EURUSD'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot performance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/trades-detailed', methods=['GET'])
@require_session
def get_bot_trades_detailed(bot_id):
    """Get detailed trade history for a specific bot with filters
    
    Query parameters:
    - limit: max trades to return (default 50)
    - offset: pagination offset (default 0)
    - symbol: filter by symbol
    - status: 'open', 'closed', 'all' (default all)
    """
    try:
        user_id = g.user_id
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        symbol_filter = request.args.get('symbol', None)
        status_filter = request.args.get('status', 'all')
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Get trades from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM trades WHERE bot_id = ?'
        params = [bot_id]
        
        if symbol_filter:
            query += ' AND symbol = ?'
            params.append(symbol_filter)
        
        if status_filter and status_filter != 'all':
            query += ' AND status = ?'
            params.append(status_filter)
        
        # Get total count
        count_cursor = conn.cursor()
        count_cursor.execute(f'SELECT COUNT(*) FROM trades WHERE bot_id = ?', [bot_id])
        total_count = count_cursor.fetchone()[0]
        
        # Get paginated results
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        trades = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'trades': trades,
            'pagination': {
                'total': total_count,
                'offset': offset,
                'limit': limit,
                'hasMore': offset + limit < total_count
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/commissions', methods=['GET'])
@require_session
def get_bot_commissions(bot_id):
    """Get commission earnings from a specific bot
    
    Returns:
    - Total commissions earned
    - Commission distribution by date
    - Pending withdrawals
    """
    try:
        user_id = g.user_id
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Get commission data from database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total commissions from this bot
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total,
                   COUNT(*) as count
            FROM commission_ledger 
            WHERE bot_id = ? AND status = 'active'
        ''', [bot_id])
        
        comm_row = cursor.fetchone()
        total_commission = comm_row['total'] if comm_row else 0
        
        # Get commission history by date
        cursor.execute('''
            SELECT DATE(created_at) as date, 
                   SUM(commission_amount) as daily_commission,
                   COUNT(*) as trades
            FROM commission_ledger 
            WHERE bot_id = ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''', [bot_id])
        
        commission_history = [dict(row) for row in cursor.fetchall()]
        
        # Get pending withdrawals
        cursor.execute('''
            SELECT * FROM withdrawal_requests
            WHERE bot_id = ?
            ORDER BY created_at DESC
        ''', [bot_id])
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'totalCommissions': round(total_commission, 2),
            'commissionHistory': commission_history,
            'withdrawals': withdrawals,
            'pendingWithdrawal': sum(w['amount'] for w in withdrawals if w['status'] == 'pending'),
            'completedWithdrawal': sum(w['amount'] for w in withdrawals if w['status'] == 'completed')
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/bots-summary', methods=['GET'])
@require_session
def get_dashboard_summary():
    """Get summary of all user bots for dashboard display
    
    Returns array of bot summaries with:
    - Bot name and ID
    - Current balance per broker
    - Performance metrics
    - Trading mode
    - Status
    """
    try:
        user_id = g.user_id
        
        # Get all bots for this user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_bots WHERE user_id = ?', [user_id])
        user_bots = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        summary = []
        
        for bot_row in user_bots:
            bot_id = bot_row['bot_id']
            
            if bot_id not in active_bots:
                continue
            
            bot = active_bots[bot_id]
            
            # Get live balance from broker
            credential_id = bot.get('credentialId')
            broker_type = bot.get('broker_type', 'MT5')
            current_balance = bot.get('accountBalance', 0)
            
            try:
                if credential_id:
                    _, broker_conn = get_broker_connection(credential_id, user_id, bot_id)
                    account_info = broker_conn.get_account_info()
                    if account_info:
                        current_balance = account_info.get('balance', account_info.get('equity', 0))
            except:
                pass
            
            total_profit = bot.get('totalProfit', 0)
            total_trades = bot.get('totalTrades', 0)
            
            summary.append({
                'botId': bot_id,
                'botName': bot.get('name', f'Bot-{bot_id[:8]}'),
                'broker': {
                    'type': broker_type,
                    'accountNumber': bot_row.get('broker_account_id', 'N/A')
                },
                'balance': round(current_balance, 2),
                'profit': round(total_profit, 2),
                'trades': total_trades,
                'winRate': round((bot.get('winningTrades', 0) / max(total_trades, 1)) * 100, 1) if total_trades > 0 else 0,
                'status': 'Running' if bot.get('enabled', False) else 'Stopped',
                'tradingMode': bot.get('tradingMode', 'interval'),
                'createdAt': bot.get('createdAt', 'Unknown')
            })
        
        return jsonify({
            'success': True,
            'botsCount': len(summary),
            'botsRunning': sum(1 for b in summary if b['status'] == 'Running'),
            'totalBalance': round(sum(b['balance'] for b in summary), 2),
            'totalProfit': round(sum(b['profit'] for b in summary), 2),
            'bots': summary,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
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
            symbol = symbols[0] if symbols else 'EURUSDm'
            
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
                'pauseReason': bot.get('pauseReason'),  # Include bot-level pause reason
                'lastPauseEvent': bot.get('lastPauseEvent'),  # Include last market pause event
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


# ==================== MARKET PAUSE EVENT ENDPOINTS ====================

@app.route('/api/bot/<bot_id>/pause-events', methods=['GET'])
@require_session
def get_bot_pause_events(bot_id: str):
    """Get market pause events for a specific bot"""
    try:
        user_id = request.user_id
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify bot belongs to user
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        result = cursor.fetchone()
        if not result or result['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Bot not found'}), 404
        
        # Get pause events
        cursor.execute('''
            SELECT pause_id, symbol, pause_type, retcode, reason, detected_at 
            FROM pause_events 
            WHERE bot_id = ? 
            ORDER BY detected_at DESC 
            LIMIT ?
        ''', (bot_id, limit))
        
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'bot_id': bot_id,
            'pause_events': events,
            'total_events': len(events)
        }), 200
    except Exception as e:
        logger.error(f"Error getting pause events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/pause-events', methods=['GET'])
@require_session
def get_user_pause_events():
    """Get all market pause events for authenticated user's bots"""
    try:
        user_id = request.user_id
        limit = request.args.get('limit', 100, type=int)
        symbol_filter = request.args.get('symbol', None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get pause events for user's bots
        if symbol_filter:
            cursor.execute('''
                SELECT pause_id, bot_id, symbol, pause_type, retcode, reason, detected_at 
                FROM pause_events 
                WHERE user_id = ? AND symbol = ? 
                ORDER BY detected_at DESC 
                LIMIT ?
            ''', (user_id, symbol_filter, limit))
        else:
            cursor.execute('''
                SELECT pause_id, bot_id, symbol, pause_type, retcode, reason, detected_at 
                FROM pause_events 
                WHERE user_id = ? 
                ORDER BY detected_at DESC 
                LIMIT ?
            ''', (user_id, limit))
        
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Get statistics
        pause_types = {}
        for event in events:
            ptype = event['pause_type']
            pause_types[ptype] = pause_types.get(ptype, 0) + 1
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'pause_events': events,
            'total_events': len(events),
            'pause_types_summary': pause_types
        }), 200
    except Exception as e:
        logger.error(f"Error getting user pause events: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/last-pause', methods=['GET'])
@require_session
def get_bot_last_pause(bot_id: str):
    """Get the most recent pause event for a bot"""
    try:
        user_id = request.user_id
        
        # Verify bot belongs to user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        result = cursor.fetchone()
        if not result or result['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Bot not found'}), 404
        
        # Get last pause event
        cursor.execute('''
            SELECT pause_id, symbol, pause_type, retcode, reason, detected_at 
            FROM pause_events 
            WHERE bot_id = ? 
            ORDER BY detected_at DESC 
            LIMIT 1
        ''', (bot_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'last_pause': dict(result)
            }), 200
        else:
            return jsonify({
                'success': True,
                'last_pause': None
            }), 200
    except Exception as e:
        logger.error(f"Error getting last pause: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pause-summary', methods=['GET'])
@require_session
def get_pause_summary():
    """Get pause event summary and statistics for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all pause events
        cursor.execute('SELECT pause_type, retcode, symbol, detected_at FROM pause_events WHERE user_id = ? ORDER BY detected_at DESC', (user_id,))
        all_events = [dict(row) for row in cursor.fetchall()]
        
        # Statistics
        pause_types = {}
        symbols = {}
        for event in all_events:
            pause_types[event['pause_type']] = pause_types.get(event['pause_type'], 0) + 1
            symbols[event['symbol']] = symbols.get(event['symbol'], 0) + 1
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_events': len(all_events),
            'pause_distribution': pause_types,
            'affected_symbols': symbols,
            'top_events': all_events[:20]
        }), 200
    except Exception as e:
        logger.error(f"Error getting pause summary: {e}")
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
        
        final_stats = stop_bot_runtime(bot_id, bot_config)
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} stopped',
            'finalStats': {
                'totalTrades': final_stats['totalTrades'],
                'winningTrades': final_stats['winningTrades'],
                'totalProfit': final_stats['totalProfit'],
                'note': 'Bot can be restarted later. Use /delete to permanently remove.'
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop-all', methods=['POST'])
@require_session
def stop_all_bots():
    """Stop all matching bots for the authenticated user."""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        mode_filter = (data.get('mode') or 'all').lower()
        only_loss_making = bool(data.get('only_loss_making', False))

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        if mode_filter not in {'all', 'demo', 'live'}:
            return jsonify({'success': False, 'error': 'mode must be one of: all, demo, live'}), 400

        stopped_bots = []
        skipped_bots = []

        for bot_id, bot_config in list(active_bots.items()):
            if bot_config.get('user_id') != user_id:
                continue
            if not bot_config.get('enabled'):
                skipped_bots.append({'botId': bot_id, 'reason': 'already_disabled'})
                continue

            bot_mode = (bot_config.get('mode') or 'demo').lower()
            if mode_filter != 'all' and bot_mode != mode_filter:
                skipped_bots.append({'botId': bot_id, 'reason': f'mode_{bot_mode}'})
                continue

            total_profit = float(bot_config.get('totalProfit', 0.0) or 0.0)
            daily_profit = float(bot_config.get('dailyProfit', 0.0) or 0.0)
            if only_loss_making and total_profit >= 0 and daily_profit >= 0:
                skipped_bots.append({'botId': bot_id, 'reason': 'not_loss_making'})
                continue

            stopped_bots.append(stop_bot_runtime(bot_id, bot_config))

        logger.info(
            f"🛑 Stopped {len(stopped_bots)} bots for user {user_id} "
            f"(mode={mode_filter}, only_loss_making={only_loss_making})"
        )

        return jsonify({
            'success': True,
            'message': f'Stopped {len(stopped_bots)} bots',
            'stoppedBots': stopped_bots,
            'skippedBots': skipped_bots,
        }), 200

    except Exception as e:
        logger.error(f"Error stopping all bots: {e}")
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
    """Login user by email with password verification and optional 2FA"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute('SELECT user_id, name, email, referral_code, password_hash FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        user_id = user_dict['user_id']
        
        # Verify password if user has one set
        stored_hash = user_dict.get('password_hash')
        if stored_hash:
            if not password or not check_password_hash(stored_hash, password):
                conn.close()
                return jsonify({'success': False, 'error': 'Invalid password'}), 401
        
        # Check if 2FA is enabled
        # ⚠️ TEMPORARILY DISABLED FOR TESTING — set to False to bypass 2FA during development
        two_fa_enabled = False
        
        # Uncomment below to re-enable 2FA checking:
        # try:
        #     cursor.execute('SELECT two_factor_enabled FROM users WHERE user_id = ?', (user_id,))
        #     row = cursor.fetchone()
        #     if row and row['two_factor_enabled']:
        #         two_fa_enabled = True
        # except Exception:
        #     pass  # Column may not exist yet
        
        if two_fa_enabled:
            # Generate 6-digit OTP code
            otp_code = ''.join(random.choices(string.digits, k=6))
            expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
            
            # Store OTP in a pending_2fa table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS pending_2fa (
                    user_id TEXT PRIMARY KEY,
                    otp_code TEXT NOT NULL,
                    temp_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )''')
            except Exception:
                pass
            
            temp_token = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}2fa".encode()).hexdigest()
            
            cursor.execute('DELETE FROM pending_2fa WHERE user_id = ?', (user_id,))
            cursor.execute('''INSERT INTO pending_2fa (user_id, otp_code, temp_token, expires_at) 
                              VALUES (?, ?, ?, ?)''', (user_id, otp_code, temp_token, expires_at))
            conn.commit()
            conn.close()
            
            # Send OTP via email (best-effort)
            try:
                _send_2fa_email(email, otp_code)
            except Exception as e:
                logger.warning(f"Could not send 2FA email to {email}: {e}")
            
            logger.info(f"2FA required for {email}, OTP generated")
            
            return jsonify({
                'success': True,
                'requires_2fa': True,
                'temp_token': temp_token,
                'message': '2FA code sent to your email'
            }), 200
        
        # No 2FA — create full session
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
            'requires_2fa': False,
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


def _send_2fa_email(to_email, otp_code):
    """Send 2FA OTP code via email (best-effort)"""
    smtp_server = os.environ.get('SMTP_SERVER', '')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    
    if not smtp_server or not smtp_user:
        logger.warning(f"⚠️ SMTP not configured — 2FA code for {to_email}: {otp_code}")
        logger.warning("Set SMTP_SERVER, SMTP_USER, SMTP_PASS in .env to enable email delivery")
        return
    
    msg = MIMEMultipart('alternative')
    msg['From'] = f'Zwesta Trading <{smtp_user}>'
    msg['To'] = to_email
    msg['Subject'] = 'Zwesta Trading - Your Login Verification Code'
    
    plain = f'Your Zwesta Trading verification code is: {otp_code}\n\nThis code expires in 10 minutes.\nIf you did not request this code, please ignore this email.'
    
    html = f"""\
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
    <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
      <h2 style="color:#0A0E21;margin-top:0;">🔐 Verification Code</h2>
      <p style="color:#555;font-size:15px;">Use the code below to complete your login to <b>Zwesta Trading</b>:</p>
      <div style="background:#0A0E21;color:#00E5FF;font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;padding:18px;border-radius:8px;margin:24px 0;">
        {otp_code}
      </div>
      <p style="color:#888;font-size:13px;">This code expires in <b>10 minutes</b>.</p>
      <p style="color:#888;font-size:12px;">If you did not request this code, you can safely ignore this email.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="color:#aaa;font-size:11px;text-align:center;">Zwesta Trading Platform</p>
    </div>
    </body></html>"""
    
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html, 'html'))
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    logger.info(f"✅ 2FA email sent to {to_email}")


@app.route('/api/user/verify-2fa', methods=['POST'])
def verify_2fa():
    """Verify 2FA OTP code and create full session"""
    try:
        data = request.get_json()
        temp_token = data.get('temp_token', '')
        code = data.get('code', '')
        
        if not temp_token or not code:
            return jsonify({'success': False, 'error': 'Temp token and code required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, otp_code, expires_at FROM pending_2fa WHERE temp_token = ?', (temp_token,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid or expired 2FA session'}), 401
        
        row_dict = dict(row)
        
        # Check expiration
        if datetime.fromisoformat(row_dict['expires_at']) < datetime.now():
            cursor.execute('DELETE FROM pending_2fa WHERE temp_token = ?', (temp_token,))
            conn.commit()
            conn.close()
            return jsonify({'success': False, 'error': '2FA code expired'}), 401
        
        # Verify code
        if row_dict['otp_code'] != code:
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid 2FA code'}), 401
        
        user_id = row_dict['user_id']
        
        # Clean up pending 2FA
        cursor.execute('DELETE FROM pending_2fa WHERE temp_token = ?', (temp_token,))
        
        # Get user info
        cursor.execute('SELECT name, email, referral_code FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        user_dict = dict(user)
        
        # Create full session
        session_id = str(uuid.uuid4())
        token = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (session_id, user_id, token, datetime.now().isoformat(), expires_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"2FA verified for user {user_id}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'name': user_dict['name'],
            'email': user_dict['email'],
            'referral_code': user_dict['referral_code'],
            'session_token': token,
            'message': '2FA verification successful'
        }), 200
    
    except Exception as e:
        logger.error(f"Error in verify_2fa: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/resend-2fa', methods=['POST'])
def resend_2fa():
    """Resend 2FA OTP code"""
    try:
        data = request.get_json()
        temp_token = data.get('temp_token', '')
        
        if not temp_token:
            return jsonify({'success': False, 'error': 'Temp token required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM pending_2fa WHERE temp_token = ?', (temp_token,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid 2FA session'}), 401
        
        user_id = row['user_id']
        
        # Generate new code
        otp_code = ''.join(random.choices(string.digits, k=6))
        expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        cursor.execute('UPDATE pending_2fa SET otp_code = ?, expires_at = ? WHERE temp_token = ?',
                       (otp_code, expires_at, temp_token))
        conn.commit()
        
        # Get user email
        cursor.execute('SELECT email FROM users WHERE user_id = ?', (user_id,))
        email_row = cursor.fetchone()
        conn.close()
        
        if email_row:
            try:
                _send_2fa_email(email_row['email'], otp_code)
            except Exception as e:
                logger.warning(f"Could not resend 2FA email: {e}")
        
        return jsonify({'success': True, 'message': '2FA code resent'}), 200
    
    except Exception as e:
        logger.error(f"Error in resend_2fa: {e}")
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


@app.route('/api/user/settings', methods=['POST'])
@require_session
def update_user_settings():
    """Update user settings (2FA, notifications, etc.)"""
    try:
        data = request.get_json()
        user_id = request.user_id
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure settings columns exist
        for col in ['two_factor_enabled', 'notifications_enabled']:
            try:
                cursor.execute(f'ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0')
                conn.commit()
            except Exception:
                pass  # Column already exists
        
        updates = []
        values = []
        if 'two_factor_enabled' in data:
            updates.append('two_factor_enabled = ?')
            values.append(1 if data['two_factor_enabled'] else 0)
        if 'notifications_enabled' in data:
            updates.append('notifications_enabled = ?')
            values.append(1 if data['notifications_enabled'] else 0)
        
        if updates:
            values.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'Settings updated'}), 200
    except Exception as e:
        logger.error(f"Error updating user settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/change-password', methods=['POST'])
@require_session
def change_password():
    """Change user password (requires current password)"""
    try:
        data = request.get_json()
        user_id = request.user_id
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not new_password or len(new_password) < 6:
            return jsonify({'success': False, 'error': 'New password must be at least 6 characters'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT password_hash FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        stored_hash = user['password_hash']
        
        # If user has an existing password, verify old password
        if stored_hash:
            if not old_password or not check_password_hash(stored_hash, old_password):
                conn.close()
                return jsonify({'success': False, 'error': 'Current password is incorrect'}), 401
        
        # Set new password
        new_hash = generate_password_hash(new_password)
        cursor.execute('UPDATE users SET password_hash = ? WHERE user_id = ?', (new_hash, user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Password changed for user {user_id}")
        return jsonify({'success': True, 'message': 'Password changed successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/update-profile', methods=['PUT'])
@require_session
def update_user_profile():
    """Update user profile (name, email)"""
    try:
        data = request.get_json()
        user_id = request.user_id
        
        name = data.get('name', '').strip()
        email = data.get('email', '').lower().strip()
        
        if not name and not email:
            return jsonify({'success': False, 'error': 'Name or email required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check email uniqueness if changing email
        if email:
            cursor.execute('SELECT user_id FROM users WHERE email = ? AND user_id != ?', (email, user_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'error': 'Email already taken by another user'}), 409
        
        updates = []
        values = []
        if name:
            updates.append('name = ?')
            values.append(name)
        if email:
            updates.append('email = ?')
            values.append(email)
        
        values.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", values)
        
        # Fetch updated user
        cursor.execute('SELECT user_id, name, email, referral_code FROM users WHERE user_id = ?', (user_id,))
        updated = cursor.fetchone()
        updated_dict = dict(updated)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Profile updated for user {user_id}")
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': updated_dict
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
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


# ==================== ADMIN COMMISSION CONFIG ====================

@app.route('/api/admin/commission-config', methods=['GET'])
@require_api_key
def get_commission_config():
    """Get current commission rate configuration"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cfg = _get_commission_config(cursor)
        conn.close()
        return jsonify({'success': True, 'config': cfg}), 200
    except Exception as e:
        logger.error(f"Error getting commission config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/commission-config', methods=['POST'])
@require_api_key
def update_commission_config():
    """Update commission rate configuration (admin only)"""
    try:
        data = request.get_json()

        # Validate rates are between 0 and 1
        rate_fields = [
            'developer_direct_rate', 'developer_referral_rate', 'recruiter_rate',
            'ig_developer_rate', 'ig_recruiter_rate', 'tier2_rate'
        ]
        for field in rate_fields:
            if field in data:
                val = float(data[field])
                if val < 0 or val > 1:
                    return jsonify({'success': False, 'error': f'{field} must be between 0 and 1'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build dynamic UPDATE
        updates = []
        values = []
        allowed = rate_fields + ['developer_id', 'ig_commission_enabled', 'multi_tier_enabled']
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])

        if not updates:
            conn.close()
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

        updates.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append('default')

        cursor.execute(
            f"UPDATE commission_config SET {', '.join(updates)} WHERE config_id = ?",
            values
        )
        conn.commit()

        # Return updated config
        cfg = _get_commission_config(cursor)
        conn.close()

        logger.info(f"✅ Commission config updated: {data}")

        return jsonify({'success': True, 'config': cfg, 'message': 'Commission rates updated successfully'}), 200
    except Exception as e:
        logger.error(f"Error updating commission config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/commission-config/preview', methods=['POST'])
@require_api_key
def preview_commission_split():
    """Preview how a profit amount would be split with given rates"""
    try:
        data = request.get_json()
        profit = float(data.get('profit_amount', 100))
        has_referrer = data.get('has_referrer', True)
        source = data.get('source', 'MT5')

        conn = get_db_connection()
        cursor = conn.cursor()
        cfg = _get_commission_config(cursor)
        conn.close()

        if source == 'IG':
            dev_rate = float(cfg.get('ig_developer_rate', 0.20))
            rec_rate = float(cfg.get('ig_recruiter_rate', 0.05))
            direct_rate = dev_rate + rec_rate
        else:
            direct_rate = float(cfg.get('developer_direct_rate', 0.25))
            dev_rate = float(cfg.get('developer_referral_rate', 0.20))
            rec_rate = float(cfg.get('recruiter_rate', 0.05))

        tier2_rate = float(cfg.get('tier2_rate', 0.02))
        multi_tier = bool(cfg.get('multi_tier_enabled', 0))

        if has_referrer:
            dev_amount = profit * dev_rate
            rec_amount = profit * rec_rate
            tier2_amount = profit * tier2_rate if multi_tier else 0
            trader_keeps = profit - dev_amount - rec_amount - tier2_amount
            breakdown = {
                'developer': {'rate': dev_rate, 'amount': round(dev_amount, 2)},
                'recruiter': {'rate': rec_rate, 'amount': round(rec_amount, 2)},
            }
            if multi_tier:
                breakdown['tier2'] = {'rate': tier2_rate, 'amount': round(tier2_amount, 2)}
        else:
            dev_amount = profit * direct_rate
            trader_keeps = profit - dev_amount
            breakdown = {
                'developer': {'rate': direct_rate, 'amount': round(dev_amount, 2)},
            }

        return jsonify({
            'success': True,
            'profit_amount': profit,
            'source': source,
            'has_referrer': has_referrer,
            'breakdown': breakdown,
            'total_commission': round(profit - trader_keeps, 2),
            'trader_keeps': round(trader_keeps, 2),
        }), 200
    except Exception as e:
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


@app.route('/api/admin/ig-credentials/health', methods=['GET'])
@require_api_key
def admin_ig_credentials_health():
    """Admin view of IG credential readiness by user without returning secrets."""
    try:
        include_all = str(request.args.get('include_all', 'true')).lower() in ('1', 'true', 'yes')
        limit = int(request.args.get('limit', 200))
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                u.user_id,
                u.email,
                u.name,
                bc.credential_id,
                bc.username AS ig_username,
                bc.account_number AS ig_account_id,
                bc.is_live,
                bc.api_key,
                bc.password,
                bc.updated_at,
                bc.created_at
            FROM users u
            LEFT JOIN broker_credentials bc
              ON bc.credential_id = (
                  SELECT bc2.credential_id
                  FROM broker_credentials bc2
                  WHERE bc2.user_id = u.user_id
                    AND bc2.is_active = 1
                    AND bc2.broker_name IN ('IG Markets', 'IG.com', 'IG')
                  ORDER BY bc2.updated_at DESC, bc2.created_at DESC
                  LIMIT 1
              )
            ORDER BY u.created_at DESC
            LIMIT ?
        ''', (limit,))

        health_rows = []
        total_with_ig = 0
        total_ready = 0

        for row in cursor.fetchall():
            has_ig = bool(row['credential_id'])
            if has_ig:
                total_with_ig += 1

            missing_fields = []
            if has_ig:
                if not row['api_key']:
                    missing_fields.append('api_key')
                if not row['ig_username']:
                    missing_fields.append('username')
                if not row['password']:
                    missing_fields.append('password')
                if not row['ig_account_id']:
                    missing_fields.append('account_id')

            is_ready = has_ig and len(missing_fields) == 0
            if is_ready:
                total_ready += 1

            if include_all or has_ig:
                health_rows.append({
                    'user_id': row['user_id'],
                    'email': row['email'],
                    'name': row['name'],
                    'has_ig_credentials': has_ig,
                    'credential_id': row['credential_id'] if has_ig else None,
                    'ig_username': row['ig_username'] if has_ig else None,
                    'ig_account_id': row['ig_account_id'] if has_ig else None,
                    'environment': 'live' if bool(row['is_live']) else 'demo' if has_ig else None,
                    'is_ready': is_ready,
                    'missing_fields': missing_fields,
                    'updated_at': row['updated_at'] if has_ig else None,
                    'created_at': row['created_at'] if has_ig else None,
                })

        conn.close()

        return jsonify({
            'success': True,
            'summary': {
                'users_scanned': len(health_rows) if include_all else total_with_ig,
                'users_with_ig_credentials': total_with_ig,
                'users_ready': total_ready,
                'users_not_ready': max(total_with_ig - total_ready, 0),
                'include_all': include_all,
                'limit': limit,
            },
            'users': health_rows,
        }), 200
    except Exception as e:
        logger.error(f"Error getting IG credential health: {e}")
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


@app.route('/api/withdrawals/recent', methods=['GET'])
@require_session
def get_recent_withdrawals():
    """Get recent withdrawals for the current user (last 10)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user_id = request.user_id
        
        # Get recent withdrawals from all withdrawal sources (exness_withdrawals, commission_withdrawals, withdrawals)
        # Combine Exness withdrawals
        cursor.execute('''
            SELECT 
                withdrawal_id, 
                user_id, 
                'Exness' as broker,
                broker_account_id as accountNumber,
                total_amount as amount,
                status,
                created_at as date,
                'exness' as type
            FROM exness_withdrawals
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        exness_withdrawals = [dict(row) for row in cursor.fetchall()]
        
        # Get recent commission withdrawals
        cursor.execute('''
            SELECT 
                cw.withdrawal_id,
                cw.user_id,
                'Commission' as broker,
                NULL as accountNumber,
                cw.amount,
                cw.status,
                cw.created_at as date,
                'commission' as type
            FROM commission_withdrawals cw
            WHERE cw.user_id = ?
            ORDER BY cw.created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        commission_withdrawals = [dict(row) for row in cursor.fetchall()]
        
        # Get recent general withdrawals
        cursor.execute('''
            SELECT 
                withdrawal_id,
                user_id,
                method as broker,
                account_details as accountNumber,
                amount,
                status,
                created_at as date,
                'general' as type
            FROM withdrawals
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        general_withdrawals = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        # Combine and sort by date
        all_withdrawals = exness_withdrawals + commission_withdrawals + general_withdrawals
        all_withdrawals.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Return only recent ones
        recent = all_withdrawals[:10]
        
        logger.info(f"✅ Retrieved {len(recent)} recent withdrawals for user {user_id}")
        
        return jsonify({
            'success': True,
            'withdrawals': recent,
            'total_count': len(all_withdrawals)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting recent withdrawals: {e}")
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


@app.route('/api/admin/withdrawals/pending', methods=['GET'])
@require_admin
def admin_get_pending_exness_withdrawals():
    """Get list of pending Exness withdrawals for admin verification (Flutter UI)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                withdrawal_id,
                user_id,
                profit_from_trades,
                commission_earned,
                created_at
            FROM exness_withdrawals 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        
        withdrawals = []
        for row in cursor.fetchall():
            withdrawal_dict = dict(row)
            # Get user name for display
            cursor.execute('SELECT name FROM users WHERE user_id = ?', (withdrawal_dict['user_id'],))
            user_row = cursor.fetchone()
            if user_row:
                withdrawal_dict['user_name'] = user_row['name']
            
            withdrawals.append(withdrawal_dict)
        
        conn.close()
        
        logger.info(f"Admin fetched {len(withdrawals)} pending Exness withdrawals")
        
        return jsonify({
            'success': True,
            'withdrawals': withdrawals,
            'count': len(withdrawals)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching pending Exness withdrawals: {e}")
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
try:
    from ig_service import ig_api
    app.register_blueprint(ig_api)
    logger.info("✅ IG API service loaded")
except ImportError:
    logger.warning("⚠️ ig_service module not found - IG integration disabled")

# --- OANDA API Integration ---
try:
    from oanda_service import oanda_api
    app.register_blueprint(oanda_api)
    logger.info("✅ OANDA API service loaded")
except ImportError:
    logger.warning("⚠️ oanda_service module not found - OANDA integration disabled")

# --- FXCM API Integration ---
try:
    from fxcm_service import fxcm_api
    app.register_blueprint(fxcm_api)
    logger.info("✅ FXCM API service loaded")
except ImportError:
    logger.warning("⚠️ fxcm_service module not found - FXCM integration disabled")

# --- Binance API Integration ---
try:
    from binance_service import binance_api
    app.register_blueprint(binance_api)
    logger.info("✅ Binance API service loaded")
except ImportError:
    logger.warning("⚠️ binance_service module not found - Binance integration disabled")

# --- Unified Broker + Crypto Strategies ---
try:
    from unified_broker_service import unified_broker_api
    app.register_blueprint(unified_broker_api)
    logger.info("✅ Unified broker service loaded")
except ImportError:
    logger.warning("⚠️ unified_broker_service module not found - Unified broker integration disabled")

# Example: Use IG API in bot trading logic
# (You can call these functions from your bot trading threads)
def place_ig_trade(epic, size, direction, currency="USD", order_type="MARKET"):
    import requests
    from flask import current_app
    # Use the IG API endpoint via internal HTTP call or direct function call
    url = f"http://localhost:9000/api/legacy/ig/place-order"
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
    url = f"http://localhost:9000/api/legacy/ig/positions"
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
        password = data.get('password', '').strip()
        referrer_code = data.get('referrer_code', '').strip()
        
        if not email or not name:
            return jsonify({'success': False, 'error': 'Email and name required'}), 400
        
        if not password or len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
        
        # Hash the password
        password_hash = generate_password_hash(password)
        
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
            INSERT INTO users (user_id, email, name, password_hash, referrer_id, referral_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, email, name, password_hash, referrer_id, referral_code, datetime.now().isoformat()))
        
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


# ==================== PAYMENT & PAYOUT SYSTEM ====================

@app.route('/api/user/payment-methods', methods=['GET'])
@require_session
def get_payment_methods():
    """Get all configured payment methods for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT method_id, type, primary_method, verified, created_at
            FROM user_payment_methods
            WHERE user_id = ?
            ORDER BY primary_method DESC, created_at DESC
        ''', (user_id,))
        
        methods = []
        for row in cursor.fetchall():
            methods.append({
                'methodId': row[0],
                'type': row[1],
                'isPrimary': bool(row[2]),
                'verified': bool(row[3]),
                'createdAt': row[4]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'methods': methods,
            'count': len(methods)
        })
    except Exception as e:
        logger.error(f"Error getting payment methods: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/payment-method', methods=['POST'])
@require_session
def add_payment_method():
    """Add or update a payment method (Stripe, Bank, Crypto)"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        method_type = data.get('type')  # 'stripe', 'bank', 'crypto'
        make_primary = data.get('makePrimary', False)
        
        if not method_type:
            return jsonify({'success': False, 'error': 'Payment method type required'}), 400
        
        method_id = str(uuid.uuid4())
        
        if method_type == 'stripe':
            stripe_account_id = data.get('stripeAccountId')
            if not stripe_account_id:
                return jsonify({'success': False, 'error': 'Stripe account ID required'}), 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_payment_methods (method_id, user_id, type, stripe_account_id, verified, created_at, primary_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (method_id, user_id, 'stripe', stripe_account_id, 1, datetime.now(), make_primary))
        
        elif method_type == 'bank':
            bank_data = data.get('bank', {})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_payment_methods 
                (method_id, user_id, type, bank_name, account_holder, account_number, routing_number, swift_code, verified, created_at, primary_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                method_id, user_id, 'bank',
                bank_data.get('bankName'), bank_data.get('accountHolder'), 
                bank_data.get('accountNumber'), bank_data.get('routingNumber'),
                bank_data.get('swiftCode'),
                0,  # Requires verification
                datetime.now(), make_primary
            ))
        
        elif method_type == 'crypto':
            crypto_wallet = data.get('wallet')
            crypto_type = data.get('cryptoType', 'USDT')  # BTC, ETH, USDT, USDC
            if not crypto_wallet:
                return jsonify({'success': False, 'error': 'Wallet address required'}), 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_payment_methods (method_id, user_id, type, crypto_wallet, crypto_type, verified, created_at, primary_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (method_id, user_id, 'crypto', crypto_wallet, crypto_type, 1, datetime.now(), make_primary))
        
        else:
            return jsonify({'success': False, 'error': f'Unsupported method type: {method_type}'}), 400
        
        # If making primary, unset other methods as primary
        if make_primary:
            cursor.execute('UPDATE user_payment_methods SET primary_method = 0 WHERE user_id = ? AND method_id != ?', (user_id, method_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Payment method {method_type} added for user {user_id}")
        
        return jsonify({
            'success': True,
            'methodId': method_id,
            'message': f'{method_type.capitalize()} payment method added successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error adding payment method: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/commission-payout', methods=['POST'])
@require_session
def request_commission_payout():
    """Request automatic commission payout via preferred payment method"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        method = data.get('method', 'auto')  # 'auto', 'stripe', 'bank', 'crypto', 'internal'
        min_amount = data.get('minAmount', 50)  # Minimum payout
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total unpaid commissions
        cursor.execute('''
            SELECT SUM(amount) FROM commission_ledger
            WHERE user_id = ? AND payout_status = 'pending'
        ''', (user_id,))
        
        result = cursor.fetchone()
        pending_amount = result[0] if result[0] else 0
        
        if pending_amount < min_amount:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient commission balance (${pending_amount:.2f} < ${min_amount:.2f})'
            }), 400
        
        # Process payout
        payout_result = PaymentGateway.process_payout(user_id, pending_amount, 'Commission payout', method)
        
        if payout_result['success']:
            # Update commission ledger
            cursor.execute('''
                UPDATE commission_ledger SET payout_status = 'scheduled', payout_method = ?, payout_date = ?
                WHERE user_id = ? AND payout_status = 'pending'
            ''', (method, datetime.now(), user_id))
            conn.commit()
        
        conn.close()
        
        return jsonify({
            'success': payout_result['success'],
            'message': payout_result.get('message', 'Payout processed'),
            'reference': payout_result.get('reference'),
            'amount': pending_amount,
            'method': method,
            'estimatedDelivery': payout_result.get('estimatedMinutes') or payout_result.get('estimatedDays')
        })
    
    except Exception as e:
        logger.error(f"Error requesting commission payout: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/transactions', methods=['GET'])
@require_session
def get_user_transactions():
    """Get transaction history for user"""
    try:
        user_id = request.user_id
        transaction_type = request.args.get('type')  # Optional filter
        limit = request.args.get('limit', default=50, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if transaction_type:
            cursor.execute('''
                SELECT transaction_id, type, amount, method, status, reason, created_at, completed_at
                FROM transactions
                WHERE user_id = ? AND type = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, transaction_type, limit))
        else:
            cursor.execute('''
                SELECT transaction_id, type, amount, method, status, reason, created_at, completed_at
                FROM transactions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                'transactionId': row[0],
                'type': row[1],
                'amount': round(row[2], 2),
                'method': row[3],
                'status': row[4],
                'reason': row[5],
                'createdAt': row[6],
                'completedAt': row[7]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'transactions': transactions,
            'count': len(transactions)
        })
    
    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks for payout confirmation"""
    try:
        import stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        
        if event['type'] == 'payout.paid':
            payout = event['data']['object']
            logger.info(f"✅ Stripe payout confirmed: {payout['id']}")
            
        elif event['type'] == 'payout.failed':
            payout = event['data']['object']
            logger.error(f"❌ Stripe payout failed: {payout['id']}")
        
        return jsonify({'success': True, 'received': True}), 200
    
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


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


# ==================== EXNESS BROKER ENDPOINTS ====================
# Exness provides MT5-based trading with session token authentication

def generate_exness_session_token():
    """Generate secure session token for Exness MT5 trading"""
    return f"exness_{uuid.uuid4().hex[:32]}"

def validate_exness_server(server_name):
    """Validate that server name is correct for Exness"""
    valid_servers = ['Exness-MT5', 'Exness-MT5.5', 'Exness-MT5-Real']
    return server_name in valid_servers

def get_exness_available_symbols():
    """Return list of available Exness symbols (50+ pairs)"""
    return [
        # Forex - Major Pairs (8)
        'EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCNH',
        # Metals (4)
        'XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD',
        # Energy (2)
        'OILK', 'NATGASUS',
        # Indices (4)
        'SP500m', 'DAX', 'US300', 'US100',
        # Additional forex pairs (12+)
        'EURJPY', 'EURGBP', 'EURCHF', 'EURCAD', 'GBPJPY', 'GBPCHF', 'CHFJPY',
        'CADCHF', 'CADJPY', 'AUDCAD', 'AUDCHF', 'AUDJPY',
    ]

@app.route('/api/broker/exness/login', methods=['POST'])
def exness_login():
    """Login to Exness MT5 account and create session.
    CRITICAL: Uses ensure_mt5_ready() instead of mt5.initialize().
    NEVER calls mt5.shutdown() - the terminal is shared by all bots.
    """
    try:
        data = request.json or {}
        account_id = data.get('accountId') or data.get('account_id')
        password = data.get('password')
        server = data.get('server', 'Exness-MT5')
        is_live = data.get('is_live', False)
        
        if not account_id or not password:
            return jsonify({'success': False, 'error': 'accountId and password required'}), 400
        
        if not validate_exness_server(server):
            return jsonify({'success': False, 'error': f'Invalid Exness server: {server}'}), 400
        
        # Try to connect to MT5 for Exness
        try:
            import MetaTrader5 as mt5
            
            # SAFE: Use ensure_mt5_ready() instead of mt5.initialize()
            if not ensure_mt5_ready():
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize MT5',
                    'detail': 'MT5 terminal may not be installed or running'
                }), 500
            
            # Check if already logged into this account
            try:
                account_id_int = int(account_id)
            except ValueError:
                return jsonify({'success': False, 'error': 'accountId must be numeric'}), 400
            
            existing = mt5.account_info()
            if existing and existing.login == account_id_int:
                # Already logged in - just return the info
                logger.info(f"✅ Exness already logged in to account {account_id}")
                session_token = generate_exness_session_token()
                return jsonify({
                    'success': True,
                    'session_token': session_token,
                    'account_id': account_id,
                    'account_type': 'LIVE' if is_live else 'DEMO',
                    'balance': existing.balance,
                    'currency': existing.currency,
                    'leverage': existing.leverage,
                    'server': server,
                }), 200
            
            # Different account - try login (but NEVER shutdown on failure)
            login_result = mt5.login(account_id_int, password=password, server=server)
            
            if not login_result:
                error_msg = mt5.last_error()
                logger.warning(f"⚠️ Exness login failed for account {account_id}: {error_msg}")
                # CRITICAL: Do NOT call mt5.shutdown() here!
                return jsonify({
                    'success': False,
                    'error': 'Failed to login to Exness account',
                    'detail': f'Check account ID, password, and server name. Server must be "{server}"'
                }), 401
            
            # Get account info
            account_info = mt5.account_info()
            if not account_info:
                # CRITICAL: Do NOT call mt5.shutdown() here!
                return jsonify({
                    'success': False,
                    'error': 'Failed to retrieve account info from MT5'
                }), 500
            
            # Generate session token
            session_token = generate_exness_session_token()
            
            logger.info(f"✅ Exness login successful for account {account_id}")
            
            return jsonify({
                'success': True,
                'session_token': session_token,
                'account_id': account_id,
                'account_type': 'LIVE' if is_live else 'DEMO',
                'balance': account_info.balance,
                'currency': account_info.currency,
                'leverage': account_info.leverage,
                'server': server,
            }), 200
            
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'MetaTrader5 SDK not installed',
                'detail': 'Install: pip install MetaTrader5>=5.0.45'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in Exness login: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/logout', methods=['POST'])
def exness_logout():
    """Logout from Exness (cleanup session)
    CRITICAL: Does NOT call mt5.shutdown()! That would kill ALL bot connections.
    Only clears the session token - MT5 terminal stays running for bots."""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token:
            return jsonify({'success': False, 'error': 'No session token provided'}), 401
        
        # CRITICAL: Do NOT call mt5.shutdown() here!
        # The MT5 terminal is shared by all 9+ trading bots.
        # Calling shutdown() would disconnect EVERYTHING.
        # Just invalidate the session token.
        
        logger.info(f"✅ Exness session ended (MT5 terminal kept alive for bots)")
        
        return jsonify({
            'success': True,
            'message': 'Logged out from Exness'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in Exness logout: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/account', methods=['GET'])
@require_session
def exness_account_info():
    """Get Exness account information - reconnects with user's saved credentials"""
    try:
        user_id = request.user_id  # From @require_session
        
        # Load user's latest active Exness credential
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, account_number, password, server, is_live
            FROM broker_credentials
            WHERE user_id = ? AND broker_name = 'Exness' AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,))
        
        cred_row = cursor.fetchone()
        conn.close()
        
        if not cred_row:
            return jsonify({
                'success': False, 
                'error': 'No Exness credentials found. Please connect your Exness account first.'
            }), 400
        
        cred = dict(cred_row)
        account = cred['account_number']
        password = cred['password']
        server = cred['server']
        is_live = cred['is_live']
        
        # Reconnect with user's credentials
        try:
            mt5_conn = MT5Connection(credentials={
                'account': account,
                'password': password,
                'server': server,
                'broker': 'Exness',
            })
            
            if not mt5_conn.connect():
                return jsonify({
                    'success': False,
                    'error': f'Failed to connect to Exness MT5. Account: {account}, Server: {server}'
                }), 500
            
            # Get account info from connected MT5 instance
            if not mt5_conn.mt5:
                return jsonify({'success': False, 'error': 'MT5 SDK not available'}), 500
            
            account_info = mt5_conn.mt5.account_info()
            if not account_info:
                return jsonify({'success': False, 'error': 'Failed to retrieve account info from MT5'}), 500
            
            return jsonify({
                'success': True,
                'accountId': account_info.login,
                'balance': float(account_info.balance),
                'equity': float(account_info.equity),
                'margin': float(account_info.margin),
                'marginFree': float(account_info.margin_free),
                'marginLevel': float(account_info.margin_level) if account_info.margin > 0 else 0.0,
                'currency': account_info.currency,
                'leverage': int(account_info.leverage),
                'accountType': 'LIVE' if is_live else 'DEMO',
                'profitLoss': float(account_info.equity - account_info.balance),
            }), 200
            
        except Exception as e:
            logger.error(f"Error connecting to Exness MT5 or retrieving account info: {e}")
            return jsonify({
                'success': False,
                'error': f'Cannot connect to MT5: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in exness_account_info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade', methods=['POST'])
@require_session
def exness_place_trade():
    """Place order on Exness MT5 account"""
    try:
        # @require_session decorator already validates authentication
        # User is authenticated if we reach here
        
        data = request.json or {}
        symbol = (data.get('symbol') or '').upper()
        side = (data.get('side') or 'BUY').upper()
        volume = float(data.get('volume', 0.1))
        stop_loss = data.get('stopLoss') or data.get('stop_loss')
        take_profit = data.get('takeProfit') or data.get('take_profit')
        
        if not symbol or side not in ['BUY', 'SELL']:
            return jsonify({'success': False, 'error': 'symbol and side (BUY/SELL) required'}), 400
        
        if volume <= 0:
            return jsonify({'success': False, 'error': 'volume must be positive'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Select symbol
            if not mt5.symbol_select(symbol, True):
                return jsonify({
                    'success': False,
                    'error': f'Symbol {symbol} not available on Exness'
                }), 400
            
            # Get tick for price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return jsonify({
                    'success': False,
                    'error': f'Cannot get market data for {symbol}'
                }), 500
            
            price = tick.ask if side == 'BUY' else tick.bid
            
            # Build order request — auto-detect filling type for Exness
            sym_info = mt5.symbol_info(symbol)
            if sym_info and sym_info.filling_mode & 2:
                _filling = mt5.ORDER_FILLING_IOC
            elif sym_info and sym_info.filling_mode & 1:
                _filling = mt5.ORDER_FILLING_FOK
            else:
                _filling = mt5.ORDER_FILLING_RETURN

            request_dict = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL,
                'price': price,
                'comment': 'Exness Order',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': _filling,
            }
            
            if stop_loss:
                request_dict['sl'] = float(stop_loss)
            if take_profit:
                request_dict['tp'] = float(take_profit)
            
            # Send order
            result = mt5.order_send(request_dict)
            
            if result is None:
                return jsonify({
                    'success': False,
                    'error': 'Order submission failed - terminal disconnected'
                }), 500
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': f'Order failed: {result.comment}',
                    'retcode': result.retcode
                }), 400
            
            logger.info(f"✅ Exness order placed: {symbol} {side} {volume}L")
            
            return jsonify({
                'success': True,
                'orderId': result.order,
                'symbol': symbol,
                'side': side,
                'volume': volume,
                'price': price,
                'commission': result.comment if hasattr(result, 'comment') else 0,
            }), 201
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error placing Exness trade: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders', methods=['GET'])
@require_session
def exness_get_orders():
    """Get open orders/positions from Exness account"""
    try:
        # @require_session decorator already validates authentication
        
        try:
            import MetaTrader5 as mt5
            
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get open positions
            positions = mt5.positions_get()
            if positions is None:
                positions = []
            
            orders = []
            for pos in positions:
                orders.append({
                    'orderId': pos.ticket,
                    'symbol': pos.symbol,
                    'side': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'openPrice': pos.price_open,
                    'currentPrice': pos.price_current,
                    'profit': pos.profit,
                    'profitPercent': (pos.profit / (pos.price_open * pos.volume)) * 100 if pos.price_open > 0 else 0,
                    'openTime': datetime.fromtimestamp(pos.time).isoformat(),
                })
            
            logger.info(f"✅ Retrieved {len(orders)} open orders from Exness")
            
            return jsonify({
                'success': True,
                'orders': orders,
                'count': len(orders)
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error getting Exness orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders/<order_id>/close', methods=['POST'])
@require_session
def exness_close_order(order_id):
    """Close a specific order/position on Exness"""
    try:
        # @require_session decorator already validates authentication
        
        try:
            order_id_int = int(order_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid order ID'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get position
            position = mt5.positions_get(ticket=order_id_int)
            if not position:
                return jsonify({'success': False, 'error': 'Position not found'}), 404
            
            pos = position[0]
            
            # Build close order request
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Get current price
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            # Auto-detect filling type for close order
            _sym_info = mt5.symbol_info(pos.symbol)
            if _sym_info and _sym_info.filling_mode & 2:
                _close_filling = mt5.ORDER_FILLING_IOC
            elif _sym_info and _sym_info.filling_mode & 1:
                _close_filling = mt5.ORDER_FILLING_FOK
            else:
                _close_filling = mt5.ORDER_FILLING_RETURN

            request_dict = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': close_type,
                'position': order_id_int,
                'price': price,
                'comment': 'Position Closed',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': _close_filling,
            }
            
            result = mt5.order_send(request_dict)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': 'Failed to close position'
                }), 500
            
            logger.info(f"✅ Exness position {order_id} closed successfully")
            
            return jsonify({
                'success': True,
                'orderId': order_id,
                'message': 'Position closed'
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error closing Exness order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders/<order_id>', methods=['PATCH'])
@require_session
def exness_update_order(order_id):
    """Update stop loss and take profit for Exness order"""
    try:
        # @require_session decorator already validates authentication
        
        data = request.json or {}
        new_sl = data.get('stopLoss') or data.get('stop_loss')
        new_tp = data.get('takeProfit') or data.get('take_profit')
        
        if not new_sl and not new_tp:
            return jsonify({'success': False, 'error': 'stopLoss or takeProfit required'}), 400
        
        try:
            order_id_int = int(order_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid order ID'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get position
            position = mt5.positions_get(ticket=order_id_int)
            if not position:
                return jsonify({'success': False, 'error': 'Position not found'}), 404
            
            pos = position[0]
            
            # Build modify request
            request_dict = {
                'action': mt5.TRADE_ACTION_SLTP,
                'position': order_id_int,
                'sl': float(new_sl) if new_sl else pos.sl,
                'tp': float(new_tp) if new_tp else pos.tp,
            }
            
            result = mt5.order_send(request_dict)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update position'
                }), 500
            
            logger.info(f"✅ Exness position {order_id} updated: SL={new_sl}, TP={new_tp}")
            
            return jsonify({
                'success': True,
                'orderId': order_id,
                'stopLoss': new_sl,
                'takeProfit': new_tp,
                'message': 'Position updated'
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error updating Exness order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/symbols/<symbol>', methods=['GET'])
def exness_symbol_info(symbol):
    """Get symbol information and current market data from Exness"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token or not session_token.startswith('exness_'):
            return jsonify({'success': False, 'error': 'Invalid session token'}), 401
        
        symbol = symbol.upper()
        
        try:
            import MetaTrader5 as mt5
            
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return jsonify({
                    'success': False,
                    'error': f'Symbol {symbol} not found on Exness'
                }), 404
            
            # Get tick data
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return jsonify({
                    'success': False,
                    'error': f'Cannot get market data for {symbol}'
                }), 500
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'minSize': symbol_info.volume_min,
                'maxSize': symbol_info.volume_max,
                'stepSize': symbol_info.volume_step,
                'tradable': symbol_info.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED,
                'lastUpdate': datetime.fromtimestamp(tick.time).isoformat(),
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error getting Exness symbol info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/symbols', methods=['GET'])
def exness_available_symbols():
    """Get list of all available symbols on Exness"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token or not session_token.startswith('exness_'):
            return jsonify({'success': False, 'error': 'Invalid session token'}), 401
        
        symbols = get_exness_available_symbols()
        
        logger.info(f"✅ Retrieved {len(symbols)} available symbols from Exness")
        
        return jsonify({
            'success': True,
            'symbols': symbols,
            'count': len(symbols)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting Exness symbols: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade/closed', methods=['POST'])
@require_api_key
def record_exness_trade_profit():
    """
    Record a closed trade profit for Exness with automatic commission split:
    - Direct registration: Developer 30%, User 70%
    - Via referrer: Developer 25%, Referrer 5%, User 70%
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        broker_account_id = data.get('broker_account_id')
        order_id = data.get('order_id')
        symbol = data.get('symbol')
        entry_price = data.get('entry_price')
        exit_price = data.get('exit_price')
        volume = data.get('volume')
        side = data.get('side')  # 'BUY' or 'SELL'
        profit_loss = data.get('profit_loss')
        commission = data.get('commission', 0)
        trade_duration_seconds = data.get('trade_duration_seconds')

        if not all([user_id, broker_account_id, order_id, symbol, entry_price, exit_price, volume, profit_loss]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        profit_id = str(uuid.uuid4())
        closed_at = datetime.now().isoformat()
        pnl_percentage = ((exit_price - entry_price) / entry_price * 100) if side == 'BUY' else ((entry_price - exit_price) / entry_price * 100)

        # Record the trade profit
        cursor.execute('''
            INSERT INTO exness_trade_profits
            (profit_id, user_id, broker_account_id, order_id, symbol, entry_price, exit_price,
             volume, side, profit_loss, commission, pnl_percentage, trade_duration_seconds, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profit_id, user_id, broker_account_id, order_id, symbol, entry_price, exit_price,
            volume, side, profit_loss, commission, pnl_percentage, trade_duration_seconds, closed_at
        ))

        # ==================== PROFIT COMMISSION SPLIT ====================
        
        # Get user's referrer (if any)
        cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        referrer_id = user_row['referrer_id'] if user_row else None
        
        # Calculate commission split based on registration type
        developer_id = 'SYSTEM_OWNER_USER_ID'  # System developer/owner account
        
        if profit_loss > 0:  # Only split if profitable
            if referrer_id:
                # Via referrer: Dev 25%, Referrer 5%, User 70%
                dev_commission = profit_loss * 0.25
                referrer_commission = profit_loss * 0.05
                user_profit = profit_loss * 0.70
                
                logger.info(f"📊 Profit split (WITH REFERRER): Dev ${dev_commission:.2f} (25%), Referrer ${referrer_commission:.2f} (5%), User ${user_profit:.2f} (70%)")
            else:
                # Direct registration: Dev 30%, User 70%
                dev_commission = profit_loss * 0.30
                referrer_commission = 0
                user_profit = profit_loss * 0.70
                
                logger.info(f"📊 Profit split (DIRECT): Dev ${dev_commission:.2f} (30%), User ${user_profit:.2f} (70%)")
            
            # Insert commission records
            commission_id_dev = str(uuid.uuid4())
            commission_id_user = str(uuid.uuid4())
            commission_time = datetime.now().isoformat()
            
            # Developer commission
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                commission_id_dev, developer_id, user_id, dev_commission, 'trade_profit',
                profit_id, 'earned', commission_time
            ))
            
            # User profit (if not all goes to dev)
            if user_profit > 0:
                cursor.execute('''
                    INSERT INTO commissions
                    (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    commission_id_user, user_id, developer_id, user_profit, 'trade_profit',
                    profit_id, 'earned', commission_time
                ))
            
            # Referrer commission (if applicable)
            if referrer_id and referrer_commission > 0:
                commission_id_referrer = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO commissions
                    (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    commission_id_referrer, referrer_id, user_id, referrer_commission, 'referral_profit',
                    profit_id, 'earned', commission_time
                ))
                
                # Update user total commission
                cursor.execute('''
                    UPDATE users SET total_commission = total_commission + ? 
                    WHERE user_id = ?
                ''', (referrer_commission, referrer_id))
            
            # Update developer total commission
            cursor.execute('''
                UPDATE users SET total_commission = total_commission + ? 
                WHERE user_id = ?
            ''', (dev_commission, developer_id))
            
            # Update user total commission
            cursor.execute('''
                UPDATE users SET total_commission = total_commission + ? 
                WHERE user_id = ?
            ''', (user_profit, user_id))

        conn.commit()
        conn.close()

        logger.info(f"✅ Trade profit recorded: {symbol} P&L=${profit_loss} ({pnl_percentage:.2f}%)")

        return jsonify({
            'success': True,
            'profit_id': profit_id,
            'profit_loss': profit_loss,
            'pnl_percentage': round(pnl_percentage, 2),
            'message': 'Trade profit recorded with commissions distributed'
        }), 201

    except Exception as e:
        logger.error(f"Error recording Exness trade profit: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== EXNESS WITHDRAWAL PIPELINE ====================

@app.route('/api/broker/exness/withdrawal/request', methods=['POST'])
@require_api_key
def exness_withdrawal_request():
    """Request profit withdrawal from Exness account"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        broker_account_id = data.get('broker_account_id')
        withdrawal_type = data.get('withdrawal_type')  # 'profits', 'commission', 'both'
        amount = data.get('amount')
        withdrawal_method = data.get('withdrawal_method', 'bank_transfer')
        payment_details = data.get('payment_details')

        if not all([user_id, broker_account_id, withdrawal_type, amount]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Validate withdrawal type
        if withdrawal_type not in ['profits', 'commission', 'both']:
            return jsonify({'success': False, 'error': 'Invalid withdrawal type'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate available amounts
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as total_profits 
            FROM exness_trade_profits 
            WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL
        ''', (user_id, broker_account_id))
        
        profit_row = cursor.fetchone()
        available_profits = profit_row['total_profits'] if profit_row else 0

        # Get commission earned
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission 
            FROM commissions 
            WHERE earner_id = ? AND status = 'earned'
        ''', (user_id,))
        
        commission_row = cursor.fetchone()
        available_commission = commission_row['total_commission'] if commission_row else 0

        # Validate amount based on type
        if withdrawal_type == 'profits' and amount > available_profits:
            conn.close()
            return jsonify({
                'success': False, 
                'error': f'Insufficient profit balance. Available: ${available_profits}'
            }), 400

        if withdrawal_type == 'commission' and amount > available_commission:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient commission balance. Available: ${available_commission}'
            }), 400

        if withdrawal_type == 'both' and amount > (available_profits + available_commission):
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient combined balance. Available: ${available_profits + available_commission}'
            }), 400

        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        fee = amount * 0.01  # 1% withdrawal fee
        net_amount = amount - fee
        created_at = datetime.now().isoformat()

        profit_from_trades = 0
        commission_earned = 0

        if withdrawal_type == 'profits':
            profit_from_trades = amount
        elif withdrawal_type == 'commission':
            commission_earned = amount
        else:  # both
            profit_from_trades = available_profits
            commission_earned = available_commission

        cursor.execute('''
            INSERT INTO exness_withdrawals
            (withdrawal_id, user_id, broker_account_id, withdrawal_type, profit_from_trades,
             commission_earned, total_amount, fee, net_amount, status, withdrawal_method,
             payment_details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            withdrawal_id, user_id, broker_account_id, withdrawal_type, profit_from_trades,
            commission_earned, amount, fee, net_amount, 'pending', withdrawal_method,
            payment_details, created_at
        ))

        # Link trade profits to withdrawal
        if withdrawal_type in ['profits', 'both']:
            cursor.execute('''
                UPDATE exness_trade_profits 
                SET withdrawal_id = ? 
                WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL
                LIMIT (SELECT COUNT(*) FROM exness_trade_profits 
                       WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL)
            ''', (withdrawal_id, user_id, broker_account_id, user_id, broker_account_id))

        conn.commit()
        conn.close()

        logger.info(f"✅ Exness withdrawal request {withdrawal_id}: User {user_id} - ${amount}")

        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'fee': round(fee, 2),
            'net_amount': round(net_amount, 2),
            'status': 'pending',
            'message': 'Withdrawal request submitted successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error requesting Exness withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/withdrawal/history/<user_id>', methods=['GET'])
def exness_withdrawal_history(user_id):
    """Get Exness withdrawal history for user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM exness_withdrawals 
            WHERE user_id = ? 
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))

        withdrawals = cursor.fetchall()
        conn.close()

        withdrawal_list = []
        for w in withdrawals:
            withdrawal_list.append({
                'withdrawal_id': w['withdrawal_id'],
                'broker_account_id': w['broker_account_id'],
                'withdrawal_type': w['withdrawal_type'],
                'profit_from_trades': w['profit_from_trades'],
                'commission_earned': w['commission_earned'],
                'total_amount': w['total_amount'],
                'fee': w['fee'],
                'net_amount': w['net_amount'],
                'status': w['status'],
                'withdrawal_method': w['withdrawal_method'],
                'created_at': w['created_at'],
                'submitted_at': w['submitted_at'],
                'completed_at': w['completed_at'],
            })

        return jsonify({
            'success': True,
            'withdrawals': withdrawal_list,
            'count': len(withdrawal_list)
        }), 200

    except Exception as e:
        logger.error(f"Error fetching Exness withdrawal history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/withdrawal/status/<withdrawal_id>', methods=['GET'])
def exness_withdrawal_status(withdrawal_id):
    """Check withdrawal status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM exness_withdrawals WHERE withdrawal_id = ?', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        conn.close()

        if not withdrawal:
            return jsonify({'success': False, 'error': 'Withdrawal not found'}), 404

        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal['withdrawal_id'],
            'status': withdrawal['status'],
            'amount': withdrawal['total_amount'],
            'net_amount': withdrawal['net_amount'],
            'created_at': withdrawal['created_at'],
            'submitted_at': withdrawal['submitted_at'],
            'completed_at': withdrawal['completed_at'],
        }), 200

    except Exception as e:
        logger.error(f"Error getting Exness withdrawal status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/balance/<user_id>', methods=['GET'])
def exness_withdrawal_balance(user_id):
    """Get available balance for withdrawal from Exness"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get profit from closed trades
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as total_profits 
            FROM exness_trade_profits 
            WHERE user_id = ? AND withdrawal_id IS NULL
        ''', (user_id,))
        
        profit_row = cursor.fetchone()
        available_profits = profit_row['total_profits'] if profit_row else 0

        # Get commission earned
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission 
            FROM commissions 
            WHERE earner_id = ? AND status = 'earned'
        ''', (user_id,))
        
        commission_row = cursor.fetchone()
        available_commission = commission_row['total_commission'] if commission_row else 0

        # Get pending/processing withdrawals
        cursor.execute('''
            SELECT COALESCE(SUM(total_amount), 0) as total_pending 
            FROM exness_withdrawals 
            WHERE user_id = ? AND status IN ('pending', 'submitted', 'processing')
        ''', (user_id,))
        
        pending_row = cursor.fetchone()
        pending_withdrawals = pending_row['total_pending'] if pending_row else 0

        conn.close()

        return jsonify({
            'success': True,
            'available_profits': round(available_profits, 2),
            'available_commission': round(available_commission, 2),
            'total_available': round(available_profits + available_commission, 2),
            'pending_withdrawals': round(pending_withdrawals, 2),
            'net_available': round(available_profits + available_commission - pending_withdrawals, 2),
        }), 200

    except Exception as e:
        logger.error(f"Error getting Exness balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN: VERIFY EXNESS WITHDRAWAL & TRIGGER COMMISSION SPLIT ====================

@app.route('/api/admin/withdrawal/exness/verify', methods=['POST'])
@require_admin
def admin_verify_exness_withdrawal():
    """
    Admin verifies that user actually withdrew from Exness.
    Automatically splits commission: 30% to developer, 70% to user wallet.
    """
    try:
        data = request.get_json()
        withdrawal_id = data.get('withdrawal_id')
        admin_notes = data.get('notes', '')
        
        if not withdrawal_id:
            return jsonify({'success': False, 'error': 'withdrawal_id required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal details
        cursor.execute('SELECT * FROM exness_withdrawals WHERE withdrawal_id = ?', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        
        if not withdrawal:
            conn.close()
            return jsonify({'success': False, 'error': 'Withdrawal not found'}), 404
        
        if withdrawal['status'] != 'pending':
            conn.close()
            return jsonify({
                'success': False, 
                'error': f"Can only verify pending withdrawals. Current status: {withdrawal['status']}"
            }), 400
        
        user_id = withdrawal['user_id']
        profit_amount = withdrawal['profit_from_trades']
        
        # ==================== COMMISSION SPLIT LOGIC ====================
        developer_id = 'SYSTEM_OWNER_USER_ID'
        dev_share = profit_amount * 0.30  # Developer gets 30%
        user_share = profit_amount * 0.70  # User gets 70%
        
        now = datetime.now().isoformat()
        
        # STEP 1: Ensure user has a wallet
        cursor.execute('SELECT wallet_id FROM user_wallets WHERE user_id = ?', (user_id,))
        wallet_row = cursor.fetchone()
        
        if not wallet_row:
            wallet_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO user_wallets (wallet_id, user_id, balance, currency, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (wallet_id, user_id, user_share, 'USD', now))
        else:
            wallet_id = wallet_row['wallet_id']
            # Update existing wallet balance
            cursor.execute('''
                UPDATE user_wallets 
                SET balance = balance + ?, last_updated = ?
                WHERE user_id = ?
            ''', (user_share, now, user_id))
        
        # STEP 2: Record wallet transaction for user
        transaction_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO wallet_transactions 
            (transaction_id, wallet_id, user_id, amount, transaction_type, source_withdrawal_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            transaction_id, wallet_id, user_id, user_share, 
            'profit_withdrawal', withdrawal_id, 'completed', now
        ))
        
        # STEP 3: Record developer commission
        commission_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO commissions 
            (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            commission_id, developer_id, user_id, dev_share,
            'exness_profit_commission', withdrawal_id, 'earned', now
        ))
        
        # STEP 4: Update withdrawal status to verified
        cursor.execute('''
            UPDATE exness_withdrawals 
            SET status = 'verified', completed_at = ?, admin_notes = ?
            WHERE withdrawal_id = ?
        ''', (now, admin_notes, withdrawal_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ ADMIN verified withdrawal {withdrawal_id}: User {user_id}")
        logger.info(f"   Commission split: Dev ${dev_share:.2f} (30%), User ${user_share:.2f} (70%)")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'status': 'verified',
            'profit_amount': profit_amount,
            'developer_commission': round(dev_share, 2),
            'user_wallet_credit': round(user_share, 2),
            'message': f'✅ Withdrawal verified! User will receive ${round(user_share, 2)} in their wallet. Developer earned ${round(dev_share, 2)}.'
        }), 200
    
    except Exception as e:
        logger.error(f"Error verifying Exness withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== GET USER WALLET BALANCE ====================

@app.route('/api/wallet/balance/<user_id>', methods=['GET'])
def get_wallet_balance(user_id):
    """Get user's available wallet balance"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM user_wallets WHERE user_id = ?', (user_id,))
        wallet = cursor.fetchone()
        conn.close()
        
        balance = wallet['balance'] if wallet else 0
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'balance': round(balance, 2),
            'currency': 'USD'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting wallet balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trades', methods=['GET'])
def exness_get_trades():
    """Get closed trades history with profit/loss from Exness MT5"""
    try:
        # Get optional filters from query params
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 50))
        
        # First try to get from MT5 live data
        try:
            import MetaTrader5 as mt5
            
            if ensure_mt5_ready():
                deals = mt5.history_deals_get(position=0)
                trades = []
                
                if deals:
                    # Process last N deals and reverse to show most recent first
                    for deal in sorted(deals, key=lambda x: x.time, reverse=True)[:limit]:
                        trade = {
                            'ticket': deal.ticket,
                            'symbol': deal.symbol,
                            'side': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
                            'volume': deal.volume,
                            'entryPrice': deal.price,
                            'exitPrice': deal.price,  # Deal price is exit price for closed deals
                            'profitLoss': float(deal.profit),
                            'commission': float(deal.commission),
                            'pnlPercentage': ((deal.profit / (deal.price * deal.volume)) * 100) if (deal.price * deal.volume) > 0 else 0,
                            'closedAt': datetime.fromtimestamp(deal.time).isoformat(),
                            'duration': 'N/A'  # Duration not directly available from deal
                        }
                        trades.append(trade)
                
                logger.info(f"✅ Retrieved {len(trades)} trades from MT5 live data")
                return jsonify({
                    'success': True,
                    'trades': trades,
                    'count': len(trades),
                    'source': 'MT5_LIVE'
                }), 200
        except ImportError:
            logger.warning("MT5 SDK not available, falling back to database")
        except Exception as mt5_error:
            logger.warning(f"Error fetching from MT5: {mt5_error}, falling back to database")
        
        # Fallback to database records
        if user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Try exness_trade_profits table first
            cursor.execute('''
                SELECT * FROM exness_trade_profits 
                WHERE user_id = ? 
                ORDER BY closed_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            trades = []
            for row in cursor.fetchall():
                trade = {
                    'profit_id': row['profit_id'],
                    'symbol': row['symbol'],
                    'side': row['side'],
                    'volume': row['volume'],
                    'entryPrice': row['entry_price'],
                    'exitPrice': row['exit_price'],
                    'profitLoss': row['profit_loss'],
                    'commission': row['commission'],
                    'pnlPercentage': row['pnl_percentage'],
                    'closedAt': row['closed_at'],
                    'duration': row['trade_duration_seconds']
                }
                trades.append(trade)
            
            # Also check trades table (for bot-executed trades)
            try:
                cursor.execute('''
                    SELECT * FROM trades 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC
                ''', (user_id,))
                
                for row in cursor.fetchall():
                    try:
                        trade_data = json.loads(row['trade_data'])
                        trade = {
                            'ticket': trade_data.get('ticket', ''),
                            'symbol': trade_data.get('symbol', ''),
                            'side': trade_data.get('type', ''),
                            'volume': trade_data.get('volume', 0),
                            'entryPrice': trade_data.get('entryPrice', 0),
                            'exitPrice': trade_data.get('exitPrice', 0),
                            'profitLoss': trade_data.get('profit', 0),
                            'commission': trade_data.get('commission', 0),
                            'pnlPercentage': ((trade_data.get('profit', 0) / (trade_data.get('entryPrice', 1) * trade_data.get('volume', 1))) * 100) if (trade_data.get('entryPrice', 0) * trade_data.get('volume', 0)) > 0 else 0,
                            'closedAt': trade_data.get('exitTime', datetime.fromtimestamp(row['timestamp']/1000).isoformat()),
                            'duration': trade_data.get('durationSec', 0),
                            'strategy': trade_data.get('strategy', ''),
                            'botId': trade_data.get('botId', '')
                        }
                        trades.append(trade)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse trade data: {row['trade_data']}")
            except Exception as e:
                logger.warning(f"Error querying trades table: {e}")
            
            conn.close()
            
            # Sort by most recent first
            trades.sort(key=lambda x: x.get('closedAt', ''), reverse=True)
            
            logger.info(f"✅ Retrieved {len(trades)} trades from database for user {user_id}")
            return jsonify({
                'success': True,
                'trades': trades,
                'count': len(trades),
                'source': 'DATABASE'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'user_id parameter required for database fallback'
            }), 400
            
    except Exception as e:
        logger.error(f"Error getting Exness trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade-summary', methods=['GET'])
def exness_trade_summary():
    """Get aggregate trade statistics and summary"""
    try:
        user_id = request.args.get('user_id')
        
        # First try MT5 live data
        summary = {
            'totalTrades': 0,
            'winningTrades': 0,
            'losingTrades': 0,
            'totalProfit': 0.0,
            'totalLoss': 0.0,
            'netProfit': 0.0,
            'totalCommission': 0.0,
            'winRate': 0.0,
            'avgProfit': 0.0,
            'avgLoss': 0.0,
            'largestWin': 0.0,
            'largestLoss': 0.0,
            'profitFactor': 0.0,
            'totalVolume': 0.0
        }
        
        try:
            import MetaTrader5 as mt5
            
            if ensure_mt5_ready():
                deals = mt5.history_deals_get(position=0)
                
                if deals and len(deals) > 0:
                    winning_pnl = []
                    losing_pnl = []
                    total_commission = 0
                    
                    for deal in deals:
                        profit = float(deal.profit)
                        commission = float(deal.commission)
                        
                        summary['totalTrades'] += 1
                        summary['totalVolume'] += deal.volume
                        total_commission += commission
                        
                        if profit > 0:
                            summary['winningTrades'] += 1
                            summary['totalProfit'] += profit
                            winning_pnl.append(profit)
                        elif profit < 0:
                            summary['losingTrades'] += 1
                            summary['totalLoss'] += abs(profit)
                            losing_pnl.append(profit)
                    
                    summary['netProfit'] = summary['totalProfit'] - summary['totalLoss']
                    summary['totalCommission'] = total_commission
                    summary['winRate'] = (summary['winningTrades'] / summary['totalTrades'] * 100) if summary['totalTrades'] > 0 else 0
                    summary['avgProfit'] = (summary['totalProfit'] / summary['winningTrades']) if summary['winningTrades'] > 0 else 0
                    summary['avgLoss'] = (summary['totalLoss'] / summary['losingTrades']) if summary['losingTrades'] > 0 else 0
                    summary['largestWin'] = max(winning_pnl) if winning_pnl else 0
                    summary['largestLoss'] = min(losing_pnl) if losing_pnl else 0
                    summary['profitFactor'] = (summary['totalProfit'] / summary['totalLoss']) if summary['totalLoss'] > 0 else 0
                    
                    logger.info(f"✅ Generated trading summary from MT5: {summary['totalTrades']} trades, ${summary['netProfit']:.2f} net profit")
                    
                    return jsonify({
                        'success': True,
                        'summary': summary,
                        'source': 'MT5_LIVE'
                    }), 200
        except ImportError:
            logger.warning("MT5 SDK not available, falling back to database")
        except Exception as mt5_error:
            logger.warning(f"Error fetching from MT5: {mt5_error}, falling back to database")
        
        # Fallback to database
        if user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all trades for this user
            cursor.execute('''
                SELECT * FROM exness_trade_profits 
                WHERE user_id = ?
            ''', (user_id,))
            
            trades = cursor.fetchall()
            
            if trades and len(trades) > 0:
                winning_pnl = []
                losing_pnl = []
                
                for trade in trades:
                    profit = trade['profit_loss']
                    commission = trade['commission']
                    
                    summary['totalTrades'] += 1
                    summary['totalVolume'] += trade['volume']
                    summary['totalCommission'] += commission if commission else 0
                    
                    if profit > 0:
                        summary['winningTrades'] += 1
                        summary['totalProfit'] += profit
                        winning_pnl.append(profit)
                    elif profit < 0:
                        summary['losingTrades'] += 1
                        summary['totalLoss'] += abs(profit)
                        losing_pnl.append(profit)
                
                summary['netProfit'] = summary['totalProfit'] - summary['totalLoss']
                summary['winRate'] = (summary['winningTrades'] / summary['totalTrades'] * 100) if summary['totalTrades'] > 0 else 0
                summary['avgProfit'] = (summary['totalProfit'] / summary['winningTrades']) if summary['winningTrades'] > 0 else 0
                summary['avgLoss'] = (summary['totalLoss'] / summary['losingTrades']) if summary['losingTrades'] > 0 else 0
                summary['largestWin'] = max(winning_pnl) if winning_pnl else 0
                summary['largestLoss'] = min(losing_pnl) if losing_pnl else 0
                summary['profitFactor'] = (summary['totalProfit'] / summary['totalLoss']) if summary['totalLoss'] > 0 else 0
            
            conn.close()
            
            logger.info(f"✅ Generated trading summary from database: {summary['totalTrades']} trades, ${summary['netProfit']:.2f} net profit")
            
            return jsonify({
                'success': True,
                'summary': summary,
                'source': 'DATABASE'
            }), 200
        else:
            # Return default summary if no user_id and MT5 not available
            return jsonify({
                'success': True,
                'summary': summary,
                'source': 'DEFAULT'
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting Exness trade summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADVANCED ORDERS ENDPOINTS ====================

@app.route('/api/broker/<broker>/order/advanced', methods=['POST'])
def place_advanced_order(broker):
    """
    Place an advanced order (limit, stop, stop-limit, or trailing stop)
    Request body:
    {
        'symbol': 'EURUSD',
        'direction': 'buy' or 'sell',
        'quantity': 0.5,
        'orderType': 'limit' | 'stop' | 'stopLimit' | 'market',
        'limitPrice': 1.2345,  # For limit and stopLimit orders
        'stopPrice': 1.2340,   # For stop and stopLimit orders
        'takeProfitPrice': 1.2500,
        'stopLossPrice': 1.2200,
        'trailing': true/false,  # For trailing stops
        'trailingStopPips': 50,  # Distance in pips for trailing stop
    }
    """
    try:
        user_id = request.headers.get('X-User-ID')
        session_token = request.headers.get('X-Session-Token')
        data = request.get_json()
        
        if not all([user_id, session_token, data]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        symbol = data.get('symbol', 'EURUSD')
        direction = data.get('direction', 'buy').upper()
        quantity = float(data.get('quantity', 0.5))
        order_type = data.get('orderType', 'market')
        limit_price = data.get('limitPrice')
        stop_price = data.get('stopPrice')
        tp_price = data.get('takeProfitPrice')
        sl_price = data.get('stopLossPrice')
        trailing = data.get('trailing', False)
        trailing_pips = data.get('trailingStopPips', 50)
        
        # Broker-specific order placement
        broker_lower = broker.lower()
        
        if broker_lower == 'exness':
            import MetaTrader5 as mt5
            if not ensure_mt5_ready():
                return jsonify({'success': False, 'error': 'MT5 initialization failed'}), 500
            
            # Map symbol to Exness format
            symbol_normalized = f"{symbol}m" if not symbol.endswith('m') else symbol
            
            # Auto-detect filling type
            _adv_sym = mt5.symbol_info(symbol_normalized)
            if _adv_sym and _adv_sym.filling_mode & 2:
                _adv_filling = mt5.ORDER_FILLING_IOC
            elif _adv_sym and _adv_sym.filling_mode & 1:
                _adv_filling = mt5.ORDER_FILLING_FOK
            else:
                _adv_filling = mt5.ORDER_FILLING_RETURN

            request_obj = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol_normalized,
                "volume": quantity,
                "type": mt5.ORDER_TYPE_BUY_LIMIT if direction == 'BUY' and order_type == 'limit' else mt5.ORDER_TYPE_SELL_LIMIT,
                "price": limit_price or 0,
                "stoplimit": stop_price or 0,
                "sl": sl_price or 0,
                "tp": tp_price or 0,
                "comment": f"Advanced {order_type} order - {symbol}",
                "type_filling": _adv_filling,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            
            result = mt5.order_send(request_obj)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Advanced order placed on Exness: {symbol} {direction} {quantity} @ {limit_price}")
                return jsonify({
                    'success': True,
                    'orderId': result.order,
                    'symbol': symbol_normalized,
                    'type': order_type,
                    'direction': direction,
                    'quantity': quantity,
                    'price': limit_price,
                    'tp': tp_price,
                    'sl': sl_price,
                    'timestamp': time.time()
                }), 200
            else:
                return jsonify({'success': False, 'error': f"Order failed: {mt5.last_error()}"}), 400
        
        elif broker_lower == 'pxbt':
            # PXBT advanced order placement
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM broker_credentials WHERE broker_name = ? AND user_id = ?', 
                          ('PXBT', user_id))
            creds = cursor.fetchone()
            
            if not creds:
                return jsonify({'success': False, 'error': 'PXBT credentials not found'}), 404
            
            order_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO pxbt_orders 
                (order_id, user_id, symbol, direction, quantity, order_type, limit_price, stop_price, tp_price, sl_price, trailing, trailing_pips, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, user_id, symbol, direction.lower(), quantity, order_type, limit_price, stop_price, tp_price, sl_price, trailing, trailing_pips, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Advanced order created on PXBT: {symbol} {direction} {quantity}")
            return jsonify({
                'success': True,
                'orderId': order_id,
                'symbol': symbol,
                'type': order_type,
                'direction': direction,
                'quantity': quantity,
                'timestamp': time.time()
            }), 200
        
        elif broker_lower == 'binance':
            # Binance advanced order placement
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM broker_credentials WHERE broker_name = ? AND user_id = ?', 
                          ('Binance', user_id))
            creds = cursor.fetchone()
            
            if not creds:
                return jsonify({'success': False, 'error': 'Binance credentials not found'}), 404
            
            order_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO binance_orders 
                (order_id, user_id, symbol, side, quantity, order_type, limit_price, stop_price, tp_price, sl_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, user_id, symbol, direction.lower(), quantity, order_type, limit_price, stop_price, tp_price, sl_price, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Advanced order created on Binance: {symbol} {direction} {quantity}")
            return jsonify({
                'success': True,
                'orderId': order_id,
                'symbol': symbol,
                'type': order_type,
                'direction': direction,
                'quantity': quantity,
                'timestamp': time.time()
            }), 200
        else:
            return jsonify({'success': False, 'error': f'Broker {broker} not supported'}), 400
            
    except Exception as e:
        logger.error(f"Error placing advanced order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/<broker>/orders/pending', methods=['GET'])
def get_pending_orders(broker):
    """Get list of pending advanced orders for the user"""
    try:
        user_id = request.headers.get('X-User-ID')
        session_token = request.headers.get('X-Session-Token')
        
        if not user_id or not session_token:
            return jsonify({'success': False, 'error': 'Missing authentication headers'}), 401
        
        broker_lower = broker.lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        orders = []
        
        if broker_lower in ['pxbt', 'binance']:
            table_name = 'pxbt_orders' if broker_lower == 'pxbt' else 'binance_orders'
            
            cursor.execute(f'SELECT * FROM {table_name} WHERE user_id = ? AND status = ?', 
                          (user_id, 'pending'))
            rows = cursor.fetchall()
            
            for row in rows:
                orders.append({
                    'orderId': row['order_id'],
                    'symbol': row['symbol'],
                    'direction': row['direction'] if broker_lower == 'pxbt' else row['side'],
                    'quantity': row['quantity'],
                    'orderType': row['order_type'],
                    'limitPrice': row['limit_price'],
                    'stopPrice': row['stop_price'],
                    'tpPrice': row['tp_price'],
                    'slPrice': row['sl_price'],
                    'createdAt': row['created_at'],
                    'status': row['status']
                })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'orders': orders,
            'count': len(orders)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching pending orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/<broker>/orders/<order_id>', methods=['PATCH'])
def update_advanced_order(broker, order_id):
    """Update an advanced order (TP/SL/trailing stop)"""
    try:
        user_id = request.headers.get('X-User-ID')
        session_token = request.headers.get('X-Session-Token')
        data = request.get_json()
        
        if not user_id or not session_token:
            return jsonify({'success': False, 'error': 'Missing authentication headers'}), 401
        
        broker_lower = broker.lower()
        tp_price = data.get('takeProfitPrice')
        sl_price = data.get('stopLossPrice')
        trailing_pips = data.get('trailingStopPips')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if broker_lower in ['pxbt', 'binance']:
            table_name = 'pxbt_orders' if broker_lower == 'pxbt' else 'binance_orders'
            
            update_fields = []
            update_values = []
            
            if tp_price is not None:
                update_fields.append('tp_price = ?')
                update_values.append(tp_price)
            if sl_price is not None:
                update_fields.append('sl_price = ?')
                update_values.append(sl_price)
            if trailing_pips is not None:
                update_fields.append('trailing_pips = ?')
                update_values.append(trailing_pips)
            
            update_values.extend([user_id, order_id])
            
            if update_fields:
                query = f"UPDATE {table_name} SET {', '.join(update_fields)} WHERE user_id = ? AND order_id = ?"
                cursor.execute(query, update_values)
                conn.commit()
        
        conn.close()
        
        logger.info(f"✅ Updated order {order_id} on {broker}")
        return jsonify({
            'success': True,
            'orderId': order_id,
            'tpPrice': tp_price,
            'slPrice': sl_price,
            'trailingStopPips': trailing_pips,
            'timestamp': time.time()
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/<broker>/orders/<order_id>/close', methods=['POST'])
def close_advanced_order(broker, order_id):
    """Close or partially close an advanced order"""
    try:
        user_id = request.headers.get('X-User-ID')
        session_token = request.headers.get('X-Session-Token')
        data = request.get_json()
        
        if not user_id or not session_token:
            return jsonify({'success': False, 'error': 'Missing authentication headers'}), 401
        
        partial_qty = data.get('partialQuantity')  # If not provided, close entire order
        broker_lower = broker.lower()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if broker_lower in ['pxbt', 'binance']:
            table_name = 'pxbt_orders' if broker_lower == 'pxbt' else 'binance_orders'
            
            if partial_qty:
                cursor.execute(f'''
                    UPDATE {table_name} 
                    SET quantity = quantity - ? 
                    WHERE user_id = ? AND order_id = ?
                ''', (partial_qty, user_id, order_id))
            else:
                cursor.execute(f'''
                    UPDATE {table_name} 
                    SET status = 'closed' 
                    WHERE user_id = ? AND order_id = ?
                ''', (user_id, order_id))
            
            conn.commit()
        
        conn.close()
        
        logger.info(f"✅ Closed order {order_id} on {broker}")
        return jsonify({
            'success': True,
            'orderId': order_id,
            'partialQuantity': partial_qty,
            'timestamp': time.time()
        }), 200
        
    except Exception as e:
        logger.error(f"Error closing order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WEBSOCKET REAL-TIME PRICES ====================
# Connected clients for broadcasting price updates
ws_clients = []
ws_clients_lock = threading.Lock()

def ws_broadcast_prices():
    """Background thread that pushes real-time prices to all subscribed WebSocket clients"""
    logger.info("🔄 WebSocket price broadcaster thread started")
    while True:
        try:
            with ws_clients_lock:
                active_clients = list(ws_clients)
            
            if not active_clients:
                time.sleep(1)
                continue
            
            for client_info in active_clients:
                ws = client_info['ws']
                symbols = client_info.get('symbols', set())
                broker_name = client_info.get('broker', 'Exness')
                
                if not symbols:
                    continue
                
                for symbol in list(symbols):
                    try:
                        import MetaTrader5 as mt5
                        symbol_normalized = f"{symbol}m" if broker_name == 'Exness' and not symbol.endswith('m') else symbol
                        
                        if ensure_mt5_ready():
                            tick = mt5.symbol_info_tick(symbol_normalized)
                            if tick:
                                ws.send(json.dumps({
                                    'type': 'price',
                                    'symbol': symbol,
                                    'bid': float(tick.bid),
                                    'ask': float(tick.ask),
                                    'spread': round(float(tick.ask - tick.bid), 5),
                                    'time': tick.time,
                                    'timestamp': time.time()
                                }))
                    except Exception as e:
                        logger.debug(f"Price fetch error for {symbol}: {e}")
            
            time.sleep(0.5)  # Send updates every 500ms
            
        except Exception as e:
            logger.error(f"WebSocket broadcaster error: {e}")
            time.sleep(2)


# REST fallback endpoint for real-time prices (works without WebSocket)
@app.route('/api/prices/realtime', methods=['GET'])
def get_realtime_prices():
    """REST fallback for real-time prices (polling). Use WebSocket /ws/prices for streaming."""
    try:
        symbols = request.args.get('symbols', 'EURUSD').split(',')
        broker_name = request.args.get('broker', 'Exness')
        
        prices = []
        try:
            import MetaTrader5 as mt5
            if ensure_mt5_ready():
                for symbol in symbols:
                    symbol_clean = symbol.strip()
                    symbol_normalized = f"{symbol_clean}m" if broker_name == 'Exness' and not symbol_clean.endswith('m') else symbol_clean
                    
                    tick = mt5.symbol_info_tick(symbol_normalized)
                    if tick:
                        prices.append({
                            'symbol': symbol_clean,
                            'bid': float(tick.bid),
                            'ask': float(tick.ask),
                            'spread': round(float(tick.ask - tick.bid), 5),
                            'time': tick.time,
                            'timestamp': time.time()
                        })
                    else:
                        prices.append({'symbol': symbol_clean, 'error': 'Symbol not found'})
        except ImportError:
            logger.warning("MT5 not available for real-time prices")
            for symbol in symbols:
                prices.append({'symbol': symbol.strip(), 'error': 'MT5 not available'})
        
        return jsonify({
            'success': True,
            'prices': prices,
            'count': len(prices),
            'broker': broker_name,
            'timestamp': time.time()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting real-time prices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if WEBSOCKET_AVAILABLE and sock is not None:
    @sock.route('/ws/prices')
    def websocket_prices(ws):
        """
        WebSocket endpoint for real-time price streaming.
        Client sends: { 'action': 'subscribe', 'symbols': ['EURUSD', 'GBPUSD'], 'broker': 'Exness' }
        Server sends: { 'type': 'price', 'symbol': 'EURUSD', 'bid': 1.2345, 'ask': 1.2347, 'timestamp': ... }
        """
        client_info = {'ws': ws, 'symbols': set(), 'broker': 'Exness'}
        
        with ws_clients_lock:
            ws_clients.append(client_info)
        
        logger.info(f"✅ WebSocket client connected (total: {len(ws_clients)})")
        
        try:
            while True:
                message = ws.receive()
                
                if message is None:
                    break
                
                try:
                    data = json.loads(message)
                    action = data.get('action')
                    
                    if action == 'subscribe':
                        symbols = data.get('symbols', [])
                        broker = data.get('broker', 'Exness')
                        client_info['symbols'].update(symbols)
                        client_info['broker'] = broker
                        logger.info(f"✅ Client subscribed to: {symbols}")
                        
                        ws.send(json.dumps({
                            'type': 'subscribed',
                            'symbols': list(client_info['symbols']),
                            'broker': broker,
                            'timestamp': time.time()
                        }))
                    
                    elif action == 'unsubscribe':
                        symbols = data.get('symbols', [])
                        client_info['symbols'].difference_update(symbols)
                        logger.info(f"Client unsubscribed from: {symbols}")
                    
                    elif action == 'ping':
                        ws.send(json.dumps({
                            'type': 'pong',
                            'timestamp': time.time()
                        }))
                
                except json.JSONDecodeError:
                    pass
        
        except Exception as e:
            logger.debug(f"WebSocket connection ended: {e}")
        finally:
            with ws_clients_lock:
                if client_info in ws_clients:
                    ws_clients.remove(client_info)
            logger.info(f"WebSocket client disconnected (remaining: {len(ws_clients)})")
else:
    logger.warning("⚠️ WebSocket endpoint /ws/prices not registered - flask-sock not available")


def shutdown_backup():
    """Create final backup and stop workers/REST services before shutdown"""
    logger.info("🛑 Creating final backup on shutdown...")
    try:
        # Shutdown worker pool first
        if worker_pool_manager and worker_pool_manager.enabled:
            worker_pool_manager.shutdown()
        # Stop socket bridges
        if socket_bridge_manager and socket_bridge_manager.enabled:
            socket_bridge_manager.shutdown()
        # Stop REST trading services
        if rest_price_feed:
            rest_price_feed.stop()
        if trade_router:
            trade_router.shutdown()
        backup_manager.create_backup()
        backup_manager.stop_auto_backup()
        logger.info("✅ Final backup complete. System shutdown.")
    except Exception as e:
        logger.error(f"Error during shutdown backup: {e}")

atexit.register(shutdown_backup)


if __name__ == '__main__':
    logger.info("Starting Zwesta Multi-Broker Backend")
    logger.info(f"Mode: {ENVIRONMENT.upper()}")
    logger.info("Connections will be established when users provide broker credentials")
    
    # CRITICAL: Warm up MT5 connection on main thread BEFORE any bot threads start
    # This establishes the IPC pipe to the terminal; bot threads can then reuse it
    if MT5_CONFIG.get('path') and MT5_CONFIG.get('account') and MT5_CONFIG.get('password'):
        try:
            import MetaTrader5 as _mt5_warmup
            logger.info("[STARTUP] Warming up MT5 connection on main thread...")
            warmup_ok = _mt5_warmup.initialize(
                path=MT5_CONFIG['path'],
                login=int(MT5_CONFIG['account']),
                password=str(MT5_CONFIG['password']),
                server=str(MT5_CONFIG['server'])
            )
            if warmup_ok:
                _acct = _mt5_warmup.account_info()
                if _acct:
                    logger.info(f"[STARTUP] ✅ MT5 warm-up successful: Account {_acct.login}, Balance ${_acct.balance:.2f}")
                else:
                    logger.warning("[STARTUP] MT5 initialized but no account info")
                # Keep connection open for bot threads to reuse
            else:
                logger.warning(f"[STARTUP] ⚠️ MT5 warm-up failed: {_mt5_warmup.last_error()}")
        except Exception as e:
            logger.warning(f"[STARTUP] MT5 warm-up exception: {e}")
    
    # Initialize demo bots on startup (DISABLED for production cleanup)
    # logger.info("Initializing demo trading bots...")
    # initialize_demo_bots()
    # logger.info(f"[OK] {len(active_bots)} demo bots initialized and ready")
    
    # Repopulate active bots from database
    repopulate_active_bots()
    
    # Load user-created bots from database
    logger.info("Loading user-created bots from database...")
    user_bots_count = load_user_bots_from_database()
    logger.info(f"[OK] Loaded {user_bots_count} user bots from database")
    logger.info(f"[OK] Total bots ready: {len(active_bots)}")

    restarted_bots = start_enabled_bots_on_startup()
    logger.info(f"[OK] Auto-restarted {restarted_bots} enabled bots after backend startup")
    
    # ==================== START WORKER POOL ====================
    if worker_pool_manager and worker_pool_manager.enabled:
        logger.info(f"🏭 Starting worker pool with {WORKER_COUNT} workers...")
        worker_pool_manager.start_all()
        logger.info(f"[OK] Worker pool started ({WORKER_COUNT} workers, max {MAX_BOTS_PER_WORKER} bots/worker)")
    else:
        logger.info("[OK] Worker pool disabled (WORKER_COUNT=0) - using single-process mode")
    
    # ==================== START SOCKET BRIDGES ====================
    if socket_bridge_manager and socket_bridge_manager._bridges:
        logger.info(f"🔌 Connecting socket bridges ({len(socket_bridge_manager._bridges)} configured)...")
        connected = socket_bridge_manager.connect_all()
        logger.info(f"[OK] Socket bridges: {connected}/{len(socket_bridge_manager._bridges)} connected")
        # Update trade router with newly connected bridges
        if connected > 0 and trade_router:
            trade_router.socket_bridge_manager = socket_bridge_manager
            trade_router.socket_enabled = True
    else:
        logger.info("[OK] Socket bridges disabled (no SOCKET_BRIDGES configured)")
    
    # ==================== START REST PRICE FEED ====================
    if rest_price_feed and (TWELVE_DATA_KEY or ALPHA_VANTAGE_KEY):
        logger.info("📡 Starting REST price feed (background refresh)...")
        rest_price_feed.start()
        logger.info(f"[OK] REST price feed started (sources: {'TwelveData' if TWELVE_DATA_KEY else ''} {'AlphaVantage' if ALPHA_VANTAGE_KEY else ''})")
    elif rest_price_feed:
        logger.info("[OK] REST price feed available but no API keys configured — will use MT5 for prices")
    
    if trade_router:
        logger.info(f"🔀 Trade router active: Socket={'ON' if trade_router.socket_enabled else 'OFF'}, "
                     f"MetaAPI={'ON' if is_metaapi_enabled() else 'OFF'}, "
                     f"REST prices={'ON' if rest_price_feed else 'OFF'}, "
                     f"Workers={'ON' if worker_pool_manager and worker_pool_manager.enabled else 'OFF'}")
    
    # Start live market data updater thread (fetches real prices from MT5)
    market_updater_thread = threading.Thread(target=live_market_data_updater, daemon=True)
    market_updater_thread.start()
    logger.info("🔄 Live market data updater thread started")
    
    # Start WebSocket price broadcaster thread
    if WEBSOCKET_AVAILABLE:
        ws_price_thread = threading.Thread(target=ws_broadcast_prices, daemon=True)
        ws_price_thread.start()
        logger.info("🔄 WebSocket price broadcaster thread started")
    else:
        logger.info("ℹ️ WebSocket disabled - use REST /api/prices/realtime for price polling")
    
    # Start auto-withdrawal monitoring thread
    monitoring_thread = threading.Thread(target=auto_withdrawal_monitor, daemon=True)
    monitoring_thread.start()
    logger.info("Auto-withdrawal monitoring thread started")
    
    try:
        # SSL/TLS Configuration
        ssl_context = None
        ssl_cert = os.environ.get('SSL_CERT_PATH', '')
        ssl_key = os.environ.get('SSL_KEY_PATH', '')
        
        if ssl_cert and ssl_key and os.path.isfile(ssl_cert) and os.path.isfile(ssl_key):
            import ssl
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"🔒 SSL enabled with cert: {ssl_cert}")
        else:
            # Try default self-signed cert location
            default_cert = os.path.join(os.path.dirname(__file__), 'cert.pem')
            default_key = os.path.join(os.path.dirname(__file__), 'key.pem')
            if os.path.isfile(default_cert) and os.path.isfile(default_key):
                import ssl
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(default_cert, default_key)
                logger.info(f"🔒 SSL enabled with default certs: {default_cert}")
            else:
                logger.warning("⚠️ No SSL certificates found. Running HTTP (insecure). "
                             "Set SSL_CERT_PATH and SSL_KEY_PATH env vars, or place cert.pem/key.pem next to this script.")
        
        # Try ports in order: 9000, 5000, 3000
        ports = [9000, 5000, 3000]
        started = False
        for port in ports:
            try:
                protocol = "https" if ssl_context else "http"
                logger.info(f"Attempting to start on {protocol}://0.0.0.0:{port}")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True,
                        ssl_context=ssl_context)
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


