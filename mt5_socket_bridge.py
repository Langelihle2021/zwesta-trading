"""
MT5 Socket Bridge Client for Zwesta Trader
============================================
Connects to ZwestaTradeServer EA running inside MT5 terminals via TCP sockets.
Provides the same interface as MetaApiTradingBridge for seamless drop-in use.

Architecture:
    Flask Backend  →  MT5SocketBridge (this)  →  TCP localhost:800X  →  ZwestaTradeServer.mq5 (in MT5)

Each MT5 terminal runs the EA on a unique port (8001, 8002, 8003...).
One terminal per broker account. Bridge auto-reconnects on connection loss.
"""

import json
import socket
import time
import logging
import threading
from typing import Optional, Dict, List, Any

logger = logging.getLogger('mt5_socket_bridge')

# Default config
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8001
DEFAULT_AUTH_TOKEN = 'zwesta'
RECV_BUFFER_SIZE = 65536
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 10


class MT5SocketBridge:
    """Bridge to MT5 terminal via TCP socket.
    Same interface as MetaApiTradingBridge — drop-in replacement.
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 auth_token=DEFAULT_AUTH_TOKEN, broker='Exness',
                 account_number=None, auto_reconnect=True):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.broker = broker
        self.account_number = account_number
        self.auto_reconnect = auto_reconnect

        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._recv_buffer = ''
        self.connected = False

        # Compatibility with MetaApiTradingBridge
        self.broker_type = type('BrokerType', (), {'value': broker})()
        self._last_balance = 0
        self._last_equity = 0

        # Stats
        self.command_count = 0
        self.error_count = 0
        self.last_error = None
        self.connect_time = None

    def connect(self) -> bool:
        """Connect to the MT5 Trade Server EA."""
        with self._lock:
            return self._connect_internal()

    def _connect_internal(self) -> bool:
        """Internal connect (must hold _lock)."""
        try:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(CONNECT_TIMEOUT)
            self._socket.connect((self.host, self.port))
            self._socket.settimeout(READ_TIMEOUT)
            self._recv_buffer = ''

            # Verify connection with ping
            ping_result = self._send_command_internal({'cmd': 'ping', 'token': self.auth_token})
            if ping_result and ping_result.get('success'):
                self.connected = True
                self.connect_time = time.time()
                account = ping_result.get('account', '?')
                server = ping_result.get('server', '?')
                logger.info(f"🔌 Socket bridge connected: {self.host}:{self.port} "
                            f"(Account {account} @ {server})")
                return True
            else:
                logger.error(f"Socket bridge ping failed: {ping_result}")
                self._socket.close()
                self._socket = None
                self.connected = False
                return False

        except Exception as e:
            logger.error(f"Socket bridge connect error ({self.host}:{self.port}): {e}")
            self.last_error = str(e)
            self._socket = None
            self.connected = False
            return False

    def _ensure_connected(self) -> bool:
        """Reconnect if needed."""
        if self.connected and self._socket:
            return True
        if self.auto_reconnect:
            logger.info(f"Reconnecting socket bridge to {self.host}:{self.port}...")
            return self._connect_internal()
        return False

    def _send_command(self, cmd_dict: dict) -> Optional[dict]:
        """Send a JSON command and receive response. Thread-safe."""
        with self._lock:
            if not self._ensure_connected():
                return {'success': False, 'error': 'not_connected'}
            return self._send_command_internal(cmd_dict)

    def _send_command_internal(self, cmd_dict: dict) -> Optional[dict]:
        """Internal send (must hold _lock). Sends JSON + newline, reads response."""
        try:
            # Add auth token
            cmd_dict['token'] = self.auth_token

            # Send JSON + newline delimiter
            data = json.dumps(cmd_dict, separators=(',', ':')) + '\n'
            self._socket.sendall(data.encode('utf-8'))
            self.command_count += 1

            # Read response until newline
            response = self._read_line()
            if response:
                return json.loads(response)
            return None

        except (socket.timeout, socket.error, ConnectionError) as e:
            logger.warning(f"Socket error: {e}")
            self.connected = False
            self.error_count += 1
            self.last_error = str(e)
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            return {'success': False, 'error': str(e)}

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            self.error_count += 1
            return {'success': False, 'error': f'json_error: {e}'}

    def _read_line(self) -> Optional[str]:
        """Read bytes until newline delimiter."""
        while '\n' not in self._recv_buffer:
            chunk = self._socket.recv(RECV_BUFFER_SIZE)
            if not chunk:
                raise ConnectionError("Connection closed by MT5")
            self._recv_buffer += chunk.decode('utf-8')

        nl_pos = self._recv_buffer.index('\n')
        line = self._recv_buffer[:nl_pos]
        self._recv_buffer = self._recv_buffer[nl_pos + 1:]
        return line.strip()

    def disconnect(self):
        """Close the socket connection."""
        with self._lock:
            self.connected = False
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            logger.info(f"Socket bridge disconnected from {self.host}:{self.port}")

    # ─── MetaApiTradingBridge-compatible interface ─────────────────────

    def wait_for_mt5_ready(self, timeout_seconds=30) -> bool:
        """Check if bridge is connected and MT5 is responsive."""
        if self.connected:
            result = self._send_command({'cmd': 'ping'})
            return result and result.get('success', False)
        return self.connect()

    def get_balance(self) -> float:
        """Get account balance."""
        result = self._send_command({'cmd': 'account_info'})
        if result and result.get('success'):
            self._last_balance = float(result.get('balance', 0))
            self._last_equity = float(result.get('equity', 0))
            return self._last_balance
        return self._last_balance

    def get_account_info(self) -> dict:
        """Get full account info."""
        result = self._send_command({'cmd': 'account_info'})
        if result and result.get('success'):
            self._last_balance = float(result.get('balance', 0))
            self._last_equity = float(result.get('equity', 0))
            return result
        return {'balance': self._last_balance, 'equity': self._last_equity}

    def place_order(self, symbol, order_type, volume, **kwargs):
        """Place a market order. Compatible with MetaApiTradingBridge."""
        sl = kwargs.get('stopLoss') or kwargs.get('stop_loss')
        tp = kwargs.get('takeProfit') or kwargs.get('take_profit')
        comment = kwargs.get('comment', '')

        cmd = {
            'cmd': 'place_order',
            'symbol': symbol,
            'action': order_type.upper(),
            'volume': float(volume),
        }
        if sl and float(sl) > 0:
            cmd['stop_loss'] = float(sl)
        if tp and float(tp) > 0:
            cmd['take_profit'] = float(tp)
        if comment:
            cmd['comment'] = str(comment)[:31]

        result = self._send_command(cmd)

        if result and result.get('success'):
            return {
                'success': True,
                'ticket': result.get('ticket', 0),
                'deal': result.get('deal', 0),
                'retcode': result.get('retcode', 10009),
                'price': result.get('price', 0),
                'volume': result.get('volume', volume),
                'comment': 'OK',
                'positionId': str(result.get('ticket', '')),
            }
        return {
            'success': False,
            'ticket': None,
            'retcode': result.get('retcode', -1) if result else -1,
            'comment': result.get('error', 'Socket trade failed') if result else 'No response',
        }

    def get_positions(self) -> list:
        """Get open positions. Returns list compatible with backend format."""
        result = self._send_command({'cmd': 'get_positions'})
        if not result or not result.get('success'):
            return []

        positions = result.get('positions', [])
        formatted = []
        for p in positions:
            pnl = float(p.get('pnl', 0))
            swap = float(p.get('swap', 0))
            formatted.append({
                'ticket': p.get('ticket', 0),
                'symbol': p.get('symbol', ''),
                'type': p.get('type', 'BUY'),
                'volume': float(p.get('volume', 0)),
                'openPrice': float(p.get('openPrice', 0)),
                'currentPrice': float(p.get('currentPrice', 0)),
                'pnl': pnl,
                'netProfit': pnl + swap,
                'swap': swap,
                'sl': float(p.get('sl', 0)),
                'tp': float(p.get('tp', 0)),
                'openTime': p.get('openTime', 0),
                'commission': 0,
            })
        return formatted

    def close_position(self, position_id) -> bool:
        """Close an open position by ticket."""
        result = self._send_command({
            'cmd': 'close_position',
            'ticket': int(position_id),
        })
        return result and result.get('success', False)

    def modify_position_stop_loss(self, position_id=None, new_sl=None, **kwargs):
        """Modify stop loss on a position."""
        pid = position_id or kwargs.get('ticket')
        sl = new_sl or kwargs.get('new_stop_loss')
        tp = kwargs.get('take_profit', 0)

        result = self._send_command({
            'cmd': 'modify_position',
            'ticket': int(pid),
            'stop_loss': float(sl) if sl else 0,
            'take_profit': float(tp) if tp else 0,
        })
        return result and result.get('success', False)

    def get_symbol_price(self, symbol) -> dict:
        """Get current bid/ask for a symbol."""
        result = self._send_command({
            'cmd': 'symbol_price',
            'symbol': symbol,
        })
        if result and result.get('success'):
            return {
                'bid': float(result.get('bid', 0)),
                'ask': float(result.get('ask', 0)),
                'spread': float(result.get('spread', 0)),
                'time': result.get('time', 0),
            }
        return {'bid': 0, 'ask': 0, 'spread': 0}

    def get_symbol_info(self, symbol) -> dict:
        """Get symbol specification (point, digits, lot sizes, etc.)."""
        result = self._send_command({
            'cmd': 'symbol_info',
            'symbol': symbol,
        })
        if result and result.get('success'):
            return result
        return {}

    def get_candle_history(self, symbol, timeframe='5m', count=50) -> list:
        """Get OHLCV candle history."""
        result = self._send_command({
            'cmd': 'candles',
            'symbol': symbol,
            'timeframe': timeframe,
            'count': int(count),
        })
        if result and result.get('success'):
            return result.get('candles', [])
        return []

    def get_status(self) -> dict:
        """Get bridge status summary."""
        return {
            'connected': self.connected,
            'host': self.host,
            'port': self.port,
            'broker': self.broker,
            'account': self.account_number,
            'commands_sent': self.command_count,
            'errors': self.error_count,
            'last_error': self.last_error,
            'uptime': time.time() - self.connect_time if self.connect_time else 0,
        }


class SocketBridgeManager:
    """Manages multiple MT5 socket bridges for different accounts.
    Each account maps to one MT5 terminal running the EA on a unique port.
    """

    def __init__(self, auth_token=DEFAULT_AUTH_TOKEN):
        self.auth_token = auth_token
        self._bridges: Dict[str, MT5SocketBridge] = {}  # "broker:account" -> bridge
        self._port_map: Dict[int, str] = {}  # port -> "broker:account"
        self._lock = threading.Lock()
        self._next_port = 8001
        self.enabled = False

    def configure_from_env(self):
        """Load socket bridge config from environment.
        Format: SOCKET_BRIDGES=broker1:account1:port1,broker2:account2:port2
        Example: SOCKET_BRIDGES=Exness:298997455:8001,PXBT:1226483:8002
        """
        import os
        config = os.environ.get('SOCKET_BRIDGES', '')
        auth = os.environ.get('SOCKET_AUTH_TOKEN', self.auth_token)
        self.auth_token = auth

        if not config:
            logger.info("No SOCKET_BRIDGES configured (use SOCKET_BRIDGES=broker:account:port,...)")
            return

        for entry in config.split(','):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(':')
            if len(parts) != 3:
                logger.warning(f"Invalid bridge config: {entry} (expected broker:account:port)")
                continue

            broker, account, port_str = parts
            try:
                port = int(port_str)
            except ValueError:
                logger.warning(f"Invalid port in bridge config: {port_str}")
                continue

            self.add_bridge(broker, account, port)

        if self._bridges:
            self.enabled = True
            logger.info(f"Socket bridge manager: {len(self._bridges)} bridges configured")

    def add_bridge(self, broker: str, account_number: str, port: int,
                   host: str = DEFAULT_HOST) -> MT5SocketBridge:
        """Add a socket bridge for a specific account."""
        cache_key = f"{broker}:{account_number}"
        bridge = MT5SocketBridge(
            host=host,
            port=port,
            auth_token=self.auth_token,
            broker=broker,
            account_number=account_number,
        )

        with self._lock:
            self._bridges[cache_key] = bridge
            self._port_map[port] = cache_key

        logger.info(f"Added socket bridge: {cache_key} on port {port}")
        return bridge

    def get_bridge(self, broker: str, account_number: str) -> Optional[MT5SocketBridge]:
        """Get an existing bridge for an account."""
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            return self._bridges.get(cache_key)

    def get_or_create_bridge(self, broker: str, account_number: str,
                             port: int = None) -> Optional[MT5SocketBridge]:
        """Get or create a bridge for an account."""
        bridge = self.get_bridge(broker, account_number)
        if bridge:
            return bridge

        if port is None:
            # Auto-assign port
            with self._lock:
                port = self._next_port
                while port in self._port_map:
                    port += 1
                self._next_port = port + 1

        return self.add_bridge(broker, account_number, port)

    def connect_all(self) -> int:
        """Connect all configured bridges. Returns count of successful connections."""
        connected = 0
        with self._lock:
            bridges = list(self._bridges.values())

        for bridge in bridges:
            try:
                if bridge.connect():
                    connected += 1
                else:
                    logger.warning(f"Failed to connect bridge {bridge.broker}:{bridge.account_number} "
                                   f"on port {bridge.port}")
            except Exception as e:
                logger.error(f"Bridge connect error: {e}")

        self.enabled = connected > 0
        logger.info(f"Socket bridges: {connected}/{len(bridges)} connected")
        return connected

    def disconnect_all(self):
        """Disconnect all bridges."""
        with self._lock:
            for bridge in self._bridges.values():
                bridge.disconnect()

    def is_account_bridged(self, broker: str, account_number: str) -> bool:
        """Check if an account has a socket bridge configured."""
        cache_key = f"{broker}:{account_number}"
        with self._lock:
            bridge = self._bridges.get(cache_key)
        return bridge is not None and bridge.connected

    def get_all_status(self) -> dict:
        """Get status of all bridges."""
        with self._lock:
            statuses = {}
            for key, bridge in self._bridges.items():
                statuses[key] = bridge.get_status()
        return {
            'enabled': self.enabled,
            'total_bridges': len(statuses),
            'connected': sum(1 for s in statuses.values() if s['connected']),
            'bridges': statuses,
        }

    def shutdown(self):
        """Clean shutdown of all bridges."""
        self.disconnect_all()
        self.enabled = False
        logger.info("Socket bridge manager shut down")


# ─── Module-level convenience ──────────────────────────────────────────

_global_manager: Optional[SocketBridgeManager] = None
_global_lock = threading.Lock()


def get_socket_bridge_manager() -> SocketBridgeManager:
    """Get or create the global SocketBridgeManager."""
    global _global_manager
    with _global_lock:
        if _global_manager is None:
            _global_manager = SocketBridgeManager()
            _global_manager.configure_from_env()
        return _global_manager


def init_socket_bridges() -> SocketBridgeManager:
    """Initialize and connect all configured socket bridges."""
    manager = get_socket_bridge_manager()
    if manager._bridges:
        manager.connect_all()
    return manager
