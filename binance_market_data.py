#!/usr/bin/env python3
"""
Binance Market Data Service - Zwesta Trading Platform
======================================================
Maintains a SINGLE WebSocket connection to Binance and fans out price data
to all Binance worker processes via Redis. This eliminates per-bot REST
polling and reduces Binance API weight consumption by ~500x.

Architecture:
  Binance WebSocket (combined stream)
    └── binance_market_data.py ──► Redis keys: binance:price:{SYMBOL}
                                        └── binance_worker.py bots read prices

Redis key format: binance:price:BTCUSDT → {"price": 43210.50, "bid": 43210.0, "ask": 43211.0, "ts": 1711234567.89}
TTL: 30 seconds (stale prices are ignored by workers, which fall back to REST)

Usage:
    python binance_market_data.py

Environment:
    REDIS_URL         Redis connection URL (default: redis://localhost:6379/0)
    BINANCE_SYMBOLS   Comma-separated symbols (default: BTCUSDT,ETHUSDT,...)
    RECONNECT_DELAY   Seconds before WebSocket reconnect (default: 5)
"""

import os
import sys
import json
import time
import logging
import threading
import signal
from typing import List, Optional, Dict
from urllib.parse import quote_plus

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    import websocket  # websocket-client package
except ImportError:
    print("ERROR: websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)

try:
    import redis as redis_lib
except ImportError:
    print("ERROR: redis not installed. Run: pip install redis")
    sys.exit(1)

# ==================== CONFIGURATION ====================
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
PRICE_TTL_SECONDS = 30
RECONNECT_DELAY = int(os.environ.get('RECONNECT_DELAY', '5'))
BINANCE_WS_BASE = os.environ.get('BINANCE_WS_BASE', 'wss://stream.binance.com:9443/stream?streams=')
BINANCE_REST_BASE = os.environ.get('BINANCE_REST_BASE', 'https://api.binance.com/api')
REST_POLL_INTERVAL = max(2, int(os.environ.get('REST_POLL_INTERVAL', '5')))
MARKET_DATA_MODE = os.environ.get('BINANCE_MARKET_DATA_MODE', 'auto').strip().lower()  # auto|ws|rest

# Default symbols to track (can be overridden via BINANCE_SYMBOLS env var)
DEFAULT_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT', 'LINKUSDT',
    'DOTUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'FILUSDT',
]

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MarketData] %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ==================== SERVICE STATE ====================
_running = True
_redis_client: Optional[redis_lib.Redis] = None
_price_stats: Dict[str, int] = {}   # symbol → update count
_last_stats_log = time.time()
_last_ws_error = ''


# ==================== REDIS ====================

def get_redis() -> redis_lib.Redis:
    """Return connected Redis client. Raises on failure."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.from_url(
            REDIS_URL,
            socket_timeout=3,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        _redis_client.ping()
        logger.info(f"Redis connected: {REDIS_URL}")
    return _redis_client


def store_price(symbol: str, price: float, bid: float, ask: float) -> None:
    """Write price data to Redis with TTL."""
    try:
        r = get_redis()
        key = f'binance:price:{symbol.upper()}'
        data = json.dumps({
            'symbol': symbol,
            'price': price,
            'bid': bid,
            'ask': ask,
            'ts': time.time(),
        })
        r.setex(key, PRICE_TTL_SECONDS, data)
        _price_stats[symbol] = _price_stats.get(symbol, 0) + 1
    except Exception as e:
        logger.warning(f"Redis write failed ({symbol}): {e}")
        global _redis_client
        _redis_client = None  # Force reconnect next call


def log_stats() -> None:
    """Log throughput stats every 60 seconds."""
    global _last_stats_log
    now = time.time()
    if now - _last_stats_log >= 60:
        total = sum(_price_stats.values())
        active = len([s for s, c in _price_stats.items() if c > 0])
        logger.info(f"Price updates in last 60s: {total} across {active} symbols")
        _price_stats.clear()
        _last_stats_log = now


# ==================== WEBSOCKET HANDLERS ====================

def on_message(ws, raw_message: str) -> None:
    """Handle incoming combined stream message."""
    try:
        envelope = json.loads(raw_message)
        # Combined stream format: {"stream": "btcusdt@ticker", "data": {...}}
        data = envelope.get('data', envelope)
        event_type = data.get('e', '')

        if event_type == '24hrTicker':
            symbol = data.get('s', '')         # e.g. BTCUSDT
            last_price = float(data.get('c', 0))  # close / last price
            bid_price = float(data.get('b', last_price))
            ask_price = float(data.get('a', last_price))

            if symbol and last_price > 0:
                store_price(symbol, last_price, bid_price, ask_price)
                log_stats()

        elif event_type == 'trade':
            symbol = data.get('s', '')
            price = float(data.get('p', 0))
            if symbol and price > 0:
                store_price(symbol, price, price, price)

    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Message parse error: {e}")
    except Exception as e:
        logger.warning(f"on_message error: {e}")


def on_error(ws, error) -> None:
    global _last_ws_error
    _last_ws_error = str(error)
    logger.warning(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg) -> None:
    logger.warning(f"WebSocket closed: code={close_status_code} msg={close_msg}")


def on_open(ws) -> None:
    logger.info("WebSocket connection established")


# ==================== MAIN SERVICE ====================

def build_stream_url(symbols: List[str]) -> str:
    """Build Binance combined stream URL for all symbols."""
    streams = '/'.join(f'{s.lower()}@ticker' for s in symbols)
    return f'{BINANCE_WS_BASE}{streams}'


def _fetch_book_ticker(symbol: str) -> Optional[Dict[str, float]]:
    """Fetch current bid/ask/price for one symbol via Binance REST."""
    try:
        url = f"{BINANCE_REST_BASE}/v3/ticker/bookTicker?symbol={quote_plus(symbol)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logger.debug(f"REST ticker failed ({symbol}): status={resp.status_code} body={resp.text[:200]}")
            return None

        data = resp.json()
        bid = float(data.get('bidPrice', 0) or 0)
        ask = float(data.get('askPrice', 0) or 0)
        if bid <= 0 and ask <= 0:
            return None

        price = (bid + ask) / 2 if bid > 0 and ask > 0 else (ask if ask > 0 else bid)
        return {'price': price, 'bid': bid or price, 'ask': ask or price}
    except Exception as e:
        logger.debug(f"REST ticker exception ({symbol}): {e}")
        return None


def run_rest_polling(symbols: List[str]) -> None:
    """Fallback market data mode using REST polling when WebSocket is blocked."""
    logger.warning(
        f"Using REST polling mode (interval={REST_POLL_INTERVAL}s). "
        "This is slower than WebSocket but keeps scanner feed active."
    )
    logger.info(f"REST endpoint base: {BINANCE_REST_BASE}")

    while _running:
        updated = 0
        for symbol in symbols:
            quote_data = _fetch_book_ticker(symbol)
            if quote_data:
                store_price(symbol, quote_data['price'], quote_data['bid'], quote_data['ask'])
                updated += 1

        if updated == 0:
            logger.warning("REST polling returned no symbol prices this cycle")
        else:
            log_stats()

        time.sleep(REST_POLL_INTERVAL)


def run_websocket(symbols: List[str]) -> None:
    """Run WebSocket loop with auto-reconnect."""
    global _running
    url = build_stream_url(symbols)
    logger.info(f"Connecting to Binance stream for {len(symbols)} symbols")
    logger.info(f"Symbols: {', '.join(symbols)}")

    retry_count = 0
    max_log_url_length = 200

    while _running:
        try:
            short_url = url[:max_log_url_length] + ('...' if len(url) > max_log_url_length else '')
            logger.info(f"WebSocket URL: {short_url}")

            ws = websocket.WebSocketApp(
                url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(
                ping_interval=20,
                ping_timeout=10,
                reconnect=0,  # We handle reconnect ourselves
            )
            retry_count += 1

            # Region restriction: Binance returns 451 with eligibility message.
            if '451' in _last_ws_error or 'restricted location' in _last_ws_error.lower():
                logger.error("WebSocket blocked by regional restriction (HTTP 451). Switching to REST mode.")
                run_rest_polling(symbols)
                return
        except Exception as e:
            logger.error(f"WebSocket exception: {e}")
            retry_count += 1

        if not _running:
            break

        # Exponential backoff: 5s, 10s, 20s, max 60s
        wait = min(RECONNECT_DELAY * (2 ** min(retry_count - 1, 3)), 60)
        logger.info(f"Reconnecting in {wait}s (attempt {retry_count})")
        time.sleep(wait)


def handle_shutdown(signum, frame) -> None:
    global _running
    logger.info("Shutdown signal received — stopping market data service")
    _running = False
    sys.exit(0)


def publish_health(symbols: List[str]) -> None:
    """Periodically write a health key to Redis so monitors can detect service liveness."""
    while _running:
        try:
            r = get_redis()
            r.setex(
                'binance:market_data:health',
                60,  # 1 minute TTL — if service dies, key expires
                json.dumps({
                    'status': 'running',
                    'symbols': len(symbols),
                    'ts': time.time(),
                    'pid': os.getpid(),
                }),
            )
        except Exception:
            pass
        time.sleep(30)


def main() -> None:
    global _running

    symbols_env = os.environ.get('BINANCE_SYMBOLS', '')
    symbols: List[str] = (
        [s.strip().upper() for s in symbols_env.split(',') if s.strip()]
        if symbols_env
        else DEFAULT_SYMBOLS
    )

    logger.info(f"{'='*60}")
    logger.info(f"  Zwesta Binance Market Data Service")
    logger.info(f"  Redis: {REDIS_URL}")
    logger.info(f"  Mode : {MARKET_DATA_MODE}")
    logger.info(f"  Tracking {len(symbols)} symbols")
    logger.info(f"  Price TTL: {PRICE_TTL_SECONDS}s")
    logger.info(f"{'='*60}")

    # Verify Redis connection on startup
    try:
        get_redis()
    except Exception as e:
        logger.error(f"Cannot connect to Redis: {e}")
        logger.error("Redis is required. Start Redis and set REDIS_URL env var.")
        sys.exit(1)

    # Register shutdown handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    # Health publisher thread
    health_thread = threading.Thread(
        target=publish_health,
        args=(symbols,),
        daemon=True,
        name='health-publisher',
    )
    health_thread.start()

    # Run selected market data mode
    if MARKET_DATA_MODE == 'rest':
        run_rest_polling(symbols)
    elif MARKET_DATA_MODE == 'ws':
        run_websocket(symbols)
    else:
        # auto mode: try WebSocket first, auto-fallback to REST on 451 restriction
        run_websocket(symbols)

    logger.info("Market data service stopped")


if __name__ == '__main__':
    import os
    main()
