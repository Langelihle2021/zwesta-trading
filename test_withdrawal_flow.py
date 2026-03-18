#!/usr/bin/env python3
"""
Test script for the complete withdrawal verification flow
Tests:
1. Admin getting pending withdrawals
2. Admin verifying a withdrawal (splits commission)
3. User checking wallet balance
"""

import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:5000"
ADMIN_API_KEY = "zwestav2-admin-key-2024"  # Update with actual admin key
USER_SESSION_TOKEN = "user_session_token_here"  # Update with actual token

def test_admin_get_pending_withdrawals():
    """Test: Admin gets list of pending Exness withdrawals"""
    print("\n" + "="*70)
    print("TEST 1: Admin gets pending Exness withdrawals")
    print("="*70)
    
    url = f"{BACKEND_URL}/api/admin/withdrawals/pending"
    headers = {
        "X-API-Key": ADMIN_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: Found {data.get('count', 0)} pending withdrawals")
            return True
        else:
            print("❌ FAILED: Could not fetch pending withdrawals")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_verify_withdrawal(withdrawal_id):
    """Test: Admin verifies a withdrawal and splits commission"""
    print("\n" + "="*70)
    print(f"TEST 2: Admin verifies withdrawal {withdrawal_id}")
    print("="*70)
    
    url = f"{BACKEND_URL}/api/admin/withdrawal/exness/verify"
    headers = {
        "X-API-Key": ADMIN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "withdrawal_id": withdrawal_id,
        "notes": "Verified: User withdrew $1,000 from Exness trading profits"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: Commission split")
            print(f"   Developer commission: ${data.get('developer_commission', 0)}")
            print(f"   User wallet credit: ${data.get('user_wallet_credit', 0)}")
            return True
        else:
            print("❌ FAILED: Could not verify withdrawal")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_user_wallet_balance(user_id):
    """Test: User checks their wallet balance"""
    print("\n" + "="*70)
    print(f"TEST 3: User checks wallet balance")
    print("="*70)
    
    url = f"{BACKEND_URL}/api/wallet/balance/{user_id}"
    headers = {
        "X-Session-Token": USER_SESSION_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: User wallet balance: ${data.get('balance', 0)}")
            return True
        else:
            print("❌ FAILED: Could not fetch wallet balance")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("ZWESTA TRADER - WITHDRAWAL VERIFICATION FLOW TEST")
    print("="*70)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Test 1: Get pending withdrawals
    test1_pass = test_admin_get_pending_withdrawals()
    
    # Test 2: Verify a withdrawal (dummy ID - replace with real one)
    test2_pass = test_verify_withdrawal("withdrawal_dummy_id_12345")
    
    # Test 3: Check user wallet balance (dummy user ID - replace with real one)
    test3_pass = test_user_wallet_balance("user_dummy_id_67890")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Test 1 (Get pending withdrawals): {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"Test 2 (Verify withdrawal): {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"Test 3 (Check wallet balance): {'✅ PASS' if test3_pass else '❌ FAIL'}")
    print("="*70)
    
    total_pass = sum([test1_pass, test2_pass, test3_pass])
    print(f"\nResult: {total_pass}/3 tests passed")
    
    if total_pass == 3:
        print("✅ All tests passed! Withdrawal flow is operational.")
    else:
        print(f"⚠️  {3 - total_pass} test(s) failed. Check the implementation.")

if __name__ == "__main__":
    main()
