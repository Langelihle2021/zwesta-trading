#!/usr/bin/env python3
"""
Zwesta Trader - MT5 Lock Diagnostic & Bot Status Monitor
Helps diagnose MT5 lock contention and bot trading issues
"""

import requests
import json
import time
from datetime import datetime
from collections import defaultdict

# Configuration
BACKEND_URL = "http://localhost:9000"
SESSION_TOKEN = "debug_token_49b6b05ad32648759f26f6ac37eebcef"  # Update with your session token

class BotMonitor:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-Session-Token": SESSION_TOKEN
        }
        self.bot_history = defaultdict(list)
        self.timeout_count = 0
        self.success_count = 0
        
    def get_bot_status(self, user_id):
        """Get status of all user's bots"""
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/bot/status?user_id={user_id}",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Error fetching bot status: {e}")
            return None
    
    def get_account_balances(self, user_id):
        """Get account balances (uses balance cache)"""
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/accounts/balances",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Error fetching balances: {e}")
            return None
    
    def analyze_logs(self, log_output):
        """Analyze backend logs for lock contention patterns"""
        timeout_count = log_output.count("TIMEOUT: Could not acquire MT5 lock")
        success_count = log_output.count("✅ Acquired MT5 connection lock")
        failure_count = log_output.count("MT5 connection failed")
        
        return {
            'timeouts': timeout_count,
            'success': success_count,
            'failures': failure_count
        }
    
    def run_diagnostic(self, user_id, duration_seconds=60, check_interval=5):
        """Run continuous diagnostic for N seconds"""
        print("\n" + "="*70)
        print("🔍 ZWESTA TRADER - MT5 LOCK & BOT DIAGNOSTIC")
        print("="*70)
        print(f"⏰ Duration: {duration_seconds}s | Check Interval: {check_interval}s")
        print(f"👤 User: {user_id[:12]}...")
        print("="*70 + "\n")
        
        start_time = time.time()
        check_num = 0
        
        while (time.time() - start_time) < duration_seconds:
            check_num += 1
            print(f"\n📊 CHECK #{check_num} at {datetime.now().strftime('%H:%M:%S')}")
            print("-" * 70)
            
            # Get bot status
            status = self.get_bot_status(user_id)
            if status:
                if status.get('success'):
                    bots_info = status.get('bots', [])
                    print(f"🤖 Found {len(bots_info)} active bots:")
                    
                    for bot in bots_info[:5]:  # Show first 5
                        bot_id = bot.get('botId', 'Unknown')[:20]
                        trades = bot.get('totalTrades', 0)
                        profit = bot.get('totalProfit', 0)
                        status_val = bot.get('status', 'UNKNOWN')
                        
                        status_icon = "🟢" if status_val == "ACTIVE" else "🟡" if status_val == "PAUSED" else "🔴"
                        print(f"   {status_icon} {bot_id:20} | Trades: {trades:3d} | Profit: ${profit:8.2f}")
                else:
                    print(f"⚠️  Could not fetch bot status: {status.get('error')}")
            
            # Get balance info (tests lock timeout on balance check)
            print(f"\n💰 Testing balance fetch (tests cache & lock timeout)...")
            balances = self.get_account_balances(user_id)
            if balances:
                if balances.get('success'):
                    total = balances.get('total_balance', 0)
                    print(f"   ✅ Balance fetched successfully: ${total:,.2f}")
                    accounts = balances.get('accounts', [])
                    for acc in accounts[:3]:
                        broker = acc.get('broker_name', 'Unknown')
                        bal = acc.get('balance', 0)
                        print(f"      • {broker}: ${bal:,.2f}")
                else:
                    print(f"   ⚠️  Error: {balances.get('error')}")
            
            # Show timing
            elapsed = time.time() - start_time
            remaining = duration_seconds - elapsed
            print(f"\n⏳ Elapsed: {elapsed:.0f}s | Remaining: {remaining:.0f}s")
            
            # Sleep before next check
            if remaining > 0:
                time.sleep(check_interval)
        
        # Summary
        print("\n" + "="*70)
        print("✅ DIAGNOSTIC COMPLETE")
        print("="*70)
        print("\n📋 RECOMMENDATIONS:")
        print("   1. If many TIMEOUT errors:")
        print("      • Reduce number of active bots (stop some)")
        print("      • Increase lock timeout in backend (done - now 20s)")
        print("      • Check if MT5 terminal is responding (restart if needed)")
        print("")
        print("   2. If bots not trading (0 trades after 5+ mins):")
        print("      • Check backend logs for MT5 connection errors")
        print("      • Verify Exness credentials are correct")
        print("      • Check if market is open for trading symbols")
        print("")
        print("   3. Balance fetches timing out:")
        print("      • Balance cache will use last known value")
        print("      • Try stopping non-essential bots to free up MT5 lock")
        print("")


def interactive_menu():
    """Interactive diagnostic menu"""
    print("\n" + "="*70)
    print("🎯 ZWESTA TRADER - DIAGNOSTIC MENU")
    print("="*70)
    
    print("\n1. Run 60-second diagnostic (all bots)")
    print("2. Run 120-second diagnostic (detailed analysis)")
    print("3. Check specific bot status")
    print("4. Get account balances")
    print("5. Exit")
    
    choice = input("\nChoose option (1-5): ").strip()
    
    # Default user ID
    user_id = "6531812c-ae51-4f53-b16a-a346aae873a1"  # From your logs
    
    monitor = BotMonitor()
    
    if choice == "1":
        monitor.run_diagnostic(user_id, duration_seconds=60, check_interval=5)
    elif choice == "2":
        monitor.run_diagnostic(user_id, duration_seconds=120, check_interval=10)
    elif choice == "3":
        status = monitor.get_bot_status(user_id)
        print("\n" + json.dumps(status, indent=2))
    elif choice == "4":
        balances = monitor.get_account_balances(user_id)
        print("\n" + json.dumps(balances, indent=2))
    elif choice == "5":
        print("👋 Exiting...")
        exit(0)
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    try:
        # Test backend connection first
        print("🔌 Connecting to backend...")
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print(f"✅ Backend is running\n")
        
        # Run interactive menu
        interactive_menu()
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Cannot connect to backend at {BACKEND_URL}")
        print("   Make sure your backend is running: python multi_broker_backend_updated.py")
    except KeyboardInterrupt:
        print("\n\n👋 Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
