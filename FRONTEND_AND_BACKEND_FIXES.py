#!/usr/bin/env python3
"""
COMPREHENSIVE FRONTEND & BACKEND FIX
1. Remove stale XM broker code from backend
2. Fix double balance display in frontend dashboard
3. Remove unused bot configuration settings
"""

print("""
╔════════════════════════════════════════════════════════════════╗
║          FRONTEND & BACKEND CLEANUP - ACTION PLAN              ║
╚════════════════════════════════════════════════════════════════╝

🎯 ISSUE 1: REMOVE STALE XM CODE FROM BACKEND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current State: XM (XM Global) broker code is unused in production
  - Only using Exness broker
  - XM classes defined but never instantiated
  - Wastes 200+ lines of code

Code to Remove:
  ❌ BrokerType.XM enum (line 959)
  ❌ XMConnection class (lines 4079-4290, ~210 lines)
  ❌ XM connection in factory (lines 4312-4315)
  ❌ XM references in __init__ default env variables
  ❌ XM in broker name canonicalization

Changes Required: 4 replacements in multi_broker_backend_updated.py

═══════════════════════════════════════════════════════════════════

✅ ISSUE 2: FIX DOUBLE BALANCE DISPLAY IN FRONTEND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current State: Balance displayed twice on dashboard
  Section 1: "Total Portfolio Balance" card (lines 1140-1189)
  Section 2: "Broker Accounts" card (lines 1215+ shows balance again)
  
Problem: Same balance value (filteredTotal) calculated twice and shown twice

Solution: Remove the balance display from "Broker Accounts" card header
  Keep: Detailed account-by-account breakdown
  Remove: Duplicate total balance in card header

Changes Required: 1 replacement in dashboard_screen.dart

═══════════════════════════════════════════════════════════════════

🧹 ISSUE 3: REMOVE UNUSED BOT CONFIG SETTINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Unused Fields Identified:

Backend (multi_broker_backend_updated.py):
  📌 pxbt_strategy (deprecated, replaced with unified strategy field)
  📌 demo-only configuration mode (Exness handles via is_live flag)
  📌 Old commission config fields (replaced with simpler structure)

Frontend (Dart files):
  📌 PXBT session manager widget (lines detect in pxbt_session_manager.dart)
  📌 Old trading mode switcher (replaced with mode dropdown)
  📌 Deprecated strategy selection fields

Changes Required:
  - Backend: Remove pxbt_strategy references
  - Frontend: Remove PXBT widget imports
  - Database: Optional migration to clean schema

═══════════════════════════════════════════════════════════════════

📋 DETAILED CHANGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BACKEND CHANGES (multi_broker_backend_updated.py):

🔧 REPLACEMENT 1: Remove XM from BrokerType enum
   Location: Line 959-967
   Old: XM = "xm" ... DARWINEX = "darwinex"
   New: Remove only XM = "xm" line (keep others)
   
🔧 REPLACEMENT 2: Remove XMConnection class  
   Location: Lines 4079-4290
   This is the entire XMConnection class definition (~210 lines)
   Remove completely

🔧 REPLACEMENT 3: Remove XM from connection factory
   Location: Lines 4312-4315 (in add_connection method)
   Old: elif broker_type == BrokerType.XM: connection = XMConnection(...)
   New: Remove these lines

🔧 REPLACEMENT 4: Remove XM from canonicalize_broker_name function
   Location: Search for function that handles broker names
   Remove: 'XM', 'XMGlobal' references
   Keep: Only Exness, Binance, BinanceSpot, BinanceFutures

─────────────────────────────────────────────────────────────────

FRONTEND CHANGES (dashboard_screen.dart):

🎨 REPLACEMENT 5: Fix double balance display
   Location: Lines 1215-1240 (in _buildBrokerAccountsCard)
   
   Current code:
   ```dart
   Row(
     mainAxisAlignment: MainAxisAlignment.spaceBetween,
     children: [
       Text('Broker Accounts', ...),
       Text('\$${shownTotal.toStringAsFixed(2)}', ...),  // ❌ DUPLICATE!
     ],
   ),
   ```
   
   Fixed code:
   ```dart
   Text('Broker Accounts', style: GoogleFonts.poppins(
     color: Colors.white, fontSize: 17, fontWeight: FontWeight.w600))
   ```
   Remove the balance display from header - it's already shown in summary above

   Updated Content: Only show account-by-account breakdown below, not double total

─────────────────────────────────────────────────────────────────

BOT CONFIG CLEANUP:

📝 REPLACEMENT 6: Remove PXBT imports from bot_configuration_screen.dart
   Remove: import '../widgets/pxbt_session_manager.dart';
   Remove: References to PXBT session manager widget

📝 REPLACEMENT 7: Remove pxbt_strategy from bot creation API
   Location: /api/bots/create endpoint
   Remove field: "pxbt_strategy" (no longer used)
   Keep field: "strategy" (unified field for all strategies)

═══════════════════════════════════════════════════════════════════

⚠️  TESTING CHECKLIST AFTER CHANGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Backend Tests:
  ☐ Backend starts without errors
  ☐ Exness broker connections work normally
  ☐ No references to "XM" in logs
  ☐ /api/accounts/balances returns correct data
  ☐ Bot creation endpoint works
  ☐ No import errors for missing XMConnection

Frontend Tests:
  ☐ Dashboard loads without errors
  ☐ "Total Portfolio Balance" shows correct amount
  ☐ "Broker Accounts" section shows individual accounts
  ☐ Balance NOT duplicated (display once, not twice)
  ☐ No red warnings about missing widgets
  ☐ Bot creation form accepts all required fields

═══════════════════════════════════════════════════════════════════

🚀 DEPLOYMENT STEPS
━━━━━━━━━━━━━━━━━━━

1. Apply all code changes (6 replacements)
2. Test locally if possible
3. Copy fixed files to VPS:
   - c:\\backend\\multi_broker_backend_updated.py
   - lib/screens/dashboard_screen.dart
   - lib/screens/bot_configuration_screen.dart
4. Restart backend: python multi_broker_backend_updated.py
5. Recompile/deploy Flutter app if needed
6. Verify in production

═══════════════════════════════════════════════════════════════════

📊 SUMMARY OF CHANGES

Files Modified: 3
  - multi_broker_backend_updated.py (4 replacements)
  - dashboard_screen.dart (1 replacement)
  - bot_configuration_screen.dart (1 replacement)

Lines Removed: ~220 (XM code cleanup)
Lines Modified: ~5 (balance display, imports)

Benefits:
  ✅ Cleaner codebase (-220 unused lines)
  ✅ Accurate dashboard balance display
  ✅ Removed confusing unused settings
  ✅ Faster code compilation
  ✅ Reduced maintenance burden

═══════════════════════════════════════════════════════════════════
""")

print("\n✅ Review complete. Ready to apply changes to files.")
print("\nNext: Backend changes will be applied automatically.")
