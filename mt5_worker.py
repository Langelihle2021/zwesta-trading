#!/usr/bin/env python3
"""
MT5 Worker Process - Zwesta Trading Platform
=============================================
Each worker runs as a SEPARATE PROCESS with its own MT5 terminal connection.
This solves MT5's single-login-per-process limitation for 100+ user scaling.

Architecture:
  Flask API (main process)
    ├── Worker 1 (this script) → MT5 Terminal → accounts group 1
    ├── Worker 2 (this script) → MT5 Terminal → accounts group 2
    └── Worker N (this script) → MT5 Terminal → accounts group N

Communication: SQLite tables (worker_pool, worker_bot_queue, worker_bot_assignments)
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import signal
import logging
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

# Configure logging for this worker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Worker %(worker_id)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Will be set after worker_id is known
logger = logging.getLogger(__name__)

# ==================== CONSTANTS ====================
DATABASE_PATH = os.environ.get('DATABASE_PATH', r'C:\backend\zwesta_trading.db')
HEARTBEAT_INTERVAL = 10  # seconds between heartbeats
COMMAND_POLL_INTERVAL = 2  # seconds between checking for new commands
TRADING_INTERVAL = 300  # default 5 min between trade cycles

# ==================== WORKER STATE ====================
worker_id = None
worker_running = True
active_bots = {}       # bot_id -> bot config dict
bot_threads = {}        # bot_id -> thread
bot_stop_flags = {}     # bot_id -> bool
running_bots = {}       # bot_id -> bool
mt5_connection = None   # This worker's MT5 connection (one per process)
mt5_module = None       # MetaTrader5 module reference


def get_db_connection():
    """Get database connection with WAL mode"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn


def update_heartbeat():
    """Update worker heartbeat in database"""
    while worker_running:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE worker_pool
                SET heartbeat_at = ?, bot_count = ?, status = 'running'
                WHERE worker_id = ?
            ''', (datetime.now().isoformat(), len(active_bots), worker_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Heartbeat update failed: {e}")
        time.sleep(HEARTBEAT_INTERVAL)


def register_worker():
    """Register this worker in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO worker_pool 
        (worker_id, pid, status, started_at, heartbeat_at, bot_count)
        VALUES (?, ?, 'running', ?, ?, 0)
    ''', (worker_id, os.getpid(), datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    logger.info(f"Worker {worker_id} registered (PID: {os.getpid()})")


def unregister_worker():
    """Mark worker as stopped in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE worker_pool
            SET status = 'stopped', stopped_at = ?, pid = NULL
            WHERE worker_id = ?
        ''', (datetime.now().isoformat(), worker_id))
        conn.commit()
        conn.close()
        logger.info(f"Worker {worker_id} unregistered")
    except Exception:
        pass


# ==================== MT5 CONNECTION ====================

def init_mt5(credentials: Dict) -> bool:
    """Initialize this worker's own MT5 connection.
    Each worker process gets its own MetaTrader5 module instance."""
    global mt5_connection, mt5_module
    
    try:
        import MetaTrader5 as mt5
        mt5_module = mt5
        
        account = int(credentials.get('account_number', 0))
        password = str(credentials.get('password', ''))
        server = str(credentials.get('server', ''))
        mt5_path = credentials.get('mt5_path', '')
        
        logger.info(f"Initializing MT5: account={account}, server={server}")
        
        init_kwargs = {
            'login': account,
            'password': password,
            'server': server,
        }
        if mt5_path and os.path.exists(mt5_path):
            init_kwargs['path'] = mt5_path
        
        if not mt5.initialize(**init_kwargs):
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            return False
        
        acct_info = mt5.account_info()
        if acct_info:
            logger.info(f"MT5 connected: Account {acct_info.login}, Balance ${acct_info.balance:.2f}, Server {acct_info.server}")
            mt5_connection = True
            return True
        else:
            logger.error("MT5 initialized but no account info")
            return False
            
    except ImportError:
        logger.error("MetaTrader5 module not installed")
        return False
    except Exception as e:
        logger.error(f"MT5 init exception: {e}")
        return False


def mt5_place_order(symbol: str, order_type: str, volume: float,
                    stop_loss: float = None, take_profit: float = None,
                    comment: str = '') -> Dict:
    """Place an order via MT5"""
    try:
        mt5 = mt5_module
        if not mt5:
            return {'success': False, 'error': 'MT5 not initialized'}
        
        # Verify symbol exists
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return {'success': False, 'error': f'Symbol {symbol} not found'}
        
        if not sym_info.visible:
            mt5.symbol_select(symbol, True)
            time.sleep(0.1)
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {'success': False, 'error': f'No tick data for {symbol}'}
        
        # Determine order type and price
        if order_type.upper() == 'BUY':
            mt5_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            mt5_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': mt5_type,
            'price': price,
            'deviation': 20,
            'magic': 234000,
            'comment': comment or 'ZwestaWorker',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        
        if stop_loss is not None:
            request['sl'] = stop_loss
        if take_profit is not None:
            request['tp'] = take_profit
        
        result = mt5.order_send(request)
        
        if result is None:
            return {'success': False, 'error': f'order_send returned None: {mt5.last_error()}'}
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Order placed: {order_type} {volume} {symbol} @ {price} | Deal: {result.deal}")
            return {
                'success': True,
                'orderId': result.order,
                'deal_id': result.deal,
                'symbol': symbol,
                'price': price,
                'volume': volume,
            }
        else:
            # Check for market pause conditions
            pause_retcodes = {10018, 10016, 10017, 10019}  # Market closed, disabled, etc.
            is_paused = result.retcode in pause_retcodes
            return {
                'success': False,
                'error': f'Order failed: retcode={result.retcode} ({result.comment})',
                'retcode': result.retcode,
                'is_paused': is_paused,
                'pause_type': 'MARKET_CLOSED' if is_paused else None,
            }
    except Exception as e:
        logger.error(f"Order exception: {e}")
        return {'success': False, 'error': str(e)}


def mt5_get_positions() -> list:
    """Get current open positions"""
    try:
        mt5 = mt5_module
        if not mt5:
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [{
            'ticket': p.ticket,
            'symbol': p.symbol,
            'type': 'BUY' if p.type == 0 else 'SELL',
            'volume': p.volume,
            'openPrice': p.price_open,
            'currentPrice': p.price_current,
            'profit': p.profit,
            'swap': p.swap,
            'comment': p.comment,
            'sl': p.sl,
            'tp': p.tp,
        } for p in positions]
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        return []


def mt5_get_account_info() -> Optional[Dict]:
    """Get MT5 account info"""
    try:
        mt5 = mt5_module
        if not mt5:
            return None
        info = mt5.account_info()
        if not info:
            return None
        return {
            'balance': info.balance,
            'equity': info.equity,
            'margin': info.margin,
            'marginFree': info.margin_free,
            'profit': info.profit,
            'accountNumber': info.login,
            'server': info.server,
            'leverage': info.leverage,
        }
    except Exception as e:
        logger.error(f"Account info error: {e}")
        return None


# ==================== SIGNAL / STRATEGY ENGINE ====================
# Simplified but complete signal generation for the worker process.
# Uses real MT5 market data (tick, OHLC bars) for signal evaluation.

def get_symbol_category(symbol: str) -> str:
    """Determine symbol category"""
    s = symbol.upper()
    if any(c in s for c in ['XAU', 'XAG', 'OIL', 'GAS', 'WHEAT']):
        return 'COMMODITIES'
    elif any(c in s for c in ['BTC', 'ETH', 'XRP', 'USDT']):
        return 'CRYPTO'
    elif any(c in s for c in ['SPX', 'NDX', 'TECH', 'DOW', 'USTEC']):
        return 'INDICES'
    elif any(p in s for p in ['EUR', 'GBP', 'USD', 'JPY', 'CHF', 'AUD', 'NZD', 'CAD']):
        return 'FOREX'
    return 'STOCKS'


MARKET_HOURS = {
    'FOREX':       {'open': (0, 0),  'close': (24, 0),  'days': [0,1,2,3,4]},
    'CRYPTO':      {'open': (0, 0),  'close': (24, 0),  'days': [0,1,2,3,4,5,6]},
    'INDICES':     {'open': (8, 0),  'close': (22, 0),  'days': [0,1,2,3,4]},
    'COMMODITIES': {'open': (1, 0),  'close': (23, 59), 'days': [0,1,2,3,4]},
    'STOCKS':      {'open': (13, 30),'close': (20, 0),  'days': [0,1,2,3,4]},
}


def is_market_open(symbol: str) -> tuple:
    """Check if market is open for symbol. Returns (is_open, reason)."""
    s = symbol.upper()
    # Crypto is 24/7
    if any(c in s for c in ['BTC', 'ETH', 'XRP', 'USDT']):
        return True, "Crypto 24/7"
    
    cat = get_symbol_category(symbol)
    hours = MARKET_HOURS.get(cat, MARKET_HOURS['FOREX'])
    now = datetime.utcnow()
    day = now.weekday()
    
    if day not in hours['days']:
        return False, f"Market closed (day {day} not trading day)"
    
    current_mins = now.hour * 60 + now.minute
    open_mins = hours['open'][0] * 60 + hours['open'][1]
    close_mins = hours['close'][0] * 60 + hours['close'][1]
    
    if open_mins <= current_mins < close_mins:
        return True, f"Market open ({cat})"
    return False, f"Market closed ({cat} hours: {hours['open'][0]:02d}:{hours['open'][1]:02d}-{hours['close'][0]:02d}:{hours['close'][1]:02d} UTC)"


def evaluate_signal(symbol: str) -> Dict:
    """
    Evaluate trade signal using real MT5 market data.
    Returns signal dict with direction, strength (0-100), and reason.
    """
    mt5 = mt5_module
    if not mt5:
        return {'direction': None, 'strength': 0, 'reason': 'MT5 not available'}
    
    try:
        # Get recent bars for analysis
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
        if rates is None or len(rates) < 20:
            return {'direction': None, 'strength': 0, 'reason': 'Insufficient data'}
        
        closes = [r[4] for r in rates]  # close prices
        
        # === Moving Average Crossover ===
        ma_fast = sum(closes[-8:]) / 8
        ma_slow = sum(closes[-20:]) / 20
        ma_signal = 'BUY' if ma_fast > ma_slow else 'SELL'
        ma_strength = min(80, abs(ma_fast - ma_slow) / ma_slow * 10000)
        
        # === RSI (14-period) ===
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 1
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        rsi_signal = 'BUY' if rsi < 35 else ('SELL' if rsi > 65 else None)
        rsi_strength = abs(50 - rsi) * 1.5  # 0-75 range
        
        # === Momentum (rate of change) ===
        roc = (closes[-1] - closes[-10]) / closes[-10] * 100 if closes[-10] != 0 else 0
        mom_signal = 'BUY' if roc > 0.05 else ('SELL' if roc < -0.05 else None)
        mom_strength = min(60, abs(roc) * 100)
        
        # === Combine signals ===
        buy_score = 0
        sell_score = 0
        
        if ma_signal == 'BUY':
            buy_score += ma_strength * 0.4
        else:
            sell_score += ma_strength * 0.4
        
        if rsi_signal == 'BUY':
            buy_score += rsi_strength * 0.35
        elif rsi_signal == 'SELL':
            sell_score += rsi_strength * 0.35
        
        if mom_signal == 'BUY':
            buy_score += mom_strength * 0.25
        elif mom_signal == 'SELL':
            sell_score += mom_strength * 0.25
        
        if buy_score > sell_score:
            direction = 'BUY'
            strength = min(100, buy_score)
        elif sell_score > buy_score:
            direction = 'SELL'
            strength = min(100, sell_score)
        else:
            direction = None
            strength = 0
        
        reasons = []
        if ma_signal:
            reasons.append(f"MA({ma_signal}:{ma_strength:.0f})")
        if rsi_signal:
            reasons.append(f"RSI({rsi:.0f})")
        if mom_signal:
            reasons.append(f"MOM({roc:.2f}%)")
        
        return {
            'direction': direction,
            'strength': strength,
            'reason': ' | '.join(reasons) if reasons else 'No signal',
            'rsi': rsi,
            'ma_fast': ma_fast,
            'ma_slow': ma_slow,
            'momentum': roc,
        }
        
    except Exception as e:
        logger.warning(f"Signal evaluation error for {symbol}: {e}")
        return {'direction': None, 'strength': 0, 'reason': str(e)}


# ==================== BOT TRADING LOOP ====================

def bot_trading_loop(bot_id: str, user_id: str, bot_config: Dict):
    """
    Trading loop for a single bot. Runs in a thread within this worker process.
    All bots in this worker share the same MT5 connection (same account).
    """
    try:
        logger.info(f"Bot {bot_id}: Trading loop STARTED (user {user_id})")
        
        symbols = bot_config.get('symbols', ['EURUSDm'])
        if isinstance(symbols, str):
            symbols = symbols.split(',')
        
        strategy = bot_config.get('strategy', 'Trend Following')
        risk_per_trade = float(bot_config.get('riskPerTrade', 2.0) or 2.0)
        trade_amount = bot_config.get('tradeAmount')
        profit_lock = float(bot_config.get('profitLock', 0) or 0)
        max_daily_loss = float(bot_config.get('maxDailyLoss', 0) or 0)
        signal_threshold = int(bot_config.get('signalThreshold', 50) or 50)
        trading_interval = int(bot_config.get('tradingInterval', TRADING_INTERVAL) or TRADING_INTERVAL)
        
        trade_cycle = 0
        total_profit = float(bot_config.get('totalProfit', 0) or 0)
        total_trades = int(bot_config.get('totalTrades', 0) or 0)
        winning_trades = int(bot_config.get('winningTrades', 0) or 0)
        daily_profits = bot_config.get('dailyProfits', {})
        if isinstance(daily_profits, str):
            try:
                daily_profits = json.loads(daily_profits)
            except Exception:
                daily_profits = {}
        peak_profit = float(bot_config.get('peakProfit', 0) or 0)
        max_drawdown = float(bot_config.get('maxDrawdown', 0) or 0)
        
        running_bots[bot_id] = True
        bot_stop_flags[bot_id] = False
        
        while not bot_stop_flags.get(bot_id, False):
            try:
                trade_cycle += 1
                logger.info(f"Bot {bot_id}: Cycle #{trade_cycle}")
                
                # Check market hours
                symbol_to_check = symbols[0] if symbols else 'EURUSDm'
                is_open, status_msg = is_market_open(symbol_to_check)
                if not is_open:
                    logger.info(f"Bot {bot_id}: {status_msg} - waiting {trading_interval}s")
                    time.sleep(trading_interval)
                    continue
                
                # Check daily profit lock / loss limit
                today = datetime.now().strftime('%Y-%m-%d')
                daily_profit = daily_profits.get(today, 0.0)
                
                if profit_lock > 0 and daily_profit >= profit_lock:
                    logger.info(f"Bot {bot_id}: Daily profit lock ${daily_profit:.2f} >= ${profit_lock:.2f} - PAUSED")
                    _update_bot_status(bot_id, 'PAUSED', f'Profit lock: ${daily_profit:.2f}')
                    time.sleep(trading_interval)
                    continue
                
                if max_daily_loss > 0 and daily_profit < -max_daily_loss:
                    logger.info(f"Bot {bot_id}: Daily loss ${abs(daily_profit):.2f} >= ${max_daily_loss:.2f} - PAUSED")
                    _update_bot_status(bot_id, 'PAUSED', f'Loss limit: ${abs(daily_profit):.2f}')
                    time.sleep(trading_interval)
                    continue
                
                # Verify MT5 is still connected
                mt5 = mt5_module
                if mt5:
                    acct = mt5.account_info()
                    if not acct:
                        logger.warning(f"Bot {bot_id}: MT5 connection lost - reinitializing")
                        if not mt5.initialize():
                            logger.error(f"Bot {bot_id}: MT5 reconnect failed - retry next cycle")
                            time.sleep(trading_interval + random.uniform(2, 15))
                            continue
                
                trades_placed = 0
                
                for symbol in symbols[:3]:
                    if bot_stop_flags.get(bot_id, False):
                        break
                    
                    try:
                        # Evaluate signal
                        signal = evaluate_signal(symbol)
                        
                        if signal['direction'] is None or signal['strength'] < signal_threshold:
                            logger.debug(f"Bot {bot_id}: {symbol} signal too weak ({signal['strength']:.0f}/{signal_threshold})")
                            continue
                        
                        logger.info(f"Bot {bot_id}: {signal['direction']} signal on {symbol} "
                                    f"(strength: {signal['strength']:.0f}/100) | {signal['reason']}")
                        
                        # Calculate position size
                        if trade_amount:
                            volume = max(0.01, round(trade_amount / 100000, 2))
                        else:
                            # Risk-based sizing
                            acct_info = mt5_get_account_info()
                            balance = acct_info['balance'] if acct_info else 10000.0
                            risk_amount = balance * (risk_per_trade / 100.0)
                            volume = max(0.01, round(risk_amount / 100000, 2))
                        
                        # Check for existing positions on this symbol
                        positions = mt5_get_positions()
                        bot_comment = f'ZBot{bot_id[-8:]}'
                        has_open = any(
                            p.get('symbol') == symbol and bot_comment in (p.get('comment', '') or '')
                            for p in positions
                        )
                        if has_open:
                            logger.info(f"Bot {bot_id}: Already has position on {symbol} - skipping")
                            continue
                        
                        # Calculate SL/TP
                        sl_price, tp_price = _calculate_sl_tp(symbol, signal['direction'])
                        
                        # Place order
                        result = mt5_place_order(
                            symbol=symbol,
                            order_type=signal['direction'],
                            volume=volume,
                            stop_loss=sl_price,
                            take_profit=tp_price,
                            comment=bot_comment,
                        )
                        
                        if result.get('success'):
                            trades_placed += 1
                            
                            # Find the position we just opened
                            trade_profit = 0.0
                            positions_after = mt5_get_positions()
                            for pos in positions_after:
                                if str(pos.get('ticket')) == str(result.get('deal_id', '')):
                                    trade_profit = pos.get('profit', 0.0)
                                    break
                            
                            # Update stats
                            total_trades += 1
                            total_profit += trade_profit
                            if trade_profit > 0:
                                winning_trades += 1
                            
                            if total_profit > peak_profit:
                                peak_profit = total_profit
                            dd = peak_profit - total_profit
                            if dd > max_drawdown:
                                max_drawdown = dd
                            
                            if today not in daily_profits:
                                daily_profits[today] = 0.0
                            daily_profits[today] += trade_profit
                            
                            # Persist trade to database
                            _store_trade(bot_id, user_id, symbol, signal['direction'],
                                         volume, result.get('price', 0), trade_profit,
                                         result.get('deal_id'))
                            
                            logger.info(f"Bot {bot_id}: Trade executed {signal['direction']} {volume} {symbol} "
                                        f"| P&L: ${trade_profit:.2f} | Total: ${total_profit:.2f}")
                        else:
                            if result.get('is_paused'):
                                logger.warning(f"Bot {bot_id}: Market paused for {symbol}")
                            else:
                                logger.warning(f"Bot {bot_id}: Order failed: {result.get('error')}")
                    
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Trade error on {symbol}: {e}")
                        continue
                
                # Update bot state in DB
                _persist_bot_state(bot_id, total_profit, total_trades, winning_trades,
                                   daily_profits, peak_profit, max_drawdown)
                
                # Update balance cache
                acct_info = mt5_get_account_info()
                if acct_info:
                    _update_balance_cache(bot_config.get('brokerName', 'MT5'),
                                          bot_config.get('accountId', ''),
                                          acct_info)
                
                logger.info(f"Bot {bot_id}: Cycle #{trade_cycle} done | Trades: {trades_placed} | Total P&L: ${total_profit:.2f}")
                
                # Wait for next cycle with stagger
                stagger = random.uniform(0, 10)
                time.sleep(trading_interval + stagger)
                
            except Exception as e:
                logger.error(f"Bot {bot_id}: Cycle error: {e}")
                time.sleep(min(trading_interval, 60))
        
        # Bot stopped
        running_bots[bot_id] = False
        logger.info(f"Bot {bot_id}: Trading loop STOPPED")
        _update_bot_status(bot_id, 'stopped')
        
    except Exception as e:
        logger.error(f"Bot {bot_id}: FATAL error: {e}")
        running_bots[bot_id] = False


def _calculate_sl_tp(symbol: str, direction: str) -> tuple:
    """Calculate stop loss and take profit prices"""
    try:
        mt5 = mt5_module
        if not mt5:
            return None, None
        
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        if not tick or not sym:
            return None, None
        
        point = sym.point
        spread = tick.ask - tick.bid
        sl_dist = max(50 * point, spread * 3)
        tp_dist = max(100 * point, spread * 5)
        
        if direction == 'BUY':
            sl = round(tick.ask - sl_dist, sym.digits)
            tp = round(tick.ask + tp_dist, sym.digits)
        else:
            sl = round(tick.bid + sl_dist, sym.digits)
            tp = round(tick.bid - tp_dist, sym.digits)
        
        return sl, tp
    except Exception as e:
        logger.warning(f"SL/TP calculation error: {e}")
        return None, None


def _store_trade(bot_id: str, user_id: str, symbol: str, order_type: str,
                 volume: float, price: float, profit: float, ticket: Any):
    """Store a completed trade in the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        trade_id = f"trade_{int(datetime.now().timestamp()*1000)}_{bot_id[-8:]}"
        now = datetime.now().isoformat()
        
        trade_data = json.dumps({
            'symbol': symbol, 'type': order_type, 'volume': volume,
            'price': price, 'profit': profit, 'ticket': str(ticket or ''),
            'source': 'WORKER', 'worker_id': worker_id,
        })
        
        cursor.execute('''
            INSERT INTO trades (trade_id, bot_id, user_id, symbol, order_type, volume,
                                price, profit, ticket, time_open, time_close, status,
                                created_at, trade_data, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trade_id, bot_id, user_id, symbol, order_type, volume, price, profit,
              str(ticket or ''), now, now, 'closed', now, trade_data,
              int(datetime.now().timestamp() * 1000)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Store trade error: {e}")


def _persist_bot_state(bot_id: str, total_profit: float, total_trades: int,
                       winning_trades: int, daily_profits: Dict,
                       peak_profit: float, max_drawdown: float):
    """Persist bot runtime state to database"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        daily_profit = daily_profits.get(today, 0.0)
        
        runtime_state = json.dumps({
            'totalProfit': total_profit,
            'totalTrades': total_trades,
            'winningTrades': winning_trades,
            'dailyProfits': daily_profits,
            'dailyProfit': daily_profit,
            'peakProfit': peak_profit,
            'maxDrawdown': max_drawdown,
        })
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_bots
            SET daily_profit = ?, total_profit = ?, runtime_state = ?,
                enabled = 1, updated_at = ?
            WHERE bot_id = ?
        ''', (daily_profit, total_profit, runtime_state,
              datetime.now().isoformat(), bot_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Persist bot state error: {e}")


def _update_bot_status(bot_id: str, status: str, reason: str = None):
    """Update bot status in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_bots SET status = ?, updated_at = ? WHERE bot_id = ?
        ''', (status, datetime.now().isoformat(), bot_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Update bot status error: {e}")


def _update_balance_cache(broker: str, account: str, acct_info: Dict):
    """Update the broker_credentials cached balance"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE broker_credentials
            SET cached_balance = ?, cached_equity = ?, cached_margin_free = ?,
                last_update = ?
            WHERE account_number = ?
        ''', (acct_info.get('balance', 0), acct_info.get('equity', 0),
              acct_info.get('marginFree', 0), datetime.now().isoformat(),
              str(account)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"Balance cache update error: {e}")


# ==================== COMMAND PROCESSOR ====================

def process_commands():
    """Poll the worker_bot_queue table for commands assigned to this worker"""
    mt5_credentials = None  # Will be set on first bot start
    
    while worker_running:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Fetch pending commands for this worker
            cursor.execute('''
                SELECT id, bot_id, user_id, command, bot_config, credentials
                FROM worker_bot_queue
                WHERE worker_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            ''', (worker_id,))
            
            commands = cursor.fetchall()
            conn.close()
            
            for cmd in commands:
                cmd = dict(cmd)
                cmd_id = cmd['id']
                bot_id = cmd['bot_id']
                command = cmd['command']
                
                logger.info(f"Processing command: {command} for bot {bot_id}")
                
                try:
                    if command == 'start':
                        _handle_start_bot(cmd, mt5_credentials)
                        # Initialize MT5 on first bot (all bots share same account)
                        if mt5_credentials is None and cmd.get('credentials'):
                            creds = json.loads(cmd['credentials'])
                            mt5_credentials = creds
                            if not mt5_connection:
                                init_mt5(creds)
                    
                    elif command == 'stop':
                        _handle_stop_bot(bot_id)
                    
                    elif command == 'restart':
                        _handle_stop_bot(bot_id)
                        time.sleep(1)
                        _handle_start_bot(cmd, mt5_credentials)
                    
                    # Mark command as processed
                    _mark_command_processed(cmd_id, 'completed')
                    
                except Exception as e:
                    logger.error(f"Command {command} failed for bot {bot_id}: {e}")
                    _mark_command_processed(cmd_id, 'failed')
            
        except Exception as e:
            logger.error(f"Command processor error: {e}")
        
        time.sleep(COMMAND_POLL_INTERVAL)


def _handle_start_bot(cmd: Dict, fallback_creds: Dict):
    """Start a bot's trading loop"""
    bot_id = cmd['bot_id']
    user_id = cmd['user_id']
    
    if bot_id in bot_threads and bot_threads[bot_id].is_alive():
        logger.info(f"Bot {bot_id} already running")
        return
    
    # Parse bot config
    config = {}
    if cmd.get('bot_config'):
        try:
            config = json.loads(cmd['bot_config'])
        except Exception:
            pass
    
    # If no config in command, load from database
    if not config:
        config = _load_bot_config_from_db(bot_id)
    
    if not config:
        logger.error(f"Bot {bot_id}: No config available")
        return
    
    # Initialize MT5 if not yet done
    if not mt5_connection:
        creds = {}
        if cmd.get('credentials'):
            try:
                creds = json.loads(cmd['credentials'])
            except Exception:
                pass
        if not creds and fallback_creds:
            creds = fallback_creds
        if creds:
            if not init_mt5(creds):
                logger.error(f"Bot {bot_id}: MT5 initialization failed")
                return
        else:
            logger.error(f"Bot {bot_id}: No MT5 credentials available")
            return
    
    # Store config locally
    active_bots[bot_id] = config
    bot_stop_flags[bot_id] = False
    
    # Start trading loop in thread
    thread = threading.Thread(
        target=bot_trading_loop,
        args=(bot_id, user_id, config),
        daemon=True,
        name=f"WorkerBot-{bot_id}"
    )
    bot_threads[bot_id] = thread
    thread.start()
    logger.info(f"Bot {bot_id}: Started in worker {worker_id}")


def _handle_stop_bot(bot_id: str):
    """Stop a bot's trading loop"""
    bot_stop_flags[bot_id] = True
    running_bots[bot_id] = False
    
    if bot_id in bot_threads:
        thread = bot_threads[bot_id]
        # Give thread up to 10 seconds to stop
        thread.join(timeout=10)
        if thread.is_alive():
            logger.warning(f"Bot {bot_id}: Thread did not stop in 10s")
        del bot_threads[bot_id]
    
    if bot_id in active_bots:
        del active_bots[bot_id]
    
    logger.info(f"Bot {bot_id}: Stopped")


def _mark_command_processed(cmd_id: int, status: str):
    """Mark a command as processed"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE worker_bot_queue
            SET status = ?, processed_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), cmd_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Mark command error: {e}")


def _load_bot_config_from_db(bot_id: str) -> Optional[Dict]:
    """Load bot configuration from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ub.bot_id, ub.user_id, ub.name, ub.strategy, ub.status, ub.symbols,
                   ub.runtime_state, ub.daily_profit, ub.total_profit,
                   bc.credential_id,
                   br.broker_name, br.account_number, br.server, br.is_live
            FROM user_bots ub
            LEFT JOIN bot_credentials bc ON ub.bot_id = bc.bot_id
            LEFT JOIN broker_credentials br ON bc.credential_id = br.credential_id
            WHERE ub.bot_id = ?
        ''', (bot_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        row = dict(row)
        
        # Parse runtime state for saved metrics
        runtime = {}
        if row.get('runtime_state'):
            try:
                runtime = json.loads(row['runtime_state'])
            except Exception:
                pass
        
        symbols = row.get('symbols', 'EURUSDm')
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]
        
        return {
            'botId': row['bot_id'],
            'user_id': row['user_id'],
            'name': row.get('name', ''),
            'strategy': row.get('strategy', 'Trend Following'),
            'symbols': symbols,
            'brokerName': row.get('broker_name', 'MT5'),
            'accountId': row.get('account_number', ''),
            'credentialId': row.get('credential_id', ''),
            'riskPerTrade': runtime.get('riskPerTrade', 2.0),
            'tradeAmount': runtime.get('tradeAmount'),
            'profitLock': runtime.get('profitLock', 0),
            'maxDailyLoss': runtime.get('maxDailyLoss', 0),
            'signalThreshold': runtime.get('signalThreshold', 50),
            'tradingInterval': runtime.get('tradingInterval', TRADING_INTERVAL),
            'totalProfit': row.get('total_profit', 0) or runtime.get('totalProfit', 0),
            'totalTrades': runtime.get('totalTrades', 0),
            'winningTrades': runtime.get('winningTrades', 0),
            'dailyProfits': runtime.get('dailyProfits', {}),
            'peakProfit': runtime.get('peakProfit', 0),
            'maxDrawdown': runtime.get('maxDrawdown', 0),
        }
    except Exception as e:
        logger.error(f"Load bot config error: {e}")
        return None


# ==================== STARTUP ON EXISTING ASSIGNMENTS ====================

def resume_assigned_bots():
    """On worker startup, resume bots that were assigned to this worker"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT wba.bot_id, wba.account_number, wba.broker_name,
                   br.password, br.server, br.is_live
            FROM worker_bot_assignments wba
            LEFT JOIN broker_credentials br ON wba.account_number = br.account_number
            WHERE wba.worker_id = ?
        ''', (worker_id,))
        
        assignments = cursor.fetchall()
        conn.close()
        
        if not assignments:
            logger.info("No existing bot assignments to resume")
            return
        
        logger.info(f"Resuming {len(assignments)} bot(s) from previous assignments")
        
        for row in assignments:
            row = dict(row)
            bot_id = row['bot_id']
            
            # Initialize MT5 if not done yet
            if not mt5_connection and row.get('account_number') and row.get('password'):
                init_mt5({
                    'account_number': row['account_number'],
                    'password': row['password'],
                    'server': row.get('server', ''),
                })
            
            # Load and start the bot
            config = _load_bot_config_from_db(bot_id)
            if config:
                _handle_start_bot({
                    'bot_id': bot_id,
                    'user_id': config.get('user_id', ''),
                    'bot_config': json.dumps(config),
                    'credentials': None,
                }, None)
                logger.info(f"Resumed bot {bot_id}")
            else:
                logger.warning(f"Could not load config for bot {bot_id}")
        
    except Exception as e:
        logger.error(f"Resume bots error: {e}")


# ==================== MAIN ====================

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global worker_running
    logger.info(f"Worker {worker_id}: Received signal {signum}, shutting down...")
    worker_running = False
    
    # Stop all bots
    for bot_id in list(bot_stop_flags.keys()):
        bot_stop_flags[bot_id] = True
    
    # Wait for threads to finish
    for bot_id, thread in list(bot_threads.items()):
        thread.join(timeout=5)
    
    unregister_worker()
    
    # Shutdown MT5
    if mt5_module:
        try:
            mt5_module.shutdown()
        except Exception:
            pass
    
    sys.exit(0)


def main():
    global worker_id, logger
    
    if len(sys.argv) < 2:
        print("Usage: python mt5_worker.py <worker_id>")
        sys.exit(1)
    
    worker_id = int(sys.argv[1])
    
    # Reconfigure logger with worker_id
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    log_file = f'worker_{worker_id}.log'
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s - [Worker {worker_id}] %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== MT5 Worker {worker_id} Starting (PID: {os.getpid()}) ===")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register in database
    register_worker()
    
    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=update_heartbeat, daemon=True)
    heartbeat_thread.start()
    
    # Resume any previously assigned bots
    resume_assigned_bots()
    
    # Main loop: process commands
    logger.info(f"Worker {worker_id}: Ready and polling for commands")
    process_commands()
    
    # Cleanup
    unregister_worker()
    if mt5_module:
        try:
            mt5_module.shutdown()
        except Exception:
            pass
    
    logger.info(f"Worker {worker_id}: Shutdown complete")


if __name__ == '__main__':
    main()
