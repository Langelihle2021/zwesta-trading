"""
REST Price Feed for Zwesta Trader
==================================
Lightweight REST-based price data fetcher that eliminates
MT5 dependency for market data. Uses multiple free data sources.

Sources (in priority order):
1. MetaAPI (if configured) - real-time, per-account
2. Twelve Data API (free tier: 800 calls/day)
3. Alpha Vantage (free tier: 25 calls/day)
4. Synthetic fallback (last known price + random walk)

Price data is cached with configurable TTL to minimize API calls.
A single background thread refreshes prices for active symbols.
"""

import os
import time
import json
import random
import logging
import threading
from datetime import datetime, timezone, timedelta
from collections import OrderedDict

import requests

logger = logging.getLogger('rest_price_feed')

# Symbol name mapping: Exness symbol -> standard symbol
EXNESS_TO_STANDARD = {
    'EURUSDm': 'EURUSD', 'USDJPYm': 'USDJPY', 'GBPUSDm': 'GBPUSD',
    'AUDUSDm': 'AUDUSD', 'USDCADm': 'USDCAD', 'USDCHFm': 'USDCHF',
    'NZDUSDm': 'NZDUSD', 'EURGBPm': 'EURGBP', 'EURJPYm': 'EURJPY',
    'XAUUSDm': 'XAUUSD', 'XAGUSDm': 'XAGUSD',
    'BTCUSDm': 'BTCUSD', 'ETHUSDm': 'ETHUSD',
    'AAPLm': 'AAPL', 'MSFTm': 'MSFT', 'GOOGLm': 'GOOGL',
    'AMZNm': 'AMZN', 'TSLAm': 'TSLA', 'NVDAm': 'NVDA',
    'METAm': 'META', 'NFLXm': 'NFLX', 'BAm': 'BA',
    'JPMm': 'JPM', 'TSMm': 'TSM',
}

# Reverse mapping
STANDARD_TO_EXNESS = {v: k for k, v in EXNESS_TO_STANDARD.items()}

# Pip values per symbol type
PIP_VALUES = {
    'FOREX_JPY': 0.01,    # JPY pairs
    'FOREX': 0.0001,      # Standard forex
    'GOLD': 0.01,         # XAU
    'SILVER': 0.001,      # XAG
    'CRYPTO': 0.01,       # BTC/ETH
    'STOCK': 0.01,        # Stocks
    'INDEX': 0.1,         # Indices
}


def get_pip_size(symbol):
    """Get pip size for a symbol."""
    sym = symbol.upper().replace('M', '')
    if 'JPY' in sym:
        return PIP_VALUES['FOREX_JPY']
    if 'XAU' in sym or 'GOLD' in sym:
        return PIP_VALUES['GOLD']
    if 'XAG' in sym or 'SILVER' in sym:
        return PIP_VALUES['SILVER']
    if 'BTC' in sym or 'ETH' in sym:
        return PIP_VALUES['CRYPTO']
    if sym in ('US30', 'SPX500', 'NAS100', 'EUR50'):
        return PIP_VALUES['INDEX']
    if len(sym) <= 5 and sym.isalpha() and len(sym) >= 3:
        # Could be stock
        if sym not in ('EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD',
                        'USDCHF', 'EURGBP', 'EURJPY', 'USDJPY'):
            return PIP_VALUES['STOCK']
    return PIP_VALUES['FOREX']


class PriceEntry:
    """Single price data point."""
    __slots__ = ('bid', 'ask', 'time', 'source', 'cached_at')

    def __init__(self, bid, ask, ts=None, source='unknown'):
        self.bid = float(bid)
        self.ask = float(ask)
        self.time = ts or time.time()
        self.source = source
        self.cached_at = time.time()

    @property
    def spread(self):
        return round(self.ask - self.bid, 6)

    @property
    def mid(self):
        return round((self.bid + self.ask) / 2, 6)

    def age(self):
        return time.time() - self.cached_at

    def to_dict(self):
        return {
            'bid': self.bid,
            'ask': self.ask,
            'time': self.time,
            'spread': self.spread,
            'source': self.source,
            'age_seconds': round(self.age(), 1),
        }


class CandleBuffer:
    """Fixed-size buffer for candle data per symbol."""

    def __init__(self, max_candles=200):
        self.candles = []
        self.max_candles = max_candles
        self.last_update = 0

    def update(self, candle_list):
        """Replace candles with fresh data."""
        self.candles = candle_list[-self.max_candles:]
        self.last_update = time.time()

    def get_closes(self, count=50):
        """Get last N close prices."""
        return [c['close'] for c in self.candles[-count:]]

    def get_ohlcv(self, count=50):
        """Get last N candles as list of dicts."""
        return self.candles[-count:]

    def age(self):
        return time.time() - self.last_update if self.last_update else float('inf')


class RestPriceFeed:
    """Multi-source REST price feed with automatic fallback."""

    def __init__(self, twelve_data_key=None, alpha_vantage_key=None):
        self.twelve_data_key = twelve_data_key or os.environ.get('TWELVE_DATA_KEY', '')
        self.alpha_vantage_key = alpha_vantage_key or os.environ.get('ALPHA_VANTAGE_KEY', '')

        # Price cache
        self._prices = {}       # symbol -> PriceEntry
        self._candles = {}      # symbol -> CandleBuffer
        self._lock = threading.Lock()

        # Active symbols that need refreshing
        self._active_symbols = set()
        self._symbols_lock = threading.Lock()

        # Background refresh
        self._running = False
        self._refresh_thread = None
        self._price_ttl = 5.0       # Refresh prices every 5s
        self._candle_ttl = 60.0     # Refresh candles every 60s

        # Rate limiting
        self._twelve_data_calls = 0
        self._twelve_data_reset = time.time() + 86400
        self._twelve_data_limit = 780  # Stay under 800/day

        # HTTP session
        self._session = requests.Session()
        self._session.headers.update({'User-Agent': 'ZwestaTrader/2.0'})

        logger.info(f"REST Price Feed initialized "
                    f"(twelve_data={'yes' if self.twelve_data_key else 'no'}, "
                    f"alpha_vantage={'yes' if self.alpha_vantage_key else 'no'})")

    # ─── Public API ────────────────────────────────────────────────────

    def start(self):
        """Start background price refresh thread."""
        if self._running:
            return
        self._running = True
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop, daemon=True, name='PriceFeedRefresh')
        self._refresh_thread.start()
        logger.info("Price feed refresh thread started")

    def stop(self):
        """Stop background refresh."""
        self._running = False
        if self._refresh_thread:
            self._refresh_thread.join(timeout=10)

    def register_symbol(self, symbol):
        """Mark a symbol as actively needed (will be refreshed)."""
        with self._symbols_lock:
            self._active_symbols.add(symbol)

    def unregister_symbol(self, symbol):
        """Remove symbol from active refresh list."""
        with self._symbols_lock:
            self._active_symbols.discard(symbol)

    def get_price(self, symbol):
        """Get current price for a symbol. Returns PriceEntry or None."""
        with self._lock:
            entry = self._prices.get(symbol)
            if entry and entry.age() < 30:  # Accept up to 30s old
                return entry

        # Try fetching fresh
        self.register_symbol(symbol)
        entry = self._fetch_price_all_sources(symbol)
        if entry:
            with self._lock:
                self._prices[symbol] = entry
        return entry

    def get_candles(self, symbol, count=50):
        """Get candle history for signal evaluation."""
        with self._lock:
            buf = self._candles.get(symbol)
            if buf and buf.age() < self._candle_ttl and len(buf.candles) >= count:
                return buf.get_ohlcv(count)

        # Fetch fresh candles
        candles = self._fetch_candles_all_sources(symbol, count)
        if candles:
            with self._lock:
                if symbol not in self._candles:
                    self._candles[symbol] = CandleBuffer()
                self._candles[symbol].update(candles)
            return candles[-count:]
        # Return whatever we have cached
        with self._lock:
            buf = self._candles.get(symbol)
            if buf:
                return buf.get_ohlcv(count)
        return []

    def get_close_prices(self, symbol, count=50):
        """Get last N close prices for indicator calculation."""
        candles = self.get_candles(symbol, count)
        return [c['close'] for c in candles]

    def inject_price(self, symbol, bid, ask, source='injected'):
        """Manually inject a price (e.g., from MT5 or WebSocket)."""
        with self._lock:
            self._prices[symbol] = PriceEntry(bid, ask, source=source)

    def get_all_prices(self):
        """Get all cached prices. Returns dict of symbol->dict."""
        with self._lock:
            return {sym: entry.to_dict() for sym, entry in self._prices.items()}

    # ─── Background Refresh ────────────────────────────────────────────

    def _refresh_loop(self):
        """Background thread that refreshes active symbol prices."""
        while self._running:
            try:
                with self._symbols_lock:
                    symbols = list(self._active_symbols)

                if symbols:
                    # Batch fetch prices
                    self._batch_fetch_prices(symbols)

                    # Refresh candles less frequently
                    for sym in symbols:
                        with self._lock:
                            buf = self._candles.get(sym)
                        if not buf or buf.age() > self._candle_ttl:
                            candles = self._fetch_candles_all_sources(sym, 50)
                            if candles:
                                with self._lock:
                                    if sym not in self._candles:
                                        self._candles[sym] = CandleBuffer()
                                    self._candles[sym].update(candles)
                            time.sleep(0.5)  # Rate limit between candle fetches

                time.sleep(self._price_ttl)
            except Exception as e:
                logger.error(f"Price refresh error: {e}")
                time.sleep(10)

    def _batch_fetch_prices(self, symbols):
        """Fetch prices for multiple symbols in one call if possible."""
        if self.twelve_data_key and self._can_call_twelve_data():
            std_symbols = [EXNESS_TO_STANDARD.get(s, s) for s in symbols]
            try:
                batch_str = ','.join(std_symbols[:8])  # Max 8 per call
                resp = self._session.get(
                    'https://api.twelvedata.com/price',
                    params={'symbol': batch_str, 'apikey': self.twelve_data_key},
                    timeout=10,
                )
                self._twelve_data_calls += 1
                if resp.status_code == 200:
                    data = resp.json()
                    for i, sym in enumerate(symbols[:8]):
                        std = std_symbols[i]
                        price_data = data.get(std, data) if len(std_symbols) > 1 else data
                        if 'price' in price_data:
                            mid = float(price_data['price'])
                            pip = get_pip_size(sym)
                            spread = pip * random.uniform(0.5, 2.0)
                            entry = PriceEntry(
                                mid - spread/2, mid + spread/2, source='twelve_data')
                            with self._lock:
                                self._prices[sym] = entry
                    return
            except Exception as e:
                logger.debug(f"Twelve Data batch error: {e}")

        # Fallback: fetch individually
        for sym in symbols:
            entry = self._fetch_price_all_sources(sym)
            if entry:
                with self._lock:
                    self._prices[sym] = entry
            time.sleep(0.3)

    # ─── Individual Fetch Methods ──────────────────────────────────────

    def _fetch_price_all_sources(self, symbol):
        """Try all price sources in order."""
        std_sym = EXNESS_TO_STANDARD.get(symbol, symbol)

        # 1) Twelve Data
        if self.twelve_data_key and self._can_call_twelve_data():
            entry = self._fetch_twelve_data_price(std_sym, symbol)
            if entry:
                return entry

        # 2) Alpha Vantage (forex only)
        if self.alpha_vantage_key and len(std_sym) == 6 and std_sym.isalpha():
            entry = self._fetch_alpha_vantage_price(std_sym, symbol)
            if entry:
                return entry

        # 3) Synthetic from last known
        return self._synthetic_price(symbol)

    def _fetch_twelve_data_price(self, std_symbol, orig_symbol):
        """Fetch from Twelve Data API."""
        try:
            resp = self._session.get(
                'https://api.twelvedata.com/price',
                params={'symbol': std_symbol, 'apikey': self.twelve_data_key},
                timeout=8,
            )
            self._twelve_data_calls += 1
            if resp.status_code == 200:
                data = resp.json()
                if 'price' in data:
                    mid = float(data['price'])
                    pip = get_pip_size(orig_symbol)
                    spread = pip * random.uniform(0.5, 2.0)
                    return PriceEntry(
                        mid - spread/2, mid + spread/2, source='twelve_data')
        except Exception as e:
            logger.debug(f"Twelve Data error for {std_symbol}: {e}")
        return None

    def _fetch_alpha_vantage_price(self, std_symbol, orig_symbol):
        """Fetch from Alpha Vantage (forex pairs)."""
        from_cur = std_symbol[:3]
        to_cur = std_symbol[3:]
        try:
            resp = self._session.get(
                'https://www.alphavantage.co/query',
                params={
                    'function': 'CURRENCY_EXCHANGE_RATE',
                    'from_currency': from_cur,
                    'to_currency': to_cur,
                    'apikey': self.alpha_vantage_key,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                rate_data = data.get('Realtime Currency Exchange Rate', {})
                if rate_data:
                    bid = float(rate_data.get('8. Bid Price', 0))
                    ask = float(rate_data.get('9. Ask Price', 0))
                    if bid > 0 and ask > 0:
                        return PriceEntry(bid, ask, source='alpha_vantage')
        except Exception as e:
            logger.debug(f"Alpha Vantage error for {std_symbol}: {e}")
        return None

    def _fetch_candles_all_sources(self, symbol, count):
        """Fetch candle history from available sources."""
        std_sym = EXNESS_TO_STANDARD.get(symbol, symbol)

        # 1) Twelve Data
        if self.twelve_data_key and self._can_call_twelve_data():
            candles = self._fetch_twelve_data_candles(std_sym, count)
            if candles:
                return candles

        # 2) Synthetic candles from last price
        return self._synthetic_candles(symbol, count)

    def _fetch_twelve_data_candles(self, std_symbol, count):
        """Fetch OHLCV from Twelve Data."""
        try:
            resp = self._session.get(
                'https://api.twelvedata.com/time_series',
                params={
                    'symbol': std_symbol,
                    'interval': '5min',
                    'outputsize': str(count),
                    'apikey': self.twelve_data_key,
                },
                timeout=10,
            )
            self._twelve_data_calls += 1
            if resp.status_code == 200:
                data = resp.json()
                values = data.get('values', [])
                if values:
                    candles = []
                    for v in reversed(values):  # Oldest first
                        candles.append({
                            'time': v.get('datetime', ''),
                            'open': float(v.get('open', 0)),
                            'high': float(v.get('high', 0)),
                            'low': float(v.get('low', 0)),
                            'close': float(v.get('close', 0)),
                            'volume': int(float(v.get('volume', 0))),
                        })
                    return candles
        except Exception as e:
            logger.debug(f"Twelve Data candles error for {std_symbol}: {e}")
        return None

    def _synthetic_price(self, symbol):
        """Generate synthetic price from last known + random walk."""
        with self._lock:
            last = self._prices.get(symbol)
        if last and last.age() < 300:  # Use if less than 5 min old
            pip = get_pip_size(symbol)
            drift = random.gauss(0, pip * 3)
            new_mid = last.mid + drift
            spread = pip * random.uniform(0.5, 2.0)
            return PriceEntry(
                new_mid - spread/2, new_mid + spread/2, source='synthetic')
        return None

    def _synthetic_candles(self, symbol, count):
        """Generate synthetic candles from last known price."""
        with self._lock:
            last = self._prices.get(symbol)
        if not last:
            return []

        pip = get_pip_size(symbol)
        candles = []
        current = last.mid
        now = time.time()
        for i in range(count):
            t = now - (count - i) * 300  # 5-min intervals
            change = random.gauss(0, pip * 5)
            o = current
            c = current + change
            h = max(o, c) + abs(random.gauss(0, pip * 2))
            l = min(o, c) - abs(random.gauss(0, pip * 2))
            candles.append({
                'time': datetime.fromtimestamp(t, tz=timezone.utc).isoformat(),
                'open': round(o, 6),
                'high': round(h, 6),
                'low': round(l, 6),
                'close': round(c, 6),
                'volume': random.randint(100, 5000),
            })
            current = c
        return candles

    def _can_call_twelve_data(self):
        """Check if we're under the daily rate limit."""
        now = time.time()
        if now > self._twelve_data_reset:
            self._twelve_data_calls = 0
            self._twelve_data_reset = now + 86400
        return self._twelve_data_calls < self._twelve_data_limit


# ─── Module Singleton ──────────────────────────────────────────────────

_global_feed = None
_feed_lock = threading.Lock()


def get_price_feed():
    """Get or create the global price feed singleton."""
    global _global_feed
    with _feed_lock:
        if _global_feed is None:
            _global_feed = RestPriceFeed()
        return _global_feed
