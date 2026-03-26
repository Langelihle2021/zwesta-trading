"""
Trade Router - Hybrid Execution Engine for Zwesta Trader
========================================================
Routes trade requests to the optimal execution path based on
broker type, configuration, and system resources.

Execution paths:
1. MetaAPI REST (Exness/any MT5 broker with METAAPI_TOKEN configured)
2. Local MT5 (PXBT and other brokers without MetaAPI)
3. Binance REST API (crypto)
4. Worker Pool (when WORKER_COUNT > 0)

The router maintains per-account execution state and provides
a unified interface for the bot trading loop.
"""

import os
import time
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger('trade_router')


# Broker classification
REST_CAPABLE_BROKERS = {'Exness', 'XM', 'XM Global', 'IG', 'IC Markets'}
CRYPTO_BROKERS = {'Binance', 'binance'}
MT5_ONLY_BROKERS = {'PXBT', 'PrimeXBT'}


class ExecutionMode:
    """Enum for trade execution modes."""
    METAAPI = 'metaapi'       # Cloud REST API via MetaAPI
    SOCKET = 'socket_bridge'  # Self-hosted TCP socket bridge to MT5 EA
    LOCAL_MT5 = 'local_mt5'   # Direct MT5 terminal on this machine
    WORKER = 'worker_pool'    # Worker subprocess with its own MT5
    BINANCE = 'binance_api'   # Binance REST API
    DEMO = 'demo'             # Demo/paper trading (no real execution)


class AccountExecution:
    """Tracks execution state for a single trading account."""

    def __init__(self, broker, account_number, mode, connection=None):
        self.broker = broker
        self.account_number = account_number
        self.mode = mode
        self.connection = connection        # MT5Connection or MetaApiTradingBridge
        self.metaapi_account_id = None      # MetaAPI cloud account ID
        self.last_trade_time = 0
        self.trade_count = 0
        self.error_count = 0
        self.last_error = None
        self.active = True

    @property
    def cache_key(self):
        return f"{self.broker}:{self.account_number}"


class TradeRouter:
    """Routes trades to the optimal execution path."""

    def __init__(self, metaapi_client=None, price_feed=None,
                 worker_manager=None, broker_manager=None,
                 socket_bridge_manager=None):
        self.metaapi_client = metaapi_client
        self.price_feed = price_feed
        self.worker_manager = worker_manager
        self.broker_manager = broker_manager
        self.socket_bridge_manager = socket_bridge_manager

        # Execution state per account
        self._accounts = {}  # cache_key -> AccountExecution
        self._lock = threading.Lock()

        # Configuration
        self.prefer_rest = os.environ.get('PREFER_REST_TRADING', 'true').lower() == 'true'
        self.metaapi_enabled = metaapi_client is not None and metaapi_client.enabled
        self.socket_enabled = (socket_bridge_manager is not None and
                               socket_bridge_manager.enabled)
        self.workers_enabled = (worker_manager is not None and
                                worker_manager.enabled if worker_manager else False)

        logger.info(f"TradeRouter initialized: "
                    f"metaapi={self.metaapi_enabled}, "
                    f"workers={self.workers_enabled}, "
                    f"prefer_rest={self.prefer_rest}")

    def determine_mode(self, broker, account_number, is_live=False):
        """Determine the best execution mode for a given account."""
        broker_upper = broker.upper() if broker else ''
        broker_title = broker.title() if broker else ''

        # Binance → always REST API
        if broker in CRYPTO_BROKERS or broker_upper == 'BINANCE':
            return ExecutionMode.BINANCE

        # Socket bridge available for this specific account?
        if self.socket_enabled:
            if self.socket_bridge_manager.is_account_bridged(broker, str(account_number)):
                return ExecutionMode.SOCKET

        # MetaAPI available and broker supports it?
        if (self.metaapi_enabled and self.prefer_rest and
                broker_title in REST_CAPABLE_BROKERS):
            return ExecutionMode.METAAPI

        # Worker pool available?
        if self.workers_enabled:
            return ExecutionMode.WORKER

        # Default to local MT5
        return ExecutionMode.LOCAL_MT5

    def get_or_create_execution(self, broker, account_number, password=None,
                                server=None, is_live=False, user_id=None):
        """Get or create an execution context for an account.
        Returns AccountExecution with connection ready.
        """
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            if cache_key in self._accounts:
                acct = self._accounts[cache_key]
                if acct.active and acct.connection:
                    return acct

        mode = self.determine_mode(broker, account_number, is_live)
        logger.info(f"Creating execution for {broker}:{account_number} mode={mode}")

        acct = AccountExecution(broker, account_number, mode)

        if mode == ExecutionMode.SOCKET:
            acct = self._setup_socket(acct)
        elif mode == ExecutionMode.METAAPI:
            acct = self._setup_metaapi(acct, password, server, broker)
        elif mode == ExecutionMode.WORKER:
            # Worker pool handles its own connections
            acct.connection = None  # Managed by worker
        elif mode == ExecutionMode.BINANCE:
            acct.connection = None  # Managed by binance_service
        # LOCAL_MT5 and DEMO: connection will be set externally

        with self._lock:
            self._accounts[cache_key] = acct
        return acct

    def _setup_metaapi(self, acct, password, server, broker):
        """Set up MetaAPI execution for an account."""
        if not self.metaapi_client:
            acct.mode = ExecutionMode.LOCAL_MT5
            return acct

        try:
            from metaapi_client import MetaApiTradingBridge

            # Provision or find existing MetaAPI account
            metaapi_id = self.metaapi_client.get_or_provision(
                login=acct.account_number,
                password=password,
                server=server,
                broker=broker,
            )
            acct.metaapi_account_id = metaapi_id

            # Create bridge with same interface as MT5Connection
            bridge = MetaApiTradingBridge(
                client=self.metaapi_client,
                account_id=metaapi_id,
                broker=broker,
            )

            if bridge.connect():
                acct.connection = bridge
                logger.info(f"MetaAPI bridge ready for {broker}:{acct.account_number}")
            else:
                logger.warning(f"MetaAPI bridge failed, falling back to MT5")
                acct.mode = ExecutionMode.LOCAL_MT5

        except Exception as e:
            logger.error(f"MetaAPI setup error: {e}, falling back to MT5")
            acct.mode = ExecutionMode.LOCAL_MT5

        return acct

    def _setup_socket(self, acct):
        """Set up socket bridge execution for an account."""
        if not self.socket_bridge_manager:
            acct.mode = ExecutionMode.LOCAL_MT5
            return acct

        try:
            bridge = self.socket_bridge_manager.get_bridge(
                acct.broker, str(acct.account_number))
            if bridge and bridge.connected:
                acct.connection = bridge
                logger.info(f"Socket bridge ready for {acct.broker}:{acct.account_number} "
                            f"on port {bridge.port}")
            elif bridge:
                # Try reconnecting
                if bridge.connect():
                    acct.connection = bridge
                    logger.info(f"Socket bridge reconnected for {acct.broker}:{acct.account_number}")
                else:
                    logger.warning(f"Socket bridge connect failed, falling back to local MT5")
                    acct.mode = ExecutionMode.LOCAL_MT5
            else:
                logger.warning(f"No socket bridge configured for {acct.broker}:{acct.account_number}")
                acct.mode = ExecutionMode.LOCAL_MT5
        except Exception as e:
            logger.error(f"Socket bridge setup error: {e}")
            acct.mode = ExecutionMode.LOCAL_MT5

        return acct

    # ─── Trade Operations (Unified Interface) ──────────────────────────

    def place_trade(self, broker, account_number, symbol, order_type, volume,
                    stop_loss=None, take_profit=None, comment='',
                    bot_id=None, user_id=None, **kwargs):
        """Place a trade via the optimal execution path.
        Returns: {success, ticket, retcode, comment, mode}
        """
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            acct = self._accounts.get(cache_key)

        if not acct:
            return {'success': False, 'comment': 'No execution context',
                    'mode': 'none', 'retcode': -1}

        try:
            if acct.mode == ExecutionMode.SOCKET:
                result = self._trade_socket(acct, symbol, order_type, volume,
                                            stop_loss, take_profit, comment)
            elif acct.mode == ExecutionMode.METAAPI:
                result = self._trade_metaapi(acct, symbol, order_type, volume,
                                             stop_loss, take_profit, comment)
            elif acct.mode == ExecutionMode.WORKER:
                result = self._trade_worker(acct, symbol, order_type, volume,
                                            stop_loss, take_profit, comment,
                                            bot_id, user_id)
            elif acct.mode == ExecutionMode.LOCAL_MT5:
                result = self._trade_local_mt5(acct, symbol, order_type, volume,
                                               stop_loss, take_profit, comment)
            elif acct.mode == ExecutionMode.BINANCE:
                result = self._trade_binance(acct, symbol, order_type, volume,
                                             stop_loss, take_profit, comment,
                                             user_id, **kwargs)
            else:
                result = {'success': False, 'comment': f'Unknown mode {acct.mode}',
                          'retcode': -1}

            result['mode'] = acct.mode
            acct.trade_count += 1
            acct.last_trade_time = time.time()
            if not result.get('success'):
                acct.error_count += 1
                acct.last_error = result.get('comment', 'Unknown error')
            return result

        except Exception as e:
            acct.error_count += 1
            acct.last_error = str(e)
            logger.error(f"Trade error ({acct.mode}): {e}")
            return {'success': False, 'comment': str(e),
                    'mode': acct.mode, 'retcode': -1}

    def close_trade(self, broker, account_number, position_id):
        """Close a position via the routed execution path."""
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            acct = self._accounts.get(cache_key)
        if not acct:
            return False

        try:
            if acct.mode == ExecutionMode.SOCKET and acct.connection:
                return acct.connection.close_position(position_id)
            elif acct.mode == ExecutionMode.METAAPI and acct.connection:
                return acct.connection.close_position(position_id)
            elif acct.mode == ExecutionMode.LOCAL_MT5 and acct.connection:
                return acct.connection.close_position(position_id)
            elif acct.mode == ExecutionMode.WORKER and self.worker_manager:
                # Send close command to worker
                return self._worker_close(acct, position_id)
        except Exception as e:
            logger.error(f"Close trade error: {e}")
        return False

    def get_positions(self, broker, account_number):
        """Get open positions for an account."""
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            acct = self._accounts.get(cache_key)
        if not acct or not acct.connection:
            return []

        try:
            return acct.connection.get_positions()
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

    def get_price(self, symbol, broker=None, account_number=None):
        """Get current price for a symbol using best available source."""
        # Try REST price feed first (cheapest)
        if self.price_feed:
            entry = self.price_feed.get_price(symbol)
            if entry:
                return {'bid': entry.bid, 'ask': entry.ask, 'spread': entry.spread,
                        'source': entry.source}

        # Try MetaAPI
        if self.metaapi_enabled and account_number:
            cache_key = f"{broker}:{account_number}"
            with self._lock:
                acct = self._accounts.get(cache_key)
            if acct and acct.mode == ExecutionMode.METAAPI and acct.connection:
                try:
                    return acct.connection.get_symbol_price(symbol)
                except Exception:
                    pass

        return None

    def get_candles(self, symbol, count=50, broker=None, account_number=None):
        """Get candle history for signal evaluation."""
        # REST price feed (most efficient)
        if self.price_feed:
            candles = self.price_feed.get_candles(symbol, count)
            if candles and len(candles) >= count // 2:
                return candles

        # MetaAPI
        if self.metaapi_enabled and account_number:
            cache_key = f"{broker}:{account_number}"
            with self._lock:
                acct = self._accounts.get(cache_key)
            if acct and acct.mode == ExecutionMode.METAAPI and acct.connection:
                try:
                    return acct.connection.get_candle_history(
                        symbol, timeframe='5m', count=count)
                except Exception:
                    pass

        return []

    # ─── Private Execution Methods ─────────────────────────────────────

    def _trade_socket(self, acct, symbol, order_type, volume, sl, tp, comment):
        """Execute trade via socket bridge to MT5 EA."""
        if not acct.connection:
            return {'success': False, 'comment': 'No socket bridge', 'retcode': -1}

        result = acct.connection.place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            stopLoss=sl,
            takeProfit=tp,
            comment=comment,
        )
        return result

    def _trade_metaapi(self, acct, symbol, order_type, volume, sl, tp, comment):
        """Execute trade via MetaAPI REST."""
        if not acct.connection:
            return {'success': False, 'comment': 'No MetaAPI connection', 'retcode': -1}

        result = acct.connection.place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            stopLoss=sl,
            takeProfit=tp,
            comment=comment,
        )
        return result

    def _trade_local_mt5(self, acct, symbol, order_type, volume, sl, tp, comment):
        """Execute trade via local MT5 terminal."""
        if not acct.connection:
            return {'success': False, 'comment': 'No MT5 connection', 'retcode': -1}

        result = acct.connection.place_order(
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            stopLoss=sl,
            takeProfit=tp,
            comment=comment,
        )
        return result

    def _trade_worker(self, acct, symbol, order_type, volume, sl, tp, comment,
                      bot_id, user_id):
        """Dispatch trade to worker pool."""
        if not self.worker_manager:
            return {'success': False, 'comment': 'Worker pool not available',
                    'retcode': -1}
        # Worker pool handles execution asynchronously
        # Trade will be placed by worker subprocess
        return {'success': True, 'comment': 'Dispatched to worker pool',
                'ticket': None, 'retcode': 0}

    def _trade_binance(self, acct, symbol, order_type, volume, sl, tp, comment,
                       user_id, **kwargs):
        """Execute trade via Binance REST API."""
        # Binance trading handled by existing binance_service.py
        return {'success': False, 'comment': 'Binance trades handled by binance_service',
                'retcode': -1}

    def _worker_close(self, acct, position_id):
        """Send close command to worker via DB queue."""
        try:
            import sqlite3
            db_path = os.environ.get('DATABASE_PATH', 'zwesta_trading.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO worker_bot_queue (worker_id, command, payload, created_at)
                SELECT worker_id, 'close_position', ?, datetime('now')
                FROM worker_bot_assignments
                WHERE account_number = ?
                LIMIT 1
            ''', (f'{{"position_id": "{position_id}"}}', str(acct.account_number)))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Worker close error: {e}")
            return False

    # ─── Status & Admin ────────────────────────────────────────────────

    def get_status(self):
        """Get router status for admin dashboard."""
        with self._lock:
            accounts = {}
            for key, acct in self._accounts.items():
                accounts[key] = {
                    'broker': acct.broker,
                    'account': acct.account_number,
                    'mode': acct.mode,
                    'active': acct.active,
                    'trades': acct.trade_count,
                    'errors': acct.error_count,
                    'last_trade': acct.last_trade_time,
                    'last_error': acct.last_error,
                    'connected': bool(acct.connection and
                                      getattr(acct.connection, 'connected', False)),
                }

        mode_counts = {}
        for acct_info in accounts.values():
            m = acct_info['mode']
            mode_counts[m] = mode_counts.get(m, 0) + 1

        return {
            'socket_enabled': self.socket_enabled,
            'metaapi_enabled': self.metaapi_enabled,
            'workers_enabled': self.workers_enabled,
            'prefer_rest': self.prefer_rest,
            'total_accounts': len(accounts),
            'mode_distribution': mode_counts,
            'accounts': accounts,
        }

    def set_account_connection(self, broker, account_number, connection):
        """Manually set a connection for an account (used by legacy MT5 path)."""
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            if cache_key in self._accounts:
                self._accounts[cache_key].connection = connection
            else:
                mode = self.determine_mode(broker, account_number)
                acct = AccountExecution(broker, account_number, mode, connection)
                self._accounts[cache_key] = acct

    def shutdown(self):
        """Clean up all connections."""
        with self._lock:
            for key, acct in self._accounts.items():
                acct.active = False
            self._accounts.clear()
        logger.info("TradeRouter shutdown complete")


# ─── Module Singleton ──────────────────────────────────────────────────

_global_router = None
_router_lock = threading.Lock()


def get_trade_router():
    """Get or create the global trade router singleton."""
    global _global_router
    with _router_lock:
        if _global_router is None:
            _global_router = TradeRouter()
        return _global_router


def init_trade_router(metaapi_client=None, price_feed=None,
                      worker_manager=None, broker_manager=None,
                      socket_bridge_manager=None):
    """Initialize the global trade router with dependencies."""
    global _global_router
    with _router_lock:
        _global_router = TradeRouter(
            metaapi_client=metaapi_client,
            price_feed=price_feed,
            worker_manager=worker_manager,
            broker_manager=broker_manager,
            socket_bridge_manager=socket_bridge_manager,
        )
    return _global_router
