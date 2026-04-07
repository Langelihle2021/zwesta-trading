"""
VPS Login Fix #2 — Run on VPS: python vps_fix_login2.py
Fixes:
  1. WORKER_COUNT=3 -> 0 in .env  (stops crashing worker restart loops)
  2. Adds 5-retry DB logic to login_user() (handles startup DB lock)
"""
import os

ENV_FILE   = r'C:\backend\.env'
BACKEND_FILE = r'C:\backend\multi_broker_backend_updated.py'

# ─── FIX 1: Set WORKER_COUNT=0 in .env ───────────────────────
with open(ENV_FILE, 'r', encoding='utf-8') as f:
    env_src = f.read()

import re
new_env = re.sub(r'^WORKER_COUNT\s*=\s*\d+', 'WORKER_COUNT=0', env_src, flags=re.MULTILINE)
if new_env != env_src:
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write(new_env)
    print("[OK] Fix 1: WORKER_COUNT=0 set in .env")
else:
    print("[SKIP] Fix 1: WORKER_COUNT already 0")

# ─── FIX 2: Add retry logic to login_user() ──────────────────
with open(BACKEND_FILE, 'r', encoding='utf-8') as f:
    src = f.read()

OLD_LOGIN = (
    "        if not email:\n"
    "            return jsonify({'success': False, 'error': 'Email required'}), 400\n"
    "        \n"
    "        conn = get_db_connection()\n"
    "        cursor = conn.cursor()"
)
NEW_LOGIN = (
    "        if not email:\n"
    "            return jsonify({'success': False, 'error': 'Email required'}), 400\n"
    "        \n"
    "        # Retry DB connection up to 5x \u2014 bots lock DB briefly on startup\n"
    "        conn = None\n"
    "        for _db_attempt in range(5):\n"
    "            try:\n"
    "                conn = get_db_connection()\n"
    "                break\n"
    "            except Exception as _db_err:\n"
    "                if _db_attempt < 4:\n"
    "                    time.sleep(1.0)\n"
    "                else:\n"
    "                    raise\n"
    "        cursor = conn.cursor()"
)

if "_db_attempt" in src:
    print("[SKIP] Fix 2: login retry already applied")
elif OLD_LOGIN in src:
    src = src.replace(OLD_LOGIN, NEW_LOGIN, 1)
    with open(BACKEND_FILE, 'w', encoding='utf-8') as f:
        f.write(src)
    print("[OK] Fix 2: login DB retry logic added")
else:
    print("[WARN] Fix 2: pattern not found - check file manually")
    # Try alternate pattern (in case whitespace differs)
    OLD2 = (
        "        if not email:\n"
        "            return jsonify({'success': False, 'error': 'Email required'}), 400\n"
        "\n"
        "        conn = get_db_connection()\n"
        "        cursor = conn.cursor()"
    )
    if OLD2 in src:
        src = src.replace(OLD2, NEW_LOGIN, 1)
        with open(BACKEND_FILE, 'w', encoding='utf-8') as f:
            f.write(src)
        print("[OK] Fix 2 (alt): login DB retry logic added")

print("\nDone. Now restart the backend:")
print("  taskkill /F /IM python.exe")
print("  cd C:\\backend")
print("  start /B pythonw multi_broker_backend_updated.py")
