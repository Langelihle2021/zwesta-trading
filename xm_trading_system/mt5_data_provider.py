"""
MT5 Data Provider - Fetches live trading data from MetaTrader5 account
Integrates with the Flask dashboard to show real positions, trades, and commodities
"""
import json
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class MT5DataProvider:
    def __init__(self):
        self.initialized = False
        self.account_info = None
        self.positions = []
        self.trades = []
        self.symbols = []
        
    def connect(self, account_id=None, password=None, server=None):
        """Connect to MT5 account - uses already logged-in terminal if available"""
        if not MT5_AVAILABLE:
            print("[MT5] MetaTrader5 library not available")
            return False
            
        try:
            # Try to initialize without re-logging in (terminal already authorized)
            if not mt5.initialize():
                print(f"[MT5] Initialize attempt 1 failed: {mt5.last_error()}")
                # Try explicit path
                if not mt5.initialize(path="C:\\Program Files\\MetaTrader 5\\terminal64.exe"):
                    print(f"[MT5] Initialize attempt 2 failed: {mt5.last_error()}")
                    return False
            
            # Check if already logged in
            account_info = mt5.account_info()
            if account_info:
                print(f"[MT5] Connected to existing session: {account_info.name} (Account {account_info.login})")
                self.initialized = True
                return True
            
            # If not logged in and credentials provided, try to login
            if account_id and password and server:
                if mt5.login(account_id, password, server):
                    print(f"[MT5] Successfully logged in to {account_id}")
                    self.initialized = True
                    return True
                else:
                    error = mt5.last_error()
                    print(f"[MT5] Login failed: {error}")
            
            # Final check - are we connected even without explicit login?
            account_info = mt5.account_info()
            if account_info:
                print(f"[MT5] Connected to account: {account_info.name}")
                self.initialized = True
                return True
            else:
                print(f"[MT5] No account info available")
                return False
                
        except Exception as e:
            print(f"[MT5] Connection error: {e}")
            return False
            return True
        except Exception as e:
            print(f"[MT5] Connection error: {e}")
            return False
    
    def get_account_info(self):
        """Get current account balance and equity"""
        if not self.initialized or not MT5_AVAILABLE:
            return None
        
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return None
            
            return {
                'balance': account_info.balance,
                'equity': account_info.equity,
                'profit': account_info.profit,
                'margin': account_info.margin,
                'margin_free': account_info.margin_free,
                'margin_level': account_info.margin_level,
                'currency': account_info.currency
            }
        except Exception as e:
            print(f"[MT5] Error getting account info: {e}")
            return None
    
    def get_positions(self):
        """Get all open positions"""
        if not self.initialized or not MT5_AVAILABLE:
            return []
        
        try:
            positions = mt5.positions_get()
            if positions is None:
                return []
            
            result = []
            for pos in positions:
                result.append({
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'Buy' if pos.type == 0 else 'Sell',
                    'volume': pos.volume,
                    'open_price': pos.price_open,
                    'current_price': pos.price_current,
                    'profit': pos.profit,
                    'profit_percent': (pos.profit / (pos.volume * pos.price_open) * 100) if pos.price_open > 0 else 0,
                    'open_time': datetime.fromtimestamp(pos.time).isoformat(),
                    'stop_loss': pos.sl,
                    'take_profit': pos.tp,
                    'comment': pos.comment
                })
            return result
        except Exception as e:
            print(f"[MT5] Error getting positions: {e}")
            return []
    
    def get_closed_trades(self, days=30):
        """Get closed trades from the last N days"""
        if not self.initialized or not MT5_AVAILABLE:
            return []
        
        try:
            from_date = datetime.now() - timedelta(days=days)
            deals = mt5.history_deals_get(from_date, datetime.now())
            
            if deals is None:
                return []
            
            result = []
            for deal in deals:
                result.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'entry_time': datetime.fromtimestamp(deal.time).isoformat(),
                    'type': 'Buy' if deal.type == 0 else 'Sell',
                    'volume': deal.volume,
                    'entry_price': deal.price,
                    'commission': deal.commission,
                    'profit': deal.profit,
                    'comment': deal.comment
                })
            return result
        except Exception as e:
            print(f"[MT5] Error getting trades: {e}")
            return []
    
    def get_symbols(self):
        """Get list of tradeable symbols"""
        if not self.initialized or not MT5_AVAILABLE:
            return ['GOLD', 'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'XAUUSD']
        
        try:
            symbols = mt5.symbols_get()
            if symbols is None:
                return []
            
            return [s.name for s in symbols if s.visible]
        except Exception as e:
            print(f"[MT5] Error getting symbols: {e}")
            return []
    
    def get_symbol_info(self, symbol):
        """Get current quote for a symbol"""
        if not self.initialized or not MT5_AVAILABLE:
            return None
        
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
            
            return {
                'symbol': symbol,
                'bid': info.bid,
                'ask': info.ask,
                'last': info.last,
                'volume': info.volume,
                'time': datetime.fromtimestamp(info.time).isoformat()
            }
        except Exception as e:
            print(f"[MT5] Error getting symbol info for {symbol}: {e}")
            return None
    
    def get_dashboard_summary(self):
        """Get complete dashboard summary with all live data"""
        account = self.get_account_info()
        if not account:
            return None
        
        positions = self.get_positions()
        trades = self.get_closed_trades(30)
        
        # Calculate statistics
        total_profit = sum(p['profit'] for p in positions)
        winning_trades = len([t for t in trades if t['profit'] > 0])
        total_trades = len(trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'account': account,
            'positions': positions,
            'trades': trades,
            'statistics': {
                'open_positions': len(positions),
                'total_profit': total_profit,
                'unrealized_profit': account['profit'],
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': round(win_rate, 2),
                'profit_factor': account['equity'] / abs(account['balance'] - account['equity']) if account['balance'] != account['equity'] else 0
            }
        }


# Global provider instance
mt5_provider = MT5DataProvider()

def init_mt5_provider():
    """Initialize MT5 provider with credentials"""
    # These should come from environment or config
    mt5_provider.connect(
        account_id=103672035,
        password='3bhNjYy',
        server='MetaQuotes-Demo'
    )

if __name__ == '__main__':
    init_mt5_provider()
    summary = mt5_provider.get_dashboard_summary()
    print(json.dumps(summary, indent=2, default=str))
