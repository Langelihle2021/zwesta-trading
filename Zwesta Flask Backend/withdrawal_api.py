"""
Withdrawal API Endpoints and Integration
Provides Flask endpoints for intelligent profit withdrawal management

Author: Zwesta Trading Bot System
Version: 1.0
"""

from flask import request, jsonify
from functools import wraps
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

try:
    from intelligent_withdrawal import IntelligentWithdrawal, WithdrawalTrigger
except ImportError:
    # Fallback path if running from different directory
    from .intelligent_withdrawal import IntelligentWithdrawal, WithdrawalTrigger

logger = logging.getLogger(__name__)

# Global state: store withdrawal managers per bot
bot_withdrawal_managers: Dict[str, IntelligentWithdrawal] = {}


def initialize_withdrawal_manager_for_bot(
    bot_id: str,
    user_id: str,
    withdrawal_config: Dict
) -> IntelligentWithdrawal:
    """
    Initialize withdrawal manager for a specific bot
    
    Args:
        bot_id: Unique bot identifier
        user_id: User who owns the bot
        withdrawal_config: Configuration dictionary
    
    Returns:
        IntelligentWithdrawal instance
    """
    manager = IntelligentWithdrawal(withdrawal_config)
    bot_withdrawal_managers[bot_id] = manager
    logger.info(f"✅ Withdrawal manager initialized for bot {bot_id} (user: {user_id})")
    return manager


def get_withdrawal_manager_for_bot(bot_id: str) -> Optional[IntelligentWithdrawal]:
    """Retrieve withdrawal manager for bot"""
    return bot_withdrawal_managers.get(bot_id)


def create_withdrawal_manager_if_needed(bot_id: str, user_id: str, db_connection) -> IntelligentWithdrawal:
    """
    Create withdrawal manager if it doesn't exist, loading config from database
    
    Args:
        bot_id: Bot identifier
        user_id: User identifier
        db_connection: Database connection
    
    Returns:
        IntelligentWithdrawal instance
    """
    # Check if manager already exists
    if bot_id in bot_withdrawal_managers:
        return bot_withdrawal_managers[bot_id]
    
    # Load config from database
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT mode, target_profit, min_profit, max_profit, win_rate_min, "
            "min_hours_between_withdrawals FROM auto_withdrawal_settings WHERE bot_id = ?",
            (bot_id,)
        )
        row = cursor.fetchone()
        
        if row:
            config = {
                'mode': row[0] or 'intelligent',
                'target_profit': row[1] or 100.0,
                'min_profit': row[2] or 50.0,
                'max_profit': row[3] or 500.0,
                'win_rate_min': row[4] or 55.0,
                'min_hours_between_withdrawals': row[5] or 24
            }
        else:
            # Default config
            config = {
                'mode': 'intelligent',
                'target_profit': 100.0,
                'min_profit': 50.0,
                'max_profit': 500.0,
                'win_rate_min': 55.0,
                'min_hours_between_withdrawals': 24
            }
    except Exception as e:
        logger.warning(f"Failed to load withdrawal config from DB: {e}. Using defaults.")
        config = {
            'mode': 'intelligent',
            'target_profit': 100.0,
            'min_profit': 50.0,
            'max_profit': 500.0,
            'win_rate_min': 55.0,
            'min_hours_between_withdrawals': 24
        }
    
    # Initialize and store manager
    return initialize_withdrawal_manager_for_bot(bot_id, user_id, config)


def register_withdrawal_endpoints(app, get_db_connection):
    """
    Register all withdrawal API endpoints
    
    Endpoints:
    1. GET /api/withdrawal/settings/<bot_id> - Get current settings
    2. POST /api/withdrawal/settings/<bot_id> - Update settings
    3. POST /api/withdrawal/evaluate - Evaluate if should withdraw now
    4. POST /api/withdrawal/execute - Execute withdrawal
    5. GET /api/withdrawal/history/<bot_id> - Withdrawal history
    6. GET /api/withdrawal/stats/<bot_id> - Withdrawal statistics
    """
    
    @app.route('/api/withdrawal/settings/<bot_id>', methods=['GET'])
    def get_withdrawal_settings(bot_id):
        """Get withdrawal settings for bot"""
        try:
            db = get_db_connection()
            cursor = db.cursor()
            
            cursor.execute(
                "SELECT mode, target_profit, min_profit, max_profit, win_rate_min, "
                "min_hours_between_withdrawals FROM auto_withdrawal_settings WHERE bot_id = ?",
                (bot_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                # Return defaults
                return jsonify({
                    'status': 'success',
                    'settings': {
                        'bot_id': bot_id,
                        'mode': 'intelligent',
                        'target_profit': 100.0,
                        'min_profit': 50.0,
                        'max_profit': 500.0,
                        'win_rate_min': 55.0,
                        'min_hours_between_withdrawals': 24
                    }
                })
            
            return jsonify({
                'status': 'success',
                'settings': {
                    'bot_id': bot_id,
                    'mode': row[0] or 'intelligent',
                    'target_profit': row[1],
                    'min_profit': row[2],
                    'max_profit': row[3],
                    'win_rate_min': row[4],
                    'min_hours_between_withdrawals': row[5]
                }
            })
        except Exception as e:
            logger.error(f"Error getting withdrawal settings: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    @app.route('/api/withdrawal/settings/<bot_id>', methods=['POST'])
    def update_withdrawal_settings(bot_id):
        """Update withdrawal settings"""
        try:
            data = request.get_json()
            
            # Validate data
            required_fields = ['mode', 'target_profit', 'win_rate_min']
            if not all(field in data for field in required_fields):
                return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
            
            db = get_db_connection()
            cursor = db.cursor()
            
            # Check if settings exist
            cursor.execute("SELECT id FROM auto_withdrawal_settings WHERE bot_id = ?", (bot_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute(
                    "UPDATE auto_withdrawal_settings SET mode=?, target_profit=?, min_profit=?, "
                    "max_profit=?, win_rate_min=?, min_hours_between_withdrawals=? WHERE bot_id=?",
                    (
                        data['mode'],
                        data['target_profit'],
                        data.get('min_profit', 50.0),
                        data.get('max_profit', 500.0),
                        data['win_rate_min'],
                        data.get('min_hours_between_withdrawals', 24),
                        bot_id
                    )
                )
            else:
                cursor.execute(
                    "INSERT INTO auto_withdrawal_settings (bot_id, mode, target_profit, min_profit, "
                    "max_profit, win_rate_min, min_hours_between_withdrawals) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        bot_id,
                        data['mode'],
                        data['target_profit'],
                        data.get('min_profit', 50.0),
                        data.get('max_profit', 500.0),
                        data['win_rate_min'],
                        data.get('min_hours_between_withdrawals', 24)
                    )
                )
            
            db.commit()
            
            # Reinitialize manager with new settings
            config = {
                'mode': data['mode'],
                'target_profit': data['target_profit'],
                'min_profit': data.get('min_profit', 50.0),
                'max_profit': data.get('max_profit', 500.0),
                'win_rate_min': data['win_rate_min'],
                'min_hours_between_withdrawals': data.get('min_hours_between_withdrawals', 24)
            }
            initialize_withdrawal_manager_for_bot(bot_id, 'unknown', config)
            
            return jsonify({
                'status': 'success',
                'message': 'Withdrawal settings updated',
                'settings': config
            })
        except Exception as e:
            logger.error(f"Error updating withdrawal settings: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    @app.route('/api/withdrawal/evaluate', methods=['POST'])
    def evaluate_withdrawal():
        """
        Evaluate if profit withdrawal should happen now
        
        Request body:
        {
            "bot_id": "bot_123",
            "current_profit": 150.50,
            "win_rate": 65.0,
            "current_price": 1.0850,
            "symbol": "EURUSDm",
            "account_balance": 5000.00,
            "open_trades": 0,
            "max_drawdown_percent": 5.0
        }
        """
        try:
            data = request.get_json()
            bot_id = data['bot_id']
            
            # Get or create manager
            db = get_db_connection()
            manager = create_withdrawal_manager_if_needed(bot_id, 'unknown', db)
            
            # Evaluate
            evaluation = manager.evaluate_withdrawal_conditions(
                current_profit=data['current_profit'],
                win_rate=data['win_rate'],
                current_price=data['current_price'],
                symbol=data['symbol'],
                account_balance=data['account_balance'],
                open_trades_count=data.get('open_trades', 0),
                max_drawdown_percent=data.get('max_drawdown_percent', 0)
            )
            
            return jsonify(evaluation)
        except Exception as e:
            logger.error(f"Error evaluating withdrawal: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    @app.route('/api/withdrawal/execute', methods=['POST'])
    def execute_withdrawal():
        """
        Execute profit withdrawal
        
        Request body:
        {
            "bot_id": "bot_123",
            "amount": 150.50,
            "symbol": "EURUSDm",
            "trigger": "spike_detected"
        }
        """
        try:
            data = request.get_json()
            bot_id = data['bot_id']
            amount = data['amount']
            symbol = data.get('symbol', 'UNKNOWN')
            trigger_str = data.get('trigger', 'unknown')
            
            # Get manager
            manager = get_withdrawal_manager_for_bot(bot_id)
            if not manager:
                return jsonify({'status': 'error', 'message': 'No withdrawal manager for this bot'}), 404
            
            # Convert trigger string to enum
            try:
                trigger = WithdrawalTrigger(trigger_str)
            except ValueError:
                trigger = None
            
            # Record withdrawal
            manager.record_withdrawal(amount, trigger, symbol)
            
            # Update database
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO auto_withdrawal_history (bot_id, amount, trigger, symbol, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (bot_id, amount, trigger_str, symbol, datetime.now().isoformat())
            )
            db.commit()
            
            logger.info(f"✅ Withdrawal executed: bot={bot_id}, amount={amount}, trigger={trigger_str}")
            
            return jsonify({
                'status': 'success',
                'message': f'Withdrew ${amount:.2f}',
                'bot_id': bot_id,
                'amount': amount,
                'trigger': trigger_str,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error executing withdrawal: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    @app.route('/api/withdrawal/history/<bot_id>', methods=['GET'])
    def get_withdrawal_history(bot_id):
        """Get withdrawal history for bot"""
        try:
            limit = request.args.get('limit', 50, type=int)
            
            db = get_db_connection()
            cursor = db.cursor()
            
            cursor.execute(
                "SELECT amount, trigger, symbol, timestamp FROM auto_withdrawal_history "
                "WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?",
                (bot_id, limit)
            )
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'amount': row[0],
                    'trigger': row[1],
                    'symbol': row[2],
                    'timestamp': row[3]
                })
            
            return jsonify({
                'status': 'success',
                'bot_id': bot_id,
                'count': len(history),
                'history': history
            })
        except Exception as e:
            logger.error(f"Error getting withdrawal history: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    @app.route('/api/withdrawal/stats/<bot_id>', methods=['GET'])
    def get_withdrawal_stats(bot_id):
        """Get withdrawal statistics for bot"""
        try:
            db = get_db_connection()
            manager = create_withdrawal_manager_if_needed(bot_id, 'unknown', db)
            
            stats = manager.get_withdrawal_statistics()
            
            return jsonify({
                'status': 'success',
                'bot_id': bot_id,
                'statistics': stats
            })
        except Exception as e:
            logger.error(f"Error getting withdrawal stats: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    
    logger.info("✅ Withdrawal API endpoints registered successfully")


def integrate_withdrawal_into_trading_loop(
    bot_id: str,
    current_profit: float,
    recent_trades: list,
    current_price: float,
    symbol: str,
    account_balance: float,
    open_positions: list,
    current_drawdown: float,
    db_connection
) -> Dict:
    """
    Integration point for bot trading loop
    Call this after each trade cycle to check if withdrawal should occur
    
    Args:
        bot_id: Bot identifier
        current_profit: Accumulated profit since last withdrawal
        recent_trades: List of recent trades, used to calculate win_rate
        current_price: Current price of trading symbol
        symbol: Trading symbol (e.g., 'EURUSDm')
        account_balance: Current account balance
        open_positions: List of currently open positions
        current_drawdown: Current drawdown percent
        db_connection: Database connection
    
    Returns:
        {
            'should_withdraw': bool,
            'amount': float,
            'confidence': float,
            'recommendation': str
        }
    """
    try:
        # Get or create manager
        manager = create_withdrawal_manager_if_needed(bot_id, 'unknown', db_connection)
        
        # Calculate win rate from recent trades
        if recent_trades and len(recent_trades) > 0:
            winning_trades = sum(1 for t in recent_trades if t.get('profit', 0) > 0)
            win_rate = (winning_trades / len(recent_trades)) * 100
        else:
            win_rate = 50.0  # Default to 50% if no trades
        
        # Evaluate withdrawal conditions
        evaluation = manager.evaluate_withdrawal_conditions(
            current_profit=current_profit,
            win_rate=win_rate,
            current_price=current_price,
            symbol=symbol,
            account_balance=account_balance,
            open_trades_count=len(open_positions),
            max_drawdown_percent=current_drawdown
        )
        
        # If should withdraw, execute immediately
        if evaluation['should_withdraw'] and evaluation['withdrawal_amount'] > 0:
            # Record in database
            cursor = db_connection.cursor()
            cursor.execute(
                "INSERT INTO auto_withdrawal_history (bot_id, amount, trigger, symbol, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    bot_id,
                    evaluation['withdrawal_amount'],
                    evaluation['trigger'].value if evaluation['trigger'] else 'unknown',
                    symbol,
                    datetime.now().isoformat()
                )
            )
            db_connection.commit()
            
            # Update manager's internal state
            manager.record_withdrawal(evaluation['withdrawal_amount'], evaluation['trigger'], symbol)
            
            logger.info(
                f"💰 Auto-withdrawal triggered: bot={bot_id}, amount=${evaluation['withdrawal_amount']:.2f}, "
                f"trigger={evaluation['trigger'].value if evaluation['trigger'] else 'unknown'}"
            )
        
        return {
            'should_withdraw': evaluation['should_withdraw'],
            'amount': evaluation['withdrawal_amount'],
            'confidence': evaluation['confidence'],
            'trigger': evaluation['trigger'].value if evaluation['trigger'] else None,
            'recommendation': evaluation['recommendation']
        }
    
    except Exception as e:
        logger.error(f"Error in withdrawal integration: {e}")
        return {
            'should_withdraw': False,
            'amount': 0,
            'confidence': 0,
            'trigger': None,
            'recommendation': f'Error evaluating withdrawal: {str(e)}'
        }

