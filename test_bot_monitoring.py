#!/usr/bin/env python3
"""
Bot Monitoring & Auto-Withdrawal System Testing Script
Tests all endpoints and monitoring functionality
"""

import requests
import json
import time
from datetime import datetime

# Configuration
API_KEY = 'your_api_key_here'  # Replace with your actual API key
BASE_URL = 'http://localhost:9000'  # Update if running on different port

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class BotMonitoringTests:
    """Test suite for bot monitoring and auto-withdrawal"""
    
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {'X-API-Key': api_key, 'Content-Type': 'application/json'}
        self.bot_id = 'bot_demo_1'
        self.user_id = 'user_test_1'
        self.tests_passed = 0
        self.tests_failed = 0
    
    def print_test(self, name, passed, response=None):
        """Print test result"""
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"\n{status} | {name}")
        if response and not passed:
            print(f"  Response: {response}")
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
    
    def test_get_bot_health(self):
        """Test: Get bot health status"""
        try:
            response = requests.get(
                f'{self.base_url}/api/bot/{self.bot_id}/health',
                headers=self.headers,
                timeout=5
            )
            
            passed = response.status_code == 200
            self.print_test("GET Bot Health Status", passed, response.text if not passed else None)
            
            if passed:
                data = response.json()
                health = data.get('health', {})
                print(f"  ├─ Status: {health.get('status')}")
                print(f"  ├─ Strategy: {health.get('strategy')}")
                print(f"  ├─ Daily Profit: ${health.get('daily_profit', 0):.2f}")
                print(f"  ├─ Total Profit: ${health.get('total_profit', 0):.2f}")
                print(f"  ├─ Uptime: {health.get('uptime_seconds', 0)}s")
                print(f"  └─ Errors: {health.get('error_count', 0)}")
            
            return passed
        
        except Exception as e:
            self.print_test("GET Bot Health Status", False, str(e))
            return False
    
    def test_set_auto_withdrawal(self, target_profit=500.00):
        """Test: Set auto-withdrawal target"""
        try:
            payload = {
                'user_id': self.user_id,
                'target_profit': target_profit
            }
            
            response = requests.post(
                f'{self.base_url}/api/bot/{self.bot_id}/auto-withdrawal',
                headers=self.headers,
                json=payload,
                timeout=5
            )
            
            passed = response.status_code == 200
            self.print_test(f"POST Set Auto-Withdrawal (${target_profit})", passed, response.text if not passed else None)
            
            if passed:
                data = response.json()
                print(f"  ├─ Setting ID: {data.get('setting_id')}")
                print(f"  ├─ Target Profit: ${data.get('target_profit', 0):.2f}")
                print(f"  ├─ Message: {data.get('message')}")
            
            return passed
        
        except Exception as e:
            self.print_test(f"POST Set Auto-Withdrawal (${target_profit})", False, str(e))
            return False
    
    def test_set_invalid_target(self):
        """Test: Set invalid auto-withdrawal target (too low)"""
        try:
            payload = {
                'user_id': self.user_id,
                'target_profit': 5.00  # Less than $10 minimum
            }
            
            response = requests.post(
                f'{self.base_url}/api/bot/{self.bot_id}/auto-withdrawal',
                headers=self.headers,
                json=payload,
                timeout=5
            )
            
            passed = response.status_code == 400  # Should fail
            self.print_test("POST Invalid Target (Too Low)", passed, response.text if not passed else None)
            
            if passed:
                print(f"  └─ Error: {response.json().get('error')}")
            
            return passed
        
        except Exception as e:
            self.print_test("POST Invalid Target (Too Low)", False, str(e))
            return False
    
    def test_set_too_high_target(self):
        """Test: Set too high auto-withdrawal target"""
        try:
            payload = {
                'user_id': self.user_id,
                'target_profit': 100000.00  # More than $50,000 maximum
            }
            
            response = requests.post(
                f'{self.base_url}/api/bot/{self.bot_id}/auto-withdrawal',
                headers=self.headers,
                json=payload,
                timeout=5
            )
            
            passed = response.status_code == 400  # Should fail
            self.print_test("POST Invalid Target (Too High)", passed, response.text if not passed else None)
            
            if passed:
                print(f"  └─ Error: {response.json().get('error')}")
            
            return passed
        
        except Exception as e:
            self.print_test("POST Invalid Target (Too High)", False, str(e))
            return False
    
    def test_get_withdrawal_status(self):
        """Test: Get auto-withdrawal status"""
        try:
            response = requests.get(
                f'{self.base_url}/api/bot/{self.bot_id}/auto-withdrawal-status',
                headers=self.headers,
                timeout=5
            )
            
            passed = response.status_code == 200
            self.print_test("GET Auto-Withdrawal Status", passed, response.text if not passed else None)
            
            if passed:
                data = response.json()
                print(f"  ├─ Current Setting: {data.get('current_setting') is not None}")
                print(f"  ├─ Total Withdrawals: {data.get('total_auto_withdrawals', 0)}")
                print(f"  ├─ Total Withdrawn: ${data.get('total_amount_withdrawn', 0):.2f}")
                
                history = data.get('history', [])
                if history:
                    print(f"  └─ Recent Withdrawals: {len(history)}")
                    for h in history[:3]:
                        print(f"      - ${h.get('net_amount', 0):.2f} ({h.get('status')})")
            
            return passed
        
        except Exception as e:
            self.print_test("GET Auto-Withdrawal Status", False, str(e))
            return False
    
    def test_disable_auto_withdrawal(self):
        """Test: Disable auto-withdrawal"""
        try:
            response = requests.post(
                f'{self.base_url}/api/bot/{self.bot_id}/disable-auto-withdrawal',
                headers=self.headers,
                timeout=5
            )
            
            passed = response.status_code == 200
            self.print_test("POST Disable Auto-Withdrawal", passed, response.text if not passed else None)
            
            if passed:
                print(f"  └─ {response.json().get('message')}")
            
            return passed
        
        except Exception as e:
            self.print_test("POST Disable Auto-Withdrawal", False, str(e))
            return False
    
    def test_invalid_bot_id(self):
        """Test: Invalid bot ID"""
        try:
            response = requests.get(
                f'{self.base_url}/api/bot/invalid_bot_xyz/health',
                headers=self.headers,
                timeout=5
            )
            
            passed = response.status_code == 404
            self.print_test("GET Invalid Bot ID (404)", passed, response.text if not passed else None)
            
            if passed:
                print(f"  └─ Error: {response.json().get('error')}")
            
            return passed
        
        except Exception as e:
            self.print_test("GET Invalid Bot ID (404)", False, str(e))
            return False
    
    def test_missing_api_key(self):
        """Test: Missing API key"""
        try:
            response = requests.get(
                f'{self.base_url}/api/bot/{self.bot_id}/health',
                timeout=5
            )
            
            passed = response.status_code == 401 or response.status_code == 403
            self.print_test("GET Missing API Key (401/403)", passed, response.text if not passed else None)
            
            return passed
        
        except Exception as e:
            self.print_test("GET Missing API Key (401/403)", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BLUE}{'='*60}")
        print(f"Bot Monitoring & Auto-Withdrawal Tests")
        print(f"{'='*60}{Colors.RESET}")
        print(f"Base URL: {self.base_url}")
        print(f"Bot ID: {self.bot_id}")
        print(f"User ID: {self.user_id}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run tests
        print(f"\n{Colors.BLUE}[1] Health & Status Tests{Colors.RESET}")
        self.test_get_bot_health()
        self.test_invalid_bot_id()
        
        print(f"\n{Colors.BLUE}[2] Auto-Withdrawal Configuration Tests{Colors.RESET}")
        self.test_set_auto_withdrawal(500.00)
        self.test_set_invalid_target()
        self.test_set_too_high_target()
        
        print(f"\n{Colors.BLUE}[3] Status & Management Tests{Colors.RESET}")
        self.test_get_withdrawal_status()
        self.test_disable_auto_withdrawal()
        
        print(f"\n{Colors.BLUE}[4] Security Tests{Colors.RESET}")
        self.test_missing_api_key()
        
        # Summary
        print(f"\n{Colors.BLUE}{'='*60}")
        print(f"Test Summary{Colors.RESET}")
        print(f"{'='*60}")
        total = self.tests_passed + self.tests_failed
        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.tests_passed}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {self.tests_failed}{Colors.RESET}")
        
        if self.tests_failed == 0:
            print(f"\n{Colors.GREEN}✓ All tests passed!{Colors.RESET}")
        else:
            print(f"\n{Colors.YELLOW}⚠ Some tests failed. Check output above.{Colors.RESET}")
        
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        return self.tests_failed == 0

def main():
    """Main test runner"""
    try:
        tester = BotMonitoringTests(API_KEY, BASE_URL)
        success = tester.run_all_tests()
        exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.RESET}\n")
        exit(1)
    
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.RESET}\n")
        exit(1)

if __name__ == '__main__':
    main()
