"""Comprehensive backend API evaluation"""
import requests
import json

VPS = "http://38.247.146.198:9000"

def test_endpoint(name, method, url, **kwargs):
    try:
        r = getattr(requests, method)(url, timeout=10, **kwargs)
        return r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else r.text[:200]
    except Exception as e:
        return 0, str(e)

print("=" * 60)
print("ZWESTA BACKEND COMPREHENSIVE EVALUATION")
print("=" * 60)

# 1. Health
print("\n[1] HEALTH CHECK")
code, data = test_endpoint("health", "get", f"{VPS}/api/health")
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    print(f"    Version: {data.get('version')} | Service: {data.get('service')}")

# 2. Login
print("\n[2] LOGIN")
code, data = test_endpoint("login", "post", f"{VPS}/api/user/login",
    json={"email": "trader2@example.com", "password": "password123"})
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
token = ""
user_id = ""
if isinstance(data, dict) and data.get("success"):
    token = data["session_token"]
    user_id = data["user_id"]
    print(f"    User: {data.get('name')} | ID: {user_id[:16]}...")
else:
    print(f"    Error: {data}")

headers = {"X-Session-Token": token}

# 3. Profile
print("\n[3] USER PROFILE")
code, data = test_endpoint("profile", "get", f"{VPS}/api/user/profile/{user_id}", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    user = data.get("user", {})
    print(f"    Name: {user.get('name')} | Email: {user.get('email')}")
    print(f"    Bots: {data.get('total_bots')} | Brokers: {data.get('total_brokers')}")
    print(f"    Referral: {user.get('referral_code')}")

# 4. Bot status
print("\n[4] BOT STATUS")
code, data = test_endpoint("bots", "get", f"{VPS}/api/bot/status", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    bots = data.get("bots", [])
    print(f"    Active: {data.get('activeBots')} | Total: {len(bots)}")
    for b in bots[:3]:
        bid = b.get("botId", "?")
        print(f"    -> {bid[:25]} | {b.get('strategy')} | Enabled:{b.get('enabled')} | P&L:${b.get('totalProfit',0):.2f} | Trades:{b.get('totalTrades',0)}")
        print(f"       Open positions: {len(b.get('openPositions',[]))} | Balance: ${b.get('accountBalance',0):.2f}")
        if b.get("stopReason"):
            print(f"       Stop reason: {b.get('stopReason')}")

# 5. Commodities
print("\n[5] COMMODITIES/SYMBOLS LIST")
code, data = test_endpoint("commodities", "get", f"{VPS}/api/commodities/list", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    syms = data.get("symbols", data.get("commodities", []))
    print(f"    Total symbols: {len(syms)}")
    if syms:
        if isinstance(syms, list):
            sample = syms[:6]
        elif isinstance(syms, dict):
            sample = list(syms.keys())[:6]
        else:
            sample = str(syms)[:200]
        print(f"    Sample: {sample}")

# 6. User settings (new)
print("\n[6] USER SETTINGS ENDPOINT (NEW)")
code, data = test_endpoint("settings", "post", f"{VPS}/api/user/settings",
    headers={**headers, "Content-Type": "application/json"},
    json={"two_factor_enabled": False})
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    print(f"    Response: {data.get('message', data.get('error', 'unknown'))}")

# 7. Register validation
print("\n[7] REGISTER (VALIDATION)")
code, data = test_endpoint("register", "post", f"{VPS}/api/user/register",
    json={"email": "", "password": "", "name": ""})
print(f"    Status: {code} | Rejects empty: {'PASS' if code >= 400 else 'FAIL'}")

# 8. Broker test-connection (check endpoint exists)
print("\n[8] BROKER TEST-CONNECTION ENDPOINT")
code, data = test_endpoint("broker-test", "post", f"{VPS}/api/broker/test-connection",
    headers=headers, json={"broker_name": "Test", "account_number": "0", "password": "test", "server": "test"})
print(f"    Status: {code} | Endpoint exists: {'PASS' if code != 404 else 'FAIL'}")

# 9. Delete-all-bots endpoint
print("\n[9] DELETE-ALL-BOTS ENDPOINT")
code, data = test_endpoint("delete-bots", "post", f"{VPS}/api/bots/delete-all", headers=headers)
print(f"    Status: {code} | Endpoint exists: {'PASS' if code != 404 else 'FAIL'}")
if isinstance(data, dict):
    print(f"    Deleted: {data.get('deleted_count', 0)} bots")

# 10. Bot strategies
print("\n[10] BOT STRATEGIES")
code, data = test_endpoint("strategies", "get", f"{VPS}/api/bot/strategies", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL' if code != 404 else 'NOT FOUND'}")

# 11. Active bots count
print("\n[11] COMMISSION DASHBOARD")
code, data = test_endpoint("commission", "get", f"{VPS}/api/commission/dashboard/{user_id}", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL' if code != 404 else 'NOT FOUND'}")

print("\n" + "=" * 60)
print("EVALUATION COMPLETE")
print("=" * 60)
