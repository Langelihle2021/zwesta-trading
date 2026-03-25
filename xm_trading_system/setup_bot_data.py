"""
Setup MetaTrader credentials and generate sample trading data
"""
import sqlite3
from datetime import datetime, timedelta
import random

DB_PATH = "zwesta_trading.db"

def setup_mt5_credentials():
    """Add MetaTrader credentials for demo user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if demo user exists
        cursor.execute("SELECT id FROM users WHERE username='demo'")
        user = cursor.fetchone()
        
        if not user:
            print("❌ Demo user not found!")
            return False
        
        user_id = user[0]
        
        # Check if credentials already exist
        cursor.execute("SELECT id FROM mt5_credentials WHERE user_id=?", (user_id,))
        if cursor.fetchone():
            print("✓ Credentials already exist for demo user")
            conn.close()
            return True
        
        # Insert default MetaTrader credentials (demo account)
        cursor.execute('''
            INSERT INTO mt5_credentials (user_id, mt5_account, mt5_password, mt5_server, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, 103672035, '3bhNjYy', 'MetaQuotes-Demo', 1))
        
        conn.commit()
        print(f"✓ Added MT5 credentials for user {user_id} (demo)")
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.close()
        return False

def generate_sample_trades():
    """Generate sample trading data for dashboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get first account (demo)
        cursor.execute("SELECT id FROM accounts WHERE account_type='demo' LIMIT 1")
        account = cursor.fetchone()
        
        if not account:
            print("❌ No demo account found!")
            return False
        
        account_id = account[0]
        
        # Check existing trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE account_id=?", (account_id,))
        trade_count = cursor.fetchone()[0]
        
        if trade_count > 0:
            print(f"✓ Account already has {trade_count} trades")
            conn.close()
            return True
        
        # Generate 5 sample trades
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'GOLD', 'XAUUSD']
        now = datetime.now()
        
        for i, symbol in enumerate(symbols):
            entry_price = random.uniform(100, 2000)
            exit_price = entry_price * random.uniform(0.99, 1.02)
            quantity = round(random.uniform(1, 10), 2)
            profit = (exit_price - entry_price) * quantity
            profit_percent = ((exit_price - entry_price) / entry_price) * 100
            
            open_date = now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
            close_date = open_date + timedelta(hours=random.randint(1, 48))
            
            cursor.execute('''
                INSERT INTO trades 
                (account_id, symbol, entry_price, exit_price, quantity, status, open_date, close_date, profit_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id, symbol, round(entry_price, 5), round(exit_price, 5), quantity,
                'closed', open_date.isoformat(), close_date.isoformat(), round(profit_percent, 2)
            ))
        
        conn.commit()
        print(f"✓ Generated 5 sample trades for account {account_id}")
        conn.close()
        return True
    
    except Exception as e:
        print(f"❌ Error generating trades: {e}")
        conn.close()
        return False

if __name__ == '__main__':
    print("=== SETTING UP BOT DATA ===\n")
    
    print("[1] Adding MT5 Credentials...")
    setup_mt5_credentials()
    
    print("\n[2] Generating Sample Trades...")
    generate_sample_trades()
    
    print("\n✓ Setup complete! Bot should now have data to process.")
