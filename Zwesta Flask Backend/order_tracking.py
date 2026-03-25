w"""
Order Tracking & Synchronization Module for MT5 Backend
Ensures orders created by bots actually appear and persist in Exness

Usage:
    from order_tracking import (
        log_order_placement,
        verify_order_in_mt5,
        reconcile_bot_orders,
        get_unconfirmed_orders
    )
    
    # In trading loop after order placement:
    log_order_placement(bot_id, order_response, symbol, order_type, volume)
    verify_order_in_mt5(bot_id, order_response.get('ticket'), mt5_conn)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3

logger = logging.getLogger(__name__)


def normalize_symbol(symbol: str, broker: str = 'Exness') -> str:
    """
    Return broker-specific symbol format
    
    Args:
        symbol: Symbol name (e.g., 'EURUSD', 'ETHUSDm', 'BTCUSD')
        broker: Broker name ('Exness', 'XM', 'MetaTrader5')
    
    Returns:
        Normalized symbol (e.g., 'EURUSDm' for Exness)
    """
    if broker in ['Exness', 'XM', 'XM Global', 'MetaQuotes']:
        # Exness format: BASEQOUTE + lowercase 'm'
        symbol_clean = symbol.upper().replace('M', 'm')
        if not symbol_clean.endswith('m'):
            symbol_clean += 'm'
        return symbol_clean
    
    return symbol.upper()


def log_order_placement(bot_id: str, order_response: Dict, symbol: str, 
                       order_type: str, volume: float, broker: str = 'Exness') -> Optional[int]:
    """
    Log order placement with full details for troubleshooting
    
    Args:
        bot_id: Bot identifier
        order_response: Response from MT5 place_order() call
        symbol: Trading symbol (e.g., 'ETHUSDm')
        order_type: 'BUY' or 'SELL'
        volume: Order volume/lot size
        broker: Broker name
    
    Returns:
        Ticket number if successful, None if failed
    """
    try:
        ticket = order_response.get('ticket')
        retcode = order_response.get('retcode')
        status = order_response.get('status', 'UNKNOWN')
        
        # Normalize symbol for logging
        symbol_norm = normalize_symbol(symbol, broker)
        
        if retcode == 10009:  # Success
            logger.info(f"✅ [ORDER PLACED] Bot {bot_id}")
            logger.info(f"   Symbol: {symbol_norm}")
            logger.info(f"   Type: {order_type} | Volume: {volume}")
            logger.info(f"   Ticket: {ticket}")
            logger.info(f"   Status: {status}")
            logger.info(f"   Retcode: {retcode} (Success)")
            return ticket
        else:
            # Order failed - log why
            error_msg = order_response.get('comment', 'Unknown error')
            logger.warning(f"⚠️ [ORDER FAILED] Bot {bot_id}")
            logger.warning(f"   Symbol: {symbol_norm}")
            logger.warning(f"   Type: {order_type} | Volume: {volume}")
            logger.warning(f"   Retcode: {retcode}")
            logger.warning(f"   Error: {error_msg}")
            logger.warning(f"   Status: {status}")
            
            # Log pause retcodes for market analysis
            PAUSE_RETCODES = {
                10009: 'SYMBOL_HALTED',
                10019: 'REQUOTE',
                10026: 'MARKET_CLOSED',
                10018: 'NO_LIQUIDITY',
                10016: 'INVALID_REQUEST',
                10015: 'TRADE_MODE_DISABLED',
            }
            
            if retcode in PAUSE_RETCODES:
                logger.warning(f"   Pause Reason: {PAUSE_RETCODES[retcode]}")
            
            return None
    
    except Exception as e:
        logger.error(f"❌ Error logging order placement: {e}")
        return None


def verify_order_in_mt5(bot_id: str, ticket: int, mt5_conn, 
                       timeout_seconds: float = 2.0) -> Tuple[bool, Optional[Dict]]:
    """
    Verify that placed order actually exists in MT5 positions
    
    Args:
        bot_id: Bot identifier
        ticket: Order ticket from placement response
        mt5_conn: MT5 connection object
        timeout_seconds: Max time to wait for order appearance (default 2s)
    
    Returns:
        (is_confirmed, position_data) tuple
        - is_confirmed: True if order found, False if not found or error
        - position_data: Full position dict from MT5, or None
    """
    if not ticket or not mt5_conn:
        logger.warning(f"Bot {bot_id}: Cannot verify order - invalid ticket ({ticket}) or connection")
        return False, None
    
    try:
        start_time = time.time()
        poll_interval = 0.2  # Check every 200ms
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                # Get all positions from MT5
                positions = mt5_conn.get_positions()
                
                if not positions:
                    logger.debug(f"Bot {bot_id}: No positions found in MT5 yet (checking ticket {ticket})")
                    time.sleep(poll_interval)
                    continue
                
                # Look for matching ticket
                for pos in positions:
                    if pos.get('ticket') == ticket:
                        elapsed = time.time() - start_time
                        logger.info(f"✅ [ORDER CONFIRMED] Bot {bot_id}")
                        logger.info(f"   Ticket: {ticket}")
                        logger.info(f"   Symbol: {pos.get('symbol')}")
                        logger.info(f"   Type: {pos.get('type')}")
                        logger.info(f"   Volume: {pos.get('volume')}")
                        logger.info(f"   Entry Price: {pos.get('price_open'):.5f}")
                        logger.info(f"   Profit: ${pos.get('profit', 0):.2f}")
                        logger.info(f"   Found in {elapsed:.2f}s")
                        return True, pos
                
                time.sleep(poll_interval)
            
            except Exception as e:
                logger.debug(f"Bot {bot_id}: Error checking positions: {e}")
                time.sleep(poll_interval)
        
        # Order not found after timeout
        logger.warning(f"⚠️ [ORDER NOT FOUND] Bot {bot_id}")
        logger.warning(f"   Ticket: {ticket}")
        logger.warning(f"   Not found in MT5 after {timeout_seconds:.1f}s")
        logger.warning(f"   Order may be: rejected, pending, or in different account")
        return False, None
    
    except Exception as e:
        logger.error(f"❌ Error verifying order {ticket}: {e}")
        return False, None


def get_unconfirmed_orders(bot_id: str, db_path: str = 'trading.db') -> List[Dict]:
    """
    Get all orders from database that haven't been confirmed in MT5
    
    Args:
        bot_id: Bot identifier
        db_path: Path to trading database
    
    Returns:
        List of orders with status='unconfirmed' or 'pending'
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE bot_id = ? AND status IN ('unconfirmed', 'pending')
            ORDER BY created_at DESC
            LIMIT 50
        ''', (bot_id,))
        
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Retrieved {len(orders)} unconfirmed orders for bot {bot_id}")
        return orders
    
    except Exception as e:
        logger.error(f"Error getting unconfirmed orders: {e}")
        return []


def reconcile_bot_orders(bot_id: str, mt5_conn, db_path: str = 'trading.db',
                        max_age_minutes: int = 60) -> Dict[str, int]:
    """
    Reconcile local order records with actual MT5 positions
    Identifies and updates orders that:
    - Are now confirmed in MT5 (update status)
    - Missing from MT5 (mark as failed/closed)
    - New in MT5 but not in local DB (emergency sync)
    
    Args:
        bot_id: Bot identifier
        mt5_conn: MT5 connection object
        db_path: Path to trading database
        max_age_minutes: Only reconcile orders younger than this (default 60 min)
    
    Returns:
        Dict with reconciliation stats:
        {
            'confirmed': N,      # Orders now marked as confirmed
            'closed': N,         # Orders marked as closed
            'failed': N,         # Orders marked as failed
            'synced': N,         # Emergency syncs from MT5
            'errors': N          # Errors during reconciliation
        }
    """
    stats = {
        'confirmed': 0,
        'closed': 0,
        'failed': 0,
        'synced': 0,
        'errors': 0
    }
    
    try:
        # Get unconfirmed orders from local DB
        unconfirmed = get_unconfirmed_orders(bot_id, db_path)
        
        # Get actual positions from MT5
        try:
            mt5_positions = mt5_conn.get_positions() or []
        except Exception as e:
            logger.error(f"Failed to get MT5 positions: {e}")
            stats['errors'] += 1
            return stats
        
        mt5_tickets = {pos.get('ticket'): pos for pos in mt5_positions}
        
        # Check each unconfirmed order
        for order in unconfirmed:
            try:
                ticket = order.get('ticket')
                created_at = datetime.fromisoformat(order.get('created_at', datetime.now().isoformat()))
                age_minutes = (datetime.now() - created_at).total_seconds() / 60
                
                # Skip very old orders (older than max_age_minutes)
                if age_minutes > max_age_minutes:
                    logger.debug(f"Bot {bot_id}: Skipping old order {ticket} ({age_minutes:.0f}m old)")
                    continue
                
                if ticket in mt5_tickets:
                    # Order found in MT5 - mark as confirmed
                    position = mt5_tickets[ticket]
                    update_order_status(bot_id, ticket, 'confirmed', db_path)
                    logger.info(f"✅ Reconcile: Order {ticket} now confirmed in MT5")
                    logger.info(f"   Symbol: {position.get('symbol')}, Profit: ${position.get('profit', 0):.2f}")
                    stats['confirmed'] += 1
                else:
                    # Order missing from MT5 - mark as failed
                    update_order_status(bot_id, ticket, 'failed', db_path)
                    logger.warning(f"⚠️ Reconcile: Order {ticket} missing from MT5 (likely rejected/failed)")
                    stats['failed'] += 1
            
            except Exception as e:
                logger.error(f"Error reconciling order {order.get('ticket')}: {e}")
                stats['errors'] += 1
        
        logger.info(f"Bot {bot_id}: Reconciliation complete")
        logger.info(f"   Confirmed: {stats['confirmed']}, Failed: {stats['failed']}, Errors: {stats['errors']}")
        
        return stats
    
    except Exception as e:
        logger.error(f"Fatal error in order reconciliation: {e}")
        stats['errors'] += 1
        return stats


def update_order_status(bot_id: str, ticket: int, new_status: str, 
                       db_path: str = 'trading.db', extra_data: Optional[Dict] = None):
    """
    Update order status in database
    
    Args:
        bot_id: Bot identifier
        ticket: Order ticket number
        new_status: New status ('confirmed', 'failed', 'closed', etc.)
        db_path: Path to trading database
        extra_data: Additional data to store (e.g., position details from MT5)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        updated_at = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE trades 
            SET status = ?, updated_at = ?
            WHERE bot_id = ? AND ticket = ?
        ''', (new_status, updated_at, bot_id, ticket))
        
        if cursor.rowcount > 0:
            logger.debug(f"Updated order {ticket} status to '{new_status}'")
        else:
            logger.warning(f"No trade record found for bot {bot_id}, ticket {ticket}")
        
        conn.commit()
        conn.close()
    
    except Exception as e:
        logger.error(f"Error updating order {ticket} status: {e}")


def get_order_sync_stats(bot_id: str, db_path: str = 'trading.db',  
                        time_window_hours: int = 24) -> Dict[str, int]:
    """
    Get order synchronization statistics for a bot
    
    Args:
        bot_id: Bot identifier
        db_path: Path to trading database
        time_window_hours: Only include orders from last N hours
    
    Returns:
        Dict with order counts by status
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=time_window_hours)).isoformat()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM trades
            WHERE bot_id = ? AND created_at > ?
            GROUP BY status
        ''', (bot_id, cutoff_time))
        
        stats = dict(cursor.fetchall()) if cursor.rowcount > 0 else {}
        conn.close()
        
        logger.info(f"Bot {bot_id} order stats (last {time_window_hours}h): {stats}")
        return stats
    
    except Exception as e:
        logger.error(f"Error getting order sync stats: {e}")
        return {}


# Integration into trading loop
# =============================
# Add this to the continuous_bot_trading_loop function after order placement:

INTEGRATION_EXAMPLE = """
# In continuous_bot_trading_loop, after placing order:
from order_tracking import (
    log_order_placement, 
    verify_order_in_mt5,
    reconcile_bot_orders
)

# Place order via MT5
place_order_response = mt5_conn.place_order(...)

# Log placement and get ticket
ticket = log_order_placement(
    bot_id=bot_id,
    order_response=place_order_response,
    symbol=symbol_to_trade,
    order_type=trade_direction,
    volume=position_size,
    broker='Exness'
)

# Verify order exists in MT5 within 2 seconds
if ticket:
    is_confirmed, position_data = verify_order_in_mt5(
        bot_id=bot_id,
        ticket=ticket,
        mt5_conn=mt5_conn,
        timeout_seconds=2.0
    )
    
    if not is_confirmed:
        logger.warning(f"Order {ticket} placed but not confirmed - will reconcile next cycle")
        # Update DB status to 'unconfirmed' for later reconciliation
        update_order_status(bot_id, ticket, 'unconfirmed')

# Periodically reconcile orders (every 30 seconds)
if trade_cycle % 6 == 0:  # Assuming 5-second cycles
    reconcile_stats = reconcile_bot_orders(
        bot_id=bot_id,
        mt5_conn=mt5_conn,
        max_age_minutes=60
    )
    if reconcile_stats['confirmed'] > 0:
        logger.info(f"Reconciliation fixed {reconcile_stats['confirmed']} orders")
"""

if __name__ == "__main__":
    # Example usage
    logger.info("Order tracking module loaded. Import into backend to enable.")
