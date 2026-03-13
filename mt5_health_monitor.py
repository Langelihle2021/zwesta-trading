#!/usr/bin/env python3
"""
MT5 Health Monitor - Automatic Restart on Disconnection
Monitors MT5 connection status and auto-restarts if disconnected
Runs as a background service/daemon
"""

import MetaTrader5 as mt5
import time
import logging
import subprocess
import os
import sys
from datetime import datetime, timedelta
import psutil
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler('mt5_health_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MT5 Configuration
MT5_CONFIG = {
    'account': 104254514,
    'password': 'Ztxb@1234',
    'server': 'MetaQuotes-Demo',
    'terminal_path': r'C:\Program Files\MetaTrader 5\terminal64.exe'
}

# Monitoring Configuration
CHECK_INTERVAL = 30  # Check every 30 seconds
MAX_CONSECUTIVE_FAILURES = 3  # Restart after 3 consecutive failures
RESTART_TIMEOUT = 60  # Wait 60 seconds for MT5 to start
HEALTH_CHECK_COOLDOWN = 5  # Wait 5 seconds after restart before checking

class MT5HealthMonitor:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_restart_time = None
        self.restart_cooldown = timedelta(minutes=5)  # Don't restart more than every 5 minutes
        self.is_connected = False
        
    def check_mt5_process(self):
        """Check if MT5 process is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'terminal64.exe' in proc.info['name'].lower() or 'terminal.exe' in proc.info['name'].lower():
                    logger.info(f"✅ MT5 process found (PID: {proc.info['pid']})")
                    return True
            logger.warning("⚠️  MT5 process NOT running")
            return False
        except Exception as e:
            logger.error(f"Error checking MT5 process: {e}")
            return False
    
    def test_mt5_connection(self):
        """Test connection to MT5"""
        try:
            # Initialize MT5
            if not mt5.initialize(path=MT5_CONFIG['terminal_path']):
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            
            # Try to login
            if not mt5.login(
                login=MT5_CONFIG['account'],
                password=MT5_CONFIG['password'],
                server=MT5_CONFIG['server']
            ):
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            # Try to get account info (simple connection test)
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("MT5 account_info returned None - connection unstable")
                mt5.shutdown()
                return False
            
            logger.info(f"✅ MT5 connection OK | Account: {account_info.login} | Balance: ${account_info.balance}")
            mt5.shutdown()
            return True
            
        except Exception as e:
            logger.error(f"MT5 connection test error: {e}")
            try:
                mt5.shutdown()
            except:
                pass
            return False
    
    def restart_mt5(self):
        """Restart MT5 terminal"""
        logger.warning("🔄 Attempting to restart MT5...")
        
        # Check cooldown
        if self.last_restart_time:
            time_since_restart = datetime.now() - self.last_restart_time
            if time_since_restart < self.restart_cooldown:
                logger.warning(f"⏳ Restart cooldown active ({self.restart_cooldown.total_seconds() - time_since_restart.total_seconds():.0f}s remaining)")
                return False
        
        try:
            # Kill existing MT5 processes
            logger.info("Killing existing MT5 processes...")
            for proc in psutil.process_iter(['pid', 'name']):
                if 'terminal64.exe' in proc.info['name'].lower() or 'terminal.exe' in proc.info['name'].lower():
                    try:
                        proc.kill()
                        logger.info(f"Killed MT5 process (PID: {proc.info['pid']})")
                        time.sleep(2)
                    except Exception as e:
                        logger.error(f"Error killing process: {e}")
            
            # Wait for processes to fully terminate
            time.sleep(3)
            
            # Start MT5
            logger.info(f"Starting MT5 from: {MT5_CONFIG['terminal_path']}")
            subprocess.Popen([MT5_CONFIG['terminal_path']])
            
            logger.info("✅ MT5 restart command sent")
            self.last_restart_time = datetime.now()
            self.consecutive_failures = 0
            
            # Wait for MT5 to start
            logger.info(f"⏳ Waiting {RESTART_TIMEOUT}s for MT5 to start...")
            time.sleep(RESTART_TIMEOUT)
            
            return True
            
        except Exception as e:
            logger.error(f"Error restarting MT5: {e}")
            return False
    
    def run(self):
        """Main monitoring loop"""
        logger.info("=" * 60)
        logger.info("🟢 MT5 HEALTH MONITOR STARTED")
        logger.info("=" * 60)
        logger.info(f"Account: {MT5_CONFIG['account']}")
        logger.info(f"Server: {MT5_CONFIG['server']}")
        logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        logger.info(f"Max Failures: {MAX_CONSECUTIVE_FAILURES}")
        logger.info("=" * 60)
        
        while True:
            try:
                logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Checking MT5 health...")
                
                # Check if process is running
                if not self.check_mt5_process():
                    self.consecutive_failures += 1
                    logger.error(f"Failure #{self.consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")
                    
                    if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        self.restart_mt5()
                    else:
                        time.sleep(CHECK_INTERVAL)
                        continue
                
                # Test connection
                if not self.test_mt5_connection():
                    self.consecutive_failures += 1
                    logger.error(f"Connection failed ({self.consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")
                    
                    if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        self.restart_mt5()
                else:
                    self.consecutive_failures = 0
                    self.is_connected = True
                
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    self.restart_mt5()
                time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    monitor = MT5HealthMonitor()
    monitor.run()
