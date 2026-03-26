"""
MetaAPI Cloud REST Trading Client for Zwesta Trader
====================================================
Provides REST-based MT5 trading via MetaAPI cloud service.
Replaces local MT5 terminal dependency for supported brokers.

Usage:
    client = MetaApiClient(token='your-metaapi-token')
    account_id = client.provision_account(login=298997455, password='xxx', server='Exness-MT5Trial9', broker='Exness')
    client.wait_for_ready(account_id)
    result = client.place_order(account_id, symbol='EURUSDm', action='BUY', volume=0.01)
    client.close_position(account_id, position_id='12345')
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import quote as url_quote

import requests

logger = logging.getLogger('metaapi_client')

# MetaAPI base URLs per region
METAAPI_REGIONS = {
    'new-york': 'https://mt-client-api-v1.new-york.agiliumtrade.ai',
    'london':   'https://mt-client-api-v1.london.agiliumtrade.ai',
    'singapore':'https://mt-client-api-v1.singapore.agiliumtrade.ai',
}

PROVISIONING_URL = 'https://mt-provisioning-api-v1.agiliumtrade.ai'


class MetaApiClient:
    """REST client for MetaAPI cloud-hosted MT5 trading."""

    def __init__(self, token=None, region='new-york', request_timeout=30):
        self.token = token or os.environ.get('METAAPI_TOKEN', '')
        self.region = region
        self.base_url = METAAPI_REGIONS.get(region, METAAPI_REGIONS['new-york'])
        self.prov_url = PROVISIONING_URL
        self.timeout = request_timeout
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'auth-token': self.token,
        })
        # Account ID cache: "broker:login" -> metaapi_account_id
        self._account_cache = {}
        self._cache_lock = threading.Lock()
        # Price cache: "symbol" -> {bid, ask, time, cached_at}
        self._price_cache = {}
        self._price_ttl = 2.0  # seconds
        self.enabled = bool(self.token)

        if self.enabled:
            logger.info(f"MetaAPI client initialized (region={region})")
        else:
            logger.info("MetaAPI client disabled (no METAAPI_TOKEN)")

    # ─── Account Provisioning ──────────────────────────────────────────

    def provision_account(self, login, password, server, broker='Exness',
                          platform='mt5', name=None):
        """Register an MT5 account with MetaAPI cloud.
        Returns the MetaAPI account ID string.
        """
        cache_key = f"{broker}:{login}"
        with self._cache_lock:
            if cache_key in self._account_cache:
                return self._account_cache[cache_key]

        if not name:
            name = f"Zwesta-{broker}-{login}"

        payload = {
            'name': name,
            'type': 'cloud-g1',
            'login': str(login),
            'password': password,
            'server': server,
            'platform': platform,
            'magic': 0,
            'quoteStreamingIntervalInSeconds': 2.5,
        }

        resp = self._session.post(
            f"{self.prov_url}/users/current/accounts",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        account_id = data['id']

        with self._cache_lock:
            self._account_cache[cache_key] = account_id

        logger.info(f"Provisioned MetaAPI account {account_id} for {broker}:{login}")
        return account_id

    def get_or_provision(self, login, password, server, broker='Exness'):
        """Get existing MetaAPI account or provision new one."""
        cache_key = f"{broker}:{login}"
        with self._cache_lock:
            if cache_key in self._account_cache:
                return self._account_cache[cache_key]

        # Search existing accounts
        try:
            resp = self._session.get(
                f"{self.prov_url}/users/current/accounts",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            accounts = resp.json()
            for acct in accounts:
                if str(acct.get('login')) == str(login) and acct.get('server') == server:
                    account_id = acct['id']
                    with self._cache_lock:
                        self._account_cache[cache_key] = account_id
                    logger.info(f"Found existing MetaAPI account {account_id}")

                    # Deploy if not deployed
                    if acct.get('state') != 'DEPLOYED':
                        self.deploy_account(account_id)
                    return account_id
        except Exception as e:
            logger.warning(f"Error searching MetaAPI accounts: {e}")

        return self.provision_account(login, password, server, broker)

    def deploy_account(self, account_id):
        """Deploy a provisioned account (start cloud MT5 instance)."""
        resp = self._session.post(
            f"{self.prov_url}/users/current/accounts/{url_quote(account_id)}/deploy",
            timeout=self.timeout,
        )
        if resp.status_code == 204 or resp.status_code == 200:
            logger.info(f"Account {account_id} deployed")
            return True
        logger.warning(f"Deploy response: {resp.status_code} {resp.text[:200]}")
        return False

    def wait_for_ready(self, account_id, timeout_seconds=120):
        """Wait until MetaAPI account is connected and ready."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                resp = self._session.get(
                    f"{self.prov_url}/users/current/accounts/{url_quote(account_id)}",
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                state = data.get('state', '')
                conn_status = data.get('connectionStatus', '')
                if state == 'DEPLOYED' and conn_status == 'CONNECTED':
                    logger.info(f"Account {account_id} ready (CONNECTED)")
                    return True
                logger.debug(f"Account {account_id}: state={state} conn={conn_status}")
            except Exception as e:
                logger.debug(f"Waiting for account {account_id}: {e}")
            time.sleep(5)

        logger.error(f"Account {account_id} not ready after {timeout_seconds}s")
        return False

    # ─── Account Information ───────────────────────────────────────────

    def get_account_info(self, account_id):
        """Get account balance, equity, margin info.
        Returns dict compatible with MT5 account_info format.
        """
        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/account-information",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'balance': data.get('balance', 0),
            'equity': data.get('equity', 0),
            'margin': data.get('margin', 0),
            'freeMargin': data.get('freeMargin', 0),
            'leverage': data.get('leverage', 100),
            'currency': data.get('currency', 'USD'),
            'login': data.get('login', 0),
            'server': data.get('server', ''),
            'name': data.get('name', ''),
        }

    # ─── Price Data ────────────────────────────────────────────────────

    def get_symbol_price(self, account_id, symbol):
        """Get current bid/ask for a symbol.
        Returns dict: {bid, ask, time, spread}
        """
        # Check cache first
        now = time.time()
        cached = self._price_cache.get(f"{account_id}:{symbol}")
        if cached and (now - cached['cached_at']) < self._price_ttl:
            return cached

        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/symbols/{url_quote(symbol)}/current-price",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        result = {
            'bid': data.get('bid', 0),
            'ask': data.get('ask', 0),
            'time': data.get('time', ''),
            'spread': round(data.get('ask', 0) - data.get('bid', 0), 6),
            'cached_at': now,
        }
        self._price_cache[f"{account_id}:{symbol}"] = result
        return result

    def get_candles(self, account_id, symbol, timeframe='1m', count=50):
        """Get OHLCV candle history for signal evaluation.
        timeframe: '1m','5m','15m','30m','1h','4h','1d'
        Returns list of dicts: [{time, open, high, low, close, volume}, ...]
        """
        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/historical-market-data/symbols/{url_quote(symbol)}"
            f"/timeframes/{timeframe}/candles",
            params={'limit': count},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        candles = resp.json()
        return [
            {
                'time': c.get('time', ''),
                'open': c.get('open', 0),
                'high': c.get('high', 0),
                'low': c.get('low', 0),
                'close': c.get('close', 0),
                'volume': c.get('tickVolume', c.get('volume', 0)),
            }
            for c in candles
        ]

    def get_symbol_spec(self, account_id, symbol):
        """Get symbol specification (digits, trade sizes, etc.)."""
        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/symbols/{url_quote(symbol)}/specification",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ─── Trading Operations ────────────────────────────────────────────

    def place_order(self, account_id, symbol, action, volume,
                    stop_loss=None, take_profit=None, comment=''):
        """Place a market order (BUY or SELL).
        Returns dict: {orderId, positionId, stringCode, message}
        """
        action_type = 'ORDER_TYPE_BUY' if action.upper() == 'BUY' else 'ORDER_TYPE_SELL'
        payload = {
            'actionType': action_type,
            'symbol': symbol,
            'volume': float(volume),
        }
        if stop_loss is not None:
            payload['stopLoss'] = float(stop_loss)
        if take_profit is not None:
            payload['takeProfit'] = float(take_profit)
        if comment:
            payload['comment'] = str(comment)[:31]

        resp = self._session.post(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}/trade",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        success = data.get('stringCode') == 'TRADE_RETCODE_DONE'
        if success:
            logger.info(f"Order placed: {action} {volume} {symbol} -> "
                        f"order={data.get('orderId')} pos={data.get('positionId')}")
        else:
            logger.error(f"Order failed: {data.get('stringCode')} - {data.get('message')}")

        return {
            'success': success,
            'orderId': data.get('orderId'),
            'positionId': data.get('positionId'),
            'stringCode': data.get('stringCode', ''),
            'numericCode': data.get('numericCode', 0),
            'message': data.get('message', ''),
        }

    def close_position(self, account_id, position_id):
        """Close an open position by ID.
        Returns dict with success status.
        """
        payload = {
            'actionType': 'POSITION_CLOSE_ID',
            'positionId': str(position_id),
        }

        resp = self._session.post(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}/trade",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        success = data.get('stringCode') == 'TRADE_RETCODE_DONE'
        if success:
            logger.info(f"Position {position_id} closed successfully")
        else:
            logger.error(f"Close failed: {data.get('stringCode')} - {data.get('message')}")

        return {
            'success': success,
            'orderId': data.get('orderId'),
            'positionId': data.get('positionId'),
            'stringCode': data.get('stringCode', ''),
            'message': data.get('message', ''),
        }

    def modify_position(self, account_id, position_id,
                        stop_loss=None, take_profit=None):
        """Modify SL/TP on an open position."""
        payload = {
            'actionType': 'POSITION_MODIFY',
            'positionId': str(position_id),
        }
        if stop_loss is not None:
            payload['stopLoss'] = float(stop_loss)
        if take_profit is not None:
            payload['takeProfit'] = float(take_profit)

        resp = self._session.post(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}/trade",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            'success': data.get('stringCode') == 'TRADE_RETCODE_DONE',
            'stringCode': data.get('stringCode', ''),
            'message': data.get('message', ''),
        }

    # ─── Position & Order Queries ──────────────────────────────────────

    def get_positions(self, account_id):
        """Get all open positions.
        Returns list compatible with MT5Connection.get_positions() format.
        """
        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/positions",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        positions = resp.json()

        results = []
        for p in positions:
            pnl = p.get('unrealizedProfit', p.get('profit', 0))
            entry = p.get('openPrice', 0)
            current = p.get('currentPrice', 0)
            volume_val = p.get('volume', 0)
            pnl_pct = 0
            if entry and volume_val:
                pnl_pct = ((current - entry) / entry) * 100
                if p.get('type', '').upper() == 'POSITION_TYPE_SELL':
                    pnl_pct = -pnl_pct
            commission = p.get('commission', 0) or 0
            swap = p.get('swap', 0) or 0
            results.append({
                'ticket': p.get('id', ''),
                'symbol': p.get('symbol', ''),
                'type': 'BUY' if 'BUY' in p.get('type', '').upper() else 'SELL',
                'volume': volume_val,
                'openPrice': float(entry),
                'currentPrice': float(current),
                'pnl': float(pnl),
                'pnlPercentage': round(pnl_pct, 2),
                'netProfit': float(pnl) + commission + swap,
                'openTime': p.get('time', ''),
                'commission': commission,
                'swap': swap,
            })
        return results

    def get_orders(self, account_id):
        """Get pending orders."""
        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/orders",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_history_deals(self, account_id, start_time=None, end_time=None):
        """Get deal history within a time range."""
        if not start_time:
            start_time = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0).isoformat()
        if not end_time:
            end_time = datetime.now(timezone.utc).isoformat()

        resp = self._session.get(
            f"{self.base_url}/users/current/accounts/{url_quote(account_id)}"
            f"/history-deals/time/{url_quote(start_time)}/{url_quote(end_time)}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ─── Health & Status ───────────────────────────────────────────────

    def ping(self):
        """Test MetaAPI connectivity."""
        if not self.enabled:
            return False
        try:
            resp = self._session.get(
                f"{self.prov_url}/users/current/accounts",
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_account_state(self, account_id):
        """Get deployment state and connection status."""
        resp = self._session.get(
            f"{self.prov_url}/users/current/accounts/{url_quote(account_id)}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'state': data.get('state', 'UNKNOWN'),
            'connectionStatus': data.get('connectionStatus', 'UNKNOWN'),
            'login': data.get('login'),
            'server': data.get('server'),
        }


class MetaApiTradingBridge:
    """Bridge that provides same interface as MT5Connection for seamless integration.
    Drop-in replacement for MT5Connection when using MetaAPI.
    """

    def __init__(self, client, account_id, broker='Exness'):
        self.client = client
        self.account_id = account_id
        self.broker = broker
        self.connected = False
        self.broker_type = type('BrokerType', (), {'value': broker})()
        self._last_balance = 0
        self._last_equity = 0

    def connect(self):
        """Deploy and wait for MetaAPI account to be ready."""
        try:
            self.client.deploy_account(self.account_id)
            if self.client.wait_for_ready(self.account_id, timeout_seconds=60):
                self.connected = True
                info = self.client.get_account_info(self.account_id)
                self._last_balance = info.get('balance', 0)
                self._last_equity = info.get('equity', 0)
                logger.info(f"MetaAPI bridge connected: {self.broker} "
                            f"balance=${self._last_balance}")
                return True
        except Exception as e:
            logger.error(f"MetaAPI bridge connect failed: {e}")
        self.connected = False
        return False

    def wait_for_mt5_ready(self, timeout_seconds=30):
        """Compatibility method - checks if account is connected."""
        if self.connected:
            return True
        return self.connect()

    def get_balance(self):
        """Get account balance."""
        try:
            info = self.client.get_account_info(self.account_id)
            self._last_balance = info.get('balance', 0)
            self._last_equity = info.get('equity', 0)
            return self._last_balance
        except Exception:
            return self._last_balance

    def place_order(self, symbol, order_type, volume, **kwargs):
        """Place a market order. Compatible with MT5Connection.place_order()."""
        sl = kwargs.get('stopLoss') or kwargs.get('stop_loss')
        tp = kwargs.get('takeProfit') or kwargs.get('take_profit')
        comment = kwargs.get('comment', '')

        result = self.client.place_order(
            self.account_id,
            symbol=symbol,
            action=order_type,
            volume=volume,
            stop_loss=sl,
            take_profit=tp,
            comment=comment,
        )

        if result['success']:
            return {
                'success': True,
                'ticket': result.get('orderId', ''),
                'positionId': result.get('positionId', ''),
                'retcode': 10009,
                'comment': result.get('message', 'OK'),
            }
        return {
            'success': False,
            'ticket': None,
            'retcode': result.get('numericCode', -1),
            'comment': result.get('message', 'Failed'),
        }

    def get_positions(self):
        """Get open positions. Compatible format."""
        try:
            return self.client.get_positions(self.account_id)
        except Exception as e:
            logger.error(f"get_positions error: {e}")
            return []

    def close_position(self, position_id):
        """Close a position by ticket/ID."""
        result = self.client.close_position(self.account_id, position_id)
        return result.get('success', False)

    def modify_position_stop_loss(self, position_id=None, new_sl=None, **kwargs):
        """Modify stop loss on a position. Accepts ticket= or position_id=."""
        pid = position_id or kwargs.get('ticket')
        sl = new_sl or kwargs.get('new_stop_loss')
        result = self.client.modify_position(
            self.account_id, pid, stop_loss=sl)
        return result.get('success', False)

    def get_symbol_price(self, symbol):
        """Get current price for a symbol."""
        try:
            return self.client.get_symbol_price(self.account_id, symbol)
        except Exception as e:
            logger.error(f"get_symbol_price error: {e}")
            return {'bid': 0, 'ask': 0, 'spread': 0}

    def get_candle_history(self, symbol, timeframe='5m', count=50):
        """Get candle data for signal evaluation."""
        try:
            return self.client.get_candles(
                self.account_id, symbol, timeframe=timeframe, count=count)
        except Exception as e:
            logger.error(f"get_candle_history error: {e}")
            return []


# ─── Module-level convenience ──────────────────────────────────────────

_global_client = None
_global_lock = threading.Lock()


def get_metaapi_client():
    """Get or create the global MetaAPI client singleton."""
    global _global_client
    with _global_lock:
        if _global_client is None:
            _global_client = MetaApiClient()
        return _global_client


def is_metaapi_enabled():
    """Check if MetaAPI is configured and available."""
    client = get_metaapi_client()
    return client.enabled
