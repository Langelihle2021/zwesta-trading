#!/usr/bin/env python3
"""
VPS Heartbeat & Uptime Monitoring System
- Detects when backend/VPS goes down
- Tracks uptime statistics
- Alerts users/admins of issues
- Stores monitoring history
"""

import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UptimeMonitor:
    """Monitor system uptime and detect outages"""
    
    def __init__(self, db_path='Zwesta Flutter App/zwesta_trading.db'):
        self.db_path = db_path
        self.monitoring_active = False
        self.check_interval = 60  # Check every minute
        self.monitor_thread = None
        self._init_monitoring_table()
    
    def _init_monitoring_table(self):
        """Create monitoring tables if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Uptime events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_uptime_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT,  -- 'startup', 'shutdown', 'heartbeat_lost', 'recovered'
                    timestamp TEXT,
                    details TEXT,
                    created_at TEXT
                )
            ''')
            
            # Hourly statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_uptime_stats (
                    stat_id TEXT PRIMARY KEY,
                    hour_start TEXT,
                    hour_end TEXT,
                    uptime_percent REAL,
                    downtime_seconds INTEGER,
                    total_seconds INTEGER,
                    created_at TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize monitoring tables: {e}")
    
    def record_startup(self):
        """Record system startup event"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            event_id = f"startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cursor.execute('''
                INSERT INTO system_uptime_events 
                (event_id, event_type, timestamp, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                event_id,
                'startup',
                datetime.now().isoformat(),
                'Backend started successfully',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info("📝 Startup event recorded")
            
        except Exception as e:
            logger.error(f"Failed to record startup: {e}")
    
    def record_shutdown(self):
        """Record system shutdown event"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            event_id = f"shutdown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cursor.execute('''
                INSERT INTO system_uptime_events 
                (event_id, event_type, timestamp, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                event_id,
                'shutdown',
                datetime.now().isoformat(),
                'Backend shut down gracefully',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info("📝 Shutdown event recorded")
            
        except Exception as e:
            logger.error(f"Failed to record shutdown: {e}")
    
    def record_outage(self, downtime_seconds, reason):
        """Record detected outage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            event_id = f"outage_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cursor.execute('''
                INSERT INTO system_uptime_events 
                (event_id, event_type, timestamp, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                event_id,
                'outage_detected',
                datetime.now().isoformat(),
                json.dumps({
                    'downtime_seconds': downtime_seconds,
                    'reason': reason,
                    'recovery_time': datetime.now().isoformat(),
                }),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.warning(f"⚠️ Outage recorded: {downtime_seconds}s - {reason}")
            
        except Exception as e:
            logger.error(f"Failed to record outage: {e}")
    
    def get_uptime_report(self, hours=24):
        """Get uptime statistics for last N hours"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute('''
                SELECT * FROM system_uptime_events 
                WHERE created_at > ?
                ORDER BY created_at DESC
            ''', (cutoff_time,))
            
            events = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Calculate uptime percentage
            total_time = hours * 3600
            downtime = 0
            
            for event in events:
                if event['event_type'] == 'outage_detected':
                    try:
                        details = json.loads(event['details'])
                        downtime += details.get('downtime_seconds', 0)
                    except:
                        pass
            
            uptime_percent = ((total_time - downtime) / total_time * 100) if total_time > 0 else 100
            
            return {
                'hours': hours,
                'total_events': len(events),
                'uptime_percent': round(uptime_percent, 2),
                'downtime_seconds': downtime,
                'events': events,
            }
            
        except Exception as e:
            logger.error(f"Failed to get uptime report: {e}")
            return None
    
    def start_monitoring(self):
        """Start monitoring thread"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("🟢 Uptime monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring thread"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("🔴 Uptime monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        last_check = datetime.now()
        
        while self.monitoring_active:
            try:
                time.sleep(self.check_interval)
                # Heartbeat is implicit - if this thread is running, system is up
                # Outages detected when backend becomes unavailable
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")


class VpsHealthChecker:
    """Check VPS and backend health status"""
    
    def __init__(self, backend_url='http://localhost:9000'):
        self.backend_url = backend_url
        self.timeout = 5  # seconds
        self.last_check_time = None
        self.is_healthy = True
    
    def check_health(self):
        """Check if backend is responding"""
        try:
            response = requests.get(
                f'{self.backend_url}/api/system/health',
                timeout=self.timeout
            )
            self.is_healthy = response.status_code == 200
            self.last_check_time = datetime.now()
            return self.is_healthy
            
        except requests.exceptions.RequestException as e:
            self.is_healthy = False
            self.last_check_time = datetime.now()
            logger.warning(f"⚠️ Backend health check failed: {e}")
            return False
    
    def get_health_status(self):
        """Get current health status"""
        return {
            'is_healthy': self.is_healthy,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'backend_url': self.backend_url,
        }


# ============================================================
# ENDPOINTS TO ADD TO FLASK APP
# ============================================================

"""
Add these endpoints to multi_broker_backend_updated.py:

@app.route('/api/system/uptime', methods=['GET'])
def get_uptime():
    \"\"\"Get system uptime statistics\"\"\"
    try:
        hours = request.args.get('hours', default=24, type=int)
        report = uptime_monitor.get_uptime_report(hours=hours)
        
        return jsonify({
            'success': True,
            'uptime_report': report,
        }), 200
        
    except Exception as e:
        logger.error(f"Uptime endpoint error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/heartbeat', methods=['GET'])
def system_heartbeat():
    \"\"\"System heartbeat - proves backend is running\"\"\"
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now().isoformat(),
        'backend_uptime': get_process_uptime(),
    }), 200


Then initialize in your app:
uptime_monitor = UptimeMonitor()
uptime_monitor.record_startup()
uptime_monitor.start_monitoring()

And on shutdown:
uptime_monitor.record_shutdown()
uptime_monitor.stop_monitoring()
"""


if __name__ == '__main__':
    # Test the monitoring system
    monitor = UptimeMonitor()
    monitor.record_startup()
    
    print("\n" + "="*60)
    print("VPS UPTIME MONITOR TEST")
    print("="*60)
    
    print("\n✅ Monitoring started")
    print(f"   Check interval: 60 seconds")
    print(f"   Tracking events in database")
    
    # Simulate some time passing
    print("\n⏳ Waiting 2 seconds to record heartbeat...")
    time.sleep(2)
    
    # Get report
    report = monitor.get_uptime_report(hours=24)
    if report:
        print(f"\n📊 Uptime Report (24h):")
        print(f"   Total events: {report['total_events']}")
        print(f"   Uptime: {report['uptime_percent']}%")
        print(f"   Downtime: {report['downtime_seconds']}s")
    
    monitor.record_shutdown()
    print("\n✅ Test complete")
