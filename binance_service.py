import os
import time
import hmac
import hashlib
import logging
from urllib.parse import urlencode
from flask import Blueprint, jsonify, request
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

binance_api = Blueprint('binance_api', __name__)

# ==================== CONFIG ====================

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_DEMO_MODE = os.getenv("BINANCE_DEMO_MODE", "true").lower() == "true"

BASE_URL = (
    "https://testnet.binance.vision/api"
    if BINANCE_DEMO_MODE
    else "https://api.binance.com/api"
)

FAPI_URL = (
    "https://testnet.binancefuture.com/fapi"
    if BINANCE_DEMO_MODE
    else "https://fapi.binance.com/fapi"
)


def _binance_headers():
    """Build standard Binance API headers."""
    return {
        "X-MBX-APIKEY": BINANCE_API_KEY,
        "Content-Type": "application/json",
    }


def _sign_params(params: dict) -> dict:
    """Add timestamp and HMAC-SHA256 signature to params."""
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    signature = hmac.new(
        BINANCE_API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    params['signature'] = signature
    return params


# ==================== AUTH / STATUS ====================

@binance_api.route('/api/binance/login', methods=['POST'])
def api_binance_login():
    """Verify Binance credentials by fetching account info."""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or BINANCE_API_KEY
        api_secret = data.get('api_secret') or BINANCE_API_SECRET

        if not api_key or not api_secret:
            return jsonify({"success": False, "error": "Binance API key and secret required"}), 400

        headers = {"X-MBX-APIKEY": api_key}
        params = {'timestamp': int(time.time() * 1000)}
        query_string = urlencode(params)
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        params['signature'] = signature

        resp = requests.get(
            f"{BASE_URL}/v3/account",
            headers=headers, params=params, timeout=15,
        )
        if resp.status_code == 200:
            acct = resp.json()
            return jsonify({
                "success": True,
                "message": "Binance connected",
                "accountType": acct.get('accountType', ''),
                "canTrade": acct.get('canTrade', False),
                "canWithdraw": acct.get('canWithdraw', False),
                "balances": [b for b in acct.get('balances', []) if float(b.get('free', 0)) > 0 or float(b.get('locked', 0)) > 0],
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== ACCOUNTS ====================

@binance_api.route('/api/binance/accounts', methods=['GET'])
def api_binance_accounts():
    """Get Binance account info including all balances."""
    try:
        headers = _binance_headers()
        params = _sign_params({})
        resp = requests.get(
            f"{BASE_URL}/v3/account",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            acct = resp.json()
            return jsonify({
                "success": True,
                "accounts": [{
                    "accountType": acct.get('accountType', ''),
                    "canTrade": acct.get('canTrade', False),
                    "canWithdraw": acct.get('canWithdraw', False),
                }],
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@binance_api.route('/api/binance/balance', methods=['GET'])
def api_binance_balance():
    """Get USDT balance and total estimated BTC value."""
    try:
        headers = _binance_headers()
        params = _sign_params({})
        resp = requests.get(
            f"{BASE_URL}/v3/account",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            acct = resp.json()
            balances = acct.get('balances', [])

            # Find USDT balance
            usdt = next((b for b in balances if b['asset'] == 'USDT'), {'free': '0', 'locked': '0'})
            btc = next((b for b in balances if b['asset'] == 'BTC'), {'free': '0', 'locked': '0'})

            # All non-zero balances
            active_balances = [
                {
                    'asset': b['asset'],
                    'free': float(b['free']),
                    'locked': float(b['locked']),
                    'total': float(b['free']) + float(b['locked']),
                }
                for b in balances
                if float(b.get('free', 0)) > 0 or float(b.get('locked', 0)) > 0
            ]

            return jsonify({
                'success': True,
                'balance': float(usdt['free']) + float(usdt['locked']),
                'available': float(usdt['free']),
                'locked': float(usdt['locked']),
                'currency': 'USDT',
                'btcBalance': float(btc['free']) + float(btc['locked']),
                'allBalances': active_balances,
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@binance_api.route('/api/binance/funds', methods=['GET'])
def api_binance_funds():
    """Alias for balance — matches existing broker pattern."""
    try:
        headers = _binance_headers()
        params = _sign_params({})
        resp = requests.get(
            f"{BASE_URL}/v3/account",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            acct = resp.json()
            balances = acct.get('balances', [])
            usdt = next((b for b in balances if b['asset'] == 'USDT'), {'free': '0', 'locked': '0'})

            return jsonify({
                'success': True,
                'funds': {
                    'balance': float(usdt['free']) + float(usdt['locked']),
                    'available': float(usdt['free']),
                    'locked': float(usdt['locked']),
                    'currency': 'USDT',
                    'accountType': acct.get('accountType', ''),
                },
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== POSITIONS / OPEN ORDERS ====================

@binance_api.route('/api/binance/positions', methods=['GET'])
def api_binance_positions():
    """Get all open orders (spot) — Binance spot doesn't have 'positions' like forex."""
    try:
        headers = _binance_headers()
        params = _sign_params({})
        resp = requests.get(
            f"{BASE_URL}/v3/openOrders",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            orders = resp.json()
            positions = []
            for o in orders:
                positions.append({
                    'dealId': str(o.get('orderId', '')),
                    'instrument': o.get('symbol', ''),
                    'direction': o.get('side', ''),
                    'size': float(o.get('origQty', 0)),
                    'level': float(o.get('price', 0)),
                    'type': o.get('type', ''),
                    'status': o.get('status', ''),
                    'openTime': o.get('time', ''),
                })
            return jsonify({"success": True, "positions": positions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance positions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== FUTURES POSITIONS ====================

@binance_api.route('/api/binance/futures-positions', methods=['GET'])
def api_binance_futures_positions():
    """Get all open futures positions with unrealized P&L."""
    try:
        headers = _binance_headers()
        params = _sign_params({})
        resp = requests.get(
            f"{FAPI_URL}/v2/positionRisk",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            raw = resp.json()
            positions = []
            for p in raw:
                amt = float(p.get('positionAmt', 0))
                if amt == 0:
                    continue
                positions.append({
                    'dealId': p.get('symbol', ''),
                    'instrument': p.get('symbol', ''),
                    'direction': 'BUY' if amt > 0 else 'SELL',
                    'size': abs(amt),
                    'level': float(p.get('entryPrice', 0)),
                    'markPrice': float(p.get('markPrice', 0)),
                    'unrealizedPL': float(p.get('unRealizedProfit', 0)),
                    'leverage': p.get('leverage', '1'),
                    'liquidationPrice': float(p.get('liquidationPrice', 0)),
                    'marginType': p.get('marginType', ''),
                })
            return jsonify({"success": True, "positions": positions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance futures positions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CLOSE POSITION (CANCEL ORDER / MARKET SELL) ====================

@binance_api.route('/api/binance/close-position', methods=['POST'])
def api_binance_close_position():
    """Close an open order (cancel) or sell a spot holding via market order."""
    try:
        data = request.json or {}
        symbol = data.get('instrument') or data.get('symbol')
        order_id = data.get('dealId') or data.get('orderId')

        if not symbol:
            return jsonify({"success": False, "error": "symbol is required"}), 400

        headers = _binance_headers()

        # If orderId provided, cancel that specific order
        if order_id:
            params = _sign_params({'symbol': symbol, 'orderId': int(order_id)})
            resp = requests.delete(
                f"{BASE_URL}/v3/order",
                headers=headers, params=params, timeout=15,
            )
        else:
            # Market sell the given quantity
            quantity = data.get('size') or data.get('quantity')
            direction = data.get('direction', 'SELL')
            if not quantity:
                return jsonify({"success": False, "error": "size/quantity required for market close"}), 400

            params = _sign_params({
                'symbol': symbol,
                'side': direction,
                'type': 'MARKET',
                'quantity': str(quantity),
            })
            resp = requests.post(
                f"{BASE_URL}/v3/order",
                headers=headers, params=params, timeout=15,
            )

        if resp.status_code == 200:
            return jsonify({"success": True, "result": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance close position error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CLOSE ALL (FUTURES) ====================

@binance_api.route('/api/binance/close-all-positions', methods=['POST'])
def api_binance_close_all():
    """Close all open futures positions via counter-orders."""
    try:
        headers = _binance_headers()

        # Get all futures positions
        params = _sign_params({})
        resp = requests.get(
            f"{FAPI_URL}/v2/positionRisk",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        raw = resp.json()
        results = []

        for p in raw:
            amt = float(p.get('positionAmt', 0))
            if amt == 0:
                continue
            symbol = p.get('symbol', '')
            # Close by placing opposite market order
            close_side = 'SELL' if amt > 0 else 'BUY'
            close_params = _sign_params({
                'symbol': symbol,
                'side': close_side,
                'type': 'MARKET',
                'quantity': str(abs(amt)),
                'reduceOnly': 'true',
            })
            close_resp = requests.post(
                f"{FAPI_URL}/v1/order",
                headers=headers, params=close_params, timeout=15,
            )
            if close_resp.status_code == 200:
                results.append({"symbol": symbol, "success": True})
            else:
                results.append({"symbol": symbol, "success": False, "error": close_resp.text})

        closed_count = sum(1 for r in results if r['success'])
        return jsonify({
            "success": True,
            "closed": closed_count,
            "total": len(results),
            "results": results,
        })
    except Exception as e:
        logger.error(f"Binance close all error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PLACE ORDER ====================

@binance_api.route('/api/binance/place-order', methods=['POST'])
def api_binance_place_order():
    """Place a spot or futures order on Binance."""
    try:
        data = request.json or {}
        headers = _binance_headers()

        symbol = data.get('instrument') or data.get('symbol')
        direction = data.get('direction', 'BUY').upper()
        size = data.get('size') or data.get('quantity')
        order_type = data.get('orderType', 'MARKET').upper()
        market = data.get('market', 'spot')  # 'spot' or 'futures'

        if not symbol or not size:
            return jsonify({"success": False, "error": "symbol and size are required"}), 400

        order_params = {
            'symbol': symbol,
            'side': direction,
            'type': order_type,
        }

        if order_type == 'MARKET':
            order_params['quantity'] = str(size)
        elif order_type == 'LIMIT':
            price = data.get('price')
            if not price:
                return jsonify({"success": False, "error": "price required for LIMIT orders"}), 400
            order_params['quantity'] = str(size)
            order_params['price'] = str(price)
            order_params['timeInForce'] = data.get('timeInForce', 'GTC')

        # Stop loss / take profit for futures
        if data.get('stopLossPrice') and market == 'futures':
            # Place as separate stop-market order
            pass  # Handled via separate endpoint
        if data.get('takeProfitPrice') and market == 'futures':
            pass

        signed = _sign_params(order_params)

        if market == 'futures':
            resp = requests.post(
                f"{FAPI_URL}/v1/order",
                headers=headers, params=signed, timeout=15,
            )
        else:
            resp = requests.post(
                f"{BASE_URL}/v3/order",
                headers=headers, params=signed, timeout=15,
            )

        if resp.status_code == 200:
            result = resp.json()
            return jsonify({
                "success": True,
                "orderId": result.get('orderId', ''),
                "symbol": result.get('symbol', ''),
                "side": result.get('side', ''),
                "type": result.get('type', ''),
                "fills": result.get('fills', []),
                "status": result.get('status', ''),
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance place order error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PENDING ORDERS ====================

@binance_api.route('/api/binance/pending-orders', methods=['GET'])
def api_binance_pending_orders():
    """Get all open (pending) orders."""
    try:
        headers = _binance_headers()
        symbol = request.args.get('symbol')
        query = {'symbol': symbol} if symbol else {}
        params = _sign_params(query)

        resp = requests.get(
            f"{BASE_URL}/v3/openOrders",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            orders = resp.json()
            formatted = []
            for o in orders:
                formatted.append({
                    'orderId': str(o.get('orderId', '')),
                    'instrument': o.get('symbol', ''),
                    'type': o.get('type', ''),
                    'side': o.get('side', ''),
                    'price': o.get('price', ''),
                    'origQty': o.get('origQty', ''),
                    'executedQty': o.get('executedQty', ''),
                    'status': o.get('status', ''),
                    'timeInForce': o.get('timeInForce', ''),
                    'createTime': o.get('time', ''),
                })
            return jsonify({"success": True, "pendingOrders": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@binance_api.route('/api/binance/pending-orders', methods=['POST'])
def api_binance_create_pending_order():
    """Create a limit order (pending)."""
    try:
        data = request.json or {}
        headers = _binance_headers()

        symbol = data.get('instrument') or data.get('symbol')
        direction = data.get('direction', 'BUY').upper()
        size = data.get('size') or data.get('quantity')
        price = data.get('price')

        if not symbol or not size or not price:
            return jsonify({"success": False, "error": "symbol, size, and price are required"}), 400

        params = _sign_params({
            'symbol': symbol,
            'side': direction,
            'type': 'LIMIT',
            'quantity': str(size),
            'price': str(price),
            'timeInForce': data.get('timeInForce', 'GTC'),
        })

        resp = requests.post(
            f"{BASE_URL}/v3/order",
            headers=headers, params=params, timeout=15,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "order": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@binance_api.route('/api/binance/pending-orders/<order_id>', methods=['DELETE'])
def api_binance_cancel_order(order_id):
    """Cancel a pending order by orderId."""
    try:
        symbol = request.args.get('symbol', '')
        if not symbol:
            return jsonify({"success": False, "error": "symbol query param required"}), 400

        headers = _binance_headers()
        params = _sign_params({'symbol': symbol, 'orderId': int(order_id)})

        resp = requests.delete(
            f"{BASE_URL}/v3/order",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "cancelled": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== TRANSACTIONS / TRADE HISTORY ====================

@binance_api.route('/api/binance/transactions', methods=['GET'])
def api_binance_transactions():
    """Get recent trade history for a symbol."""
    try:
        headers = _binance_headers()
        symbol = request.args.get('symbol', 'BTCUSDT')
        limit = request.args.get('pageSize', '50')

        params = _sign_params({'symbol': symbol, 'limit': int(limit)})
        resp = requests.get(
            f"{BASE_URL}/v3/myTrades",
            headers=headers, params=params, timeout=15,
        )
        if resp.status_code == 200:
            trades = resp.json()
            formatted = []
            for t in trades:
                formatted.append({
                    'tradeId': t.get('id', ''),
                    'orderId': t.get('orderId', ''),
                    'symbol': t.get('symbol', ''),
                    'side': 'BUY' if t.get('isBuyer') else 'SELL',
                    'price': float(t.get('price', 0)),
                    'quantity': float(t.get('qty', 0)),
                    'quoteQty': float(t.get('quoteQty', 0)),
                    'commission': float(t.get('commission', 0)),
                    'commissionAsset': t.get('commissionAsset', ''),
                    'time': t.get('time', ''),
                    'isMaker': t.get('isMaker', False),
                })
            return jsonify({"success": True, "transactions": formatted, "count": len(formatted)})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance transactions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== MARKET SEARCH / INSTRUMENTS ====================

@binance_api.route('/api/binance/instruments', methods=['GET'])
def api_binance_instruments():
    """Get available trading pairs. Optional filter via searchTerm."""
    try:
        resp = requests.get(
            f"{BASE_URL}/v3/exchangeInfo",
            timeout=15,
        )
        if resp.status_code == 200:
            symbols = resp.json().get('symbols', [])
            search_term = request.args.get('searchTerm', '').upper()
            if search_term:
                symbols = [s for s in symbols if search_term in s.get('symbol', '').upper()
                           or search_term in s.get('baseAsset', '').upper()
                           or search_term in s.get('quoteAsset', '').upper()]

            formatted = []
            for s in symbols[:200]:
                formatted.append({
                    'instrument': s.get('symbol', ''),
                    'displayName': f"{s.get('baseAsset', '')}/{s.get('quoteAsset', '')}",
                    'baseAsset': s.get('baseAsset', ''),
                    'quoteAsset': s.get('quoteAsset', ''),
                    'status': s.get('status', ''),
                    'type': 'CRYPTO',
                })
            return jsonify({"success": True, "instruments": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PRICING ====================

@binance_api.route('/api/binance/pricing', methods=['GET'])
def api_binance_pricing():
    """Get current prices. Query: instruments=BTCUSDT,ETHUSDT (comma-separated)."""
    try:
        instruments = request.args.get('instruments', '')
        if not instruments:
            return jsonify({"success": False, "error": "instruments param required (e.g. BTCUSDT,ETHUSDT)"}), 400

        symbols = [s.strip() for s in instruments.split(',')]
        prices = []

        for sym in symbols:
            resp = requests.get(
                f"{BASE_URL}/v3/ticker/bookTicker",
                params={"symbol": sym}, timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                ask = float(data.get('askPrice', 0))
                bid = float(data.get('bidPrice', 0))
                prices.append({
                    'instrument': sym,
                    'ask': ask,
                    'bid': bid,
                    'spread': round(ask - bid, 8),
                    'tradeable': True,
                })

        return jsonify({"success": True, "prices": prices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CANDLES / HISTORICAL DATA ====================

@binance_api.route('/api/binance/candles/<symbol>', methods=['GET'])
def api_binance_candles(symbol):
    """Get candlestick/kline data. Query: interval=1h&limit=100"""
    try:
        interval = request.args.get('granularity') or request.args.get('interval', '1h')
        limit = request.args.get('count') or request.args.get('limit', '100')

        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': int(limit),
        }
        if request.args.get('startTime'):
            params['startTime'] = int(request.args['startTime'])
        if request.args.get('endTime'):
            params['endTime'] = int(request.args['endTime'])

        resp = requests.get(
            f"{BASE_URL}/v3/klines",
            params=params, timeout=15,
        )
        if resp.status_code == 200:
            raw = resp.json()
            candles = []
            for c in raw:
                candles.append({
                    'time': c[0],  # Open time (ms)
                    'open': float(c[1]),
                    'high': float(c[2]),
                    'low': float(c[3]),
                    'close': float(c[4]),
                    'volume': float(c[5]),
                    'closeTime': c[6],
                    'quoteVolume': float(c[7]),
                    'trades': int(c[8]),
                })
            return jsonify({
                "success": True,
                "instrument": symbol,
                "interval": interval,
                "candles": candles,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PROFIT MONITOR & AUTO-CLOSE (FUTURES) ====================

@binance_api.route('/api/binance/profit-check', methods=['POST'])
def api_binance_profit_check():
    """
    Check open Binance futures positions against a USDT profit target.
    If total unrealized P&L >= target, auto-close ALL positions and distribute commissions.

    Body: { "target_profit": 100.0, "user_id": "...", "auto_close": true }
    """
    try:
        data = request.json or {}
        target_profit = float(data.get('target_profit', 0))
        user_id = data.get('user_id', '')
        auto_close = data.get('auto_close', True)

        if target_profit <= 0:
            return jsonify({"success": False, "error": "target_profit must be > 0"}), 400

        headers = _binance_headers()

        # 1. Fetch open futures positions
        params = _sign_params({})
        resp = requests.get(
            f"{FAPI_URL}/v2/positionRisk",
            headers=headers, params=params, timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        raw = resp.json()
        total_pnl = 0.0
        position_details = []
        active_positions = []

        for p in raw:
            amt = float(p.get('positionAmt', 0))
            if amt == 0:
                continue
            pnl = float(p.get('unRealizedProfit', 0))
            total_pnl += pnl
            active_positions.append(p)
            position_details.append({
                'symbol': p.get('symbol', ''),
                'direction': 'BUY' if amt > 0 else 'SELL',
                'size': abs(amt),
                'entryPrice': float(p.get('entryPrice', 0)),
                'markPrice': float(p.get('markPrice', 0)),
                'pnl': round(pnl, 2),
                'leverage': p.get('leverage', '1'),
            })

        target_reached = total_pnl >= target_profit
        close_results = []

        if target_reached and auto_close and len(active_positions) > 0:
            # 2. Auto-close all futures positions
            for p in active_positions:
                amt = float(p.get('positionAmt', 0))
                symbol = p.get('symbol', '')
                close_side = 'SELL' if amt > 0 else 'BUY'

                close_params = _sign_params({
                    'symbol': symbol,
                    'side': close_side,
                    'type': 'MARKET',
                    'quantity': str(abs(amt)),
                    'reduceOnly': 'true',
                })
                close_resp = requests.post(
                    f"{FAPI_URL}/v1/order",
                    headers=headers, params=close_params, timeout=15,
                )
                if close_resp.status_code == 200:
                    close_results.append({"symbol": symbol, "success": True})
                else:
                    close_results.append({"symbol": symbol, "success": False, "error": close_resp.text})

            closed_count = sum(1 for r in close_results if r['success'])
            logger.info(
                f"Binance profit target ${target_profit} reached (P&L: ${total_pnl:.2f}). "
                f"Closed {closed_count}/{len(active_positions)} positions for user {user_id}."
            )

        # 3. Fetch updated balance
        balance_info = {}
        if target_reached:
            bal_params = _sign_params({})
            bal_resp = requests.get(
                f"{FAPI_URL}/v2/balance",
                headers=headers, params=bal_params, timeout=10,
            )
            if bal_resp.status_code == 200:
                balances = bal_resp.json()
                usdt_bal = next((b for b in balances if b.get('asset') == 'USDT'), {})
                balance_info = {
                    'balance': float(usdt_bal.get('balance', 0)),
                    'available': float(usdt_bal.get('availableBalance', 0)),
                    'currency': 'USDT',
                }

            # 4. Distribute commissions
            if total_pnl > 0 and user_id:
                try:
                    from multi_broker_backend_updated import distribute_trade_commissions
                    distribute_trade_commissions(
                        bot_id=f'binance_profit_{user_id}',
                        user_id=user_id,
                        profit_amount=total_pnl,
                        source='BINANCE'
                    )
                    logger.info(f"Binance commission distributed for user {user_id}: ${total_pnl:.2f}")
                except Exception as comm_err:
                    logger.error(f"Binance commission distribution error: {comm_err}")

        return jsonify({
            "success": True,
            "target_profit": target_profit,
            "current_pnl": round(total_pnl, 2),
            "target_reached": target_reached,
            "positions_checked": len(active_positions),
            "positions": position_details,
            "positions_closed": len(close_results),
            "close_results": close_results,
            "balance_after": balance_info,
            "message": (
                f"Profit target ${target_profit:.2f} reached! "
                f"P&L: ${total_pnl:.2f} USDT. Positions closed. "
                f"Withdraw USDT to your wallet."
            ) if target_reached else (
                f"P&L ${total_pnl:.2f} / target ${target_profit:.2f} USDT — not yet reached."
            ),
        })
    except Exception as e:
        logger.error(f"Binance profit check error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== USDT WITHDRAWAL ====================

@binance_api.route('/api/binance/withdraw', methods=['POST'])
def api_binance_withdraw():
    """
    Withdraw USDT to an external wallet address.
    Body: { "amount": 50.0, "address": "T...", "network": "TRC20" }
    """
    try:
        data = request.json or {}
        amount = float(data.get('amount', 0))
        address = data.get('address', '').strip()
        network = data.get('network', 'TRC20')

        if amount <= 0:
            return jsonify({"success": False, "error": "amount must be > 0"}), 400
        if not address:
            return jsonify({"success": False, "error": "wallet address is required"}), 400

        headers = _binance_headers()
        params = _sign_params({
            'coin': 'USDT',
            'amount': str(amount),
            'address': address,
            'network': network,
        })

        resp = requests.post(
            "https://api.binance.com/sapi/v1/capital/withdraw/apply",
            headers=headers, params=params, timeout=30,
        )
        if resp.status_code == 200:
            result = resp.json()
            return jsonify({
                "success": True,
                "withdrawId": result.get('id', ''),
                "message": f"Withdrawal of {amount} USDT initiated to {address} via {network}.",
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"Binance withdrawal error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== WITHDRAWAL NOTIFICATIONS ====================

@binance_api.route('/api/binance/withdrawal-notifications', methods=['GET'])
def api_binance_withdrawal_notifications():
    """Get all Binance withdrawal-ready notifications for a user."""
    try:
        import sqlite3
        user_id = request.args.get('user_id', '')
        if not user_id:
            return jsonify({"success": False, "error": "user_id required"}), 400

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM broker_withdrawal_notifications
            WHERE user_id = ? AND broker = 'BINANCE'
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "notifications": rows})
    except Exception as e:
        logger.error(f"Binance withdrawal notifications error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@binance_api.route('/api/binance/withdrawal-notifications', methods=['POST'])
def api_binance_create_withdrawal_notification():
    """Create a withdrawal notification after profits are realized."""
    try:
        import sqlite3, uuid
        data = request.json or {}
        user_id = data.get('user_id', '')
        realized_profit = float(data.get('realized_profit', 0))
        positions_closed = int(data.get('positions_closed', 0))
        balance_available = float(data.get('balance_available', 0))
        wallet_address = data.get('wallet_address', '')

        if not user_id:
            return jsonify({"success": False, "error": "user_id required"}), 400

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broker_withdrawal_notifications (
                notification_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                broker TEXT NOT NULL DEFAULT 'BINANCE',
                realized_profit REAL DEFAULT 0,
                positions_closed INTEGER DEFAULT 0,
                balance_available REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT
            )
        ''')

        notif_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO broker_withdrawal_notifications
            (notification_id, user_id, broker, realized_profit, positions_closed,
             balance_available, status, created_at)
            VALUES (?, ?, 'BINANCE', ?, ?, ?, 'pending', ?)
        ''', (notif_id, user_id, realized_profit, positions_closed,
              balance_available, created_at))

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "notification_id": notif_id,
            "message": "Withdrawal notification created. Withdraw USDT to your wallet.",
        })
    except Exception as e:
        logger.error(f"Binance withdrawal notification error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
