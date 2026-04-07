"""
VPS Login Fix - Apply DB/login/startup fixes to the running backend file.
Run this on the VPS:  python vps_fix_login.py
"""
import re

BACKEND_FILE = r'C:\backend\multi_broker_backend_updated.py'
ENV_FILE = r'C:\backend\.env'

try:
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        env_src = f.read()
    new_env = re.sub(r'^WORKER_COUNT\s*=\s*\d+', 'WORKER_COUNT=0', env_src, flags=re.MULTILINE)
    new_env = re.sub(r'^AUTO_RESTART_BOTS_ON_STARTUP\s*=\s*true', 'AUTO_RESTART_BOTS_ON_STARTUP=false', new_env, flags=re.MULTILINE | re.IGNORECASE)
    if new_env != env_src:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(new_env)
        print('[OK] Fix 0 applied: WORKER_COUNT=0 and AUTO_RESTART_BOTS_ON_STARTUP=false set in .env')
    else:
        print('[SKIP] Fix 0 already applied: .env startup settings already safe')
except FileNotFoundError:
    print('[WARN] Fix 0: .env not found — check C:\\backend\\.env manually')

with open(BACKEND_FILE, 'r', encoding='utf-8') as f:
    src = f.read()

original = src

# ──────────────────────────────────────────────────────────────
# FIX 1: get_db_connection — timeout=30.0 → 3.0 + busy_timeout
# ──────────────────────────────────────────────────────────────
OLD1 = (
    "def get_db_connection():\n"
    '    """Get database connection with WAL mode for concurrent writes"""\n'
    "    conn = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)\n"
    "    conn.row_factory = sqlite3.Row\n"
    "    # Enable WAL mode for concurrent access\n"
    "    conn.execute('PRAGMA journal_mode=WAL')\n"
    "    conn.execute('PRAGMA synchronous=NORMAL')\n"
    "    return conn"
)
NEW1 = (
    "def get_db_connection():\n"
    '    """Get database connection with WAL mode for concurrent writes"""\n'
    "    conn = sqlite3.connect(DATABASE_PATH, timeout=3.0, check_same_thread=False)\n"
    "    conn.row_factory = sqlite3.Row\n"
    "    # Enable WAL mode — set busy_timeout BEFORE journal_mode\n"
    "    conn.execute('PRAGMA busy_timeout = 1500')\n"
    "    conn.execute('PRAGMA journal_mode=WAL')\n"
    "    conn.execute('PRAGMA synchronous=NORMAL')\n"
    "    return conn"
)
if OLD1 in src:
    src = src.replace(OLD1, NEW1, 1)
    print("[OK] Fix 1 applied: get_db_connection timeout=3.0 + busy_timeout")
elif "timeout=3.0" in src and "busy_timeout" in src:
    print("[SKIP] Fix 1 already applied")
elif "timeout=3.0" in src:
    # timeout already 3.0 but no busy_timeout — add it
    OLD1B = (
        "def get_db_connection():\n"
        '    """Get database connection with WAL mode for concurrent writes"""\n'
        "    conn = sqlite3.connect(DATABASE_PATH, timeout=3.0, check_same_thread=False)\n"
        "    conn.row_factory = sqlite3.Row\n"
        "    # Enable WAL mode for concurrent access\n"
        "    conn.execute('PRAGMA journal_mode=WAL')\n"
        "    conn.execute('PRAGMA synchronous=NORMAL')\n"
        "    return conn"
    )
    if OLD1B in src:
        src = src.replace(OLD1B, NEW1, 1)
        print("[OK] Fix 1b applied: added busy_timeout (timeout=3.0 was already present)")
    else:
        print("[WARN] Fix 1: pattern not found — check file manually")
else:
    print("[WARN] Fix 1: pattern not found — check file manually")

# ──────────────────────────────────────────────────────────────
# FIX 2 (debounce): persist_bot_runtime_state — add 30s guard
# ──────────────────────────────────────────────────────────────
OLD2 = (
    "def persist_bot_runtime_state(bot_id: str):\n"
    '    """Persist bot runtime metrics so they can be restored after a VPS restart."""\n'
    "    bot_config = active_bots.get(bot_id)"
)
NEW2 = (
    "_persist_last_time: dict = {}\n"
    "\n"
    "def persist_bot_runtime_state(bot_id: str):\n"
    '    """Persist bot runtime metrics so they can be restored after a VPS restart."""\n'
    "    global _persist_last_time\n"
    "    _now = time.time()\n"
    "    if _now - _persist_last_time.get(bot_id, 0) < 30:\n"
    "        return  # Debounce: max 1 DB write per bot per 30 seconds\n"
    "    _persist_last_time[bot_id] = _now\n"
    "\n"
    "    bot_config = active_bots.get(bot_id)"
)
if "_persist_last_time" in src:
    print("[SKIP] Fix 2 (debounce) already applied")
elif OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)
    print("[OK] Fix 2 applied: persist_bot_runtime_state 30s debounce")
else:
    print("[WARN] Fix 2: pattern not found — check file manually")

# ──────────────────────────────────────────────────────────────
# FIX 3 (background thread): move bot startup off main thread
# ──────────────────────────────────────────────────────────────
OLD3 = (
    "    restarted_bots = start_enabled_bots_on_startup()\n"
    "    logger.info(f\"[OK] Auto-restarted {restarted_bots} enabled bots after backend startup\")"
)
NEW3 = (
    "    restarted_bots = None  # Will be set by background thread\n"
    "    def _bg_bot_startup():\n"
    "        n = start_enabled_bots_on_startup()\n"
    "        logger.info(f\"[OK] Auto-restarted {n} enabled bots after backend startup\")\n"
    "    threading.Thread(target=_bg_bot_startup, daemon=True).start()\n"
    "    logger.info(\"[OK] Bot startup running in background - Flask starting now\")"
)
if "_bg_bot_startup" in src:
    print("[SKIP] Fix 3 (background thread) already applied")
elif OLD3 in src:
    src = src.replace(OLD3, NEW3, 1)
    print("[OK] Fix 3 applied: bot startup moved to background thread")
else:
    print("[WARN] Fix 3: pattern not found — check file manually")

# ──────────────────────────────────────────────────────────────
# FIX 4: stop startup path from forcing an immediate bot-state DB write
# ──────────────────────────────────────────────────────────────
OLD4 = (
    "        bot_stop_flags[bot_id] = False\n"
    "        running_bots[bot_id] = True\n"
    "        bot_credentials = _get_bot_thread_credentials(bot_config)\n"
    "        persist_bot_runtime_state(bot_id)\n"
    "\n"
    "        bot_thread = threading.Thread("
)
NEW4 = (
    "        bot_stop_flags[bot_id] = False\n"
    "        running_bots[bot_id] = True\n"
    "        bot_credentials = _get_bot_thread_credentials(bot_config)\n"
    "\n"
    "        bot_thread = threading.Thread("
)
if OLD4 in src:
    src = src.replace(OLD4, NEW4, 1)
    print("[OK] Fix 4 applied: removed startup persist_bot_runtime_state() write")
else:
    print("[SKIP] Fix 4 already applied or pattern not found")

# ──────────────────────────────────────────────────────────────
# FIX 5: retry session insert/commit in login_user()
# ──────────────────────────────────────────────────────────────
OLD5 = (
    "        # No 2FA — create full session\n"
    "        session_id = str(uuid.uuid4())\n"
    "        token = hashlib.sha256(f\"{user_id}{datetime.now().isoformat()}\".encode()).hexdigest()\n"
    "        expires_at = (datetime.now() + timedelta(days=30)).isoformat()\n"
    "        \n"
    "        cursor.execute('''\n"
    "            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)\n"
    "            VALUES (?, ?, ?, ?, ?, 1)\n"
    "        ''', (session_id, user_id, token, datetime.now().isoformat(), expires_at))\n"
    "        \n"
    "        conn.commit()"
)
NEW5 = (
    "        # No 2FA — create full session\n"
    "        session_id = str(uuid.uuid4())\n"
    "        token = hashlib.sha256(f\"{user_id}{datetime.now().isoformat()}\".encode()).hexdigest()\n"
    "        expires_at = (datetime.now() + timedelta(days=30)).isoformat()\n"
    "\n"
    "        created_at = datetime.now().isoformat()\n"
    "        session_saved = False\n"
    "        for _session_attempt in range(5):\n"
    "            try:\n"
    "                cursor.execute('''\n"
    "                    INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)\n"
    "                    VALUES (?, ?, ?, ?, ?, 1)\n"
    "                ''', (session_id, user_id, token, created_at, expires_at))\n"
    "                conn.commit()\n"
    "                session_saved = True\n"
    "                break\n"
    "            except sqlite3.OperationalError as session_err:\n"
    "                if 'locked' not in str(session_err).lower():\n"
    "                    raise\n"
    "                conn.rollback()\n"
    "                if _session_attempt >= 4:\n"
    "                    logger.warning(f\"Session table still locked after retries for {email}; using temporary session cache\")\n"
    "                    break\n"
    "                time.sleep(1.0)\n"
    "\n"
    "        if not session_saved:\n"
    "            raise RuntimeError('Could not create user session due to database lock')"
)
if "session_saved = False" in src:
    BUGGY5 = (
        "            except sqlite3.OperationalError as session_err:\n"
        "                if 'locked' not in str(session_err).lower() or _session_attempt >= 4:\n"
        "                    raise\n"
        "                time.sleep(1.0)\n"
    )
    FIXED5 = (
        "            except sqlite3.OperationalError as session_err:\n"
        "                if 'locked' not in str(session_err).lower():\n"
        "                    raise\n"
        "                conn.rollback()\n"
        "                if _session_attempt >= 4:\n"
        "                    logger.warning(f\"Session table still locked after retries for {email}; using temporary session cache\")\n"
        "                    break\n"
        "                time.sleep(1.0)\n"
    )
    if BUGGY5 in src:
        src = src.replace(BUGGY5, FIXED5, 1)
        print("[OK] Fix 5b applied: repaired session retry fallback to stop raising on final DB lock")
    else:
        print("[SKIP] Fix 5 already applied")
elif OLD5 in src:
    src = src.replace(OLD5, NEW5, 1)
    print("[OK] Fix 5 applied: login session write retries on DB lock")
else:
    print("[WARN] Fix 5: pattern not found — check login_user manually")

# ──────────────────────────────────────────────────────────────
# FIX 6: temporary in-memory session fallback for login/session validation
# ──────────────────────────────────────────────────────────────
if "TEMP_SESSION_CACHE = {}" not in src:
    anchor = "# Initialize backup system\nbackup_manager, recovery_manager = init_backup_system(app)"
    replacement = anchor + "\n\nTEMP_SESSION_CACHE = {}"
    if anchor in src:
        src = src.replace(anchor, replacement, 1)
        print("[OK] Fix 6a applied: temporary session cache added")
    else:
        print("[WARN] Fix 6a: anchor not found — add TEMP_SESSION_CACHE manually")
else:
    print("[SKIP] Fix 6a already applied")

OLD6B = (
    "        if not session_token:\n"
    "            logger.error(f\"[SESSION FAIL] Missing X-Session-Token header for {request.endpoint}\")\n"
    "            return jsonify({'success': False, 'error': 'Missing session token in X-Session-Token header'}), 401\n"
    "\n"
    "        try:\n"
)
NEW6B = (
    "        if not session_token:\n"
    "            logger.error(f\"[SESSION FAIL] Missing X-Session-Token header for {request.endpoint}\")\n"
    "            return jsonify({'success': False, 'error': 'Missing session token in X-Session-Token header'}), 401\n"
    "\n"
    "        cached_session = TEMP_SESSION_CACHE.get(session_token)\n"
    "        if cached_session:\n"
    "            expires_at = datetime.fromisoformat(cached_session['expires_at'])\n"
    "            if expires_at >= datetime.now():\n"
    "                request.user_id = cached_session['user_id']\n"
    "                logger.info(f\"[SESSION OK] Temporary cached session for user {cached_session['user_id']} authenticated for {request.endpoint}\")\n"
    "                return f(*args, **kwargs)\n"
    "            TEMP_SESSION_CACHE.pop(session_token, None)\n"
    "\n"
    "        try:\n"
)
if "cached_session = TEMP_SESSION_CACHE.get(session_token)" in src:
    print("[SKIP] Fix 6b already applied")
elif OLD6B in src:
    src = src.replace(OLD6B, NEW6B, 1)
    print("[OK] Fix 6b applied: require_session temporary cache fallback")
else:
    print("[WARN] Fix 6b: pattern not found — update require_session manually")

OLD6C = (
    "        # Find user by email\n"
    "        cursor.execute('SELECT user_id, name, email, referral_code, password_hash FROM users WHERE email = ?', (email,))\n"
    "        user = cursor.fetchone()"
)
NEW6C = (
    "        # Find user by email, retry if the DB is briefly locked during startup/recovery.\n"
    "        user = None\n"
    "        for _query_attempt in range(5):\n"
    "            try:\n"
    "                cursor.execute('SELECT user_id, name, email, referral_code, password_hash FROM users WHERE email = ?', (email,))\n"
    "                user = cursor.fetchone()\n"
    "                break\n"
    "            except sqlite3.OperationalError as query_err:\n"
    "                if 'locked' not in str(query_err).lower() or _query_attempt >= 4:\n"
    "                    raise\n"
    "                time.sleep(1.0)"
)
if "for _query_attempt in range(5):" in src:
    print("[SKIP] Fix 6c already applied")
elif OLD6C in src:
    src = src.replace(OLD6C, NEW6C, 1)
    print("[OK] Fix 6c applied: login query retries on DB lock")
else:
    print("[WARN] Fix 6c: pattern not found — update login query manually")

OLD6D = (
    "        if not session_saved:\n"
    "            raise RuntimeError('Could not create user session due to database lock')"
)
NEW6D = (
    "        if not session_saved:\n"
    "            TEMP_SESSION_CACHE[token] = {\n"
    "                'user_id': user_id,\n"
    "                'expires_at': expires_at,\n"
    "            }\n"
    "            logger.warning(f\"Login session stored in temporary cache for {email} due to DB lock\")"
)
if "Login session stored in temporary cache" in src:
    print("[SKIP] Fix 6d already applied")
elif OLD6D in src:
    src = src.replace(OLD6D, NEW6D, 1)
    print("[OK] Fix 6d applied: login falls back to temporary session cache")
else:
    print("[WARN] Fix 6d: pattern not found — update login fallback manually")

# ──────────────────────────────────────────────────────────────
# Write result
# ──────────────────────────────────────────────────────────────
if src != original:
    backup = BACKEND_FILE + '.pre_login_fix.bak'
    with open(backup, 'w', encoding='utf-8') as f:
        f.write(original)
    print(f"[OK] Backup saved: {backup}")
    with open(BACKEND_FILE, 'w', encoding='utf-8') as f:
        f.write(src)
    print("[OK] Backend file updated. Restart the backend to apply changes.")
else:
    print("[INFO] No changes made to backend file.")
