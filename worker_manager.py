#!/usr/bin/env python3
"""
Worker Manager - Zwesta Trading Platform
==========================================
Manages a pool of MT5 worker subprocesses for scaling to 100+ users.

Usage from backend:
    from worker_manager import WorkerPoolManager
    wpm = WorkerPoolManager(worker_count=3)
    wpm.start_all()
    wpm.dispatch_bot('bot_123', 'user_456', bot_config, credentials)
    wpm.stop_bot('bot_123')
    wpm.shutdown()

When WORKER_COUNT=0 (default), the system falls back to the original
single-process threading model. This makes the worker pool opt-in.
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get('DATABASE_PATH', r'C:\backend\zwesta_trading.db')
WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mt5_worker.py')
HEARTBEAT_TIMEOUT = 30  # seconds before a worker is considered dead
MONITOR_INTERVAL = 15   # seconds between health checks


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


class WorkerPoolManager:
    """Manages a pool of MT5 worker subprocesses."""

    def __init__(self, worker_count: int = 0, max_bots_per_worker: int = 35):
        self.worker_count = worker_count
        self.max_bots_per_worker = max_bots_per_worker
        self.workers = {}          # worker_id -> subprocess.Popen
        self.monitor_thread = None
        self.running = False
        self._lock = threading.Lock()

        if self.worker_count > 0:
            logger.info(f"WorkerPoolManager: Configured for {worker_count} workers "
                        f"(max {max_bots_per_worker} bots/worker)")
        else:
            logger.info("WorkerPoolManager: DISABLED (WORKER_COUNT=0, using single-process mode)")

    @property
    def enabled(self) -> bool:
        return self.worker_count > 0

    def start_all(self):
        """Start all configured workers."""
        if not self.enabled:
            return

        self.running = True

        for wid in range(1, self.worker_count + 1):
            self._start_worker(wid)

        # Start health-check monitor
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True,
                                               name="WorkerMonitor")
        self.monitor_thread.start()
        logger.info(f"Worker pool started: {len(self.workers)} workers active")

    def _start_worker(self, worker_id: int):
        """Launch a single worker subprocess."""
        with self._lock:
            if worker_id in self.workers:
                proc = self.workers[worker_id]
                if proc.poll() is None:
                    logger.debug(f"Worker {worker_id} already running (PID {proc.pid})")
                    return

            python_exe = sys.executable
            log_file = f'worker_{worker_id}.log'

            try:
                proc = subprocess.Popen(
                    [python_exe, WORKER_SCRIPT, str(worker_id)],
                    stdout=open(log_file, 'a', encoding='utf-8'),
                    stderr=subprocess.STDOUT,
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                )
                self.workers[worker_id] = proc
                logger.info(f"Worker {worker_id} started (PID {proc.pid})")
            except Exception as e:
                logger.error(f"Failed to start worker {worker_id}: {e}")

    def _monitor_loop(self):
        """Periodically check worker health and restart dead workers."""
        while self.running:
            try:
                self._check_workers()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(MONITOR_INTERVAL)

    def _check_workers(self):
        """Check heartbeats and restart unresponsive workers."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT worker_id, pid, status, heartbeat_at FROM worker_pool')
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not read worker_pool: {e}")
            return

        now = datetime.now()
        healthy_workers = set()

        for row in rows:
            row = dict(row)
            wid = row['worker_id']
            status = row.get('status', 'unknown')
            heartbeat = row.get('heartbeat_at')

            if status == 'running' and heartbeat:
                try:
                    last_hb = datetime.fromisoformat(heartbeat)
                    if (now - last_hb).total_seconds() < HEARTBEAT_TIMEOUT:
                        healthy_workers.add(wid)
                        continue
                except (ValueError, TypeError):
                    pass

            # Worker is dead or unresponsive
            if wid in self.workers:
                logger.warning(f"Worker {wid}: unhealthy (status={status}), restarting...")
                self._kill_worker(wid)
                self._start_worker(wid)

        # Also check any workers we launched but that aren't in the DB yet
        with self._lock:
            for wid, proc in list(self.workers.items()):
                if proc.poll() is not None:
                    logger.warning(f"Worker {wid}: process exited (code {proc.returncode}), restarting...")
                    self._start_worker(wid)

    def _kill_worker(self, worker_id: int):
        """Terminate a worker subprocess."""
        with self._lock:
            proc = self.workers.get(worker_id)
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception as e:
                    logger.error(f"Error killing worker {worker_id}: {e}")

    def find_best_worker(self, account_number: str = None, broker_name: str = None) -> int:
        """
        Find the best worker to assign a new bot to.

        Strategy:
        1. If another bot for the SAME account is already on a worker, use that worker
           (avoids MT5 account switching).
        2. Otherwise, pick the worker with the fewest bots.
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 1. Check if this account is already on a worker
            if account_number:
                cursor.execute('''
                    SELECT worker_id FROM worker_bot_assignments
                    WHERE account_number = ? LIMIT 1
                ''', (str(account_number),))
                row = cursor.fetchone()
                if row:
                    wid = row['worker_id']
                    # Verify worker has capacity
                    cursor.execute('''
                        SELECT COUNT(*) as cnt FROM worker_bot_assignments WHERE worker_id = ?
                    ''', (wid,))
                    cnt = cursor.fetchone()['cnt']
                    if cnt < self.max_bots_per_worker:
                        conn.close()
                        return wid

            # 2. Pick worker with fewest bots
            cursor.execute('''
                SELECT wp.worker_id, COALESCE(bc.cnt, 0) as bot_count
                FROM worker_pool wp
                LEFT JOIN (
                    SELECT worker_id, COUNT(*) as cnt FROM worker_bot_assignments GROUP BY worker_id
                ) bc ON wp.worker_id = bc.worker_id
                WHERE wp.status = 'running'
                ORDER BY bot_count ASC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            conn.close()

            if row:
                return row['worker_id']

            # Fallback: worker 1
            return 1

        except Exception as e:
            logger.error(f"find_best_worker error: {e}")
            return 1

    def dispatch_bot(self, bot_id: str, user_id: str, bot_config: Dict,
                     credentials: Dict = None) -> bool:
        """
        Dispatch a bot to the optimal worker via the command queue.
        Returns True if dispatch succeeded.
        """
        if not self.enabled:
            return False

        account_number = (credentials or {}).get('account_number', '') or \
                         bot_config.get('accountId', '')
        broker_name = bot_config.get('brokerName', 'MT5')

        worker_id = self.find_best_worker(account_number, broker_name)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Insert command into queue
            cursor.execute('''
                INSERT INTO worker_bot_queue
                (bot_id, user_id, worker_id, command, status, bot_config, credentials, created_at)
                VALUES (?, ?, ?, 'start', 'pending', ?, ?, ?)
            ''', (bot_id, user_id, worker_id,
                  json.dumps(bot_config) if bot_config else None,
                  json.dumps(credentials) if credentials else None,
                  now))

            # Create or update assignment
            cursor.execute('''
                INSERT OR REPLACE INTO worker_bot_assignments
                (bot_id, worker_id, account_number, broker_name, assigned_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (bot_id, worker_id, str(account_number), broker_name, now))

            conn.commit()
            conn.close()

            logger.info(f"Bot {bot_id} dispatched to worker {worker_id} "
                        f"(account={account_number}, broker={broker_name})")
            return True

        except Exception as e:
            logger.error(f"dispatch_bot error: {e}")
            return False

    def stop_bot(self, bot_id: str) -> bool:
        """Send a stop command to the worker running this bot."""
        if not self.enabled:
            return False

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Find which worker has this bot
            cursor.execute('''
                SELECT worker_id FROM worker_bot_assignments WHERE bot_id = ?
            ''', (bot_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                logger.warning(f"stop_bot: No worker assignment for bot {bot_id}")
                return False

            worker_id = row['worker_id']

            # Queue stop command
            cursor.execute('''
                INSERT INTO worker_bot_queue
                (bot_id, user_id, worker_id, command, status, created_at)
                VALUES (?, '', ?, 'stop', 'pending', ?)
            ''', (bot_id, worker_id, datetime.now().isoformat()))

            # Remove assignment
            cursor.execute('DELETE FROM worker_bot_assignments WHERE bot_id = ?', (bot_id,))

            conn.commit()
            conn.close()

            logger.info(f"Stop command queued for bot {bot_id} on worker {worker_id}")
            return True

        except Exception as e:
            logger.error(f"stop_bot error: {e}")
            return False

    def get_worker_status(self) -> List[Dict]:
        """Get status of all workers (for admin/monitoring API)."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT wp.worker_id, wp.pid, wp.status, wp.heartbeat_at, wp.bot_count,
                       wp.started_at, wp.error_message
                FROM worker_pool wp
                ORDER BY wp.worker_id
            ''')
            rows = cursor.fetchall()
            conn.close()

            result = []
            for row in rows:
                row = dict(row)
                # Check if process is still alive
                pid = row.get('pid')
                is_alive = False
                if pid:
                    try:
                        os.kill(pid, 0)
                        is_alive = True
                    except (ProcessLookupError, PermissionError, OSError):
                        pass

                row['is_alive'] = is_alive
                result.append(row)

            return result

        except Exception as e:
            logger.error(f"get_worker_status error: {e}")
            return []

    def shutdown(self):
        """Stop all workers gracefully."""
        self.running = False
        logger.info("Shutting down worker pool...")

        with self._lock:
            for wid, proc in self.workers.items():
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=10)
                        logger.info(f"Worker {wid} terminated")
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        logger.warning(f"Worker {wid} force-killed")
                    except Exception as e:
                        logger.error(f"Error stopping worker {wid}: {e}")

        # Update DB
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE worker_pool SET status = 'stopped', stopped_at = ?",
                           (datetime.now().isoformat(),))
            conn.commit()
            conn.close()
        except Exception:
            pass

        logger.info("Worker pool shutdown complete")
