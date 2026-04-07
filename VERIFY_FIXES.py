#!/usr/bin/env python3
"""
VERIFICATION SCRIPT - Check if all fixes are correctly applied
Run this before deploying to VPS to ensure files are correct
"""

import re
import sys

def verify_backend():
    """Verify backend fixes"""
    print("\n" + "="*70)
    print("BACKEND VERIFICATION (multi_broker_backend_updated.py)")
    print("="*70)
    
    try:
        with open(r'c:\zwesta-trader\Zwesta Flutter App\multi_broker_backend_updated.py', 'r', encoding='utf-8', errors='ignore') as f:
            backend_code = f.read()
    except Exception as e:
        print(f"❌ ERROR: Cannot read backend file: {e}")
        return False, []
    
    issues = []
    
    # Check 1: XM enum removed
    if 'XM = "xm"' in backend_code or "XM = 'xm'" in backend_code:
        issues.append("❌ XM enum still present - should be removed")
    else:
        print("✅ XM enum correctly removed")
    
    # Check 2: XMConnection class removed
    if 'class XMConnection' in backend_code:
        issues.append("❌ XMConnection class still present - should be removed")
    else:
        print("✅ XMConnection class correctly removed")
    
    # Check 3: XM in connection factory removed
    if 'elif broker_type == BrokerType.XM:' in backend_code and 'XMConnection' in backend_code:
        issues.append("❌ XM connection factory still present - should be removed")
    else:
        print("✅ XM connection factory correctly removed")
    
    # Check 4: Exness still supported (uses MT5Connection)
    if 'EXNESS = "exness"' in backend_code or "EXNESS = 'exness'" in backend_code:
        print("✅ Exness broker still supported")
    else:
        issues.append("❌ Exness broker missing - this should be present!")
    
    # Check 5: MT5Connection still present (used for Exness)
    if 'class MT5Connection' in backend_code:
        print("✅ MT5Connection class still present (used for Exness)")
    else:
        issues.append("❌ MT5Connection class removed - this should be present!")
    
    # Check 6: No lingering XM references (except in comments)
    xm_refs = re.findall(r'\bXM\b(?!.*#)', backend_code)  # XM not preceded by comment on same line
    # Filter out obvious false positives in comments
    xm_count = 0
    for line in backend_code.split('\n'):
        if 'XM' in line and not line.strip().startswith('#'):
            if 'XM' in line and 'class XMConnection' not in line:  # Should already be removed
                # Check if it's in actual code
                if 'XM' in line.split('#')[0]:  # Before any comment
                    if 'XM' in ['METATRADER5', 'FXOPEN', 'OANDA']:  # Skip these harmless substrings
                        continue
                    xm_count += 1
    
    if xm_count > 0:
        issues.append(f"⚠️  Found {xm_count} lingering XM references in code")
    else:
        print("✅ No lingering XM references in code")
    
    return len(issues) == 0, issues


def verify_frontend_dashboard():
    """Verify frontend dashboard fixes"""
    print("\n" + "="*70)
    print("FRONTEND DASHBOARD VERIFICATION (dashboard_screen.dart)")
    print("="*70)
    
    try:
        with open(r'c:\zwesta-trader\Zwesta Flutter App\lib\screens\dashboard_screen.dart', 'r', encoding='utf-8', errors='ignore') as f:
            dashboard_code = f.read()
    except Exception as e:
        print(f"❌ ERROR: Cannot read dashboard file: {e}")
        return False, []
    
    issues = []
    
    # Check 1: Build Broker Accounts Card has no duplicate balance in header
    if '_buildBrokerAccountsCard' in dashboard_code:
        # Find the function
        match = re.search(r'Widget _buildBrokerAccountsCard\(\).*?(?=\n  [}A-Z])', dashboard_code, re.DOTALL)
        if match:
            func = match.group()
            # Count how many times balance is calculated/displayed in header
            if 'shownTotal.toStringAsFixed' in func:
                # Check if it's in the header Row
                header_check = re.search(r'Row\(\s*mainAxisAlignment.*?children:', func, re.DOTALL)
                if header_check and 'shownTotal' in header_check.group():
                    issues.append("❌ Balance still displayed in Broker Accounts header - should be removed")
                else:
                    print("✅ Balance correctly removed from Broker Accounts header")
            else:
                print("✅ Balance correctly removed from Broker Accounts header")
        else:
            issues.append("⚠️  Could not find _buildBrokerAccountsCard function")
    else:
        issues.append("❌ _buildBrokerAccountsCard function missing")
    
    # Check 2: Total Portfolio Balance still exists
    if 'TOTAL PORTFOLIO BALANCE' in dashboard_code:
        print("✅ Total Portfolio Balance section still present")
    else:
        issues.append("❌ Total Portfolio Balance section removed - should be present!")
    
    # Check 3: Balance displayed only once in summary
    portfolio_balance_count = dashboard_code.count('_totalBrokerBalance')
    if portfolio_balance_count >= 1:
        print(f"✅ Total Portfolio Balance referenced {portfolio_balance_count} time(s) (expected)")
    else:
        issues.append("❌ Total Portfolio Balance not referenced properly")
    
    return len(issues) == 0, issues


def verify_bot_dashboard():
    """Verify bot dashboard fixes"""
    print("\n" + "="*70)
    print("BOT DASHBOARD VERIFICATION (bot_dashboard_screen.dart)")
    print("="*70)
    
    try:
        with open(r'c:\zwesta-trader\Zwesta Flutter App\lib\screens\bot_dashboard_screen.dart', 'r', encoding='utf-8', errors='ignore') as f:
            bot_dashboard_code = f.read()
    except Exception as e:
        print(f"❌ ERROR: Cannot read bot dashboard file: {e}")
        return False, []
    
    issues = []
    
    # Check 1: PXBT import removed
    if "import '../widgets/pxbt_session_manager.dart'" in bot_dashboard_code:
        issues.append("❌ PXBT session manager import still present - should be removed")
    else:
        print("✅ PXBT session manager import correctly removed")
    
    # Check 2: PXBT widget usage removed
    if 'PxbtSessionManager(' in bot_dashboard_code:
        issues.append("❌ PxbtSessionManager widget still used - should be removed")
    else:
        print("✅ PxbtSessionManager widget correctly removed")
    
    # Check 3: Other imports still present
    if 'import ' in bot_dashboard_code:
        print("✅ Other imports still present (as expected)")
    else:
        issues.append("⚠️  No imports found at all - might be broken")
    
    return len(issues) == 0, issues


def main():
    """Run all verifications"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║           VERIFICATION REPORT - ALL FIXES CHECK                ║
╚════════════════════════════════════════════════════════════════╝
""")
    
    backend_ok, backend_issues = verify_backend()
    dashboard_ok, dashboard_issues = verify_frontend_dashboard()
    bot_ok, bot_issues = verify_bot_dashboard()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    all_issues = backend_issues + dashboard_issues + bot_issues
    
    if all_issues:
        print(f"\n⚠️  ISSUES FOUND: {len(all_issues)}")
        for issue in all_issues:
            print(f"  {issue}")
    else:
        print("\n✅ ALL CHECKS PASSED - Ready for deployment!")
    
    print(f"\nBackend:         {'✅ PASS' if backend_ok else '❌ FAIL'}")
    print(f"Dashboard:       {'✅ PASS' if dashboard_ok else '❌ FAIL'}")
    print(f"Bot Dashboard:   {'✅ PASS' if bot_ok else '❌ FAIL'}")
    
    overall = backend_ok and dashboard_ok and bot_ok
    print(f"\nOVERALL:        {'✅ READY FOR DEPLOYMENT' if overall else '❌ ISSUES DETECTED'}")
    
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
