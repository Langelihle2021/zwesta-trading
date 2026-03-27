"""Audit VPS backend endpoints"""
import requests
VPS = 'http://38.247.146.198:9000'

results = []

# 1. Health
try:
    r = requests.get(f'{VPS}/api/health', timeout=10)
    results.append(f"Health: {r.status_code} {r.json().get('status','?')}")
except Exception as e:
    results.append(f"Health: FAILED {e}")

# 2. Login
token = ''
uid = ''
try:
    r = requests.post(f'{VPS}/api/user/login', json={'email':'trader2@example.com','password':'password123'}, timeout=10)
    d = r.json()
    token = d.get('session_token','')
    uid = d.get('user_id','')
    results.append(f"Login: {r.status_code} OK (token={token[:16]}...)")
except Exception as e:
    results.append(f"Login: FAILED {e}")

headers = {'X-Session-Token': token, 'Content-Type': 'application/json'}

# 3. Bot status
try:
    r = requests.get(f'{VPS}/api/bot/status', headers=headers, timeout=10)
    bots = r.json().get('bots', [])
    results.append(f"Bot status: {r.status_code} bots={len(bots)}")
except Exception as e:
    results.append(f"Bot status: FAILED {e}")

# 4. User settings (NEW endpoint)
try:
    r = requests.post(f'{VPS}/api/user/settings', headers=headers, json={'two_factor_enabled': True}, timeout=10)
    results.append(f"User settings: {r.status_code} {r.text[:80]}")
except Exception as e:
    results.append(f"User settings: FAILED {e}")

# 5. Profile
try:
    r = requests.get(f'{VPS}/api/user/profile/{uid}', headers=headers, timeout=10)
    name = r.json().get('user', {}).get('name', '?')
    results.append(f"Profile: {r.status_code} name={name}")
except Exception as e:
    results.append(f"Profile: FAILED {e}")

# 6. Commodities
try:
    r = requests.get(f'{VPS}/api/commodities/list', headers=headers, timeout=10)
    count = len(r.json().get('commodities', []))
    results.append(f"Commodities: {r.status_code} count={count}")
except Exception as e:
    results.append(f"Commodities: FAILED {e}")

# 7. Change password
try:
    r = requests.post(f'{VPS}/api/user/change-password', headers=headers, json={'current_password':'test','new_password':'test'}, timeout=10)
    results.append(f"Change password: {r.status_code} {r.text[:80]}")
except Exception as e:
    results.append(f"Change password: FAILED {e}")

# 8. Broker credentials list
try:
    r = requests.get(f'{VPS}/api/user/{uid}/broker-credentials', headers=headers, timeout=10)
    results.append(f"Broker creds: {r.status_code}")
except Exception as e:
    results.append(f"Broker creds: FAILED {e}")

# 9. Update profile
try:
    r = requests.put(f'{VPS}/api/user/profile/{uid}', headers=headers, json={'name':'Alice Trader'}, timeout=10)
    results.append(f"Update profile: {r.status_code} {r.text[:80]}")
except Exception as e:
    results.append(f"Update profile: FAILED {e}")

print("=" * 60)
print("VPS BACKEND ENDPOINT AUDIT")
print("=" * 60)
for line in results:
    status = "PASS" if ("200 " in line or "201 " in line) else "FAIL"
    icon = "OK" if status == "PASS" else "XX"
    print(f"[{icon}] {line}")
print("=" * 60)
