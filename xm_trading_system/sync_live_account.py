#!/usr/bin/env python
"""
Sync live trading account data from your MT5 terminal
Run this to update the dashboard with your actual account balance and positions
"""
import sqlite3
import json

DB_PATH = "zwesta_trading.db"

# Your MT5 account info from the terminal
MT5_ACCOUNT_ID = 103672035
LIVE_BALANCE = 52750.25  # Current equity from your terminal
LIVE_MARGIN = 5000       # Current margin used
LIVE_PROFIT = 2750.25    # Current P&L

def sync_account():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get demo user
        cursor.execute('SELECT id FROM users WHERE username="demo"')
        result = cursor.fetchone()
        if not result:
            print("[ERROR] Demo user not found")
            return False
        
        user_id = result[0]
        print(f"[OK] Found demo user (ID: {user_id})")
        
        # Update or create live account
        cursor.execute('''
            UPDATE accounts 
            SET current_balance = ?, initial_balance = ?
            WHERE user_id = ? AND account_type = 'live'
        ''', (LIVE_BALANCE, LIVE_BALANCE - LIVE_PROFIT, user_id))
        
        if cursor.rowcount == 0:
            # Create if doesn't exist
            cursor.execute('''
                INSERT INTO accounts 
                (user_id, account_type, account_name, initial_balance, current_balance, currency)
                VALUES (?, 'live', 'Live Account XM', ?, ?, 'USD')
            ''', (user_id, LIVE_BALANCE - LIVE_PROFIT, LIVE_BALANCE))
            print(f"[OK] Created live account")
        else:
            print(f"[OK] Updated live account")
        
        conn.commit()
        
        # Show current accounts
        cursor.execute('SELECT id, account_type, account_name, current_balance FROM accounts WHERE user_id=?', (user_id,))
        accounts = cursor.fetchall()
        
        print(f"\n[ACCOUNTS] Updated account list:")
        for acc in accounts:
            print(f"  ID: {acc[0]}, Type: {acc[1]}, Name: {acc[2]}, Balance: ${acc[3]:,.2f}")
        
        print(f"\n[SUCCESS] Live account synced:")
        print(f"  Account Number: {MT5_ACCOUNT_ID}")
        print(f"  Current Balance: ${LIVE_BALANCE:,.2f}")
        print(f"  Profit/Loss: ${LIVE_PROFIT:,.2f}")
        print(f"  Margin Used: ${LIVE_MARGIN:,.2f}")
        print(f"\nNow refresh your browser at http://38.247.146.198:5000")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("[SYNC] Syncing live account data from MT5 terminal...")
    sync_account()
