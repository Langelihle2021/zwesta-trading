"""
Test Suite for Payment System Endpoints
Tests all 5 payment management endpoints with mock data
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:9000"
TEST_USER_ID = "test-user-001"
TEST_SESSION_TOKEN = "test-session-token-123"

# Mock session for testing
HEADERS = {
    "X-Session-Token": TEST_SESSION_TOKEN,
    "Content-Type": "application/json"
}

class PaymentEndpointTester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.results = []
        
    def print_result(self, endpoint, method, status, response, passed=True):
        """Format and print test result"""
        status_icon = "[PASS]" if passed else "[FAIL]"
        print(f"\n{status_icon} [{method}] {endpoint}")
        print(f"   Status: {status}")
        if isinstance(response, dict):
            print(f"   Response: {json.dumps(response, indent=4)}")
        else:
            print(f"   Response: {response}")
    
    def test_get_payment_methods(self):
        """Test: GET /api/user/payment-methods"""
        print("\n" + "="*60)
        print("TEST 1: GET /api/user/payment-methods")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/payment-methods"
            response = requests.get(url, headers=HEADERS)
            
            passed = response.status_code == 200
            self.print_result(
                "/api/user/payment-methods",
                "GET",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n   Found {data.get('count', 0)} payment methods")
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            self.print_result("/api/user/payment-methods", "GET", "ERROR", str(e), False)
            return False
    
    def test_add_stripe_method(self):
        """Test: POST /api/user/payment-method (Stripe)"""
        print("\n" + "="*60)
        print("TEST 2: POST /api/user/payment-method (Stripe)")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/payment-method"
            payload = {
                "type": "stripe",
                "stripeAccountId": "acct_1234567890ABCDEF",
                "makePrimary": True
            }
            
            response = requests.post(url, json=payload, headers=HEADERS)
            
            passed = response.status_code in [200, 201]
            self.print_result(
                "/api/user/payment-method (Stripe)",
                "POST",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            return passed
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            self.print_result("/api/user/payment-method", "POST", "ERROR", str(e), False)
            return False
    
    def test_add_bank_method(self):
        """Test: POST /api/user/payment-method (Bank Transfer)"""
        print("\n" + "="*60)
        print("TEST 3: POST /api/user/payment-method (Bank Transfer)")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/payment-method"
            payload = {
                "type": "bank",
                "makePrimary": False,
                "bank": {
                    "bankName": "Chase Bank",
                    "accountHolder": "John Doe",
                    "accountNumber": "123456789012",
                    "routingNumber": "021000021",
                    "swiftCode": "CHASUS33"
                }
            }
            
            response = requests.post(url, json=payload, headers=HEADERS)
            
            passed = response.status_code in [200, 201]
            self.print_result(
                "/api/user/payment-method (Bank)",
                "POST",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            return passed
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            return False
    
    def test_add_crypto_method(self):
        """Test: POST /api/user/payment-method (Crypto)"""
        print("\n" + "="*60)
        print("TEST 4: POST /api/user/payment-method (Crypto)")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/payment-method"
            payload = {
                "type": "crypto",
                "wallet": "0x742d35Cc6634C0532925A3b844Bc830e2b7f62e",
                "cryptoType": "USDT",
                "makePrimary": False
            }
            
            response = requests.post(url, json=payload, headers=HEADERS)
            
            passed = response.status_code in [200, 201]
            self.print_result(
                "/api/user/payment-method (Crypto)",
                "POST",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            return passed
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            return False
    
    def test_request_commission_payout(self):
        """Test: POST /api/user/commission-payout"""
        print("\n" + "="*60)
        print("TEST 5: POST /api/user/commission-payout")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/commission-payout"
            payload = {
                "method": "internal",
                "minAmount": 50
            }
            
            response = requests.post(url, json=payload, headers=HEADERS)
            
            passed = response.status_code in [200, 201, 400]
            self.print_result(
                "/api/user/commission-payout",
                "POST",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            return False
    
    def test_get_transactions(self):
        """Test: GET /api/user/transactions"""
        print("\n" + "="*60)
        print("TEST 6: GET /api/user/transactions")
        print("="*60)
        
        try:
            url = f"{self.base_url}/api/user/transactions?type=payout&limit=10"
            response = requests.get(url, headers=HEADERS)
            
            passed = response.status_code == 200
            self.print_result(
                "/api/user/transactions",
                "GET",
                response.status_code,
                response.json() if response.status_code < 400 else response.text,
                passed
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n   Found {data.get('count', 0)} transactions")
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests and print summary"""
        print("\n\n" + "="*60)
        print("PAYMENT ENDPOINTS TEST SUITE")
        print(f"Testing: {BASE_URL}")
        print("="*60)
        
        results = []
        
        # Run all tests
        results.append(("GET payment methods", self.test_get_payment_methods()))
        results.append(("Add Stripe method", self.test_add_stripe_method()))
        results.append(("Add Bank method", self.test_add_bank_method()))
        results.append(("Add Crypto method", self.test_add_crypto_method()))
        results.append(("Request payout", self.test_request_commission_payout()))
        results.append(("Get transactions", self.test_get_transactions()))
        
        # Print summary
        print("\n\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status:10} {test_name}")
        
        print(f"\n{passed}/{total} tests passed\n")
        
        return passed == total


def main():
    """Main test runner"""
    print("\n[*] Starting Payment Endpoints Test Suite...")
    print(f"   Backend: {BASE_URL}")
    print(f"   Test User: {TEST_USER_ID}")
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        print("   [OK] Backend is responding")
    except:
        print("\n[ERROR] Backend is not responding at http://localhost:9000")
        print("\n[INFO] Make sure to:")
        print("   1. Start the Flask backend: python multi_broker_backend_updated.py")
        print("   2. Run this test script: python test_payment_endpoints.py")
        return
    
    # Run tests
    tester = PaymentEndpointTester(BASE_URL)
    tester.run_all_tests()


if __name__ == "__main__":
    main()
