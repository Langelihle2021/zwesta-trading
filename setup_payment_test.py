#!/usr/bin/env python3
"""
Setup test user and session for payment endpoint testing
"""

import sqlite3
import uuid
from datetime import datetime, timedelta

def setup_test_environment():
    """Create test user and valid session in database"""
    
    conn = sqlite3.connect('zwesta_trading.db')
    cursor = conn.cursor()
    
    # Test credentials
    test_user_id = "test_user_payment_001"
    test_session_token = "session_test_payment_" + str(uuid.uuid4())[:20]
    test_referral_code = "paymenttest" + str(uuid.uuid4())[:8]
    
    # Create test user
    try:
        cursor.execute('''
            INSERT INTO users (user_id, email, name, referral_code, created_at, total_commission)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_user_id, "payment@test.com", "Payment Test User", test_referral_code, 
              datetime.now().isoformat(), 0))
        print(f"[+] Created test user: {test_user_id}")
    except sqlite3.IntegrityError as e:
        print(f"[*] Test user already exists: {test_user_id}")
        # Delete old sessions
        cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (test_user_id,))
    
    # Create session record
    session_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7)
    cursor.execute('''
        INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, ip_address, user_agent, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, test_user_id, test_session_token, datetime.now().isoformat(), 
          expires_at.isoformat(), "127.0.0.1", "test_client", 1))
    print(f"[+] Created session token: {test_session_token}")
    
    # Verify session was created
    cursor.execute('SELECT * FROM user_sessions WHERE token = ?', (test_session_token,))
    session = cursor.fetchone()
    if session:
        print(f"[+] Session verified in database")
    
    conn.commit()
    conn.close()
    
    return test_user_id, test_session_token

if __name__ == "__main__":
    user_id, token = setup_test_environment()
    print(f"\nTest credentials ready:")
    print(f"User ID: {user_id}")
    print(f"Session Token: {token}")
    print(f"\nUse this header in requests:")
    print(f"X-Session-Token: {token}")
