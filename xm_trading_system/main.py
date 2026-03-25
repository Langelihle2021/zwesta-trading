"""
Zwesta Trading System - Multi-User Trading Bot
Processes trades for each user based on their MT5 credentials
Sends WhatsApp profit alerts via Twilio
"""
import sqlite3
import time
import threading
import logging
from datetime import datetime, timedelta
import json
import os
from enum import Enum

# Twilio for WhatsApp alerts
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("[WARN] Twilio SDK not installed. Install with: pip install twilio")

# MetaTrader5 for trading
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("[WARN] MetaTrader5 SDK not installed")

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = "zwesta_trading.db"
SCAN_INTERVAL = 5  # Scan for trades every 5 seconds
SYMBOLS_TO_TRADE = ['GOLD', 'XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD']

# Twilio Configuration (set via environment variables)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', '')  # e.g., 'whatsapp:+1234567890'

class TradeStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    FAILED = "failed"

class UserTradingSession:
    """Manages a single user's trading session"""
    
    def __init__(self, user_id, mt5_creds, db_path):
        self.user_id = user_id
        self.mt5_creds = mt5_creds
        self.db_path = db_path
        self.mt5_connected = False
        self.active_positions = []
        self.last_alert_profit = 0
        
    def connect_mt5(self):
        """Connect to user's MT5 account"""
        if not MT5_AVAILABLE:
            logger.warning(f"[User {self.user_id}] MT5 not available - using demo mode")
            return True
        
        try:
            if not mt5.initialize():
                logger.error(f"[User {self.user_id}] Failed to initialize MT5: {mt5.last_error()}")
                return False
            
            # Parse account number (remove commas if present)
            account_num = int(str(self.mt5_creds['mt5_account']).replace(',', ''))
            result = mt5.login(account_num, self.mt5_creds['mt5_password'], self.mt5_creds['mt5_server'])
            
            if result:
                logger.info(f"[User {self.user_id}] Connected to MT5 account {account_num}")
                self.mt5_connected = True
                return True
            else:
                logger.error(f"[User {self.user_id}] Failed to login: {mt5.last_error()}")
                self.mt5_connected = False
                return False
        except Exception as e:
            logger.error(f"[User {self.user_id}] Exception connecting to MT5: {str(e)}")
            self.mt5_connected = False
            return False
    
    def scan_trades(self):
        """Scan for trading opportunities and execute trades"""
        if not self.mt5_connected:
            return
        
        try:
            for symbol in SYMBOLS_TO_TRADE:
                # Get current price
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    continue
                
                # Get account info
                account_info = mt5.account_info()
                if account_info is None:
                    continue
                
                # Simple trading logic: check if we should trade
                # This is demo logic - customize based on your strategy
                balance = account_info.balance
                free_margin = account_info.margin_free
                
                # Check if we have margin available
                if free_margin > 100:
                    # Simplified strategy: random entry/exit
                    # In production, implement your actual trading logic here
                    pass
        
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error scanning trades: {str(e)}")
    
    def check_profit_threshold(self, user_data):
        """Check if profit exceeded user's alert threshold and send alert"""
        if not user_data['alert_enabled']:
            return
        
        try:
            if not self.mt5_connected:
                return
            
            account_info = mt5.account_info()
            if account_info is None:
                return
            
            current_profit = account_info.profit
            alert_threshold = user_data['alert_threshold']
            
            # Send alert if profit exceeds threshold and we haven't sent this alert level yet
            if current_profit > alert_threshold and current_profit > self.last_alert_profit:
                self.send_whatsapp_alert(user_data, current_profit)
                self.last_alert_profit = current_profit
        
        except Exception as e:
            logger.error(f"[User {self.user_id}] Error checking profit: {str(e)}")
    
    def send_whatsapp_alert(self, user_data, profit_amount):
        """Send WhatsApp profit alert to user"""
        from threading import Thread
        
        # Run in separate thread to not block trading
        thread = Thread(target=self._send_alert_async, args=(user_data, profit_amount))
        thread.daemon = True
        thread.start()
    
    def _send_alert_async(self, user_data, profit_amount):
        """Async WhatsApp alert sending"""
        if not TWILIO_AVAILABLE or not TWILIO_ACCOUNT_SID:
            logger.warning(f"[User {self.user_id}] Twilio not configured - logging alert instead")
            logger.info(f"[ALERT] User {self.user_id} ({user_data['full_name']}) reached ${profit_amount:.2f} profit!")
            return
        
        try:
            phone_number = user_data['phone_number']
            if not phone_number:
                logger.warning(f"[User {self.user_id}] No phone number on file - skipping WhatsApp alert")
                return
            
            # Format phone number for Twilio (ensure it starts with +)
            if not phone_number.startswith('+'):
                phone_number = '+' + phone_number.lstrip('+1')
            
            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            message = twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                to=f'whatsapp:{phone_number}',
                body=f"🎉 *Zwesta Trading Alert*\n\nYour account has reached ${profit_amount:.2f} profit! 💰\n\nKeep trading smart!\n\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            logger.info(f"[User {self.user_id}] WhatsApp alert sent (SID: {message.sid})")
            
            # Record alert in database
            self.record_alert(profit_amount)
        
        except Exception as e:
            logger.error(f"[User {self.user_id}] Failed to send WhatsApp alert: {str(e)}")
    
    def record_alert(self, profit_amount):
        """Record sent alert in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''INSERT INTO profit_alerts (user_id, profit_amount, alert_type, sent_date)
                VALUES (?, ?, ?, ?)''',
                (self.user_id, profit_amount, 'whatsapp', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[User {self.user_id}] Failed to record alert: {str(e)}")
    
    def disconnect_mt5(self):
        """Disconnect from MT5"""
        if MT5_AVAILABLE and self.mt5_connected:
            mt5.shutdown()
            self.mt5_connected = False
            logger.info(f"[User {self.user_id}] Disconnected from MT5")

class MultiUserTradingBot:
    """Main trading bot that manages multiple user sessions"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.user_sessions = {}
        self.is_running = False
        self.scan_thread = None
    
    def load_active_users(self):
        """Load all active users with MT5 credentials from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all users with MT5 credentials configured
            cursor.execute('''
                SELECT u.id, u.full_name, u.email, u.phone_number, u.alert_threshold, u.alert_enabled,
                       m.mt5_account, m.mt5_password, m.mt5_server, m.mt5_path, m.is_active
                FROM users u
                LEFT JOIN mt5_credentials m ON u.id = m.user_id
                WHERE u.is_active = 1
            ''')
            
            users = cursor.fetchall()
            conn.close()
            
            return users
        except Exception as e:
            logger.error(f"Failed to load active users: {str(e)}")
            return []
    
    def update_user_sessions(self):
        """Sync user sessions with database"""
        try:
            active_users = self.load_active_users()
            
            # Get current session user IDs
            current_user_ids = set(self.user_sessions.keys())
            active_user_ids = set()
            
            for user_row in active_users:
                user_id = user_row['id']
                active_user_ids.add(user_id)
                
                # Skip if user has no MT5 credentials
                if not user_row['mt5_account']:
                    if user_id in self.user_sessions:
                        logger.info(f"[User {user_id}] Removing session - no MT5 credentials")
                        session = self.user_sessions.pop(user_id)
                        session.disconnect_mt5()
                    continue
                
                # Create new session if user added MT5 credentials
                if user_id not in self.user_sessions:
                    logger.info(f"[User {user_id}] Starting new trading session ({user_row['full_name']})")
                    
                    mt5_creds = {
                        'mt5_account': user_row['mt5_account'],
                        'mt5_password': user_row['mt5_password'],
                        'mt5_server': user_row['mt5_server'],
                        'mt5_path': user_row['mt5_path']
                    }
                    
                    session = UserTradingSession(user_id, mt5_creds, self.db_path)
                    session.connect_mt5()
                    self.user_sessions[user_id] = session
            
            # Remove sessions for users no longer active
            for user_id in current_user_ids - active_user_ids:
                logger.info(f"[User {user_id}] Removing trading session")
                session = self.user_sessions.pop(user_id)
                session.disconnect_mt5()
            
            if self.user_sessions:
                logger.info(f"Active trading sessions: {len(self.user_sessions)} users")
        
        except Exception as e:
            logger.error(f"Failed to update user sessions: {str(e)}")
    
    def trading_loop(self):
        """Main trading loop - scans markets and processes trades"""
        logger.info("Trading bot started - scanning markets every 5 seconds")
        
        while self.is_running:
            try:
                # Update sessions based on database state
                self.update_user_sessions()
                
                # Process each active user's session
                for user_id, session in list(self.user_sessions.items()):
                    try:
                        # Scan for trading opportunities
                        session.scan_trades()
                        
                        # Get user data for profit checks
                        conn = sqlite3.connect(self.db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
                        user_data = dict(cursor.fetchone() or {})
                        conn.close()
                        
                        # Check if profit threshold reached
                        if user_data:
                            session.check_profit_threshold(user_data)
                    
                    except Exception as e:
                        logger.error(f"[User {user_id}] Session error: {str(e)}")
                
                # Wait before next scan
                time.sleep(SCAN_INTERVAL)
            
            except Exception as e:
                logger.error(f"Trading loop error: {str(e)}")
                time.sleep(SCAN_INTERVAL)
    
    def start(self):
        """Start the trading bot"""
        if self.is_running:
            logger.warning("Bot already running")
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self.trading_loop, daemon=True)
        self.scan_thread.start()
        logger.info("Trading bot initialized and running")
    
    def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        
        # Disconnect all user sessions
        for user_id, session in self.user_sessions.items():
            session.disconnect_mt5()
        
        self.user_sessions.clear()
        
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        
        logger.info("Trading bot stopped")

# Global bot instance
bot = None

def start_bot():
    """Start the trading bot in background"""
    global bot
    bot = MultiUserTradingBot(DB_PATH)
    bot.start()

def stop_bot():
    """Stop the trading bot"""
    global bot
    if bot:
        bot.stop()

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("Zwesta Trading Bot - Multi-User Edition")
    logger.info("="*60)
    
    # Check Twilio configuration
    if TWILIO_AVAILABLE:
        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER:
            logger.info("[OK] Twilio WhatsApp integration enabled")
        else:
            logger.warning("[WARN] Twilio credentials not configured - alerts will be logged only")
            logger.info("  Set environment variables:")
            logger.info("  - TWILIO_ACCOUNT_SID")
            logger.info("  - TWILIO_AUTH_TOKEN")
            logger.info("  - TWILIO_WHATSAPP_NUMBER (e.g., whatsapp:+1234567890)")
    else:
        logger.warning("[WARN] Twilio SDK not installed - WhatsApp alerts disabled")
        logger.info("  Install with: pip install twilio")
    
    # Check MT5
    if MT5_AVAILABLE:
        logger.info("[OK] MetaTrader5 support enabled")
    else:
        logger.warning("[WARN] MetaTrader5 SDK not available - demo mode only")
    
    logger.info("="*60)
    
    # Start bot
    start_bot()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        stop_bot()
        logger.info("Bot stopped cleanly")
