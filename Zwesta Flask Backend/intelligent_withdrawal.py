"""
Intelligent Profit Withdrawal System for Zwesta Trading Bot
Detects market spikes and withdraws profits at optimal times

Author: Zwesta Trading Bot System
Last Updated: 2026-03-12
"""

import logging
import time
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class MarketCondition(Enum):
    """Market condition classifications"""
    NORMAL = "normal"
    VOLATILE = "volatile"
    SPIKE_UP = "spike_up"
    SPIKE_DOWN = "spike_down"
    CONSOLIDATING = "consolidating"
    TRENDING = "trending"


class WithdrawalTrigger(Enum):
    """Reasons for withdrawal trigger"""
    FIXED_TARGET = "fixed_target"        # Fixed profit amount reached
    SPIKE_DETECTED = "spike_detected"    # Market spike detected
    WIN_RATE_HIGH = "win_rate_high"      # Win rate above threshold
    TIME_BASED = "time_based"            # Time interval since last withdrawal
    DRAWDOWN_PROTECTION = "drawdown"     # Protect against future drawdown
    PROFIT_LOCK = "profit_lock"          # Lock in gains above threshold


class SpikeDetector:
    """Detects market spikes in price data"""
    
    def __init__(self, lookback_periods: int = 50, std_dev_threshold: float = 2.0):
        """
        Initialize spike detector
        
        Args:
            lookback_periods: Number of periods to calculate moving average (50 = ~10 hours at 12-min intervals)
            std_dev_threshold: Number of standard deviations for spike detection (2.0 = 95% confidence)
        """
        self.lookback_periods = lookback_periods
        self.std_dev_threshold = std_dev_threshold
        self.price_history = {}  # {symbol: [prices]}
        self.volume_history = {}  # {symbol: [volumes]}
    
    def add_price_data(self, symbol: str, price: float, volume: float = 0):
        """Add price data point for spike detection"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.volume_history[symbol] = []
        
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)
        
        # Keep only recent data to prevent memory bloat
        if len(self.price_history[symbol]) > self.lookback_periods * 2:
            self.price_history[symbol] = self.price_history[symbol][-self.lookback_periods:]
            self.volume_history[symbol] = self.volume_history[symbol][-self.lookback_periods:]
    
    def calculate_moving_average(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate simple moving average for symbol"""
        if symbol not in self.price_history:
            return None
        
        period = period or self.lookback_periods
        prices = self.price_history[symbol]
        
        if len(prices) < period:
            return None
        
        return statistics.mean(prices[-period:])
    
    def calculate_std_deviation(self, symbol: str, period: int = None) -> Optional[float]:
        """Calculate standard deviation of prices"""
        if symbol not in self.price_history:
            return None
        
        period = period or self.lookback_periods
        prices = self.price_history[symbol]
        
        if len(prices) < period:
            return None
        
        try:
            return statistics.stdev(prices[-period:])
        except:
            return None
    
    def is_spike_detected(self, symbol: str, current_price: float) -> Tuple[bool, Dict]:
        """
        Detect if current price represents a spike
        
        Returns:
            (is_spike: bool, spike_info: dict with analysis details)
        """
        ma = self.calculate_moving_average(symbol)
        std_dev = self.calculate_std_deviation(symbol)
        
        if ma is None or std_dev is None:
            return False, {'reason': 'insufficient_data'}
        
        # Calculate how many standard deviations away from mean
        price_deviation = abs(current_price - ma) / (std_dev + 0.0001)  # Avoid division by zero
        
        # Determine spike direction
        spike_direction = "up" if current_price > ma else "down"
        
        # Spike detected if price is more than threshold std devs from mean
        is_spike = price_deviation > self.std_dev_threshold
        
        return is_spike, {
            'current_price': current_price,
            'moving_average': ma,
            'std_deviation': std_dev,
            'price_deviation_std': round(price_deviation, 2),
            'spike_direction': spike_direction,
            'threshold_std': self.std_dev_threshold,
            'percent_above_ma': round(((current_price - ma) / ma * 100), 2) if ma > 0 else 0
        }
    
    def detect_market_condition(self, symbol: str, current_price: float) -> Tuple[MarketCondition, Dict]:
        """
        Analyze market condition comprehensively
        
        Returns:
            (condition: MarketCondition, analysis: dict)
        """
        ma = self.calculate_moving_average(symbol)
        std_dev = self.calculate_std_deviation(symbol)
        
        if ma is None or std_dev is None:
            return MarketCondition.NORMAL, {}
        
        if symbol not in self.price_history or len(self.price_history[symbol]) < 5:
            return MarketCondition.NORMAL, {}
        
        prices = self.price_history[symbol]
        recent_prices = prices[-5:]
        
        # Calculate trend
        price_diff = prices[-1] - prices[-5] if len(prices) >= 5 else 0
        is_trending_up = price_diff > 0
        trend_magnitude = abs(price_diff) / prices[-5] * 100 if prices[-5] != 0 else 0
        
        # Detect volatility
        cv = std_dev / ma if ma > 0 else 0  # Coefficient of variation
        
        # Determine condition
        spike_detected, spike_info = self.is_spike_detected(symbol, current_price)
        
        if spike_detected:
            condition = MarketCondition.SPIKE_UP if current_price > ma else MarketCondition.SPIKE_DOWN
        elif cv > 0.05:  # 5% volatility threshold
            condition = MarketCondition.VOLATILE
        elif trend_magnitude > 1.0:  # >1% movement over recent periods
            condition = MarketCondition.TRENDING
        else:
            condition = MarketCondition.CONSOLIDATING
        
        return condition, {
            'condition': condition.value,
            'recent_trend': 'up' if is_trending_up else 'down',
            'trend_magnitude_percent': round(trend_magnitude, 2),
            'volatility_cv': round(cv, 4),
            'spike_info': spike_info
        }


class IntelligentWithdrawal:
    """
    Intelligently manages profit withdrawal based on market conditions
    
    Withdrawal Modes:
    1. FIXED: Withdraw at fixed profit target (e.g., every $100 profit)
    2. INTELLIGENT: Wait for spike conditions + win rate validation
    3. HYBRID: Use fixed as fallback, intelligent as preferred
    """
    
    def __init__(self, withdrawal_config: Dict = None):
        """
        Initialize intelligent withdrawal manager
        
        Config example:
        {
            'mode': 'intelligent',
            'target_profit': 100.0,
            'min_profit': 50.0,
            'max_profit': 500.0,
            'win_rate_min': 60.0,  # Only withdraw if win rate > 60%
            'min_hours_between_withdrawals': 6,
            'volatility_threshold': 0.02,  # 2% volatility for spike detection
            'spike_std_threshold': 2.0,  # 2 standard deviations = spike
        }
        """
        self.config = withdrawal_config or {}
        self.mode = self.config.get('mode', 'intelligent')  # 'fixed', 'intelligent', 'hybrid'
        self.target_profit = self.config.get('target_profit', 100.0)
        self.min_profit = self.config.get('min_profit', 50.0)
        self.max_profit = self.config.get('max_profit', 500.0)
        self.win_rate_min = self.config.get('win_rate_min', 55.0)  # 55% minimum win rate
        self.min_hours_between_withdrawals = self.config.get('min_hours_between_withdrawals', 24)
        self.volatility_threshold = self.config.get('volatility_threshold', 0.02)
        self.spike_std_threshold = self.config.get('spike_std_threshold', 2.0)
        
        # Runtime state
        self.last_withdrawal_time = None
        self.withdrawal_history = []
        self.spike_detector = SpikeDetector(
            lookback_periods=50,
            std_dev_threshold=self.spike_std_threshold
        )
        
        logger.info(f"✅ IntelligentWithdrawal initialized (mode={self.mode}, target={self.target_profit})")
    
    def can_withdraw_now(self) -> bool:
        """Check if enough time has passed since last withdrawal"""
        if self.last_withdrawal_time is None:
            return True
        
        elapsed_hours = (time.time() - self.last_withdrawal_time) / 3600
        return elapsed_hours >= self.min_hours_between_withdrawals
    
    def evaluate_withdrawal_conditions(
        self,
        current_profit: float,
        win_rate: float,
        current_price: float,
        symbol: str,
        account_balance: float,
        open_trades_count: int = 0,
        max_drawdown_percent: float = 0
    ) -> Dict:
        """
        Comprehensive evaluation of whether to withdraw profit
        
        Returns:
            {
                'should_withdraw': bool,
                'withdrawal_amount': float,
                'trigger': WithdrawalTrigger,
                'confidence': float (0-100),
                'analysis': {details of analysis},
                'recommendation': 'string explaining decision'
            }
        """
        
        # ==================== BASIC CHECKS ====================
        analysis = {
            'current_profit': current_profit,
            'win_rate': win_rate,
            'minimum_profit_check': current_profit >= self.min_profit,
            'open_trades': open_trades_count,
            'account_balance': account_balance,
            'max_drawdown_percent': max_drawdown_percent
        }
        
        # Check if price history has enough data
        if symbol not in self.spike_detector.price_history:
            return {
                'should_withdraw': False,
                'withdrawal_amount': 0,
                'trigger': None,
                'confidence': 0,
                'analysis': {**analysis, 'reason': 'no_market_data'},
                'recommendation': 'Insufficient market data collected. Wait for more price samples.'
            }
        
        # ==================== RULE 1: MINIMUM PROFIT CHECK ====================
        if current_profit < self.min_profit:
            return {
                'should_withdraw': False,
                'withdrawal_amount': 0,
                'trigger': None,
                'confidence': 0,
                'analysis': {**analysis, 'reason': 'profit_below_minimum'},
                'recommendation': f'Profit ${current_profit:.2f} is below minimum ${self.min_profit:.2f}. Wait for more profit.'
            }
        
        # ==================== RULE 2: TIME-BASED COOLDOWN ====================
        if not self.can_withdraw_now():
            time_remaining_hours = self.min_hours_between_withdrawals - (
                (time.time() - self.last_withdrawal_time) / 3600
            )
            return {
                'should_withdraw': False,
                'withdrawal_amount': 0,
                'trigger': None,
                'confidence': 0,
                'analysis': {**analysis, 'reason': 'cooldown_active', 'hours_remaining': round(time_remaining_hours, 1)},
                'recommendation': f'Last withdrawal was {self.min_hours_between_withdrawals} hours ago. Wait {time_remaining_hours:.1f} more hours.'
            }
        
        # ==================== RULE 3: OPEN TRADES PROTECTION ====================
        if open_trades_count > 0 and self.mode == 'intelligent':
            # In intelligent mode, don't withdraw if trades are open (avoid interfering with active positions)
            return {
                'should_withdraw': False,
                'withdrawal_amount': 0,
                'trigger': None,
                'confidence': 0,
                'analysis': {**analysis, 'reason': 'open_trades_protection'},
                'recommendation': f'Have {open_trades_count} open trade(s). Wait for all trades to close before intelligent withdrawal.'
            }
        
        # ==================== RULE 4: DRAWDOWN PROTECTION ====================
        if max_drawdown_percent > 10:  # If already in significant drawdown
            # In this case, withdraw smaller amounts more frequently to protect capital
            withdrawal_amount = min(current_profit * 0.5, self.target_profit * 0.3)
            return {
                'should_withdraw': True,
                'withdrawal_amount': withdrawal_amount,
                'trigger': WithdrawalTrigger.DRAWDOWN_PROTECTION,
                'confidence': 75,
                'analysis': {**analysis, 'reason': 'drawdown_protection', 'withdrawal_mode': 'defensive'},
                'recommendation': f'In drawdown ({max_drawdown_percent:.1f}%). Withdrawing ${withdrawal_amount:.2f} to protect capital.'
            }
        
        # ==================== MODE-SPECIFIC LOGIC ====================
        if self.mode == 'fixed' or self.mode == 'hybrid':
            # FIXED MODE: Withdraw when target is reached (simple and reliable)
            if current_profit >= self.target_profit:
                return {
                    'should_withdraw': True,
                    'withdrawal_amount': min(current_profit * 0.8, self.target_profit),
                    'trigger': WithdrawalTrigger.FIXED_TARGET,
                    'confidence': 100,
                    'analysis': {**analysis, 'reason': 'target_reached'},
                    'recommendation': f'Fixed target of ${self.target_profit:.2f} reached. Withdrawing ${min(current_profit * 0.8, self.target_profit):.2f}.'
                }
        
        if self.mode == 'intelligent' or self.mode == 'hybrid':
            # INTELLIGENT MODE: Analyze market conditions for optimal withdrawal
            
            # Add current price to history for spike detection
            self.spike_detector.add_price_data(symbol, current_price)
            
            # ==================== CHECK MARKET CONDITION ====================
            condition, condition_analysis = self.spike_detector.detect_market_condition(symbol, current_price)
            analysis['market_condition'] = condition_analysis
            
            # ==================== CHECK WIN RATE ====================
            win_rate_ok = win_rate >= self.win_rate_min
            analysis['win_rate_ok'] = win_rate_ok
            
            if not win_rate_ok and self.mode == 'intelligent':
                return {
                    'should_withdraw': False,
                    'withdrawal_amount': 0,
                    'trigger': None,
                    'confidence': 0,
                    'analysis': {**analysis, 'reason': 'low_win_rate'},
                    'recommendation': f'Win rate {win_rate:.1f}% is below minimum {self.win_rate_min:.1f}%. Wait for better trading performance.'
                }
            
            # ==================== DETECT SPIKE CONDITIONS ====================
            is_spike, spike_info = self.spike_detector.is_spike_detected(symbol, current_price)
            analysis['spike_analysis'] = spike_info
            
            if is_spike and win_rate_ok:
                # SPIKE DETECTED + GOOD WIN RATE = High confidence withdrawal
                confidence = 95
                # Withdraw more aggressively during spikes
                withdrawal_amount = min(current_profit * 0.9, self.max_profit)
                
                return {
                    'should_withdraw': True,
                    'withdrawal_amount': withdrawal_amount,
                    'trigger': WithdrawalTrigger.SPIKE_DETECTED,
                    'confidence': confidence,
                    'analysis': {**analysis, 'reason': 'spike_detected_high_winrate'},
                    'recommendation': f'🚀 SPIKE DETECTED! {spike_info["spike_direction"].upper()} {spike_info["percent_above_ma"]:.1f}% from MA. Win rate {win_rate:.1f}% ✓. Withdrawing ${withdrawal_amount:.2f} at peak.'
                }
            
            elif not is_spike and current_profit >= self.target_profit * 1.5:
                # No spike, but profit is high = medium confidence withdrawal
                confidence = 70
                withdrawal_amount = self.target_profit
                
                return {
                    'should_withdraw': True,
                    'withdrawal_amount': withdrawal_amount,
                    'trigger': WithdrawalTrigger.PROFIT_LOCK,
                    'confidence': confidence,
                    'analysis': {**analysis, 'reason': 'profit_lock', 'market_condition': condition.value},
                    'recommendation': f'Profit locked: ${withdrawal_amount:.2f}. Market is {condition.value}. Good time to secure gains.'
                }
        
        # ==================== DEFAULT: NO WITHDRAWAL ====================
        return {
            'should_withdraw': False,
            'withdrawal_amount': 0,
            'trigger': None,
            'confidence': 0,
            'analysis': analysis,
            'recommendation': 'Waiting for better withdrawal conditions (spike, high win rate, or more profit).'
        }
    
    def record_withdrawal(self, amount: float, trigger: WithdrawalTrigger, symbol: str = None):
        """Record a withdrawal in history"""
        self.last_withdrawal_time = time.time()
        record = {
            'timestamp': datetime.now().isoformat(),
            'amount': amount,
            'trigger': trigger.value if trigger else None,
            'symbol': symbol
        }
        self.withdrawal_history.append(record)
        logger.info(f"💰 Withdrawal recorded: ${amount:.2f} ({trigger.value if trigger else 'unknown'})")
    
    def get_withdrawal_statistics(self) -> Dict:
        """Get statistics about past withdrawals"""
        if not self.withdrawal_history:
            return {
                'total_withdrawals': 0,
                'total_amount_withdrawn': 0,
                'average_withdrawal': 0,
                'last_withdrawal': None,
                'history': []
            }
        
        amounts = [w['amount'] for w in self.withdrawal_history]
        
        return {
            'total_withdrawals': len(self.withdrawal_history),
            'total_amount_withdrawn': sum(amounts),
            'average_withdrawal': sum(amounts) / len(amounts),
            'min_withdrawal': min(amounts),
            'max_withdrawal': max(amounts),
            'last_withdrawal': self.withdrawal_history[-1]['timestamp'],
            'triggers_used': {
                trigger: sum(1 for w in self.withdrawal_history if w['trigger'] == trigger)
                for trigger in set(w['trigger'] for w in self.withdrawal_history)
            }
        }

