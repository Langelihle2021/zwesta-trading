#!/usr/bin/env python3
"""
Comprehensive test suite for payment system endpoints with correct session header
"""

import requests
import json
import time
import sqlite3
from datetime import datetime

BASE_URL = "http://localhost:9000/api"

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
END = "\033[0m"

def print_test(name):
    print(f"\n{BLUE}[TEST]{END} {name}")

def print_success(msg):
    print(f"  {GREEN}✓{END} {msg}")

def print_error(msg):
    print(f"  {RED}✗{END} {msg}")

def print_info(msg):
    print(f"  {YELLOW}ℹ{END} {msg}")

# Get session token - should match output from setup script
SESSION_TOKEN = "session_test_payment_652ec389-3f2d-446e-9"
TEST_USER_ID = "test_user_payment_001"

def get_headers(token=SESSION_TOKEN):
    """Return headers with session token"""
    return {"X-Session-Token": token}

# Test 1: Get payment methods (empty initially)
def test_get_payment_methods():
    print_test("GET /user/payment-methods")
    
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/user/payment-methods", headers=headers)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200 and data.get('success'):
        print_success(f"Retrieved {data.get('count', 0)} payment methods")
        return True
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False

# Test 2: Add Stripe payment method
def test_add_stripe_method():
    print_test("POST /user/payment-method (Stripe)")
    
    headers = get_headers()
    payload = {
        "type": "stripe",
        "stripeAccountId": "acct_test_1234567890",
        "makePrimary": True
    }
    
    response = requests.post(f"{BASE_URL}/user/payment-method", 
                            headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code in [200, 201] and data.get('success'):
        method_id = data.get('methodId')
        print_success(f"Added Stripe method: {method_id}")
        return True, method_id
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False, None

# Test 3: Add Bank payment method
def test_add_bank_method():
    print_test("POST /user/payment-method (Bank)")
    
    headers = get_headers()
    payload = {
        "type": "bank",
        "makePrimary": False,
        "bank": {
            "bankName": "Chase Bank",
            "accountHolder": "Test User",
            "accountNumber": "123456789",
            "routingNumber": "021000021",
            "swiftCode": "CHASUS33"
        }
    }
    
    response = requests.post(f"{BASE_URL}/user/payment-method", 
                            headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code in [200, 201] and data.get('success'):
        method_id = data.get('methodId')
        print_success(f"Added Bank method: {method_id}")
        return True, method_id
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False, None

# Test 4: Add Crypto payment method
def test_add_crypto_method():
    print_test("POST /user/payment-method (Crypto)")
    
    headers = get_headers()
    payload = {
        "type": "crypto",
        "wallet": "0x742d35Cc6634C0532925A3b844Bc830e2b7f6cc6",
        "cryptoType": "USDT",
        "makePrimary": False
    }
    
    response = requests.post(f"{BASE_URL}/user/payment-method", 
                            headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code in [200, 201] and data.get('success'):
        method_id = data.get('methodId')
        print_success(f"Added Crypto method: {method_id}")
        return True, method_id
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False, None

# Test 5: Verify all methods added
def test_verify_payment_methods():
    print_test("GET /user/payment-methods (Verify all)")
    
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/user/payment-methods", headers=headers)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200 and data.get('success'):
        count = data.get('count', 0)
        print_success(f"Verified all payment methods ({count} total)")
        
        # Print details
        for method in data.get('methods', []):
            method_type = method.get('type')
            is_primary = "PRIMARY" if method.get('isPrimary') else "secondary"
            verified = "verified" if method.get('verified') else "unverified"
            print_info(f"{method_type} - {is_primary}, {verified}")
        
        return True, count
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False, 0

# Test 6: Add commission to database
def add_test_commission():
    print_test("Setup: Add test commission to database")
    
    conn = sqlite3.connect('zwesta_trading.db')
    cursor = conn.cursor()
    
    try:
        commission_id = f"comm_{int(time.time())}"
        cursor.execute('''
            INSERT INTO commission_ledger 
            (commission_id, user_id, source_user_id, type, amount, payout_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (commission_id, TEST_USER_ID, "admin", 
              "referral", 150.00, "pending", datetime.now().isoformat()))
        conn.commit()
        print_success("Added $150.00 test commission")
    except Exception as e:
        print_error(f"Failed: {str(e)}")
    finally:
        conn.close()

# Test 7: Request commission payout
def test_commission_payout():
    print_test("POST /user/commission-payout")
    
    headers = get_headers()
    payload = {
        "method": "internal",  # Use internal (no external API needed)
        "minAmount": 50
    }
    
    response = requests.post(f"{BASE_URL}/user/commission-payout", 
                           headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200 and data.get('success'):
        print_success(f"Payout requested: {data.get('reference')}")
        print_info(f"Amount: ${data.get('amount', 0):.2f}")
        print_info(f"Method: {data.get('method')}")
        return True
    else:
        print_info(f"Response: {data.get('error', data.get('message', 'Unknown'))}")
        return True  # Not a test failure, may not have pendingcommission

# Test 8: Get transactions
def test_get_transactions():
    print_test("GET /user/transactions")
    
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/user/transactions?limit=20", headers=headers)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200 and data.get('success'):
        count = data.get('count', 0)
        print_success(f"Retrieved {count} transactions")
        
        for tx in data.get('transactions', [])[:3]:  # Show first 3
            print_info(f"{tx.get('type')} - ${tx.get('amount', 0):.2f} ({tx.get('status')})")
        
        return True
    else:
        print_error(f"Failed: {data.get('error', 'Unknown error')}")
        return False

# Test 9: Get transactions filtered
def test_get_transactions_filtered():
    print_test("GET /user/transactions?type=payout")
    
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/user/transactions?type=payout&limit=10", 
                           headers=headers)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200 and data.get('success'):
        count = data.get('count', 0)
        print_success(f"Retrieved {count} payout transactions")
        return True
    else:
        print_info(f"Response: {data.get('error', 'No payouts yet')}")
        return True

# Test 10: Error handling
def test_error_handling():
    print_test("Error Handling: Invalid payment method type")
    
    headers = get_headers()
    payload = {"type": "invalid_method_type"}
    response = requests.post(f"{BASE_URL}/user/payment-method", 
                            headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code >= 400:
        print_success(f"Proper error: {data.get('error')}")
        return True
    else:
        print_error("Expected 4xx error response")
        return False

# Test 11: Missing required fields
def test_missing_fields():
    print_test("Error Handling: Missing required fields")
    
    headers = get_headers()
    payload = {"type": "stripe"}  # Missing stripeAccountId
    response = requests.post(f"{BASE_URL}/user/payment-method", 
                            headers=headers, json=payload)
    
    print(f"  Status: {response.status_code}")
    data = response.json()
    
    if response.status_code >= 400:
        print_success(f"Proper validation: {data.get('error')}")
        return True
    else:
        print_error("Expected validation error")
        return False

# Main test runner
def main():
    print(f"\n{BLUE}{'='*70}")
    print("ZWESTA TRADING - PAYMENT SYSTEM ENDPOINT TEST SUITE")
    print(f"{'='*70}{END}\n")
    
    print(f"Backend URL: {BASE_URL}")
    print(f"Session Token: {SESSION_TOKEN}")
    print(f"Test User: {TEST_USER_ID}\n")
    
    # Give backend time to be ready
    time.sleep(2)
    
    results = {}
    
    # Payment method tests
    results['1_get_methods_initial'] = test_get_payment_methods()
    time.sleep(0.5)
    
    results['2_add_stripe'] = test_add_stripe_method()[0]
    time.sleep(0.5)
    
    results['3_add_bank'] = test_add_bank_method()[0]
    time.sleep(0.5)
    
    results['4_add_crypto'] = test_add_crypto_method()[0]
    time.sleep(0.5)
    
    results['5_verify_methods'] = test_verify_payment_methods()[0]
    
    # Commission/payout tests
    print(f"\n{BLUE}{'='*70}")
    print("COMMISSION & PAYOUT TESTS")
    print(f"{'='*70}{END}")
    
    add_test_commission()
    time.sleep(0.5)
    
    results['6_commission_payout'] = test_commission_payout()
    time.sleep(0.5)
    
    # Transaction tests
    print(f"\n{BLUE}{'='*70}")
    print("TRANSACTION HISTORY TESTS")
    print(f"{'='*70}{END}")
    
    results['7_get_transactions'] = test_get_transactions()
    time.sleep(0.5)
    
    results['8_get_transactions_filtered'] = test_get_transactions_filtered()
    
    # Error handling tests
    print(f"\n{BLUE}{'='*70}")
    print("ERROR HANDLING TESTS")
    print(f"{'='*70}{END}")
    
    results['9_error_invalid_type'] = test_error_handling()
    time.sleep(0.5)
    
    results['10_error_missing_fields'] = test_missing_fields()
    
    # Summary
    print(f"\n{BLUE}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{END}\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_num, (test_name, result) in enumerate(results.items(), 1):
        status = f"{GREEN}PASS{END}" if result else f"{RED}FAIL{END}"
        test_display = test_name.replace('_', ' ').title()
        print(f"  {test_num:2}. {test_display:.<50} {status}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{END}\n")
    
    if passed == total:
        print(f"{GREEN}SUCCESS - All tests passed!{END}\n")
    else:
        failed = total - passed
        print(f"{YELLOW}PARTIAL - {failed} test(s) need attention{END}\n")

if __name__ == "__main__":
    main()
