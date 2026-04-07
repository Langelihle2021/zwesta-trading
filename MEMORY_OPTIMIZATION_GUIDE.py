#!/usr/bin/env python3
"""
Backend Memory Optimization - Reduce Flask process memory usage
- Clear in-memory caches periodically
- Limit cache sizes
- Garbage collection optimization
- Connection pooling
"""

import sqlite3
import gc
import sys
from datetime import datetime, timedelta

print("""
╔════════════════════════════════════════════════════════════════╗
║         BACKEND MEMORY OPTIMIZATION RECOMMENDATIONS            ║
╚════════════════════════════════════════════════════════════════╝

🔧 QUICK WINS (Implement in multi_broker_backend_updated.py):

1. LIMIT BALANCE CACHE SIZE
   Add max entries cap to prevent unbounded growth:
   
   # In global section:
   MAX_BALANCE_CACHE_ENTRIES = 50
   MAX_PRICE_HISTORY_SIZE = 1000  # Per symbol
   
   # In cache update:
   if len(balance_cache) > MAX_BALANCE_CACHE_ENTRIES:
       # Remove oldest entries
       oldest_key = min(balance_cache, key=lambda k: balance_cache[k]['timestamp'])
       del balance_cache[oldest_key]

2. PERIODIC GARBAGE COLLECTION
   Add cleanup during idle periods:
   
   # After each trade cycle or hourly:
   gc.collect()
   logger.info(f"Memory cleanup: {gc.get_count()} objects")

3. LIMIT PRICE HISTORY SIZE
   Replace unbounded lists with circular buffers:
   
   # Use collections.deque with maxlen
   from collections import deque
   price_history[symbol] = deque(maxlen=500)  # Keep only 500 entries

4. DISABLE UNNECESSARY LOGGING
   Reduce string allocations in hot loops:
   
   # Replace frequent logger.info() in trade loops with:
   if DEBUG_MODE:  # Only log if debug enabled
       logger.debug(f"Detailed info...")

5. CONNECTION POOLING
   Reuse database connections instead of creating new ones:
   
   # Use connection pool for MT5
   from queue import Queue
   mt5_connection_pool = Queue(maxsize=10)

🔍 MONITORING CHECKLIST:

□ Check memory usage before/after restart:    python vps_memory_monitor.py
□ Monitor backend process growth:             python monitor_backend.py
□ Check Flask app memory footprint:           python flask_memory_analyzer.py
□ Set up alerts for >80% memory usage
□ Create auto-restart script if >90% memory

📊 TYPICAL MEMORY USAGE (Expected):

✅ Flask backend + MT5 API:     200-500 MB
✅ SQLite database + cache:      100-200 MB  
✅ Python runtime + libraries:   100-150 MB
─────────────────────────────────────────────
   TOTAL HEALTHY:                400-850 MB

⚠️  WARNING SIGNS:

❌ Backend using >1000 MB (1 GB) = Memory leak likely
❌ Memory grows 10+ MB per minute = Accumulation issue
❌ VPS swap usage increasing = Physical RAM exhausted
❌ High CPU + high memory = Garbage collection struggles

🔴 CRITICAL ACTION (If >90% used):

1. Kill backend: Ctrl+C in terminal
2. Restart backend: python multi_broker_backend_updated.py
3. If problem persists: Run daily restart script at 2 AM

📋 CREATE DAILY RESTART SCRIPT:

Create file: restart_backend_daily.py
- Checks memory every hour
- Auto-restarts if >90% for >10 minutes
- Logs restart reason
- Notifies user via email/webhook

═══════════════════════════════════════════════════════════════════
""")

# Give specific implementation code
print("\n💻 READY-TO-USE CODE SNIPPETS:\n")

print("=" * 70)
print("1. ADD TO TOP OF multi_broker_backend_updated.py:")
print("=" * 70)
print("""
import gc
from collections import deque
from threading import Timer

# Memory management constants
MAX_BALANCE_CACHE_ENTRIES = 50
MAX_PRICE_HISTORY_ENTRIES = 500
CLEANUP_INTERVAL_SECONDS = 300  # Run cleanup every 5 minutes

def periodic_cleanup():
    '''Periodic memory cleanup to prevent leaks'''
    global balance_cache, price_history
    
    try:
        # Limit balance cache
        if len(balance_cache) > MAX_BALANCE_CACHE_ENTRIES:
            # Remove 25% oldest entries
            to_remove = len(balance_cache) // 4
            for _ in range(to_remove):
                oldest = min(balance_cache, key=lambda k: balance_cache[k].get('timestamp', 0))
                del balance_cache[oldest]
            logger.info(f'✅ Trimmed balance_cache to {len(balance_cache)} entries')
        
        # Force garbage collection in bot loops
        gc.collect()
        
        # Schedule next cleanup
        timer = Timer(CLEANUP_INTERVAL_SECONDS, periodic_cleanup)
        timer.daemon = True
        timer.start()
        
    except Exception as e:
        logger.warning(f'Cleanup error: {e}')

# Start cleanup on app startup
periodic_cleanup()
""")

print("\n" + "=" * 70)
print("2. CONVERT price_history TO DEQUE (Bounded memory):")
print("=" * 70)
print("""
# Replace:
#   price_history[symbol] = self.price_data[-50:]  # Growing list!

# With:
#   from collections import deque
#   price_history[symbol] = deque(self.price_data[-500:], maxlen=500)
#   # Now capped at 500 entries, never grows beyond that
""")

print("\n" + "=" * 70)
print("3. AUTO-RESTART IF MEMORY CRITICAL:")
print("=" * 70)
print("""
# Add to backend startup:
def monitor_memory():
    '''Monitor backend memory and restart if critical'''
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024 * 1024)
    memory_percent = psutil.virtual_memory().percent
    
    if memory_percent > 90:
        logger.critical(f'🔴 CRITICAL: {memory_percent}% memory - RESTARTING')
        # Notify user (optional)
        # send_alert(f'Backend restarted due to memory: {memory_mb} MB')
        os.system('restart_backend_service')  # Requires configured service
    
    # Schedule next check
    Timer(60, monitor_memory).daemon = True
    Timer(60, monitor_memory).start()

monitor_memory()  # Start on app boot
""")

print("\n" + "=" * 70)
print("4. CHECK CURRENT MEMORY LEAK:")
print("=" * 70)
print("""
# Run this to identify what's growing:

import tracemalloc
import sys

tracemalloc.start()

# ... run bot for 5 minutes ...

current, peak = tracemalloc.get_traced_memory()
print(f'Current: {current / 1024 / 1024:.1f} MB')
print(f'Peak: {peak / 1024 / 1024:.1f} MB')

# Print top memory consumers:
stats = tracemalloc.take_snapshot().statistics('lineno')
for stat in stats[:10]:
    print(stat)
""")

print("\n" + "="*70)
print("RECOMMENDED: Run vps_memory_monitor.py every 5 minutes")
print("="*70)
