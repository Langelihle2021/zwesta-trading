#!/usr/bin/env python3
"""
Create a demo bot for testing
"""

import sqlite3
from datetime import datetime
import json

DB_PATH = r"C:\backend\zwesta_trading.db"

def create_demo_bot():
    """Create a simple BTC demo bot"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("🤖 CREATING DEMO BOT FOR TESTING")
        print("=" * 70)
        
        # Bot config
        bot_id = "demo_btc_test_001"
        user_id = "user_demo_1"
        bot_config = {
            "strategy": "signal-based",
            "symbols": ["BTCUSDm"],
            "timeframe": 5,
            "risk_per_trade": 2.0,
            "max_positions": 1,
            "take_profit": 100,  # $100 profit target
            "stop_loss": 50,     # $50 max loss
        }
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO users (user_id, email, first_name, last_name, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, 'demo@test.com', 'Demo', 'User', 'hash..', datetime.now().isoformat()))
            print("✅ Created demo user")
        
        # Check if credential exists
        cursor.execute("SELECT credential_id FROM broker_credentials WHERE credential_id = ?", 
                      ('cred_demo_exness_btc',))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('cred_demo_exness_btc', user_id, 'Exness', '298997455', 'password', 
                  'Exness-MT5Trial9', 0, datetime.now().isoformat()))
            print("✅ Created demo credentials")
        
        # Create bot
        cursor.execute('''
            INSERT INTO user_bots 
            (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, is_live, runtime_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bot_id, user_id, 'Demo BTC Test', 'signal-based', 'inactive', 1, 
              '298997455', 'BTCUSDm', 0, json.dumps(bot_config), 
              datetime.now().isoformat(), datetime.now().isoformat()))
        print(f"✅ Created bot: {bot_id}")
        
        # Link bot to credentials
        cursor.execute('''
            INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
        ''', (bot_id, 'cred_demo_exness_btc', user_id, datetime.now().isoformat()))
        print(f"✅ Linked bot to credentials")
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print("✅ DEMO BOT CREATED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\nBot Details:")
        print(f"  Bot ID: {bot_id}")
        print(f"  User: {user_id} (Demo User)")
        print(f"  Symbol: BTCUSDm (Bitcoin)")
        print(f"  Strategy: Signal-based with TP/SL")
        print(f"  Account: Exness Demo #298997455")
        print(f"  Status: Ready to start trading")
        print(f"\n💡 To activate: Start the bot from the Flutter app")
        print(f"   The bot will begin trading automatically every 5 minutes")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    create_demo_bot()
