#!/usr/bin/env python3
"""
Quick script to disable 2FA for all users or a specific user
"""
import sqlite3
import sys

def disable_2fa_all():
    """Disable 2FA for all users"""
    # Try backend db first, then try local paths
    db_paths = [
        r'C:\backend\zwesta_trading.db',  # VPS path
        'zwesta_trading.db',              # Current directory
        'backend.db'                      # Fallback
    ]
    
    conn = None
    for db_path in db_paths:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1 FROM users LIMIT 1")  # Test if users table exists
            print(f"✅ Connected to: {db_path}\n")
            break
        except:
            conn = None
            continue
    
    if not conn:
        print("❌ Could not connect to any database")
        return
    cursor = conn.cursor()
    
    try:
        # Disable 2FA for all users
        cursor.execute('UPDATE users SET two_factor_enabled = 0')
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE two_factor_enabled = 0')
        count = cursor.fetchone()[0]
        print(f"✅ 2FA disabled for {count} users")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

def check_2fa_status():
    """Check which users have 2FA enabled"""
    # Try backend db first, then try local paths
    db_paths = [
        r'C:\backend\zwesta_trading.db',  # VPS path
        'zwesta_trading.db',              # Current directory
        'backend.db'                      # Fallback
    ]
    
    conn = None
    for db_path in db_paths:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1 FROM users LIMIT 1")  # Test if users table exists
            break
        except:
            conn = None
            continue
    
    if not conn:
        print("❌ Could not connect to any database")
        return
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT user_id, email, two_factor_enabled FROM users LIMIT 10')
        rows = cursor.fetchall()
        
        print("\nUser 2FA Status:")
        for row in rows:
            status = "✅ ENABLED" if row[2] else "❌ DISABLED"
            print(f"  {row[1]:30} {status}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    print("Disabling 2FA...\n")
    check_2fa_status()
    disable_2fa_all()
    check_2fa_status()
