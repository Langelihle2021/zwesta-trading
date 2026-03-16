import os
import logging
from flask import Blueprint, jsonify, request
import sqlite3
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ig_api = Blueprint('ig_api', __name__)

# Per-user token cache; key format: user_id:username:mode.
_ig_tokens = {}

IG_API_KEY = os.getenv("IG_API_KEY")
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")
IG_DEMO_MODE = os.getenv("IG_DEMO_MODE", "true").lower() == "true"
BASE_URL = "https://demo-api.ig.com/gateway/deal" if IG_DEMO_MODE else "https://api.ig.com/gateway/deal"
DATABASE_PATH = os.getenv('DATABASE_PATH', 'zwesta_trading.db')


def _get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _get_base_url(credentials=None):
    creds = credentials or getattr(request, 'ig_credentials', None)
    if not creds:
        return BASE_URL
    is_live = bool(creds.get('is_live', False))
    return "https://api.ig.com/gateway/deal" if is_live else "https://demo-api.ig.com/gateway/deal"


def _token_cache_key(user_id, credentials):
    mode = 'live' if bool(credentials.get('is_live', False)) else 'demo'
    return f"{user_id}:{credentials.get('username', '')}:{mode}"


def _get_user_ig_credentials(user_id):
    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT api_key, username, password, account_number, server, is_live
            FROM broker_credentials
            WHERE user_id = ?
              AND is_active = 1
              AND broker_name IN ('IG Markets', 'IG.com', 'IG')
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        if not row:
            return None

        credentials = dict(row)
        return {
            'api_key': credentials.get('api_key') or IG_API_KEY,
            'username': credentials.get('username') or IG_USERNAME,
            'password': credentials.get('password') or IG_PASSWORD,
            'account_id': credentials.get('account_number') or IG_ACCOUNT_ID,
            'is_live': bool(credentials.get('is_live', 0)),
            'server': credentials.get('server')
        }
    finally:
        conn.close()


@ig_api.before_request
def _require_ig_session():
    session_token = request.headers.get('X-Session-Token')
    if not session_token:
        return jsonify({'success': False, 'error': 'Missing session token in X-Session-Token header'}), 401

    conn = _get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, expires_at
            FROM user_sessions
            WHERE token = ? AND is_active = 1
        ''', (session_token,))
        session = cursor.fetchone()
        if not session:
            return jsonify({'success': False, 'error': 'Invalid or inactive session token'}), 401

        expires_at = datetime.fromisoformat(session['expires_at'])
        if datetime.now() > expires_at:
            return jsonify({'success': False, 'error': 'Session token expired'}), 401

        request.user_id = session['user_id']
        request.ig_credentials = _get_user_ig_credentials(request.user_id)
        if not request.ig_credentials:
            return jsonify({'success': False, 'error': 'No IG credentials configured for this user'}), 400
    except Exception as e:
        logger.error(f"IG session validation error: {e}")
        return jsonify({'success': False, 'error': 'Session validation error'}), 500
    finally:
        conn.close()


def _ig_headers(cst, xst, version="1", content_type=True):
    """Build standard IG API headers."""
    if not cst or not xst:
        raise ValueError("IG session not initialized for authenticated user")

    credentials = getattr(request, 'ig_credentials', None)
    api_key = (credentials or {}).get('api_key') or IG_API_KEY
    h = {
        "X-IG-API-KEY": api_key,
        "CST": cst,
        "X-SECURITY-TOKEN": xst,
        "Accept": "application/json; charset=UTF-8",
        "Version": version,
    }
    if content_type:
        h["Content-Type"] = "application/json; charset=UTF-8"
    return h

def ig_login(user_id, credentials):
    url = f"{_get_base_url(credentials)}/session"
    headers = {
        "X-IG-API-KEY": credentials.get('api_key') or IG_API_KEY,
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
        "Version": "2"
    }
    data = {
        "identifier": credentials.get('username') or IG_USERNAME,
        "password": credentials.get('password') or IG_PASSWORD
    }

    if not data['identifier'] or not data['password']:
        return False, "IG username/password missing for this user"

    resp = requests.post(url, headers=headers, json=data, timeout=15)
    if resp.status_code == 200:
        cst = resp.headers.get("CST")
        xst = resp.headers.get("X-SECURITY-TOKEN")
        cache_key = _token_cache_key(user_id, credentials)
        _ig_tokens[cache_key] = {
            'CST': cst,
            'XST': xst,
            'expires_at': datetime.utcnow() + timedelta(hours=5)
        }
        return True, "Login successful"
    else:
        return False, resp.text

def get_ig_tokens():
    user_id = getattr(request, 'user_id', None)
    credentials = getattr(request, 'ig_credentials', None)

    if user_id and credentials:
        cache_key = _token_cache_key(user_id, credentials)
        cached = _ig_tokens.get(cache_key)
        if not cached or not cached.get('CST') or not cached.get('XST') or datetime.utcnow() > cached.get('expires_at'):
            ok, msg = ig_login(user_id, credentials)
            if not ok:
                logger.error(f"IG login failed for user {user_id}: {msg}")
                return None, None
            cached = _ig_tokens.get(cache_key)
        return cached.get('CST'), cached.get('XST')

    # Compatibility fallback (legacy environment-level credentials)
    fallback_credentials = {
        'api_key': IG_API_KEY,
        'username': IG_USERNAME,
        'password': IG_PASSWORD,
        'is_live': not IG_DEMO_MODE,
    }
    legacy_key = _token_cache_key('legacy', fallback_credentials)
    cached = _ig_tokens.get(legacy_key)
    if not cached or not cached.get('CST') or not cached.get('XST') or datetime.utcnow() > cached.get('expires_at'):
        ok, msg = ig_login('legacy', fallback_credentials)
        if not ok:
            logger.error(f"Legacy IG login failed: {msg}")
            return None, None
        cached = _ig_tokens.get(legacy_key)
    if not cached:
        return None, None
    return cached.get('CST'), cached.get('XST')

# ==================== AUTH ====================

@ig_api.route('/api/ig/login', methods=['POST'])
def api_ig_login():
    ok, msg = ig_login(request.user_id, request.ig_credentials)
    return jsonify({"success": ok, "message": msg})

# ==================== ACCOUNTS ====================

@ig_api.route('/api/ig/accounts', methods=['GET'])
def api_ig_accounts():
    cst, xst = get_ig_tokens()
    headers = _ig_headers(cst, xst, version="1", content_type=False)
    resp = requests.get(f"{_get_base_url()}/accounts", headers=headers, timeout=10)
    if resp.status_code == 200:
        return jsonify({"success": True, "accounts": resp.json()})
    return jsonify({"success": False, "error": resp.text}), resp.status_code

@ig_api.route('/api/ig/funds', methods=['GET'])
def api_ig_funds():
    cst, xst = get_ig_tokens()
    headers = _ig_headers(cst, xst, version="1", content_type=False)
    resp = requests.get(f"{_get_base_url()}/accounts", headers=headers, timeout=10)
    if resp.status_code == 200:
        accounts = resp.json().get('accounts', [])
        # Return first account or match by ID
        target_id = request.args.get('account_id', request.ig_credentials.get('account_id'))
        for acc in accounts:
            if not target_id or acc.get('accountId') == target_id:
                bal = acc.get('balance', {})
                return jsonify({
                    "success": True,
                    "funds": {
                        "accountId": acc.get('accountId'),
                        "accountName": acc.get('accountName', ''),
                        "accountType": acc.get('accountType', ''),
                        "balance": bal.get('balance', 0),
                        "deposit": bal.get('deposit', 0),
                        "profitLoss": bal.get('profitLoss', 0),
                        "available": bal.get('available', 0),
                        "currency": acc.get('currency', 'USD'),
                        "status": acc.get('status', ''),
                    }
                })
        return jsonify({"success": False, "error": "Account not found"}), 404
    return jsonify({"success": False, "error": resp.text}), resp.status_code

@ig_api.route('/api/ig/balance', methods=['GET'])
def ig_balance():
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="1", content_type=False)
        resp = requests.get(f"{_get_base_url()}/accounts", headers=headers, timeout=10)
        if resp.status_code == 200:
            accounts = resp.json().get('accounts', [])
            target_id = request.args.get('account_id', request.ig_credentials.get('account_id'))
            for acc in accounts:
                if not target_id or acc.get('accountId') == target_id:
                    bal = acc.get('balance', {})
                    return jsonify({
                        'success': True,
                        'balance': bal.get('balance', 0),
                        'available': bal.get('available', 0),
                        'deposit': bal.get('deposit', 0),
                        'profitLoss': bal.get('profitLoss', 0),
                        'currency': acc.get('currency', 'USD'),
                    })
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        return jsonify({'success': False, 'error': resp.text}), resp.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== POSITIONS ====================

@ig_api.route('/api/ig/positions', methods=['GET'])
def api_ig_positions():
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)
        resp = requests.get(f"{_get_base_url()}/positions", headers=headers, timeout=10)
        if resp.status_code == 200:
            raw = resp.json().get('positions', [])
            positions = []
            for p in raw:
                pos = p.get('position', {})
                mkt = p.get('market', {})
                positions.append({
                    'dealId': pos.get('dealId', ''),
                    'dealReference': pos.get('dealReference', ''),
                    'epic': mkt.get('epic', ''),
                    'instrumentName': mkt.get('instrumentName', ''),
                    'direction': pos.get('direction', ''),
                    'size': float(pos.get('size', 0)),
                    'level': float(pos.get('level', 0)),
                    'currency': pos.get('currency', ''),
                    'contractSize': float(pos.get('contractSize', 0)),
                    'controlledRisk': pos.get('controlledRisk', False),
                    'stopLevel': pos.get('stopLevel'),
                    'limitLevel': pos.get('limitLevel'),
                    'profitLoss': float(mkt.get('bid', 0)) - float(pos.get('level', 0)) if pos.get('direction') == 'BUY'
                        else float(pos.get('level', 0)) - float(mkt.get('offer', 0)),
                    'bid': float(mkt.get('bid', 0)),
                    'offer': float(mkt.get('offer', 0)),
                    'high': float(mkt.get('high', 0)),
                    'low': float(mkt.get('low', 0)),
                    'percentageChange': float(mkt.get('percentageChange', 0)),
                    'createdDateUTC': pos.get('createdDateUTC', ''),
                })
            return jsonify({"success": True, "positions": positions})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG positions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== CLOSE POSITION ====================

@ig_api.route('/api/ig/close-position', methods=['POST'])
def api_ig_close_position():
    """Close a specific IG position by dealId.
    Per IG API: DELETE /positions/otc with _method=DELETE header or body."""
    try:
        data = request.json or {}
        deal_id = data.get('dealId')
        if not deal_id:
            return jsonify({"success": False, "error": "dealId is required"}), 400

        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="1")
        headers["_method"] = "DELETE"

        payload = {
            "dealId": deal_id,
            "direction": data.get('direction', 'SELL'),  # opposite of position direction
            "size": data.get('size'),
            "orderType": "MARKET",
            "timeInForce": "EXECUTE_AND_ELIMINATE",
        }

        resp = requests.post(f"{_get_base_url()}/positions/otc", headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            result = resp.json()
            deal_ref = result.get('dealReference', '')
            # Confirm the deal
            confirm = _confirm_deal(cst, xst, deal_ref)
            return jsonify({
                "success": True,
                "dealReference": deal_ref,
                "confirmation": confirm,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG close position error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/close-all-positions', methods=['POST'])
def api_ig_close_all_positions():
    """Close all open IG positions."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)
        resp = requests.get(f"{_get_base_url()}/positions", headers=headers, timeout=10)

        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        raw = resp.json().get('positions', [])
        results = []
        for p in raw:
            pos = p.get('position', {})
            deal_id = pos.get('dealId')
            direction = pos.get('direction', '')
            size = float(pos.get('size', 0))
            close_dir = 'SELL' if direction == 'BUY' else 'BUY'

            close_headers = _ig_headers(cst, xst, version="1")
            close_headers["_method"] = "DELETE"
            payload = {
                "dealId": deal_id,
                "direction": close_dir,
                "size": size,
                "orderType": "MARKET",
                "timeInForce": "EXECUTE_AND_ELIMINATE",
            }
            close_resp = requests.post(f"{_get_base_url()}/positions/otc", headers=close_headers, json=payload, timeout=15)
            if close_resp.status_code == 200:
                deal_ref = close_resp.json().get('dealReference', '')
                confirm = _confirm_deal(cst, xst, deal_ref)
                results.append({"dealId": deal_id, "success": True, "confirmation": confirm})
            else:
                results.append({"dealId": deal_id, "success": False, "error": close_resp.text})

        closed_count = sum(1 for r in results if r['success'])
        return jsonify({
            "success": True,
            "closed": closed_count,
            "total": len(raw),
            "results": results,
        })
    except Exception as e:
        logger.error(f"IG close all error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== PLACE ORDER ====================

@ig_api.route('/api/ig/place-order', methods=['POST'])
def api_ig_place_order():
    try:
        cst, xst = get_ig_tokens()
        data = request.json or {}
        headers = _ig_headers(cst, xst, version="2")

        order = {
            "epic": data.get("epic"),
            "expiry": data.get("expiry", "-"),
            "direction": data.get("direction"),
            "size": data.get("size"),
            "orderType": data.get("orderType", "MARKET"),
            "timeInForce": data.get("timeInForce", "FILL_OR_KILL"),
            "guaranteedStop": data.get("guaranteedStop", False),
            "forceOpen": data.get("forceOpen", True),
            "currencyCode": data.get("currencyCode", "USD"),
        }
        # Optional stop/limit
        if data.get("stopDistance"):
            order["stopDistance"] = data["stopDistance"]
        if data.get("limitDistance"):
            order["limitDistance"] = data["limitDistance"]
        if data.get("stopLevel"):
            order["stopLevel"] = data["stopLevel"]
        if data.get("limitLevel"):
            order["limitLevel"] = data["limitLevel"]

        resp = requests.post(f"{_get_base_url()}/positions/otc", headers=headers, json=order, timeout=15)

        if resp.status_code == 200:
            result = resp.json()
            deal_ref = result.get('dealReference', '')
            confirm = _confirm_deal(cst, xst, deal_ref)
            return jsonify({
                "success": True,
                "dealReference": deal_ref,
                "confirmation": confirm,
            })
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG place order error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== TRADE HISTORY / TRANSACTIONS ====================

@ig_api.route('/api/ig/transactions', methods=['GET'])
def api_ig_transactions():
    """Get transaction history. Query params: type (ALL/TRADE/DEPOSIT), from, to, pageSize"""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)

        params = {}
        tx_type = request.args.get('type', 'ALL')
        params['type'] = tx_type
        if request.args.get('from'):
            params['from'] = request.args['from']
        if request.args.get('to'):
            params['to'] = request.args['to']
        page_size = request.args.get('pageSize', '50')
        params['pageSize'] = page_size

        resp = requests.get(f"{_get_base_url()}/history/transactions", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            transactions = data.get('transactions', [])
            formatted = []
            for t in transactions:
                formatted.append({
                    'reference': t.get('reference', ''),
                    'instrumentName': t.get('instrumentName', ''),
                    'type': t.get('transactionType', ''),
                    'date': t.get('dateUtc', t.get('date', '')),
                    'openDateUtc': t.get('openDateUtc', ''),
                    'closeDateUtc': t.get('closeDateUtc', ''),
                    'openLevel': t.get('openLevel', ''),
                    'closeLevel': t.get('closeLevel', ''),
                    'size': t.get('size', ''),
                    'profitAndLoss': t.get('profitAndLoss', ''),
                    'currency': t.get('currency', ''),
                    'cashTransaction': t.get('cashTransaction', False),
                })
            return jsonify({"success": True, "transactions": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG transactions error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/activity', methods=['GET'])
def api_ig_activity():
    """Get recent account activity (orders, amendments, etc.)."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="3", content_type=False)

        params = {}
        if request.args.get('from'):
            params['from'] = request.args['from']
        if request.args.get('to'):
            params['to'] = request.args['to']
        page_size = request.args.get('pageSize', '50')
        params['pageSize'] = page_size

        resp = requests.get(f"{_get_base_url()}/history/activity", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return jsonify({"success": True, "activities": resp.json().get('activities', [])})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG activity error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== MARKET SEARCH & WATCHLISTS ====================

@ig_api.route('/api/ig/markets/search', methods=['GET'])
def api_ig_market_search():
    """Search for markets by keyword. Query param: searchTerm"""
    try:
        search_term = request.args.get('searchTerm', '')
        if not search_term:
            return jsonify({"success": False, "error": "searchTerm is required"}), 400

        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="1", content_type=False)
        resp = requests.get(f"{_get_base_url()}/markets?searchTerm={search_term}", headers=headers, timeout=10)
        if resp.status_code == 200:
            markets = resp.json().get('markets', [])
            formatted = []
            for m in markets:
                formatted.append({
                    'epic': m.get('epic', ''),
                    'instrumentName': m.get('instrumentName', ''),
                    'instrumentType': m.get('instrumentType', ''),
                    'expiry': m.get('expiry', ''),
                    'bid': m.get('bid'),
                    'offer': m.get('offer'),
                    'high': m.get('high'),
                    'low': m.get('low'),
                    'percentageChange': m.get('netChange'),
                    'scalingFactor': m.get('scalingFactor'),
                })
            return jsonify({"success": True, "markets": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG market search error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/markets/<epic>', methods=['GET'])
def api_ig_market_detail(epic):
    """Get detailed market data for a specific epic."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="3", content_type=False)
        resp = requests.get(f"{_get_base_url()}/markets/{epic}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "market": resp.json()})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        logger.error(f"IG market detail error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/watchlists', methods=['GET'])
def api_ig_watchlists():
    """Get all watchlists."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="1", content_type=False)
        resp = requests.get(f"{_get_base_url()}/watchlists", headers=headers, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "watchlists": resp.json().get('watchlists', [])})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/watchlists/<watchlist_id>', methods=['GET'])
def api_ig_watchlist_markets(watchlist_id):
    """Get markets in a specific watchlist."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="1", content_type=False)
        resp = requests.get(f"{_get_base_url()}/watchlists/{watchlist_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "markets": resp.json().get('markets', [])})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== DEAL CONFIRMATION ====================

@ig_api.route('/api/ig/confirms/<deal_reference>', methods=['GET'])
def api_ig_confirm(deal_reference):
    """Get deal confirmation for a deal reference."""
    try:
        cst, xst = get_ig_tokens()
        confirm = _confirm_deal(cst, xst, deal_reference)
        if confirm:
            return jsonify({"success": True, "confirmation": confirm})
        return jsonify({"success": False, "error": "Confirmation not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def _confirm_deal(cst, xst, deal_reference):
    """Fetch deal confirmation from IG API."""
    if not deal_reference:
        return None
    try:
        headers = _ig_headers(cst, xst, version="1", content_type=False)
        resp = requests.get(f"{_get_base_url()}/confirms/{deal_reference}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"IG confirm deal error: {e}")
    return None

# ==================== WORKING ORDERS ====================

@ig_api.route('/api/ig/working-orders', methods=['GET'])
def api_ig_working_orders():
    """Get all working orders."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)
        resp = requests.get(f"{_get_base_url()}/workingorders", headers=headers, timeout=10)
        if resp.status_code == 200:
            orders = resp.json().get('workingOrders', [])
            formatted = []
            for o in orders:
                wo = o.get('workingOrderData', {})
                mkt = o.get('marketData', {})
                formatted.append({
                    'dealId': wo.get('dealId', ''),
                    'epic': mkt.get('epic', ''),
                    'instrumentName': mkt.get('instrumentName', ''),
                    'direction': wo.get('direction', ''),
                    'size': wo.get('size', 0),
                    'level': wo.get('level', 0),
                    'type': wo.get('type', ''),
                    'timeInForce': wo.get('timeInForce', ''),
                    'goodTillDate': wo.get('goodTillDate', ''),
                    'createdDateUTC': wo.get('createdDateUTC', ''),
                    'bid': mkt.get('bid'),
                    'offer': mkt.get('offer'),
                })
            return jsonify({"success": True, "workingOrders": formatted})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/working-orders', methods=['POST'])
def api_ig_create_working_order():
    """Create a new working order (limit/stop)."""
    try:
        cst, xst = get_ig_tokens()
        data = request.json or {}
        headers = _ig_headers(cst, xst, version="2")

        order = {
            "epic": data.get("epic"),
            "expiry": data.get("expiry", "-"),
            "direction": data.get("direction"),
            "size": data.get("size"),
            "level": data.get("level"),
            "type": data.get("type", "LIMIT"),  # LIMIT or STOP
            "timeInForce": data.get("timeInForce", "GOOD_TILL_CANCELLED"),
            "currencyCode": data.get("currencyCode", "USD"),
            "forceOpen": data.get("forceOpen", True),
            "guaranteedStop": data.get("guaranteedStop", False),
        }
        if data.get("stopDistance"):
            order["stopDistance"] = data["stopDistance"]
        if data.get("limitDistance"):
            order["limitDistance"] = data["limitDistance"]
        if data.get("goodTillDate"):
            order["goodTillDate"] = data["goodTillDate"]

        resp = requests.post(f"{_get_base_url()}/workingorders/otc", headers=headers, json=order, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            deal_ref = result.get('dealReference', '')
            confirm = _confirm_deal(cst, xst, deal_ref)
            return jsonify({"success": True, "dealReference": deal_ref, "confirmation": confirm})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@ig_api.route('/api/ig/working-orders/<deal_id>', methods=['DELETE'])
def api_ig_delete_working_order(deal_id):
    """Delete a working order."""
    try:
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)
        resp = requests.delete(f"{_get_base_url()}/workingorders/otc/{deal_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return jsonify({"success": True, "dealReference": resp.json().get('dealReference', '')})
        return jsonify({"success": False, "error": resp.text}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== WITHDRAW (placeholder) ====================

@ig_api.route('/api/ig/withdraw', methods=['POST'])
def ig_withdraw():
    data = request.json
    amount = data.get('amount')
    return jsonify({'success': False, 'error': 'Direct withdrawal via IG API is not supported. Please process manually.'}), 400


# ==================== IG PROFIT MONITOR & AUTO-CLOSE ====================

@ig_api.route('/api/ig/profit-check', methods=['POST'])
def api_ig_profit_check():
    """
    Check all open IG positions against a profit target.
    If total unrealized P&L >= target, auto-close ALL positions and create
    a withdrawal-ready notification so the user can withdraw on IG's website.
    
    Body: { "target_profit": 100.0, "user_id": "...", "auto_close": true }
    """
    try:
        data = request.json or {}
        target_profit = float(data.get('target_profit', 0))
        user_id = request.user_id
        auto_close = data.get('auto_close', True)

        if target_profit <= 0:
            return jsonify({"success": False, "error": "target_profit must be > 0"}), 400

        # 1. Fetch open positions
        cst, xst = get_ig_tokens()
        headers = _ig_headers(cst, xst, version="2", content_type=False)
        resp = requests.get(f"{_get_base_url()}/positions", headers=headers, timeout=10)

        if resp.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch positions"}), 500

        raw = resp.json().get('positions', [])
        total_pnl = 0.0
        position_details = []

        for p in raw:
            pos = p.get('position', {})
            mkt = p.get('market', {})
            direction = pos.get('direction', '')
            level = float(pos.get('level', 0))
            size = float(pos.get('size', 0))
            bid = float(mkt.get('bid', 0))
            offer = float(mkt.get('offer', 0))

            if direction == 'BUY':
                pnl = (bid - level) * size
            else:
                pnl = (level - offer) * size

            total_pnl += pnl
            position_details.append({
                'dealId': pos.get('dealId', ''),
                'epic': mkt.get('epic', ''),
                'instrumentName': mkt.get('instrumentName', ''),
                'direction': direction,
                'size': size,
                'openLevel': level,
                'currentPrice': bid if direction == 'BUY' else offer,
                'pnl': round(pnl, 2),
            })

        target_reached = total_pnl >= target_profit

        close_results = []
        if target_reached and auto_close and len(raw) > 0:
            # 2. Auto-close all positions to realize the profit
            for p in raw:
                pos = p.get('position', {})
                deal_id = pos.get('dealId')
                direction = pos.get('direction', '')
                size = float(pos.get('size', 0))
                close_dir = 'SELL' if direction == 'BUY' else 'BUY'

                close_headers = _ig_headers(cst, xst, version="1")
                close_headers["_method"] = "DELETE"
                payload = {
                    "dealId": deal_id,
                    "direction": close_dir,
                    "size": size,
                    "orderType": "MARKET",
                    "timeInForce": "EXECUTE_AND_ELIMINATE",
                }
                close_resp = requests.post(
                    f"{_get_base_url()}/positions/otc",
                    headers=close_headers, json=payload, timeout=15
                )
                if close_resp.status_code == 200:
                    deal_ref = close_resp.json().get('dealReference', '')
                    confirm = _confirm_deal(cst, xst, deal_ref)
                    close_results.append({"dealId": deal_id, "success": True, "confirmation": confirm})
                else:
                    close_results.append({"dealId": deal_id, "success": False, "error": close_resp.text})

            closed_count = sum(1 for r in close_results if r['success'])
            logger.info(
                f"IG profit target ${target_profit} reached (P&L: ${total_pnl:.2f}). "
                f"Closed {closed_count}/{len(raw)} positions for user {user_id}."
            )

        # 3. Fetch updated balance after closes
        balance_info = {}
        if target_reached:
            bal_headers = _ig_headers(cst, xst, version="1", content_type=False)
            bal_resp = requests.get(f"{_get_base_url()}/accounts", headers=bal_headers, timeout=10)
            if bal_resp.status_code == 200:
                accounts = bal_resp.json().get('accounts', [])
                if accounts:
                    bal = accounts[0].get('balance', {})
                    balance_info = {
                        'balance': bal.get('balance', 0),
                        'available': bal.get('available', 0),
                        'deposit': bal.get('deposit', 0),
                        'profitLoss': bal.get('profitLoss', 0),
                    }

            # 4. Distribute IG commissions on realized profit
            if total_pnl > 0 and user_id:
                try:
                    from multi_broker_backend_updated import distribute_trade_commissions
                    distribute_trade_commissions(
                        bot_id=f'ig_profit_{user_id}',
                        user_id=user_id,
                        profit_amount=total_pnl,
                        source='IG'
                    )
                    logger.info(f"IG commission distributed for user {user_id}: ${total_pnl:.2f}")
                except Exception as comm_err:
                    logger.error(f"IG commission distribution error: {comm_err}")

        return jsonify({
            "success": True,
            "target_profit": target_profit,
            "current_pnl": round(total_pnl, 2),
            "target_reached": target_reached,
            "positions_checked": len(raw),
            "positions": position_details,
            "positions_closed": len(close_results),
            "close_results": close_results,
            "balance_after": balance_info,
            "message": (
                f"Profit target ${target_profit:.2f} reached! "
                f"P&L: ${total_pnl:.2f}. Positions closed. "
                f"Please withdraw funds from IG's website or app."
            ) if target_reached else (
                f"P&L ${total_pnl:.2f} / target ${target_profit:.2f} — not yet reached."
            ),
        })

    except Exception as e:
        logger.error(f"IG profit check error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ig_api.route('/api/ig/withdrawal-notifications', methods=['GET'])
def api_ig_withdrawal_notifications():
    """Get all IG withdrawal-ready notifications for a user."""
    try:
        import sqlite3
        user_id = request.user_id

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM ig_withdrawal_notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return jsonify({"success": True, "notifications": rows})
    except Exception as e:
        logger.error(f"IG withdrawal notifications error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ig_api.route('/api/ig/withdrawal-notifications', methods=['POST'])
def api_ig_create_withdrawal_notification():
    """Create a withdrawal-ready notification after profits are realized."""
    try:
        import sqlite3, uuid
        data = request.json or {}
        user_id = request.user_id
        realized_profit = float(data.get('realized_profit', 0))
        positions_closed = int(data.get('positions_closed', 0))
        balance_available = float(data.get('balance_available', 0))

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        notif_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO ig_withdrawal_notifications
            (notification_id, user_id, realized_profit, positions_closed,
             balance_available, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        ''', (notif_id, user_id, realized_profit, positions_closed,
              balance_available, created_at))

        conn.commit()
        conn.close()

        logger.info(
            f"IG withdrawal notification created: {notif_id} | "
            f"User: {user_id} | Profit: ${realized_profit:.2f}"
        )

        return jsonify({
            "success": True,
            "notification_id": notif_id,
            "message": "Withdrawal notification created. Please withdraw from IG platform.",
        })
    except Exception as e:
        logger.error(f"IG create withdrawal notification error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ig_api.route('/api/ig/withdrawal-notifications/<notif_id>/mark-done', methods=['POST'])
def api_ig_mark_withdrawal_done(notif_id):
    """Mark a withdrawal notification as completed (user confirms they withdrew on IG)."""
    try:
        import sqlite3
        user_id = request.user_id
        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE ig_withdrawal_notifications
            SET status = 'completed', completed_at = ?
            WHERE notification_id = ? AND user_id = ?
        ''', (datetime.now().isoformat(), notif_id, user_id))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Notification not found for this user"}), 404

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Withdrawal marked as completed."})
    except Exception as e:
        logger.error(f"IG mark withdrawal done error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
