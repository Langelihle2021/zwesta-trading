#!/usr/bin/env python3
"""
Add missing two_factor_enabled column to users table if it doesn't exist
"""
import sqlite3

def add_2fa_column():
    """Add two_factor_enabled column to users table"""
    conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'two_factor_enabled' not in columns:
            print("Adding two_factor_enabled column...")
            cursor.execute('ALTER TABLE users ADD COLUMN two_factor_enabled INTEGER DEFAULT 0')
            conn.commit()
            print("✅ Column added successfully")
        else:
            print("✅ Column already exists")
        
        # Now disable 2FA for all users
        print("\nDisabling 2FA for all users...")
        cursor.execute('UPDATE users SET two_factor_enabled = 0')
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        print(f"✅ 2FA disabled for {count} users")
        
        # Show status
        cursor.execute('SELECT email, two_factor_enabled FROM users LIMIT 5')
        print("\nFirst 5 users:")
        for row in cursor.fetchall():
            status = "ENABLED" if row[1] else "DISABLED"
            print(f"  {row[0]:35} 2FA: {status}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    add_2fa_column()
