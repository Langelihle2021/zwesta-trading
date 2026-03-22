#!/usr/bin/env python3
"""
Comprehensive Payment System Test Suite
Tests all payment endpoints and workflows
"""

import requests
import json
import sqlite3
from datetime import datetime

BASE_URL = "http://localhost:9000"
TEST_USER_ID = "test_user_payment_system"
VALID_SESSION_TOKEN = "test_session_token_12345"

# Colors for console output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def setup_test_user():
    """Create test user and session in database"""
    try:
        conn = sqlite3.connect('zwesta_trading.db')
        cursor = conn.cursor()
        
        # Insert test user if not exists
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, email, name, created_at)
            VALUES (?, ?, ?, ?)
        ''', (TEST_USER_ID, 'test@payment.com', 'Test User', datetime.now()))
        
        # Insert test session
        cursor.execute('''
            INSERT OR REPLACE INTO user_sessions (session_id, user_id, token, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', ('session_1', TEST_USER_ID, VALID_SESSION_TOKEN, datetime.now(), '2099-12-31'))
        
        conn.commit()
        conn.close()
        print(f"{GREEN}✓{RESET} Test user and session created")
        return True
    except Exception as e:
        print(f"{RED}✗ Failed to setup test user: {e}{RESET}")
        return False

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{BLUE}{'='*60}")
    print(f"  {test_name}")
    print(f"{'='*60}{RESET}")

def print_response(response, test_name):
    """Pretty print response"""
    print(f"\nStatus: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
        return data
    except:
        print(response.text)
        return None

def test_get_payment_methods():
    """Test GET /api/user/payment-methods"""
    print_test_header("TEST 1: Get Payment Methods")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f"{BASE_URL}/api/user/payment-methods", headers=headers)
    data = print_response(response, "Get payment methods")
    
    if response.status_code == 200:
        print(f"{GREEN}✓ PASS: Got payment methods list{RESET}")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 200, got {response.status_code}{RESET}")
        return False

def test_add_stripe_payment_method():
    """Test POST /api/user/payment-method - Stripe"""
    print_test_header("TEST 2: Add Stripe Payment Method")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "type": "stripe",
        "stripeAccountId": "acct_1234567890abcdef",
        "makePrimary": True
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/payment-method",
        headers=headers,
        json=payload
    )
    data = print_response(response, "Add Stripe payment method")
    
    if response.status_code == 201:
        print(f"{GREEN}✓ PASS: Stripe payment method added{RESET}")
        return True, data.get('methodId') if data else None
    else:
        print(f"{RED}✗ FAIL: Expected 201, got {response.status_code}{RESET}")
        return False, None

def test_add_bank_payment_method():
    """Test POST /api/user/payment-method - Bank Transfer"""
    print_test_header("TEST 3: Add Bank Transfer Payment Method")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "type": "bank",
        "makePrimary": False,
        "bank": {
            "bankName": "Chase",
            "accountHolder": "Test Account",
            "accountNumber": "1234567890",
            "routingNumber": "021000021",
            "swiftCode": "CHASUS33"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/payment-method",
        headers=headers,
        json=payload
    )
    data = print_response(response, "Add bank payment method")
    
    if response.status_code == 201:
        print(f"{GREEN}✓ PASS: Bank payment method added{RESET}")
        return True, data.get('methodId') if data else None
    else:
        print(f"{RED}✗ FAIL: Expected 201, got {response.status_code}{RESET}")
        return False, None

def test_add_crypto_payment_method():
    """Test POST /api/user/payment-method - Crypto"""
    print_test_header("TEST 4: Add Crypto Payment Method")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "type": "crypto",
        "wallet": "0x742d35Cc6634C0532925A3b844Bc830e2b7f89f",
        "cryptoType": "USDT",
        "makePrimary": False
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/payment-method",
        headers=headers,
        json=payload
    )
    data = print_response(response, "Add crypto payment method")
    
    if response.status_code == 201:
        print(f"{GREEN}✓ PASS: Crypto payment method added{RESET}")
        return True, data.get('methodId') if data else None
    else:
        print(f"{RED}✗ FAIL: Expected 201, got {response.status_code}{RESET}")
        return False, None

def test_verify_payment_methods():
    """Test GET /api/user/payment-methods - Verify all methods added"""
    print_test_header("TEST 5: Verify All Payment Methods")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f"{BASE_URL}/api/user/payment-methods", headers=headers)
    data = print_response(response, "Get all payment methods")
    
    if response.status_code == 200 and data and data.get('count', 0) >= 3:
        print(f"{GREEN}✓ PASS: All 3 payment methods were added{RESET}")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 3+ payment methods, got {data.get('count', 0) if data else 0}{RESET}")
        return False

def test_commission_payout_insufficient():
    """Test POST /api/user/commission-payout - Insufficient balance"""
    print_test_header("TEST 6: Commission Payout - Insufficient Balance")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "method": "stripe",
        "minAmount": 50
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/commission-payout",
        headers=headers,
        json=payload
    )
    data = print_response(response, "Request commission payout (insufficient)")
    
    if response.status_code == 400:
        print(f"{GREEN}✓ PASS: Correctly rejected insufficient balance{RESET}")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 400, got {response.status_code}{RESET}")
        return False

def add_test_commissions():
    """Add test commission data to database"""
    try:
        conn = sqlite3.connect('zwesta_trading.db')
        cursor = conn.cursor()
        
        # Add test commission
        cursor.execute('''
            INSERT INTO commission_ledger (entry_id, commission_id, user_id, source_user_id, type, amount, payout_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('entry_1', 'comm_1', TEST_USER_ID, 'source_user_1', 'profit_share', 150.0, 'pending', datetime.now()))
        
        conn.commit()
        conn.close()
        print(f"{GREEN}✓ Test commission added ($150.00){RESET}")
        return True
    except Exception as e:
        print(f"{RED}✗ Failed to add test commission: {e}{RESET}")
        return False

def test_commission_payout_success():
    """Test POST /api/user/commission-payout - Success"""
    print_test_header("TEST 7: Commission Payout - Successful")
    
    # First add commission
    add_test_commissions()
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "method": "internal",  # Use internal to avoid external API calls
        "minAmount": 50
    }
    
    response = requests.post(
        f"{BASE_URL}/api/user/commission-payout",
        headers=headers,
        json=payload
    )
    data = print_response(response, "Request commission payout (success)")
    
    if response.status_code == 200:
        print(f"{GREEN}✓ PASS: Commission payout processed successfully{RESET}")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 200, got {response.status_code}{RESET}")
        return False

def test_get_transactions():
    """Test GET /api/user/transactions"""
    print_test_header("TEST 8: Get Transaction History")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(
        f"{BASE_URL}/api/user/transactions?limit=50",
        headers=headers
    )
    data = print_response(response, "Get transaction history")
    
    if response.status_code == 200:
        print(f"{GREEN}✓ PASS: Transaction history retrieved{RESET}")
        if data:
            print(f"   Found {data.get('count', 0)} transactions")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 200, got {response.status_code}{RESET}")
        return False

def test_get_transactions_filtered():
    """Test GET /api/user/transactions - Filtered by type"""
    print_test_header("TEST 9: Get Transactions - Filtered")
    
    headers = {
        'X-Session-Token': VALID_SESSION_TOKEN,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(
        f"{BASE_URL}/api/user/transactions?type=payout&limit=50",
        headers=headers
    )
    data = print_response(response, "Get payout transactions")
    
    if response.status_code == 200:
        print(f"{GREEN}✓ PASS: Filtered transactions retrieved{RESET}")
        if data:
            print(f"   Found {data.get('count', 0)} payout transactions")
        return True
    else:
        print(f"{RED}✗ FAIL: Expected 200, got {response.status_code}{RESET}")
        return False

def test_invalid_session():
    """Test payment endpoints with invalid session"""
    print_test_header("TEST 10: Invalid Session Token")
    
    headers = {
        'X-Session-Token': 'invalid_token_xyz',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f"{BASE_URL}/api/user/payment-methods", headers=headers)
    
    if response.status_code == 401:
        print(f"{GREEN}✓ PASS: Invalid session correctly rejected{RESET}")
        return True
    else:
        print(f"{YELLOW}! Status: {response.status_code} (expected 401){RESET}")
        # Some endpoints might return different codes, that's ok
        return response.status_code in [401, 403]

def run_all_tests():
    """Run all payment system tests"""
    print(f"\n{BLUE}{'='*60}")
    print(f"  PAYMENT SYSTEM TEST SUITE")
    print(f"  Testing at: {BASE_URL}")
    print(f"{'='*60}{RESET}")
    
    # Setup
    if not setup_test_user():
        print(f"{RED}Cannot continue without test user setup{RESET}")
        return
    
    results = {}
    
    # Run tests
    results['1_get_payment_methods'] = test_get_payment_methods()
    results['2_add_stripe'] = test_add_stripe_payment_method()[0]
    results['3_add_bank'] = test_add_bank_payment_method()[0]
    results['4_add_crypto'] = test_add_crypto_payment_method()[0]
    results['5_verify_methods'] = test_verify_payment_methods()
    results['6_payout_insufficient'] = test_commission_payout_insufficient()
    results['7_payout_success'] = test_commission_payout_success()
    results['8_get_transactions'] = test_get_transactions()
    results['9_get_transactions_filtered'] = test_get_transactions_filtered()
    results['10_invalid_session'] = test_invalid_session()
    
    # Summary
    print(f"\n{BLUE}{'='*60}")
    print(f"  TEST SUMMARY")
    print(f"{'='*60}{RESET}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"{GREEN}All tests passed!{RESET}\n")
    else:
        print(f"{YELLOW}Some tests failed - see details above{RESET}\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print(f"{RED}ERROR: Cannot connect to backend at {BASE_URL}")
        print(f"Make sure the backend is running on port 9000{RESET}")
    except Exception as e:
        print(f"{RED}ERROR: {e}{RESET}")
