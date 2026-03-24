#!/usr/bin/env python3
"""
Extract closing-related logs from backend to show what happened
"""

import sys
from datetime import datetime, timedelta

# Check most recent backend log file
backend_logs = [
    r'C:\backend\backend_live.log',
    r'C:\backend\backend_restart.log',
    r'C:\backend\backend_optimized.log',
    r'C:\backend\backend_fixed.log',
]

print("=" * 80)
print("BACKEND POSITION CLOSING LOGS - LAST 30 MINUTES")
print("=" * 80)

cutoff_time = datetime.now() - timedelta(minutes=30)

lines_found = 0

for log_file in backend_logs:
    try:
        with open(log_file, 'r', errors='ignore') as f:
            lines = f.readlines()
            
        # Filter for closing-related logs
        for line in lines[-2000:]:  # Check last 2000 lines
            if any(x in line.lower() for x in ['close', 'zclose', 'exit', 'retcode', 'mt5 order_send', 'position', 'filled']):
                # Try to parse timestamp
                try:
                    if ',' in line:
                        time_part = line.split(',')[0]
                        # Skip very old lines
                        if 'INFO' in line or 'WARNING' in line or 'ERROR' in line:
                            lines_found += 1
                            print(line.rstrip())
                except:
                    pass
    except FileNotFoundError:
        pass
    except Exception as e:
        pass

if lines_found == 0:
    print("No closing-related logs found in recent backend logs")
    print("\nTo generate logs and test closing:")
    print("1. Run: python diagnose_trade_closing.py")
    print("2. Then restart backend: python multi_broker_backend_updated.py")
    print("3. Create a test bot and run it for 1 cycle")
    print("4. Check this script again")
else:
    print(f"\nFound {lines_found} closing-related log entries")

print("\n" + "=" * 80)
print("WHAT TO LOOK FOR IN LOGS:")
print("=" * 80)
print("""
✅ GOOD SIGNS:
   - "Position X closed successfully"
   - "MT5 retry succeeded"
   - "Holding symbol position for 5s before closing"
   
❌ BAD SIGNS:
   - "MT5 close failed"
   - "retcode" with error code
   - "Order not found"
   - "Authorization failed"
   
⏳ INFO:
   - How many trades were placed?
   - How many successfully closed?
   - Are there retry attempts?
""")
