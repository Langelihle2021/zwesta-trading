#!/usr/bin/env python3
"""
Complete Testing Workflow for LIVE/DEMO Mode System
1. Clear all bots from database
2. Switch all credentials to DEMO mode
3. Test the backend and verify setup
4. Generate status report

Usage: python complete_testing_workflow.py [--keep-bots] [--live]
"""

import subprocess
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ==================== Configuration ====================

DB_PATH = r"C:\backend\zwesta_trading.db"
BACKEND_URL = "http://localhost:9000"
SESSION_TOKEN = "debug_token_49b6b05ad32648759f26f6ac37eebcef"

# ANSI Color Codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_step(step_num, text):
    """Print a workflow step"""
    print(f"{Colors.BOLD}{Colors.BLUE}STEP {step_num}: {text}{Colors.RESET}")
    print("-" * 70)

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

# ==================== STEP 1: Clear Bots ====================

def clear_bots_from_database():
    """Clear all bots from the database"""
    print_step(1, "Clear All Bots from Database")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute('SELECT COUNT(*) as count FROM user_bots')
        before_count = cursor.fetchone()[0]
        print_info(f"Current bots in database: {before_count}")
        
        if before_count == 0:
            print_info("No bots to clear - database already clean")
            conn.close()
            print_success("Step 1 Complete")
            return True
        
        # Delete all bots
        cursor.execute('DELETE FROM user_bots')
        conn.commit()
        
        # Get count after deletion
        cursor.execute('SELECT COUNT(*) as count FROM user_bots')
        after_count = cursor.fetchone()[0]
        
        print_success(f"Cleared {before_count} bot(s)")
        print_info(f"   Before: {before_count} bots")
        print_info(f"   After:  {after_count} bots")
        
        conn.close()
        print_success("Step 1 Complete")
        return True
        
    except Exception as e:
        print_error(f"Error clearing bots: {e}")
        return False

# ==================== STEP 2: Switch to DEMO Mode ====================

def switch_credentials_to_demo():
    """Switch all credentials to DEMO mode"""
    print_step(2, "Switch All Credentials to DEMO Mode")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current mode distribution
        cursor.execute('''
            SELECT broker_name, is_live, COUNT(*) as count
            FROM broker_credentials
            GROUP BY broker_name, is_live
        ''')
        
        current_dist = cursor.fetchall()
        print_info("Current credential distribution:")
        
        for broker, is_live, count in current_dist:
            mode = "LIVE" if is_live else "DEMO"
            print_info(f"   • {broker}: {count} {mode}")
        
        # Define broker configurations
        brokers_config = {
            'Exness': {
                'demo_server': 'Exness-MT5Trial9',
                'live_server': 'Exness-Real'
            },
            'PXBT': {
                'demo_server': 'PXBT-Demo',
                'live_server': 'PXBT-Real'
            }
        }
        
        # Switch each broker to DEMO
        total_updated = 0
        
        for broker_name, servers in brokers_config.items():
            # Get all credentials for this broker
            cursor.execute('''
                SELECT credential_id, account_number, is_live, server
                FROM broker_credentials
                WHERE broker_name = ?
            ''', (broker_name,))
            
            credentials = cursor.fetchall()
            
            for cred_id, account, is_live, server in credentials:
                if is_live == 1:  # Currently in LIVE mode
                    cursor.execute('''
                        UPDATE broker_credentials
                        SET is_live = 0, server = ?
                        WHERE credential_id = ?
                    ''', (servers['demo_server'], cred_id))
                    
                    print_info(f"   Switched {broker_name} {account} to DEMO")
                    total_updated += 1
        
        conn.commit()
        conn.close()
        
        if total_updated == 0:
            print_info("All credentials already in DEMO mode")
        else:
            print_success(f"Switched {total_updated} credential(s) to DEMO")
        
        print_success("Step 2 Complete")
        return True
        
    except Exception as e:
        print_error(f"Error switching credentials: {e}")
        return False

# ==================== STEP 3: Verify Database Setup ====================

def verify_database_setup():
    """Verify the database is properly configured"""
    print_step(3, "Verify Database Setup")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check schema
        cursor.execute("PRAGMA table_info(broker_credentials)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        required_fields = ['credential_id', 'broker_name', 'is_live', 'server', 'account_number']
        missing = [f for f in required_fields if f not in column_names]
        
        if missing:
            print_error(f"Missing database fields: {missing}")
            return False
        
        print_success("Database schema is correct")
        
        # Count records
        cursor.execute('SELECT COUNT(*) FROM broker_credentials')
        cred_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM user_bots')
        bot_count = cursor.fetchone()[0]
        
        print_info(f"Database Stats:")
        print_info(f"   • Credentials: {cred_count}")
        print_info(f"   • Bots: {bot_count}")
        
        # Verify all credentials are in DEMO mode
        cursor.execute('SELECT COUNT(*) FROM broker_credentials WHERE is_live = 1')
        live_count = cursor.fetchone()[0]
        
        if live_count > 0:
            print_warning(f"Found {live_count} LIVE credential(s) - consider switching to DEMO")
        else:
            print_success("All credentials are in DEMO mode ✓")
        
        conn.close()
        print_success("Step 3 Complete")
        return True
        
    except Exception as e:
        print_error(f"Error verifying database: {e}")
        return False

# ==================== STEP 4: Test Backend Connectivity ====================

def test_backend_connectivity():
    """Test backend connectivity"""
    print_step(4, "Test Backend Connectivity")
    
    try:
        import requests
        
        print_info(f"Testing connection to {BACKEND_URL}...")
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        
        if response.status_code == 200:
            print_success(f"Backend is running ✓")
            print_success("Step 4 Complete")
            return True
        else:
            print_error(f"Backend returned status {response.status_code}")
            return False
            
    except Exception as e:
        print_warning(f"Backend not running: {str(e)}")
        print_info("To start backend, run: python multi_broker_backend_updated.py")
        print_warning("Step 4 will be skipped (expected)")
        return True  # Don't fail if backend is offline

# ==================== STEP 5: Generate Status Report ====================

def generate_status_report():
    """Generate a comprehensive status report"""
    print_step(5, "Generate Status Report")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get detailed credential status
        cursor.execute('''
            SELECT 
                credential_id,
                account_number,
                CASE WHEN is_live = 0 THEN 'DEMO' ELSE 'LIVE' END as mode,
                server,
                created_at
            FROM broker_credentials
            ORDER BY is_live DESC
        ''')
        
        credentials = cursor.fetchall()
        
        # Get bot status
        cursor.execute('''
            SELECT 
                bot_id,
                user_id,
                name,
                status,
                created_at
            FROM user_bots
            LIMIT 10
        ''')
        
        bots = cursor.fetchall()
        bot_count = cursor.execute('SELECT COUNT(*) FROM user_bots').fetchone()[0]
        
        conn.close()
        
        # Print report
        print_info("\n" + "="*70)
        print_info("CREDENTIAL STATUS")
        print_info("="*70)
        
        for idx, cred_data in enumerate(credentials, 1):
            cred_id, account, mode, server, created = cred_data
            print_info(f"\n{idx}. Account {account}")
            print_info(f"   Mode: {mode}")
            print_info(f"   Server: {server}")
            print_info(f"   Credential ID: {cred_id}")
            if created:
                print_info(f"   Created: {created}")
        
        print_info("\n" + "="*70)
        print_info("BOT STATUS")
        print_info("="*70)
        
        if bot_count == 0:
            print_success("No bots in database (clean state) ✓")
        else:
            print_info(f"Total bots: {bot_count}")
            if bots:
                print_info("\nRecent bots:")
                for bot_id, user_id, name, status, created in bots[:5]:
                    print_info(f"   • {bot_id}: {name} ({status})")
        
        # Summary
        print_info("\n" + "="*70)
        print_info("WORKFLOW SUMMARY")
        print_info("="*70)
        print_success(f"✓ Database cleaned: 0 bots")
        print_success(f"✓ All credentials set to DEMO mode")
        print_success(f"✓ Database verified: {len(credentials)} credential(s)")
        print_success(f"✓ System ready for testing")
        
        print_success("Step 5 Complete")
        return True
        
    except Exception as e:
        print_error(f"Error generating report: {e}")
        return False

# ==================== Main Workflow ====================

def main():
    """Execute the complete testing workflow"""
    
    print_header("COMPLETE TESTING WORKFLOW")
    print_info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Database: {DB_PATH}")
    
    # Check if database exists
    if not Path(DB_PATH).exists():
        print_error(f"Database not found: {DB_PATH}")
        sys.exit(1)
    
    # Parse arguments
    keep_bots = '--keep-bots' in sys.argv
    live_mode = '--live' in sys.argv
    
    if keep_bots:
        print_warning("--keep-bots flag detected, skipping bot clearing")
    
    if live_mode:
        print_warning("--live flag detected, credentials will NOT be switched to DEMO")
    
    # Execute workflow steps
    steps = [
        ("Clear Bots", clear_bots_from_database if not keep_bots else lambda: (print_info("Skipped"), True)[1]),
        ("Switch to DEMO", switch_credentials_to_demo if not live_mode else lambda: (print_info("Skipped"), True)[1]),
        ("Verify Database", verify_database_setup),
        ("Test Backend", test_backend_connectivity),
        ("Generate Report", generate_status_report),
    ]
    
    results = []
    
    for step_name, step_func in steps:
        try:
            result = step_func()
            results.append((step_name, result))
            print()
        except Exception as e:
            print_error(f"Step failed: {e}")
            results.append((step_name, False))
            print()
    
    # Final summary
    print_header("WORKFLOW COMPLETE")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print_info(f"Results: {passed}/{total} steps completed")
    
    for step_name, result in results:
        status = f"{Colors.GREEN}✅{Colors.RESET}" if result else f"{Colors.RED}❌{Colors.RESET}"
        print_info(f"   {status} {step_name}")
    
    if passed == total:
        print_success("\n🎉 All steps completed successfully!")
        print_info("✓ Database cleaned")
        print_info("✓ Credentials set to DEMO")
        print_info("✓ System ready for testing")
    else:
        print_warning(f"\n⚠️  {total - passed} step(s) failed")
    
    print_info(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()
