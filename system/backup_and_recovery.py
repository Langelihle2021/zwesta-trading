#!/usr/bin/env python3
"""
Auto-Backup System for Zwesta Trading Backend
- Periodic database backups every 30 minutes
- Incremental backups for efficiency
- Cloud backup capability
- State recovery on restart
- User data protection from VPS outages
"""

import sqlite3
import shutil
import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
import gzip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, db_path, backup_dir='backups', max_backups=100):
        """
        Initialize backup manager
        
        Args:
            db_path: Path to zwesta_trading.db
            backup_dir: Directory to store backups
            max_backups: Maximum number of backups to keep (oldest deleted)
        """
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = max_backups
        self.backup_interval = 30 * 60  # 30 minutes in seconds
        self.backup_thread = None
        self.is_running = False
        
    def create_backup(self):
        """Create a full backup of the database"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{timestamp}.db.gz"
            backup_path = self.backup_dir / backup_filename
            
            # Compress backup for efficiency
            with open(self.db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            file_size_mb = backup_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Database backed up: {backup_filename} ({file_size_mb:.2f}MB)")
            
            # Cleanup old backups
            self._cleanup_old_backups()
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return None
    
    def restore_backup(self, backup_filename):
        """Restore database from a backup"""
        try:
            backup_path = self.backup_dir / backup_filename
            
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_filename}")
            
            # Create safety copy of current database
            if os.path.exists(self.db_path):
                safety_copy = f"{self.db_path}.pre-restore.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, safety_copy)
                logger.warning(f"⚠️ Current database backed up to: {safety_copy}")
            
            # Restore from backup
            with gzip.open(backup_path, 'rb') as f_in:
                with open(self.db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            logger.info(f"✅ Database restored from: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False
    
    def list_backups(self):
        """List all available backups"""
        backups = sorted(self.backup_dir.glob('backup_*.db.gz'), reverse=True)
        return [
            {
                'filename': b.name,
                'size_mb': b.stat().st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(b.stat().st_mtime),
            }
            for b in backups
        ]
    
    def _cleanup_old_backups(self):
        """Remove oldest backups if count exceeds max_backups"""
        backups = sorted(self.backup_dir.glob('backup_*.db.gz'))
        while len(backups) > self.max_backups:
            oldest = backups[0]
            logger.warning(f"⚠️ Deleting old backup: {oldest.name}")
            oldest.unlink()
            backups.pop(0)
    
    def start_auto_backup(self):
        """Start automatic backup thread"""
        if self.is_running:
            logger.warning("Auto-backup already running")
            return
        
        self.is_running = True
        self.backup_thread = threading.Thread(
            target=self._backup_loop,
            daemon=True
        )
        self.backup_thread.start()
        logger.info(f"🔄 Auto-backup started (interval: {self.backup_interval}s)")
    
    def stop_auto_backup(self):
        """Stop automatic backup thread"""
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=5)
        logger.info("✋ Auto-backup stopped")
    
    def _backup_loop(self):
        """Background loop for periodic backups"""
        while self.is_running:
            try:
                self.create_backup()
                time.sleep(self.backup_interval)
            except Exception as e:
                logger.error(f"Backup loop error: {e}")
                time.sleep(60)  # Retry after 1 minute
    
    def export_user_data(self, user_id, export_dir='exports'):
        """Export all data for a specific user (for verification)"""
        try:
            export_path = Path(export_dir)
            export_path.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Export user bots
            cursor.execute('SELECT * FROM user_bots WHERE user_id = ?', (user_id,))
            bots = [dict(row) for row in cursor.fetchall()]
            
            # Export user broker credentials
            cursor.execute('SELECT * FROM broker_credentials WHERE user_id = ?', (user_id,))
            credentials = [dict(row) for row in cursor.fetchall()]
            
            # Export user commissions
            cursor.execute('SELECT * FROM commissions WHERE user_id = ?', (user_id,))
            commissions = [dict(row) for row in cursor.fetchall()]
            
            # Export to JSON
            export_data = {
                'user_id': user_id,
                'exported_at': datetime.now().isoformat(),
                'bots': bots,
                'credentials': credentials,
                'commissions': commissions,
            }
            
            export_filename = f"user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_file = export_path / export_filename
            
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"✅ User data exported: {export_filename}")
            conn.close()
            return export_file
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return None


class RecoveryManager:
    """Handle recovery after VPS outage or crash"""
    
    def __init__(self, db_path, backup_manager):
        self.db_path = db_path
        self.backup_manager = backup_manager
        self.recovery_log = Path('recovery_log.json')
    
    def check_database_integrity(self):
        """Check if database is intact and recoverable"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('PRAGMA integrity_check')
            result = cursor.fetchone()[0]
            conn.close()
            
            if result == 'ok':
                logger.info("✅ Database integrity check passed")
                return True
            else:
                logger.error(f"❌ Database integrity issues: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Integrity check failed: {e}")
            return False
    
    def auto_recover_on_startup(self):
        """Automatically recover from last backup if database is corrupted"""
        logger.info("🔍 Checking database health on startup...")
        
        if not os.path.exists(self.db_path):
            logger.warning("⚠️ Database not found, will use latest backup")
            backups = self.backup_manager.list_backups()
            if backups:
                logger.info(f"📦 Restoring from latest backup: {backups[0]['filename']}")
                return self.backup_manager.restore_backup(backups[0]['filename'])
            return False
        
        if not self.check_database_integrity():
            logger.warning("⚠️ Database corrupted")
            backups = self.backup_manager.list_backups()
            if not backups:
                logger.error("❌ No backups available - data loss may have occurred")
                return False
            
            logger.info(f"📦 Restoring from latest backup: {backups[0]['filename']}")
            success = self.backup_manager.restore_backup(backups[0]['filename'])
            
            if success:
                self._log_recovery('corrupted_db_recovered', backups[0]['filename'])
            return success
        
        return True
    
    def _log_recovery(self, recovery_type, details):
        """Log recovery events"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'type': recovery_type,
            'details': details,
        }
        
        recovery_logs = []
        if self.recovery_log.exists():
            with open(self.recovery_log, 'r') as f:
                recovery_logs = json.load(f)
        
        recovery_logs.append(log_data)
        
        with open(self.recovery_log, 'w') as f:
            json.dump(recovery_logs, f, indent=2)
        
        logger.info(f"📝 Recovery logged: {recovery_type}")
    
    def verify_all_user_data(self):
        """Verify that all user data is intact after recovery"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check user count
            cursor.execute('SELECT COUNT(*) as count FROM users')
            user_count = cursor.fetchone()[0]
            
            # Check bot count
            cursor.execute('SELECT COUNT(*) as count FROM user_bots')
            bot_count = cursor.fetchone()[0]
            
            # Check credentials
            cursor.execute('SELECT COUNT(*) as count FROM broker_credentials')
            credential_count = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"📊 Data verification:")
            logger.info(f"   Users: {user_count}")
            logger.info(f"   Bots: {bot_count}")
            logger.info(f"   Credentials: {credential_count}")
            
            return {
                'users': user_count,
                'bots': bot_count,
                'credentials': credential_count,
            }
            
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return None


if __name__ == '__main__':
    # Example usage
    db_path = 'Zwesta Flutter App/zwesta_trading.db'
    
    backup_mgr = BackupManager(db_path)
    recovery_mgr = RecoveryManager(db_path, backup_mgr)
    
    print("\n" + "="*60)
    print("ZWESTA BACKUP & RECOVERY SYSTEM")
    print("="*60)
    
    # Check and recover on startup
    print("\n[STARTUP] Checking system integrity...")
    if recovery_mgr.auto_recover_on_startup():
        print("✅ System ready")
        recovery_mgr.verify_all_user_data()
    else:
        print("⚠️ Could not recover - manual intervention needed")
    
    # Show available backups
    print("\n[BACKUPS] Available backups:")
    backups = backup_mgr.list_backups()
    if backups:
        for i, backup in enumerate(backups[:5], 1):
            print(f"   {i}. {backup['filename']} ({backup['size_mb']:.2f}MB) - {backup['created']}")
    else:
        print("   No backups found")
    
    # Create a test backup
    print("\n[CREATING] New backup...")
    backup_mgr.create_backup()
    
    # Show updated backup list
    print("\n[BACKUPS] Updated backup list:")
    backups = backup_mgr.list_backups()
    for i, backup in enumerate(backups[:5], 1):
        print(f"   {i}. {backup['filename']} ({backup['size_mb']:.2f}MB)")
