import os
import logging
from flask import Blueprint, jsonify, request
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

oanda_api = Blueprint('oanda_api', __name__)

# In-memory token cache
_oanda_tokens = {
    'access_token': None,
    'account_id': None,
    'expires_at': None,
}

OANDA_API_KEY = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_DEMO_MODE = os.getenv("OANDA_DEMO_MODE", "true").lower() == "true"

BASE_URL = (
    "https://api-fxpractice.oanda.com/v3"
    if OANDA_DEMO_MODE
    else "https://api-fxtrade.oanda.com/v3"
)

STREAM_URL = (
    "https://stream-fxpractice.oanda.com/v3"
    if OANDA_DEMO_MODE
    else "https://stream-fxtrade.oanda.com/v3"
)


def _oanda_headers(content_type=True):
    """Build standard OANDA API headers with Bearer token."""
    h = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Accept": "application/json",
    }
    if content_type:
        h["Content-Type"] = "application/json"
    return h


def _get_account_id():
    """Return configured OANDA account ID."""
    return request.args.get('account_id', OANDA_ACCOUNT_ID) or OANDA_ACCOUNT_ID


# ==================== AUTH / STATUS ====================

@oanda_api.route('/api/oanda/login', methods=['POST'])
def api_oanda_login():
    """Verify OANDA credentials by fetching account list."""
    try:
        headers = _oanda_headers(content_type=False)
        resp = requests.get(f"{BASE_URL}/accounts", headers=headers, timeout=10)
        if resp.status_code == 200:
            accounts = resp.json().get('accounts', [])
            _oanda_tokens['access_token'] = OANDA_API_KEY
            _oanda_tokens['expires_at'] = datetime.utcnow() + timedelta(days=365)
            return jsonify({
                "success": True,
                "message": "OANDA connected",
                "accounts": accounts,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== ACCOUNTS ====================

@oanda_api.route('/api/oanda/accounts', methods=['GET'])
def api_oanda_accounts():
    try:
        headers = _oanda_headers(content_type=False)
        resp = requests.get(f"{BASE_URL}/accounts", headers=headers, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "accounts": resp.json().get('accounts', [])})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/balance', methods=['GET'])
def api_oanda_balance():
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/summary",
            headers=headers, timeout=10,
        )
        if resp.status_code == 200:
            acct = resp.json().get('account', {})
            return jsonify({
                'success': True,
                'balance': float(acct.get('balance', 0)),
                'available': float(acct.get('marginAvailable', 0)),
                'unrealizedPL': float(acct.get('unrealizedPL', 0)),
                'pl': float(acct.get('pl', 0)),
                'currency': acct.get('currency', 'USD'),
                'openTradeCount': int(acct.get('openTradeCount', 0)),
                'NAV': float(acct.get('NAV', 0)),
                'marginUsed': float(acct.get('marginUsed', 0)),
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@oanda_api.route('/api/oanda/funds', methods=['GET'])
def api_oanda_funds():
    """Alias for balance — matches IG pattern."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/summary",
            headers=headers, timeout=10,
        )
        if resp.status_code == 200:
            acct = resp.json().get('account', {})
            return jsonify({
                'success': True,
                'funds': {
                    'accountId': acct.get('id', account_id),
                    'balance': float(acct.get('balance', 0)),
                    'available': float(acct.get('marginAvailable', 0)),
                    'profitLoss': float(acct.get('unrealizedPL', 0)),
                    'currency': acct.get('currency', 'USD'),
                    'NAV': float(acct.get('NAV', 0)),
                },
            })
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== POSITIONS / OPEN TRADES ====================

@oanda_api.route('/api/oanda/positions', methods=['GET'])
def api_oanda_positions():
    """Get all open trades (positions)."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/openTrades",
            headers=headers, timeout=10,
        )
        if resp.status_code == 200:
            raw = resp.json().get('trades', [])
            positions = []
            for t in raw:
                positions.append({
                    'dealId': t.get('id', ''),
                    'instrument': t.get('instrument', ''),
                    'direction': 'BUY' if float(t.get('currentUnits', 0)) > 0 else 'SELL',
                    'size': abs(float(t.get('currentUnits', 0))),
                    'level': float(t.get('price', 0)),
                    'unrealizedPL': float(t.get('unrealizedPL', 0)),
                    'currency': t.get('instrument', '').split('_')[-1] if '_' in t.get('instrument', '') else 'USD',
                    'stopLossPrice': t.get('stopLossOrder', {}).get('price') if t.get('stopLossOrder') else None,
                    'takeProfitPrice': t.get('takeProfitOrder', {}).get('price') if t.get('takeProfitOrder') else None,
                    'trailingStopDistance': t.get('trailingStopLossOrder', {}).get('distance') if t.get('trailingStopLossOrder') else None,
                    'openTime': t.get('openTime', ''),
                })
            return jsonify({"success": True, "positions": positions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"OANDA positions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CLOSE POSITION ====================

@oanda_api.route('/api/oanda/close-position', methods=['POST'])
def api_oanda_close_position():
    """Close a specific open trade by trade ID."""
    try:
        data = request.json or {}
        trade_id = data.get('dealId') or data.get('tradeId')
        if not trade_id:
            return jsonify({"success": False, "error": "dealId/tradeId is required"}), 400

        account_id = _get_account_id()
        headers = _oanda_headers()

        # Close entire position (units=ALL) or partial
        units = data.get('units', 'ALL')
        payload = {"units": str(units)}

        resp = requests.put(
            f"{BASE_URL}/accounts/{account_id}/trades/{trade_id}/close",
            headers=headers, json=payload, timeout=15,
        )
        if resp.status_code == 200:
            result = resp.json()
            return jsonify({
                "success": True,
                "orderFillTransaction": result.get('orderFillTransaction', {}),
                "orderCreateTransaction": result.get('orderCreateTransaction', {}),
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"OANDA close position error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/close-all-positions', methods=['POST'])
def api_oanda_close_all():
    """Close all open trades."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/openTrades",
            headers=headers, timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch trades"}), 500

        trades = resp.json().get('trades', [])
        results = []
        close_headers = _oanda_headers()

        for t in trades:
            trade_id = t.get('id')
            close_resp = requests.put(
                f"{BASE_URL}/accounts/{account_id}/trades/{trade_id}/close",
                headers=close_headers, json={"units": "ALL"}, timeout=15,
            )
            if close_resp.status_code == 200:
                results.append({"tradeId": trade_id, "success": True})
            else:
                results.append({"tradeId": trade_id, "success": False, "error": close_resp.text})

        closed_count = sum(1 for r in results if r['success'])
        return jsonify({
            "success": True,
            "closed": closed_count,
            "total": len(trades),
            "results": results,
        })
    except Exception as e:
        logger.error(f"OANDA close all error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PLACE ORDER ====================

@oanda_api.route('/api/oanda/place-order', methods=['POST'])
def api_oanda_place_order():
    """Place a market order on OANDA."""
    try:
        data = request.json or {}
        account_id = _get_account_id()
        headers = _oanda_headers()

        instrument = data.get('instrument') or data.get('epic')
        direction = data.get('direction', 'BUY')
        size = float(data.get('size', 0))
        units = size if direction == 'BUY' else -size

        order = {
            "order": {
                "instrument": instrument,
                "units": str(int(units)),
                "type": data.get('orderType', 'MARKET'),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }

        # Optional stop loss / take profit
        if data.get('stopLossPrice'):
            order['order']['stopLossOnFill'] = {"price": str(data['stopLossPrice'])}
        if data.get('takeProfitPrice'):
            order['order']['takeProfitOnFill'] = {"price": str(data['takeProfitPrice'])}
        if data.get('trailingStopDistance'):
            order['order']['trailingStopLossOnFill'] = {"distance": str(data['trailingStopDistance'])}

        resp = requests.post(
            f"{BASE_URL}/accounts/{account_id}/orders",
            headers=headers, json=order, timeout=15,
        )
        if resp.status_code == 201:
            result = resp.json()
            fill = result.get('orderFillTransaction', {})
            return jsonify({
                "success": True,
                "orderFillTransaction": fill,
                "tradeId": fill.get('tradeOpened', {}).get('tradeID', ''),
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"OANDA place order error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== LIMIT / STOP ORDERS ====================

@oanda_api.route('/api/oanda/pending-orders', methods=['GET'])
def api_oanda_pending_orders():
    """Get all pending (working) orders."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/pendingOrders",
            headers=headers, timeout=10,
        )
        if resp.status_code == 200:
            orders = resp.json().get('orders', [])
            formatted = []
            for o in orders:
                formatted.append({
                    'orderId': o.get('id', ''),
                    'instrument': o.get('instrument', ''),
                    'type': o.get('type', ''),
                    'units': o.get('units', ''),
                    'price': o.get('price', ''),
                    'timeInForce': o.get('timeInForce', ''),
                    'createTime': o.get('createTime', ''),
                })
            return jsonify({"success": True, "pendingOrders": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/pending-orders', methods=['POST'])
def api_oanda_create_pending_order():
    """Create a limit or stop order."""
    try:
        data = request.json or {}
        account_id = _get_account_id()
        headers = _oanda_headers()

        instrument = data.get('instrument') or data.get('epic')
        direction = data.get('direction', 'BUY')
        size = float(data.get('size', 0))
        units = size if direction == 'BUY' else -size
        price = data.get('price')
        order_type = data.get('type', 'LIMIT')

        order = {
            "order": {
                "instrument": instrument,
                "units": str(int(units)),
                "price": str(price),
                "type": order_type,
                "timeInForce": data.get('timeInForce', 'GTC'),
                "positionFill": "DEFAULT",
            }
        }
        if data.get('stopLossPrice'):
            order['order']['stopLossOnFill'] = {"price": str(data['stopLossPrice'])}
        if data.get('takeProfitPrice'):
            order['order']['takeProfitOnFill'] = {"price": str(data['takeProfitPrice'])}

        resp = requests.post(
            f"{BASE_URL}/accounts/{account_id}/orders",
            headers=headers, json=order, timeout=15,
        )
        if resp.status_code == 201:
            return jsonify({"success": True, "order": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/pending-orders/<order_id>', methods=['DELETE'])
def api_oanda_cancel_order(order_id):
    """Cancel a pending order."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.put(
            f"{BASE_URL}/accounts/{account_id}/orders/{order_id}/cancel",
            headers=headers, timeout=10,
        )
        if resp.status_code == 200:
            return jsonify({"success": True, "cancelled": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== TRANSACTIONS / TRADE HISTORY ====================

@oanda_api.route('/api/oanda/transactions', methods=['GET'])
def api_oanda_transactions():
    """Get recent transaction history."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)

        params = {}
        if request.args.get('from'):
            params['from'] = request.args['from']
        if request.args.get('to'):
            params['to'] = request.args['to']
        page_size = request.args.get('pageSize', '50')
        params['count'] = page_size
        tx_type = request.args.get('type')
        if tx_type:
            params['type'] = tx_type

        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/transactions",
            headers=headers, params=params, timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            transactions = data.get('transactions', [])

            # Some OANDA transaction responses return page URLs instead of embedded transactions.
            # Resolve those pages so the frontend receives actual transaction records.
            if not transactions:
                page_urls = data.get('pages', [])
                resolved_transactions = []
                for page_url in page_urls:
                    try:
                        page_resp = requests.get(page_url, headers=headers, timeout=15)
                        if page_resp.status_code == 200:
                            page_data = page_resp.json()
                            resolved_transactions.extend(page_data.get('transactions', []))
                    except Exception as page_error:
                        logger.warning(f"OANDA transactions page fetch failed: {page_error}")
                transactions = resolved_transactions

            return jsonify({
                "success": True,
                "transactions": transactions,
                "count": len(transactions),
                "lastTransactionID": data.get('lastTransactionID'),
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"OANDA transactions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== MARKET SEARCH / INSTRUMENTS ====================

@oanda_api.route('/api/oanda/instruments', methods=['GET'])
def api_oanda_instruments():
    """Get tradeable instruments for the account."""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/instruments",
            headers=headers, timeout=15,
        )
        if resp.status_code == 200:
            instruments = resp.json().get('instruments', [])
            search_term = request.args.get('searchTerm', '').upper()
            if search_term:
                instruments = [i for i in instruments if search_term in i.get('name', '').upper()
                               or search_term in i.get('displayName', '').upper()]

            formatted = []
            for inst in instruments[:100]:
                formatted.append({
                    'instrument': inst.get('name', ''),
                    'displayName': inst.get('displayName', ''),
                    'type': inst.get('type', ''),
                    'pipLocation': inst.get('pipLocation', 0),
                    'minimumTradeSize': inst.get('minimumTradeSize', ''),
                    'maximumOrderUnits': inst.get('maximumOrderUnits', ''),
                })
            return jsonify({"success": True, "instruments": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/pricing', methods=['GET'])
def api_oanda_pricing():
    """Get current prices for instruments. Query: instruments=EUR_USD,GBP_USD"""
    try:
        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)
        instruments = request.args.get('instruments', '')
        if not instruments:
            return jsonify({"success": False, "error": "instruments param required (e.g. EUR_USD,GBP_USD)"}), 400

        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/pricing",
            headers=headers, params={"instruments": instruments}, timeout=10,
        )
        if resp.status_code == 200:
            prices = resp.json().get('prices', [])
            formatted = []
            for p in prices:
                asks = p.get('asks', [{}])
                bids = p.get('bids', [{}])
                formatted.append({
                    'instrument': p.get('instrument', ''),
                    'ask': float(asks[0].get('price', 0)) if asks else 0,
                    'bid': float(bids[0].get('price', 0)) if bids else 0,
                    'spread': round(float(asks[0].get('price', 0)) - float(bids[0].get('price', 0)), 6) if asks and bids else 0,
                    'tradeable': p.get('tradeable', False),
                    'time': p.get('time', ''),
                })
            return jsonify({"success": True, "prices": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== CANDLES / HISTORICAL DATA ====================

@oanda_api.route('/api/oanda/candles/<instrument>', methods=['GET'])
def api_oanda_candles(instrument):
    """Get candlestick data. Query: granularity=H1&count=100"""
    try:
        headers = _oanda_headers(content_type=False)
        params = {
            'granularity': request.args.get('granularity', 'H1'),
            'count': request.args.get('count', '100'),
        }
        if request.args.get('from'):
            params['from'] = request.args['from']
        if request.args.get('to'):
            params['to'] = request.args['to']

        resp = requests.get(
            f"{BASE_URL}/instruments/{instrument}/candles",
            headers=headers, params=params, timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            candles = data.get('candles', [])
            formatted = []
            for c in candles:
                mid = c.get('mid', {})
                formatted.append({
                    'time': c.get('time', ''),
                    'open': float(mid.get('o', 0)),
                    'high': float(mid.get('h', 0)),
                    'low': float(mid.get('l', 0)),
                    'close': float(mid.get('c', 0)),
                    'volume': int(c.get('volume', 0)),
                    'complete': c.get('complete', False),
                })
            return jsonify({
                "success": True,
                "instrument": data.get('instrument', instrument),
                "granularity": data.get('granularity', ''),
                "candles": formatted,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PROFIT MONITOR & AUTO-CLOSE ====================

@oanda_api.route('/api/oanda/profit-check', methods=['POST'])
def api_oanda_profit_check():
    """
    Check all open OANDA trades against a profit target.
    If total unrealized P&L >= target, auto-close ALL trades and distribute commissions.

    Body: { "target_profit": 100.0, "user_id": "...", "auto_close": true }
    """
    try:
        data = request.json or {}
        target_profit = float(data.get('target_profit', 0))
        user_id = data.get('user_id', '')
        auto_close = data.get('auto_close', True)

        if target_profit <= 0:
            return jsonify({"success": False, "error": "target_profit must be > 0"}), 400

        account_id = _get_account_id()
        headers = _oanda_headers(content_type=False)

        # 1. Fetch open trades
        resp = requests.get(
            f"{BASE_URL}/accounts/{account_id}/openTrades",
            headers=headers, timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch trades"}), 500

        trades = resp.json().get('trades', [])
        total_pnl = 0.0
        position_details = []

        for t in trades:
            pnl = float(t.get('unrealizedPL', 0))
            total_pnl += pnl
            units = float(t.get('currentUnits', 0))
            position_details.append({
                'tradeId': t.get('id', ''),
                'instrument': t.get('instrument', ''),
                'direction': 'BUY' if units > 0 else 'SELL',
                'size': abs(units),
                'openLevel': float(t.get('price', 0)),
                'pnl': round(pnl, 2),
                'openTime': t.get('openTime', ''),
            })

        target_reached = total_pnl >= target_profit
        close_results = []

        if target_reached and auto_close and len(trades) > 0:
            # 2. Auto-close all trades
            close_headers = _oanda_headers()
            for t in trades:
                trade_id = t.get('id')
                close_resp = requests.put(
                    f"{BASE_URL}/accounts/{account_id}/trades/{trade_id}/close",
                    headers=close_headers, json={"units": "ALL"}, timeout=15,
                )
                if close_resp.status_code == 200:
                    close_results.append({"tradeId": trade_id, "success": True})
                else:
                    close_results.append({"tradeId": trade_id, "success": False, "error": close_resp.text})

            closed_count = sum(1 for r in close_results if r['success'])
            logger.info(
                f"OANDA profit target ${target_profit} reached (P&L: ${total_pnl:.2f}). "
                f"Closed {closed_count}/{len(trades)} trades for user {user_id}."
            )

        # 3. Fetch updated balance
        balance_info = {}
        if target_reached:
            bal_resp = requests.get(
                f"{BASE_URL}/accounts/{account_id}/summary",
                headers=_oanda_headers(content_type=False), timeout=10,
            )
            if bal_resp.status_code == 200:
                acct = bal_resp.json().get('account', {})
                balance_info = {
                    'balance': float(acct.get('balance', 0)),
                    'available': float(acct.get('marginAvailable', 0)),
                    'NAV': float(acct.get('NAV', 0)),
                }

            # 4. Distribute commissions
            if total_pnl > 0 and user_id:
                try:
                    from multi_broker_backend_updated import distribute_trade_commissions
                    distribute_trade_commissions(
                        bot_id=f'oanda_profit_{user_id}',
                        user_id=user_id,
                        profit_amount=total_pnl,
                        source='OANDA'
                    )
                    logger.info(f"OANDA commission distributed for user {user_id}: ${total_pnl:.2f}")
                except Exception as comm_err:
                    logger.error(f"OANDA commission distribution error: {comm_err}")

        return jsonify({
            "success": True,
            "target_profit": target_profit,
            "current_pnl": round(total_pnl, 2),
            "target_reached": target_reached,
            "positions_checked": len(trades),
            "positions": position_details,
            "positions_closed": len(close_results),
            "close_results": close_results,
            "balance_after": balance_info,
            "message": (
                f"Profit target ${target_profit:.2f} reached! "
                f"P&L: ${total_pnl:.2f}. Trades closed. "
                f"Please withdraw funds from OANDA's website or app."
            ) if target_reached else (
                f"P&L ${total_pnl:.2f} / target ${target_profit:.2f} — not yet reached."
            ),
        })
    except Exception as e:
        logger.error(f"OANDA profit check error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== WITHDRAWAL NOTIFICATIONS ====================

@oanda_api.route('/api/oanda/withdrawal-notifications', methods=['GET'])
def api_oanda_withdrawal_notifications():
    """Get all OANDA withdrawal-ready notifications for a user."""
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
            WHERE user_id = ? AND broker = 'OANDA'
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "notifications": rows})
    except Exception as e:
        logger.error(f"OANDA withdrawal notifications error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@oanda_api.route('/api/oanda/withdrawal-notifications', methods=['POST'])
def api_oanda_create_withdrawal_notification():
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

        # Create table if not exists (shared across brokers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broker_withdrawal_notifications (
                notification_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                broker TEXT NOT NULL DEFAULT 'OANDA',
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
            VALUES (?, ?, 'OANDA', ?, ?, ?, 'pending', ?)
        ''', (notif_id, user_id, realized_profit, positions_closed,
              balance_available, created_at))

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "notification_id": notif_id,
            "message": "Withdrawal notification created. Please withdraw from OANDA platform.",
        })
    except Exception as e:
        logger.error(f"OANDA withdrawal notification error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
