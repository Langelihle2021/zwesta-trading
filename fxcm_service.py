import os
import logging
from flask import Blueprint, jsonify, request
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

fxcm_api = Blueprint('fxcm_api', __name__)

# In-memory token cache
_fxcm_tokens = {
    'access_token': None,
    'expires_at': None,
}

FXCM_API_TOKEN = os.getenv("FXCM_API_TOKEN", "")
FXCM_DEMO_MODE = os.getenv("FXCM_DEMO_MODE", "true").lower() == "true"

BASE_URL = (
    "https://api-demo.fxcm.com"
    if FXCM_DEMO_MODE
    else "https://api.fxcm.com"
)


def _fxcm_headers(content_type=True):
    """Build standard FXCM REST API headers with Bearer token."""
    h = {
        "Authorization": f"Bearer {FXCM_API_TOKEN}",
        "Accept": "application/json",
    }
    if content_type:
        h["Content-Type"] = "application/json"
    return h


def _get_account_id():
    """Return configured FXCM account ID from query params or env."""
    return request.args.get('account_id', os.getenv('FXCM_ACCOUNT_ID', ''))


# ==================== AUTH / STATUS ====================

@fxcm_api.route('/api/fxcm/login', methods=['POST'])
def api_fxcm_login():
    """Verify FXCM credentials by fetching account info."""
    try:
        data = request.json or {}
        token = data.get('token') or FXCM_API_TOKEN
        if not token:
            return jsonify({"success": False, "error": "FXCM API token required"}), 400

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Account"},
            timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            accounts = result.get('accounts', result.get('response', {}).get('accounts', []))
            _fxcm_tokens['access_token'] = token
            _fxcm_tokens['expires_at'] = datetime.utcnow() + timedelta(days=30)
            return jsonify({
                "success": True,
                "message": "FXCM connected",
                "accounts": accounts if isinstance(accounts, list) else [accounts],
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== ACCOUNTS ====================

@fxcm_api.route('/api/fxcm/accounts', methods=['GET'])
def api_fxcm_accounts():
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Account"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            accounts = data.get('accounts', [])
            return jsonify({"success": True, "accounts": accounts})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@fxcm_api.route('/api/fxcm/balance', methods=['GET'])
def api_fxcm_balance():
    try:
        account_id = _get_account_id()
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Account"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            accounts = data.get('accounts', [])
            acct = {}
            if isinstance(accounts, list):
                for a in accounts:
                    if str(a.get('accountId', '')) == str(account_id) or not account_id:
                        acct = a
                        break
                if not acct and accounts:
                    acct = accounts[0]

            return jsonify({
                'success': True,
                'balance': float(acct.get('balance', 0)),
                'available': float(acct.get('usableMargin', 0)),
                'equity': float(acct.get('equity', 0)),
                'unrealizedPL': float(acct.get('grossPL', 0)),
                'usedMargin': float(acct.get('usedMargin', 0)),
                'currency': acct.get('mc', 'USD'),
                'accountId': acct.get('accountId', ''),
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@fxcm_api.route('/api/fxcm/funds', methods=['GET'])
def api_fxcm_funds():
    """Alias for balance — matches IG/OANDA pattern."""
    try:
        account_id = _get_account_id()
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Account"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            accounts = data.get('accounts', [])
            acct = {}
            if isinstance(accounts, list):
                for a in accounts:
                    if str(a.get('accountId', '')) == str(account_id) or not account_id:
                        acct = a
                        break
                if not acct and accounts:
                    acct = accounts[0]

            return jsonify({
                'success': True,
                'funds': {
                    'accountId': acct.get('accountId', ''),
                    'balance': float(acct.get('balance', 0)),
                    'available': float(acct.get('usableMargin', 0)),
                    'equity': float(acct.get('equity', 0)),
                    'profitLoss': float(acct.get('grossPL', 0)),
                    'currency': acct.get('mc', 'USD'),
                },
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== POSITIONS / OPEN TRADES ====================

@fxcm_api.route('/api/fxcm/positions', methods=['GET'])
def api_fxcm_positions():
    """Get all open positions."""
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "OpenPosition"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get('open_positions', data.get('openPositions', []))
            positions = []
            for p in (raw if isinstance(raw, list) else []):
                positions.append({
                    'dealId': str(p.get('tradeId', '')),
                    'instrument': p.get('currency', ''),
                    'direction': 'BUY' if p.get('isBuy', False) else 'SELL',
                    'size': abs(float(p.get('amountK', 0))),
                    'level': float(p.get('open', 0)),
                    'unrealizedPL': float(p.get('grossPL', 0)),
                    'stopPrice': p.get('stop'),
                    'limitPrice': p.get('limit'),
                    'openTime': p.get('time', ''),
                    'currency': p.get('currency', ''),
                })
            return jsonify({"success": True, "positions": positions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"FXCM positions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CLOSE POSITION ====================

@fxcm_api.route('/api/fxcm/close-position', methods=['POST'])
def api_fxcm_close_position():
    """Close a specific open trade."""
    try:
        data = request.json or {}
        trade_id = data.get('dealId') or data.get('tradeId')
        if not trade_id:
            return jsonify({"success": False, "error": "dealId/tradeId is required"}), 400

        headers = _fxcm_headers()
        payload = {"trade_id": str(trade_id)}

        # Close via FXCM REST
        resp = requests.post(
            f"{BASE_URL}/trading/close_trade",
            headers=headers, json=payload, timeout=15,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "result": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"FXCM close position error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fxcm_api.route('/api/fxcm/close-all-positions', methods=['POST'])
def api_fxcm_close_all():
    """Close all open positions."""
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "OpenPosition"},
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        data = resp.json()
        raw = data.get('open_positions', data.get('openPositions', []))
        positions = raw if isinstance(raw, list) else []

        results = []
        close_headers = _fxcm_headers()

        for p in positions:
            trade_id = p.get('tradeId', '')
            close_resp = requests.post(
                f"{BASE_URL}/trading/close_trade",
                headers=close_headers,
                json={"trade_id": str(trade_id)},
                timeout=15,
            )
            if close_resp.status_code == 200:
                results.append({"tradeId": str(trade_id), "success": True})
            else:
                results.append({"tradeId": str(trade_id), "success": False, "error": close_resp.text})

        closed_count = sum(1 for r in results if r['success'])
        return jsonify({
            "success": True,
            "closed": closed_count,
            "total": len(positions),
            "results": results,
        })
    except Exception as e:
        logger.error(f"FXCM close all error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PLACE ORDER ====================

@fxcm_api.route('/api/fxcm/place-order', methods=['POST'])
def api_fxcm_place_order():
    """Place a market order on FXCM."""
    try:
        data = request.json or {}
        headers = _fxcm_headers()
        account_id = _get_account_id()

        instrument = data.get('instrument') or data.get('epic') or data.get('symbol')
        direction = data.get('direction', 'BUY')
        size = float(data.get('size', 0))
        is_buy = direction.upper() == 'BUY'

        payload = {
            "account_id": account_id,
            "symbol": instrument,
            "is_buy": is_buy,
            "amount": size,
            "order_type": "AtMarket",
            "time_in_force": "GTC",
        }

        # Optional stop/limit
        if data.get('stopPrice'):
            payload['stop'] = float(data['stopPrice'])
        if data.get('limitPrice') or data.get('takeProfitPrice'):
            payload['limit'] = float(data.get('limitPrice') or data['takeProfitPrice'])
        if data.get('trailingStep'):
            payload['trailing_step'] = float(data['trailingStep'])

        resp = requests.post(
            f"{BASE_URL}/trading/open_trade",
            headers=headers, json=payload, timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            return jsonify({
                "success": True,
                "orderId": result.get('data', {}).get('orderId', ''),
                "tradeId": result.get('data', {}).get('tradeId', ''),
                "result": result,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"FXCM place order error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PENDING / ENTRY ORDERS ====================

@fxcm_api.route('/api/fxcm/pending-orders', methods=['GET'])
def api_fxcm_pending_orders():
    """Get all pending (entry) orders."""
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Order"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            orders = data.get('orders', [])
            formatted = []
            for o in (orders if isinstance(orders, list) else []):
                formatted.append({
                    'orderId': str(o.get('orderId', '')),
                    'instrument': o.get('currency', ''),
                    'type': o.get('type', ''),
                    'isBuy': o.get('isBuy', False),
                    'amount': float(o.get('amountK', 0)),
                    'rate': float(o.get('buy', 0) if o.get('isBuy') else o.get('sell', 0)),
                    'timeInForce': o.get('timeInForce', ''),
                    'status': o.get('status', ''),
                })
            return jsonify({"success": True, "pendingOrders": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@fxcm_api.route('/api/fxcm/pending-orders', methods=['POST'])
def api_fxcm_create_pending_order():
    """Create an entry (limit/stop) order."""
    try:
        data = request.json or {}
        headers = _fxcm_headers()
        account_id = _get_account_id()

        instrument = data.get('instrument') or data.get('symbol')
        direction = data.get('direction', 'BUY')
        size = float(data.get('size', 0))
        price = float(data.get('price', 0))
        order_type = data.get('type', 'Limit')

        payload = {
            "account_id": account_id,
            "symbol": instrument,
            "is_buy": direction.upper() == 'BUY',
            "amount": size,
            "order_type": order_type,
            "rate": price,
            "time_in_force": data.get('timeInForce', 'GTC'),
        }

        if data.get('stopPrice'):
            payload['stop'] = float(data['stopPrice'])
        if data.get('limitPrice'):
            payload['limit'] = float(data['limitPrice'])

        resp = requests.post(
            f"{BASE_URL}/trading/create_entry_order",
            headers=headers, json=payload, timeout=15,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "order": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@fxcm_api.route('/api/fxcm/pending-orders/<order_id>', methods=['DELETE'])
def api_fxcm_cancel_order(order_id):
    """Cancel a pending entry order."""
    try:
        headers = _fxcm_headers()
        resp = requests.post(
            f"{BASE_URL}/trading/delete_order",
            headers=headers, json={"order_id": str(order_id)},
            timeout=10,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "cancelled": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== TRADE HISTORY ====================

@fxcm_api.route('/api/fxcm/transactions', methods=['GET'])
def api_fxcm_transactions():
    """Get closed trade history."""
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "ClosedPosition"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            closed = data.get('closed_positions', data.get('closedPositions', []))
            transactions = []
            for c in (closed if isinstance(closed, list) else []):
                transactions.append({
                    'tradeId': str(c.get('tradeId', '')),
                    'instrument': c.get('currency', ''),
                    'direction': 'BUY' if c.get('isBuy', False) else 'SELL',
                    'size': abs(float(c.get('amountK', 0))),
                    'openPrice': float(c.get('open', 0)),
                    'closePrice': float(c.get('close', 0)),
                    'grossPL': float(c.get('grossPL', 0)),
                    'openTime': c.get('openTime', ''),
                    'closeTime': c.get('closeTime', ''),
                })
            return jsonify({"success": True, "transactions": transactions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"FXCM transactions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== INSTRUMENTS / SYMBOLS ====================

@fxcm_api.route('/api/fxcm/instruments', methods=['GET'])
def api_fxcm_instruments():
    """Get available trading instruments/symbols."""
    try:
        headers = _fxcm_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/trading/get_instruments",
            headers=headers, timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            instruments = data.get('data', {}).get('instrument', [])
            search_term = request.args.get('searchTerm', '').upper()
            if search_term:
                instruments = [i for i in instruments
                               if search_term in str(i.get('symbol', '')).upper()
                               or search_term in str(i.get('currency', '')).upper()]

            formatted = []
            for inst in instruments[:100]:
                formatted.append({
                    'instrument': inst.get('symbol', inst.get('currency', '')),
                    'displayName': inst.get('symbol', inst.get('currency', '')),
                    'type': inst.get('type', 'CURRENCY'),
                    'pipSize': inst.get('pipSize', 0),
                    'visible': inst.get('visible', True),
                })
            return jsonify({"success": True, "instruments": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PRICING ====================

@fxcm_api.route('/api/fxcm/pricing', methods=['GET'])
def api_fxcm_pricing():
    """Get current prices for instruments. Query: instruments=EUR/USD,GBP/USD"""
    try:
        headers = _fxcm_headers(content_type=False)
        instruments = request.args.get('instruments', '')
        if not instruments:
            return jsonify({"success": False, "error": "instruments param required (e.g. EUR/USD,GBP/USD)"}), 400

        # FXCM provides prices via their subscription model;
        # we fetch from the offers model
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "Offer"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            offers = data.get('offers', [])
            requested = [s.strip() for s in instruments.split(',')]
            formatted = []
            for o in (offers if isinstance(offers, list) else []):
                symbol = o.get('currency', '')
                if symbol in requested or not requested[0]:
                    formatted.append({
                        'instrument': symbol,
                        'ask': float(o.get('sell', 0)),
                        'bid': float(o.get('buy', 0)),
                        'spread': float(o.get('sell', 0)) - float(o.get('buy', 0)),
                        'high': float(o.get('high', 0)),
                        'low': float(o.get('low', 0)),
                        'time': o.get('time', ''),
                    })
            return jsonify({"success": True, "prices": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CANDLES / HISTORICAL DATA ====================

@fxcm_api.route('/api/fxcm/candles/<instrument>', methods=['GET'])
def api_fxcm_candles(instrument):
    """Get candlestick data. Query: period=H1&num=100"""
    try:
        headers = _fxcm_headers(content_type=False)
        period = request.args.get('period', request.args.get('granularity', 'H1'))
        num = request.args.get('num', request.args.get('count', '100'))

        # Clean instrument name (EUR/USD -> EUR%2FUSD for URL)
        safe_instrument = instrument.replace('/', '%2F')

        resp = requests.get(
            f"{BASE_URL}/candles/{safe_instrument}/{period}",
            headers=headers, params={"num": num},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            candles_raw = data.get('candles', [])
            formatted = []
            for c in candles_raw:
                formatted.append({
                    'time': c.get('timestamp', c.get('time', '')),
                    'open': float(c.get('openBid', c.get('open', 0))),
                    'high': float(c.get('highBid', c.get('high', 0))),
                    'low': float(c.get('lowBid', c.get('low', 0))),
                    'close': float(c.get('closeBid', c.get('close', 0))),
                    'volume': int(c.get('tickQty', c.get('volume', 0))),
                })
            return jsonify({
                "success": True,
                "instrument": instrument,
                "period": period,
                "candles": formatted,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PROFIT MONITOR & AUTO-CLOSE ====================

@fxcm_api.route('/api/fxcm/profit-check', methods=['POST'])
def api_fxcm_profit_check():
    """
    Check all open FXCM positions against a profit target.
    If total unrealized P&L >= target, auto-close ALL and distribute commissions.

    Body: { "target_profit": 100.0, "user_id": "...", "auto_close": true }
    """
    try:
        data = request.json or {}
        target_profit = float(data.get('target_profit', 0))
        user_id = data.get('user_id', '')
        auto_close = data.get('auto_close', True)

        if target_profit <= 0:
            return jsonify({"success": False, "error": "target_profit must be > 0"}), 400

        headers = _fxcm_headers(content_type=False)

        # 1. Fetch open positions
        resp = requests.get(
            f"{BASE_URL}/trading/get_model",
            headers=headers, params={"models": "OpenPosition"},
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        raw_data = resp.json()
        raw = raw_data.get('open_positions', raw_data.get('openPositions', []))
        positions_list = raw if isinstance(raw, list) else []

        total_pnl = 0.0
        position_details = []

        for p in positions_list:
            pnl = float(p.get('grossPL', 0))
            total_pnl += pnl
            position_details.append({
                'tradeId': str(p.get('tradeId', '')),
                'instrument': p.get('currency', ''),
                'direction': 'BUY' if p.get('isBuy', False) else 'SELL',
                'size': abs(float(p.get('amountK', 0))),
                'openLevel': float(p.get('open', 0)),
                'pnl': round(pnl, 2),
                'openTime': p.get('time', ''),
            })

        target_reached = total_pnl >= target_profit
        close_results = []

        if target_reached and auto_close and len(positions_list) > 0:
            # 2. Auto-close all positions
            close_headers = _fxcm_headers()
            for p in positions_list:
                trade_id = p.get('tradeId', '')
                close_resp = requests.post(
                    f"{BASE_URL}/trading/close_trade",
                    headers=close_headers,
                    json={"trade_id": str(trade_id)},
                    timeout=15,
                )
                if close_resp.status_code == 200:
                    close_results.append({"tradeId": str(trade_id), "success": True})
                else:
                    close_results.append({"tradeId": str(trade_id), "success": False, "error": close_resp.text})

            closed_count = sum(1 for r in close_results if r['success'])
            logger.info(
                f"FXCM profit target ${target_profit} reached (P&L: ${total_pnl:.2f}). "
                f"Closed {closed_count}/{len(positions_list)} positions for user {user_id}."
            )

        # 3. Fetch updated balance
        balance_info = {}
        if target_reached:
            bal_resp = requests.get(
                f"{BASE_URL}/trading/get_model",
                headers=_fxcm_headers(content_type=False),
                params={"models": "Account"}, timeout=10,
            )
            if bal_resp.status_code == 200:
                accts = bal_resp.json().get('accounts', [])
                acct = accts[0] if isinstance(accts, list) and accts else {}
                balance_info = {
                    'balance': float(acct.get('balance', 0)),
                    'available': float(acct.get('usableMargin', 0)),
                    'equity': float(acct.get('equity', 0)),
                }

            # 4. Distribute commissions
            if total_pnl > 0 and user_id:
                try:
                    from multi_broker_backend_updated import distribute_trade_commissions
                    distribute_trade_commissions(
                        bot_id=f'fxcm_profit_{user_id}',
                        user_id=user_id,
                        profit_amount=total_pnl,
                        source='FXCM'
                    )
                    logger.info(f"FXCM commission distributed for user {user_id}: ${total_pnl:.2f}")
                except Exception as comm_err:
                    logger.error(f"FXCM commission distribution error: {comm_err}")

        return jsonify({
            "success": True,
            "target_profit": target_profit,
            "current_pnl": round(total_pnl, 2),
            "target_reached": target_reached,
            "positions_checked": len(positions_list),
            "positions": position_details,
            "positions_closed": len(close_results),
            "close_results": close_results,
            "balance_after": balance_info,
            "message": (
                f"Profit target ${target_profit:.2f} reached! "
                f"P&L: ${total_pnl:.2f}. Positions closed. "
                f"Please withdraw funds from FXCM's website or app."
            ) if target_reached else (
                f"P&L ${total_pnl:.2f} / target ${target_profit:.2f} — not yet reached."
            ),
        })
    except Exception as e:
        logger.error(f"FXCM profit check error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== WITHDRAWAL NOTIFICATIONS ====================

@fxcm_api.route('/api/fxcm/withdrawal-notifications', methods=['GET'])
def api_fxcm_withdrawal_notifications():
    """Get all FXCM withdrawal-ready notifications for a user."""
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
            WHERE user_id = ? AND broker = 'FXCM'
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "notifications": rows})
    except Exception as e:
        logger.error(f"FXCM withdrawal notifications error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@fxcm_api.route('/api/fxcm/withdrawal-notifications', methods=['POST'])
def api_fxcm_create_withdrawal_notification():
    """Create a withdrawal notification after profits are realized."""
    try:
        import sqlite3, uuid
        data = request.json or {}
        user_id = data.get('user_id', '')
        realized_profit = float(data.get('realized_profit', 0))
        positions_closed = int(data.get('positions_closed', 0))
        balance_available = float(data.get('balance_available', 0))

        if not user_id:
            return jsonify({"success": False, "error": "user_id required"}), 400

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broker_withdrawal_notifications (
                notification_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                broker TEXT NOT NULL DEFAULT 'FXCM',
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
            VALUES (?, ?, 'FXCM', ?, ?, ?, 'pending', ?)
        ''', (notif_id, user_id, realized_profit, positions_closed,
              balance_available, created_at))

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "notification_id": notif_id,
            "message": "Withdrawal notification created. Please withdraw from FXCM platform.",
        })
    except Exception as e:
        logger.error(f"FXCM withdrawal notification error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
