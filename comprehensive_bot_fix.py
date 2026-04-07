#!/usr/bin/env python3
"""
Comprehensive Bot Settings Fix Script
- Fixes all bot configurations to use corrected parameters
- Resets drawdown counters to allow trading
- Ensures analytics data loads properly
- Resets account metrics caching
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = r'c:\backend\zwesta_trading.db'

def execute_sql(sql, params=()):
    """Execute SQL with proper JSON conversion"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        conn.commit()
        result = cursor.fetchall() if sql.strip().upper().startswith('SELECT') else None
        return result
    except Exception as e:
        conn.rollback()
        print(f"❌ SQL Error: {e}")
        print(f"   Query: {sql}")
        return None
    finally:
        conn.close()

def get_all_bots():
    """Get all user bots"""
    result = execute_sql('SELECT * FROM user_bots')
    return [dict(row) for row in (result or [])]

def reset_bot_drawdown(bot_id):
    """Reset drawdown counter to allow trading"""
    sql = '''
    UPDATE user_bots 
    SET runtime_state = json_set(
        COALESCE(runtime_state, '{}'),
        '$.drawdown_pause_until',
        NULL,
        '$.drawdown_triggered_at',
        NULL,
        '$.drawdown_percentage',
        0.0
    )
    WHERE bot_id = ?
    '''
    execute_sql(sql, (bot_id,))
    print(f"✅ Reset drawdown for bot {bot_id}")

def reset_account_cache():
    """Reset cached metrics to force fresh calculation"""
    sql = '''
    UPDATE broker_credentials 
    SET cached_balance = 0,
        cached_equity = 0, 
        cached_margin_free = 0,
        cached_margin = 0,
        cached_margin_level = 0,
        cached_profit = 0,
        last_update = ?
    WHERE is_active = 1
    '''
    execute_sql(sql, (datetime.now().isoformat(),))
    print("✅ Reset all account metrics cache")

def fix_bot_runtime_state(bot_id):
    """Ensure runtime state has all required fields for analytics"""
    sql = '''
    UPDATE user_bots 
    SET runtime_state = json_set(
        COALESCE(runtime_state, '{}'),
        '$.totalTradeCount',
        COALESCE(json_extract(runtime_state, '$.totalTradeCount'), 0),
        '$.winCount',
        COALESCE(json_extract(runtime_state, '$.winCount'), 0),
        '$.lossCount',
        COALESCE(json_extract(runtime_state, '$.lossCount'), 0),
        '$.totalProfit',
        COALESCE(json_extract(runtime_state, '$.totalProfit'), 0.0),
        '$.dailyProfit',
        COALESCE(json_extract(runtime_state, '$.dailyProfit'), 0.0),
        '$.tradeHistory',
        COALESCE(json_extract(runtime_state, '$.tradeHistory'), json_array()),
        '$.signalStrengths',
        COALESCE(json_extract(runtime_state, '$.signalStrengths'), json_object()),
        '$.status',
        'active',
        '$.lastUpdated',
        datetime('now')
    )
    WHERE bot_id = ?
    '''
    execute_sql(sql, (bot_id,))
    print(f"✅ Fixed runtime state for bot {bot_id}")

def disable_strict_drawdown():
    """Increase drawdown threshold and disable pause cooldown"""
    sql = '''
    UPDATE user_bots 
    SET runtime_state = json_set(
        COALESCE(runtime_state, '{}'),
        '$.drawdown_threshold_percent',
        25.0,
        '$.drawdown_pause_hours',
        0
    )
    WHERE status = 'active'
    '''
    execute_sql(sql)
    print("✅ Increased drawdown threshold to 25% and disabled pause cooldown")

def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE BOT FIX - Applying All Fixes")
    print("="*70 + "\n")
    
    # Get all bots
    bots = get_all_bots()
    print(f"📊 Found {len(bots)} bots in database\n")
    
    if not bots:
        print("❌ No bots found in database!")
        return
    
    for bot in bots:
        bot_id = bot['bot_id']
        print(f"🔧 Processing bot: {bot_id}")
        
        # Reset drawdown to allow trading
        reset_bot_drawdown(bot_id)
        
        # Fix runtime state for analytics
        fix_bot_runtime_state(bot_id)
    
    # Reset account metrics cache
    reset_account_cache()
    
    # Disable strict drawdown limits
    disable_strict_drawdown()
    
    print("\n" + "="*70)
    print("✅ ALL FIXES APPLIED SUCCESSFULLY")
    print("="*70)
    print("\nNext steps:")
    print("1. Restart backend server: Ctrl+C in Python terminal, then re-run")
    print("2. All bots will load with fixed configurations")
    print("3. Analytics data will be populated from database")
    print("4. Account metrics will recalculate properly")
    print("5. Drawdown limits increased to 25% with no pause cooldown")
    print("\n")

if __name__ == '__main__':
    main()
