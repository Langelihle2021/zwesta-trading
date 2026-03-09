#!/usr/bin/env python3
"""
Data Isolation Test Suite
Tests multi-tenant data isolation in Zwesta Trading Backend
Verifies that users cannot access each other's data
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:9000"
TEST_RESULTS = {
    'passed': 0,
    'failed': 0,
    'tests': []
}

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_header(text):
    """Print test section header"""
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{RESET}\n")

def print_test(name, passed, message=""):
    """Print test result"""
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"  {status} - {name}")
    if message:
        print(f"      {message}")
    
    TEST_RESULTS['tests'].append({
        'name': name,
        'passed': passed,
        'message': message
    })
    
    if passed:
        TEST_RESULTS['passed'] += 1
    else:
        TEST_RESULTS['failed'] += 1

def print_summary():
    """Print test summary"""
    total = TEST_RESULTS['passed'] + TEST_RESULTS['failed']
    print(f"\n{BLUE}{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}{RESET}")
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {TEST_RESULTS['passed']}{RESET}")
    print(f"{RED}Failed: {TEST_RESULTS['failed']}{RESET}")
    
    if TEST_RESULTS['failed'] == 0:
        print(f"\n{GREEN}🎉 ALL TESTS PASSED!{RESET}")
        return True
    else:
        print(f"\n{RED}❌ SOME TESTS FAILED{RESET}")
        return False

# ==================== TEST SETUP ====================

def register_user(email, name, referral_code=None):
    """Register a new user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/user/register",
            json={"email": email, "name": name, "referral_code": referral_code},
            timeout=5
        )
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Registration error: {e}")
        return None

def login_user(email):
    """Login user and get session token"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/user/login",
            json={"email": email},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                return {
                    'user_id': data['user_id'],
                    'session_token': data['session_token'],
                    'name': data['name']
                }
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_session_headers(session_token):
    """Get headers with session token"""
    return {
        'X-Session-Token': session_token,
        'Content-Type': 'application/json'
    }

def create_bot(user_id, session_token, bot_name, bot_id):
    """Create a bot for user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/bot/create",
            headers=get_session_headers(session_token),
            json={
                'user_id': user_id,
                'name': bot_name,
                'botId': bot_id,
                'strategy': 'Scalping',
                'accountId': '123456789',
                'symbols': ['EURUSD', 'GBPUSD'],
                'riskPerTrade': 100,
                'maxDailyLoss': 500,
                'enabled': True
            },
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Bot creation error: {e}")
        return None

def add_broker_credentials(user_id, session_token, broker_name):
    """Add broker credentials for user"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/user/{user_id}/broker-credentials",
            headers=get_session_headers(session_token),
            json={
                'broker_name': broker_name,
                'account_number': f'123456789_{datetime.now().timestamp()}',
                'password': 'test_password',
                'server': 'XMGlobal-MT5',
                'is_live': False
            },
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Broker credentials error: {e}")
        return None

# ==================== TEST CASES ====================

def test_user_registration():
    """Test 1: User Registration"""
    print_header("Test 1: User Registration")
    
    result = register_user(f"user1_{datetime.now().timestamp()}@test.com", "User One")
    passed = result and result['success']
    print_test("User 1 registration", passed, f"User ID: {result['user_id']}" if result else "")
    
    result = register_user(f"user2_{datetime.now().timestamp()}@test.com", "User Two")
    passed = result and result['success']
    print_test("User 2 registration", passed, f"User ID: {result['user_id']}" if result else "")
    
    return result['user_id'] if result else None

def test_user_login(email):
    """Test 2: User Login and Session"""
    print_header("Test 2: User Login and Session")
    
    session = login_user(email)
    passed = session is not None
    print_test("Login successful", passed, f"Session token: {session['session_token'][:20]}..." if session else "")
    
    return session

def test_bot_isolation(user1_session, user2_session):
    """Test 3: Bot Data Isolation"""
    print_header("Test 3: Bot Data Isolation")
    
    user1_id = user1_session['user_id']
    user2_id = user2_session['user_id']
    
    # User 1 creates a bot
    bot_result = create_bot(user1_id, user1_session['session_token'], "User1 Bot", f"bot_user1_{datetime.now().timestamp()}")
    bot1_id = bot_result['botId'] if bot_result and bot_result['success'] else None
    print_test("User 1 creates bot", bot_result and bot_result['success'], f"Bot ID: {bot1_id}")
    
    # User 2 creates a bot
    bot_result = create_bot(user2_id, user2_session['session_token'], "User2 Bot", f"bot_user2_{datetime.now().timestamp()}")
    bot2_id = bot_result['botId'] if bot_result and bot_result['success'] else None
    print_test("User 2 creates bot", bot_result and bot_result['success'], f"Bot ID: {bot2_id}")
    
    # User 1 gets their bots - should only see User1 Bot
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/{user1_id}/bots",
            headers=get_session_headers(user1_session['session_token']),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            bots_count = len(data.get('bots', []))
            passed = bots_count == 1 and data['bots'][0]['name'] == "User1 Bot"
            print_test("User 1 sees only their bot", passed, f"Count: {bots_count}, Expected: 1")
        else:
            print_test("User 1 sees only their bot", False, f"Status: {response.status_code}")
    except Exception as e:
        print_test("User 1 sees only their bot", False, str(e))
    
    # User 2 gets their bots - should only see User2 Bot
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/{user2_id}/bots",
            headers=get_session_headers(user2_session['session_token']),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            bots_count = len(data.get('bots', []))
            passed = bots_count == 1 and data['bots'][0]['name'] == "User2 Bot"
            print_test("User 2 sees only their bot", passed, f"Count: {bots_count}, Expected: 1")
        else:
            print_test("User 2 sees only their bot", False, f"Status: {response.status_code}")
    except Exception as e:
        print_test("User 2 sees only their bot", False, str(e))
    
    return bot1_id, bot2_id

def test_cross_user_bot_access(user1_session, user2_session, bot2_id):
    """Test 4: Cross-User Bot Access Prevention"""
    print_header("Test 4: Cross-User Bot Access Prevention")
    
    user1_id = user1_session['user_id']
    
    # User 1 tries to stop User 2's bot (should fail with 403)
    try:
        response = requests.post(
            f"{BASE_URL}/api/bot/stop/{bot2_id}",
            headers=get_session_headers(user1_session['session_token']),
            json={'user_id': user1_id},
            timeout=5
        )
        passed = response.status_code == 403
        print_test("User 1 cannot stop User 2's bot", passed, f"Status: {response.status_code} (expected 403)")
    except Exception as e:
        print_test("User 1 cannot stop User 2's bot", False, str(e))
    
    # User 1 tries to delete User 2's bot (should fail with 403)
    try:
        response = requests.delete(
            f"{BASE_URL}/api/bot/delete/{bot2_id}",
            headers=get_session_headers(user1_session['session_token']),
            json={'user_id': user1_id},
            timeout=5
        )
        passed = response.status_code == 403
        print_test("User 1 cannot delete User 2's bot", passed, f"Status: {response.status_code} (expected 403)")
    except Exception as e:
        print_test("User 1 cannot delete User 2's bot", False, str(e))

def test_broker_isolation(user1_session, user2_session):
    """Test 5: Broker Credentials Isolation"""
    print_header("Test 5: Broker Credentials Isolation")
    
    user1_id = user1_session['user_id']
    user2_id = user2_session['user_id']
    
    # User 1 adds broker credentials
    result = add_broker_credentials(user1_id, user1_session['session_token'], "XM")
    passed = result and result['success']
    print_test("User 1 adds broker credentials", passed)
    
    # User 2 adds broker credentials
    result = add_broker_credentials(user2_id, user2_session['session_token'], "IC Markets")
    passed = result and result['success']
    print_test("User 2 adds broker credentials", passed)
    
    # User 1 gets their brokers - should only see XM
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/{user1_id}/broker-credentials",
            headers=get_session_headers(user1_session['session_token']),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            credentials = data.get('credentials', [])
            passed = len(credentials) == 1 and credentials[0]['broker_name'] == 'XM'
            print_test("User 1 sees only their broker", passed, f"Count: {len(credentials)}")
        else:
            print_test("User 1 sees only their broker", False, f"Status: {response.status_code}")
    except Exception as e:
        print_test("User 1 sees only their broker", False, str(e))
    
    # User 2 gets their brokers - should only see IC Markets
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/{user2_id}/broker-credentials",
            headers=get_session_headers(user2_session['session_token']),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            credentials = data.get('credentials', [])
            passed = len(credentials) == 1 and credentials[0]['broker_name'] == 'IC Markets'
            print_test("User 2 sees only their broker", passed, f"Count: {len(credentials)}")
        else:
            print_test("User 2 sees only their broker", False, f"Status: {response.status_code}")
    except Exception as e:
        print_test("User 2 sees only their broker", False, str(e))

def test_profile_isolation(user1_session, user2_session):
    """Test 6: Profile Data Isolation"""
    print_header("Test 6: Profile Data Isolation")
    
    user1_id = user1_session['user_id']
    user2_id = user2_session['user_id']
    
    # User 1 gets their profile
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/profile/{user1_id}",
            headers=get_session_headers(user1_session['session_token']),
            timeout=5
        )
        passed = response.status_code == 200
        print_test("User 1 can access own profile", passed, f"Status: {response.status_code}")
    except Exception as e:
        print_test("User 1 can access own profile", False, str(e))
    
    # User 1 tries to access User 2's profile (should fail with 403)
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/profile/{user2_id}",
            headers=get_session_headers(user1_session['session_token']),
            timeout=5
        )
        passed = response.status_code == 403
        print_test("User 1 cannot access User 2's profile", passed, f"Status: {response.status_code} (expected 403)")
    except Exception as e:
        print_test("User 1 cannot access User 2's profile", False, str(e))

def test_invalid_sessions():
    """Test 7: Invalid Session Handling"""
    print_header("Test 7: Invalid Session Handling")
    
    # Try with invalid session token
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/profile/invalid_user_id",
            headers={'X-Session-Token': 'invalid_token', 'Content-Type': 'application/json'},
            timeout=5
        )
        passed = response.status_code == 401
        print_test("Invalid session token rejected", passed, f"Status: {response.status_code} (expected 401)")
    except Exception as e:
        print_test("Invalid session token rejected", False, str(e))
    
    # Try without session token
    try:
        response = requests.get(
            f"{BASE_URL}/api/user/profile/invalid_user_id",
            timeout=5
        )
        passed = response.status_code == 401
        print_test("Missing session token rejected", passed, f"Status: {response.status_code} (expected 401)")
    except Exception as e:
        print_test("Missing session token rejected", False, str(e))

# ==================== MAIN TEST EXECUTION ====================

def run_all_tests():
    """Run all test suites"""
    print(f"\n{YELLOW}{'*'*60}")
    print("ZWESTA TRADING - DATA ISOLATION TEST SUITE")
    print(f"{'*'*60}{RESET}")
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/api/market/commodities", timeout=5)
        if response.status_code != 200:
            print(f"{RED}❌ Backend not responding correctly (status {response.status_code}){RESET}")
            return False
    except Exception as e:
        print(f"{RED}❌ Cannot connect to backend at {BASE_URL}{RESET}")
        print(f"   Error: {e}")
        return False
    
    # Test 1: Registration
    user1_id = test_user_registration()
    user2_id = test_user_registration()
    
    # Test 2: Login
    user1_email = f"user1_{datetime.now().timestamp()}@test.com"
    user2_email = f"user2_{datetime.now().timestamp()}@test.com"
    
    # Re-register with known emails for login
    register_user(user1_email, "User One")
    register_user(user2_email, "User Two")
    
    user1_session = test_user_login(user1_email)
    user2_session = test_user_login(user2_email)
    
    if not (user1_session and user2_session):
        print(f"\n{RED}❌ Could not establish sessions for testing{RESET}")
        return False
    
    # Test 3: Bot Isolation
    bot1_id, bot2_id = test_bot_isolation(user1_session, user2_session)
    
    # Test 4: Cross-User Bot Access
    if bot2_id:
        test_cross_user_bot_access(user1_session, user2_session, bot2_id)
    
    # Test 5: Broker Isolation
    test_broker_isolation(user1_session, user2_session)
    
    # Test 6: Profile Isolation
    test_profile_isolation(user1_session, user2_session)
    
    # Test 7: Invalid Sessions
    test_invalid_sessions()
    
    # Print summary
    success = print_summary()
    
    return success

if __name__ == '__main__':
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Fatal error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
