import os
import logging
from flask import Blueprint, jsonify, request
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

unified_broker_api = Blueprint('unified_broker_api', __name__)

# Backend base URL for internal calls
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:9000')


def _safe_get(url, timeout=10):
    """Safely make a GET request, returning JSON or error."""
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Request to {url} failed: {e}")
    return None


def _safe_post(url, json_data=None, timeout=15):
    """Safely make a POST request, returning JSON or error."""
    try:
        resp = requests.post(url, json=json_data or {}, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"POST to {url} failed: {e}")
    return None


# ==================== UNIFIED PORTFOLIO OVERVIEW ====================

@unified_broker_api.route('/api/unified/portfolio', methods=['GET'])
def api_unified_portfolio():
    """
    Get aggregated portfolio across ALL connected brokers.
    Returns combined balances, positions, P&L for IG, OANDA, FXCM, Binance.
    """
    try:
        brokers = {}
        total_balance = 0.0
        total_available = 0.0
        total_pnl = 0.0
        total_positions = 0
        errors = []

        # --- IG ---
        ig_bal = _safe_get(f"{BACKEND_URL}/api/ig/funds")
        if ig_bal and ig_bal.get('success'):
            funds = ig_bal.get('funds', {})
            bal = float(funds.get('balance', 0))
            avail = float(funds.get('available', 0))
            pnl = float(funds.get('profitLoss', 0))
            brokers['IG'] = {
                'connected': True,
                'balance': bal,
                'available': avail,
                'pnl': pnl,
                'currency': funds.get('currency', 'USD'),
                'positions': 0,
            }
            total_balance += bal
            total_available += avail
            total_pnl += pnl
        else:
            brokers['IG'] = {'connected': False, 'error': 'Not connected'}

        # --- OANDA ---
        oanda_bal = _safe_get(f"{BACKEND_URL}/api/oanda/balance")
        if oanda_bal and oanda_bal.get('success'):
            bal = float(oanda_bal.get('balance', 0))
            avail = float(oanda_bal.get('available', 0))
            pnl = float(oanda_bal.get('unrealizedPL', 0))
            brokers['OANDA'] = {
                'connected': True,
                'balance': bal,
                'available': avail,
                'pnl': pnl,
                'currency': oanda_bal.get('currency', 'USD'),
                'positions': oanda_bal.get('openTradeCount', 0),
            }
            total_balance += bal
            total_available += avail
            total_pnl += pnl
            total_positions += oanda_bal.get('openTradeCount', 0)
        else:
            brokers['OANDA'] = {'connected': False, 'error': 'Not connected'}

        # --- FXCM ---
        fxcm_bal = _safe_get(f"{BACKEND_URL}/api/fxcm/balance")
        if fxcm_bal and fxcm_bal.get('success'):
            bal = float(fxcm_bal.get('balance', 0))
            avail = float(fxcm_bal.get('available', 0))
            pnl = float(fxcm_bal.get('unrealizedPL', 0))
            brokers['FXCM'] = {
                'connected': True,
                'balance': bal,
                'available': avail,
                'pnl': pnl,
                'currency': fxcm_bal.get('currency', 'USD'),
                'positions': 0,
            }
            total_balance += bal
            total_available += avail
            total_pnl += pnl
        else:
            brokers['FXCM'] = {'connected': False, 'error': 'Not connected'}

        # --- Binance ---
        binance_bal = _safe_get(f"{BACKEND_URL}/api/binance/balance")
        if binance_bal and binance_bal.get('success'):
            bal = float(binance_bal.get('balance', 0))
            avail = float(binance_bal.get('available', 0))
            brokers['Binance'] = {
                'connected': True,
                'balance': bal,
                'available': avail,
                'pnl': 0,
                'currency': 'USDT',
                'positions': 0,
                'allBalances': binance_bal.get('allBalances', []),
            }
            total_balance += bal
            total_available += avail
        else:
            brokers['Binance'] = {'connected': False, 'error': 'Not connected'}

        # Count positions from IG and FXCM
        ig_pos = _safe_get(f"{BACKEND_URL}/api/ig/positions")
        if ig_pos and ig_pos.get('success'):
            count = len(ig_pos.get('positions', []))
            brokers['IG']['positions'] = count
            total_positions += count

        fxcm_pos = _safe_get(f"{BACKEND_URL}/api/fxcm/positions")
        if fxcm_pos and fxcm_pos.get('success'):
            count = len(fxcm_pos.get('positions', []))
            brokers['FXCM']['positions'] = count
            total_positions += count

        # Binance futures positions
        binance_fpos = _safe_get(f"{BACKEND_URL}/api/binance/futures-positions")
        if binance_fpos and binance_fpos.get('success'):
            positions = binance_fpos.get('positions', [])
            count = len(positions)
            pnl = sum(float(p.get('unrealizedPL', 0)) for p in positions)
            brokers['Binance']['positions'] = count
            brokers['Binance']['pnl'] = round(pnl, 2)
            total_positions += count
            total_pnl += pnl

        connected_count = sum(1 for b in brokers.values() if b.get('connected'))

        return jsonify({
            'success': True,
            'portfolio': {
                'total_balance': round(total_balance, 2),
                'total_available': round(total_available, 2),
                'total_pnl': round(total_pnl, 2),
                'total_positions': total_positions,
                'connected_brokers': connected_count,
                'total_brokers': len(brokers),
            },
            'brokers': brokers,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Unified portfolio error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== UNIFIED POSITIONS ====================

@unified_broker_api.route('/api/unified/positions', methods=['GET'])
def api_unified_positions():
    """Get all open positions across all brokers."""
    try:
        all_positions = []

        # IG positions
        ig_data = _safe_get(f"{BACKEND_URL}/api/ig/positions")
        if ig_data and ig_data.get('success'):
            for p in ig_data.get('positions', []):
                p['broker'] = 'IG'
                all_positions.append(p)

        # OANDA positions
        oanda_data = _safe_get(f"{BACKEND_URL}/api/oanda/positions")
        if oanda_data and oanda_data.get('success'):
            for p in oanda_data.get('positions', []):
                p['broker'] = 'OANDA'
                all_positions.append(p)

        # FXCM positions
        fxcm_data = _safe_get(f"{BACKEND_URL}/api/fxcm/positions")
        if fxcm_data and fxcm_data.get('success'):
            for p in fxcm_data.get('positions', []):
                p['broker'] = 'FXCM'
                all_positions.append(p)

        # Binance futures positions
        binance_data = _safe_get(f"{BACKEND_URL}/api/binance/futures-positions")
        if binance_data and binance_data.get('success'):
            for p in binance_data.get('positions', []):
                p['broker'] = 'Binance'
                all_positions.append(p)

        return jsonify({
            'success': True,
            'positions': all_positions,
            'total': len(all_positions),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Unified positions error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== UNIFIED CLOSE ALL ====================

@unified_broker_api.route('/api/unified/close-all', methods=['POST'])
def api_unified_close_all():
    """Emergency close all positions across ALL brokers."""
    try:
        results = {}

        ig_result = _safe_post(f"{BACKEND_URL}/api/ig/close-all-positions")
        results['IG'] = ig_result if ig_result else {'success': False, 'error': 'Not connected'}

        oanda_result = _safe_post(f"{BACKEND_URL}/api/oanda/close-all-positions")
        results['OANDA'] = oanda_result if oanda_result else {'success': False, 'error': 'Not connected'}

        fxcm_result = _safe_post(f"{BACKEND_URL}/api/fxcm/close-all-positions")
        results['FXCM'] = fxcm_result if fxcm_result else {'success': False, 'error': 'Not connected'}

        binance_result = _safe_post(f"{BACKEND_URL}/api/binance/close-all-positions")
        results['Binance'] = binance_result if binance_result else {'success': False, 'error': 'Not connected'}

        total_closed = sum(
            r.get('closed', 0) for r in results.values() if isinstance(r, dict)
        )

        return jsonify({
            'success': True,
            'total_closed': total_closed,
            'results': results,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Unified close all error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== CRYPTO BOT STRATEGIES ====================

@unified_broker_api.route('/api/crypto/strategies', methods=['GET'])
def api_crypto_strategies():
    """Get available crypto trading strategies for the bot."""
    strategies = [
        {
            'id': 'grid_trading',
            'name': 'Grid Trading',
            'description': 'Places buy/sell orders at preset intervals above and below price. Profits from sideways markets.',
            'risk': 'Medium',
            'market': 'Sideways/Range',
            'pairs': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            'params': {
                'grid_count': {'type': 'int', 'default': 10, 'min': 3, 'max': 50, 'label': 'Grid Lines'},
                'upper_price': {'type': 'float', 'default': 0, 'label': 'Upper Price (USDT)'},
                'lower_price': {'type': 'float', 'default': 0, 'label': 'Lower Price (USDT)'},
                'investment': {'type': 'float', 'default': 100, 'min': 10, 'label': 'Investment (USDT)'},
            },
        },
        {
            'id': 'dca_bot',
            'name': 'DCA (Dollar Cost Averaging)',
            'description': 'Buys at regular intervals regardless of price. Reduces impact of volatility over time.',
            'risk': 'Low',
            'market': 'Any/Long-term',
            'pairs': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
            'params': {
                'buy_amount': {'type': 'float', 'default': 10, 'min': 1, 'label': 'Buy Amount (USDT)'},
                'interval_hours': {'type': 'int', 'default': 24, 'min': 1, 'max': 720, 'label': 'Buy Interval (hours)'},
                'take_profit_pct': {'type': 'float', 'default': 5.0, 'min': 0.5, 'max': 100, 'label': 'Take Profit (%)'},
            },
        },
        {
            'id': 'momentum_scalper',
            'name': 'Momentum Scalper',
            'description': 'Detects strong price momentum and rides the trend with quick entries/exits.',
            'risk': 'High',
            'market': 'Trending/Volatile',
            'pairs': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'DOGEUSDT'],
            'params': {
                'rsi_period': {'type': 'int', 'default': 14, 'min': 5, 'max': 50, 'label': 'RSI Period'},
                'rsi_overbought': {'type': 'int', 'default': 70, 'label': 'RSI Overbought'},
                'rsi_oversold': {'type': 'int', 'default': 30, 'label': 'RSI Oversold'},
                'position_size': {'type': 'float', 'default': 50, 'min': 5, 'label': 'Position Size (USDT)'},
                'stop_loss_pct': {'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 10, 'label': 'Stop Loss (%)'},
                'take_profit_pct': {'type': 'float', 'default': 3.0, 'min': 0.5, 'max': 20, 'label': 'Take Profit (%)'},
            },
        },
        {
            'id': 'mean_reversion',
            'name': 'Mean Reversion',
            'description': 'Buys when price drops significantly below average, sells when it returns. Works in stable markets.',
            'risk': 'Medium',
            'market': 'Stable/Range',
            'pairs': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
            'params': {
                'sma_period': {'type': 'int', 'default': 20, 'min': 5, 'max': 100, 'label': 'SMA Period'},
                'deviation_pct': {'type': 'float', 'default': 3.0, 'min': 1, 'max': 15, 'label': 'Deviation Trigger (%)'},
                'position_size': {'type': 'float', 'default': 50, 'min': 5, 'label': 'Position Size (USDT)'},
                'take_profit_pct': {'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 10, 'label': 'Take Profit (%)'},
            },
        },
        {
            'id': 'breakout_trader',
            'name': 'Breakout Trader',
            'description': 'Enters positions when price breaks key support/resistance levels with volume confirmation.',
            'risk': 'High',
            'market': 'Breakout/Volatile',
            'pairs': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'AVAXUSDT'],
            'params': {
                'lookback_period': {'type': 'int', 'default': 20, 'min': 5, 'max': 100, 'label': 'Lookback Candles'},
                'volume_multiplier': {'type': 'float', 'default': 1.5, 'min': 1.0, 'max': 5.0, 'label': 'Volume Multiplier'},
                'position_size': {'type': 'float', 'default': 50, 'min': 5, 'label': 'Position Size (USDT)'},
                'stop_loss_pct': {'type': 'float', 'default': 2.0, 'min': 0.5, 'max': 10, 'label': 'Stop Loss (%)'},
                'take_profit_pct': {'type': 'float', 'default': 5.0, 'min': 0.5, 'max': 20, 'label': 'Take Profit (%)'},
            },
        },
        {
            'id': 'arbitrage_spotter',
            'name': 'Arbitrage Spotter',
            'description': 'Monitors price differences between trading pairs for profitable arbitrage opportunities.',
            'risk': 'Low',
            'market': 'Any',
            'pairs': ['BTCUSDT', 'ETHBTC', 'ETHUSDT', 'BNBBTC', 'BNBUSDT'],
            'params': {
                'min_spread_pct': {'type': 'float', 'default': 0.3, 'min': 0.1, 'max': 5.0, 'label': 'Min Spread (%)'},
                'trade_amount': {'type': 'float', 'default': 100, 'min': 10, 'label': 'Trade Amount (USDT)'},
                'scan_interval_sec': {'type': 'int', 'default': 5, 'min': 1, 'max': 60, 'label': 'Scan Interval (sec)'},
            },
        },
    ]

    return jsonify({'success': True, 'strategies': strategies})


# ==================== ACTIVATE CRYPTO STRATEGY ====================

@unified_broker_api.route('/api/crypto/strategies/activate', methods=['POST'])
def api_activate_crypto_strategy():
    """Activate a crypto trading strategy for a user's bot."""
    try:
        import sqlite3, uuid
        data = request.json or {}
        user_id = data.get('user_id', '')
        strategy_id = data.get('strategy_id', '')
        pair = data.get('pair', 'BTCUSDT')
        params = data.get('params', {})

        if not user_id or not strategy_id:
            return jsonify({"success": False, "error": "user_id and strategy_id required"}), 400

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_bot_strategies (
                bot_strategy_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                pair TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at TEXT,
                total_trades INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0,
                updated_at TEXT
            )
        ''')

        bot_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        import json
        params_json = json.dumps(params)

        cursor.execute('''
            INSERT INTO crypto_bot_strategies
            (bot_strategy_id, user_id, strategy_id, pair, params, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
        ''', (bot_id, user_id, strategy_id, pair, params_json, now, now))

        conn.commit()
        conn.close()

        logger.info(f"Crypto strategy {strategy_id} activated for user {user_id} on {pair}")

        return jsonify({
            'success': True,
            'bot_strategy_id': bot_id,
            'message': f'Strategy {strategy_id} activated on {pair}',
        })
    except Exception as e:
        logger.error(f"Activate crypto strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== GET USER'S ACTIVE STRATEGIES ====================

@unified_broker_api.route('/api/crypto/strategies/active', methods=['GET'])
def api_active_crypto_strategies():
    """Get all active crypto strategies for a user."""
    try:
        import sqlite3, json
        user_id = request.args.get('user_id', '')
        if not user_id:
            return jsonify({"success": False, "error": "user_id required"}), 400

        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_bot_strategies (
                bot_strategy_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                pair TEXT NOT NULL,
                params TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at TEXT,
                total_trades INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            SELECT * FROM crypto_bot_strategies
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))

        rows = []
        for r in cursor.fetchall():
            row = dict(r)
            try:
                row['params'] = json.loads(row.get('params', '{}'))
            except Exception:
                row['params'] = {}
            rows.append(row)

        conn.close()
        return jsonify({'success': True, 'strategies': rows})
    except Exception as e:
        logger.error(f"Active crypto strategies error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== DEACTIVATE STRATEGY ====================

@unified_broker_api.route('/api/crypto/strategies/<bot_id>/deactivate', methods=['POST'])
def api_deactivate_crypto_strategy(bot_id):
    """Deactivate (stop) a crypto bot strategy."""
    try:
        import sqlite3
        db_path = os.getenv('DATABASE_PATH', 'zwesta_trading.db')
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE crypto_bot_strategies SET status = 'stopped', updated_at = ?
            WHERE bot_strategy_id = ?
        ''', (datetime.now().isoformat(), bot_id))

        conn.commit()
        updated = cursor.rowcount
        conn.close()

        if updated:
            return jsonify({'success': True, 'message': 'Strategy deactivated'})
        return jsonify({'success': False, 'error': 'Strategy not found'}), 404
    except Exception as e:
        logger.error(f"Deactivate crypto strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
