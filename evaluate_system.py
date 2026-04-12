"""Comprehensive backend API evaluation"""
import json
import os

import requests

VPS = os.getenv("ZWESTA_VPS", "http://38.247.146.198:9000").rstrip("/")
LOGIN_EMAIL = os.getenv("ZWESTA_EVAL_EMAIL", "trader2@example.com")
LOGIN_PASSWORD = os.getenv("ZWESTA_EVAL_PASSWORD", "password123")
ALLOW_DESTRUCTIVE = os.getenv("ZWESTA_EVAL_ALLOW_DESTRUCTIVE", "0").strip().lower() in {"1", "true", "yes", "on"}

findings = []
recommendations = []


def add_finding(level, message):
    findings.append((level, message))


def add_recommendation(message):
    if message not in recommendations:
        recommendations.append(message)


def outcome_label(ok):
    return "PASS" if ok else "FAIL"


def bot_key(bot):
    strategy = str(bot.get("strategy") or "").strip().lower()
    symbols = bot.get("symbols") or []
    if not isinstance(symbols, list):
        symbols = [str(bot.get("symbol") or "")]
    normalized_symbols = ",".join(sorted(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
    return f"{strategy}|{normalized_symbols}"


def short_symbols(bot):
    symbols = bot.get("symbols") or []
    if isinstance(symbols, list) and symbols:
        return ", ".join(str(symbol) for symbol in symbols)
    return str(bot.get("symbol") or "N/A")


def bot_score(bot):
    profit = float(bot.get("currentProfit") or bot.get("profit") or 0)
    win_rate = float(bot.get("winRate") or 0)
    trades = int(bot.get("totalTrades") or 0)
    return (profit * 10.0) + (win_rate * 2.0) + min(trades, 50)


def live_similarity_score(demo_bot, live_bot):
    score = 0
    if str(demo_bot.get("strategy") or "").strip().lower() == str(live_bot.get("strategy") or "").strip().lower():
        score += 50

    demo_symbols = set(str(symbol).strip().upper() for symbol in (demo_bot.get("symbols") or []) if str(symbol).strip())
    live_symbols = set(str(symbol).strip().upper() for symbol in (live_bot.get("symbols") or []) if str(symbol).strip())
    if not demo_symbols and demo_bot.get("symbol"):
        demo_symbols = {str(demo_bot.get("symbol")).strip().upper()}
    if not live_symbols and live_bot.get("symbol"):
        live_symbols = {str(live_bot.get("symbol")).strip().upper()}

    overlap = len(demo_symbols & live_symbols)
    score += overlap * 20
    score -= abs(len(demo_symbols) - len(live_symbols)) * 5
    return score

def test_endpoint(name, method, url, **kwargs):
    try:
        r = getattr(requests, method)(url, timeout=10, **kwargs)
        return r.status_code, r.json() if r.headers.get('content-type','').startswith('application/json') else r.text[:200]
    except Exception as e:
        return 0, str(e)

print("=" * 60)
print("ZWESTA BACKEND COMPREHENSIVE EVALUATION")
print("=" * 60)
print(f"Target VPS: {VPS}")
print(f"Login user: {LOGIN_EMAIL}")
print(f"Destructive checks enabled: {ALLOW_DESTRUCTIVE}")

# 1. Health
print("\n[1] HEALTH CHECK")
code, data = test_endpoint("health", "get", f"{VPS}/api/health")
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    print(f"    Version: {data.get('version')} | Service: {data.get('service')}")

# 2. Login
print("\n[2] LOGIN")
code, data = test_endpoint("login", "post", f"{VPS}/api/user/login",
    json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
token = ""
user_id = ""
if isinstance(data, dict) and data.get("success"):
    token = data["session_token"]
    user_id = data["user_id"]
    print(f"    User: {data.get('name')} | ID: {user_id[:16]}...")
else:
    print(f"    Error: {data}")
    add_finding("critical", "Login failed; no authenticated evaluation could be performed.")
    add_recommendation("Set ZWESTA_EVAL_EMAIL and ZWESTA_EVAL_PASSWORD to a real account with brokers and bots.")

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
    if (data.get('total_bots') or 0) == 0 or (data.get('total_brokers') or 0) == 0:
        print("    Warning: this user has no active bots/brokers, so live trading readiness is not fully represented")
        add_finding("warning", "Evaluation user has no active bots and/or broker credentials, so live readiness is not proven.")
        add_recommendation("Run the evaluator against the actual live trading user instead of the sample account.")

# 4. Bot status
print("\n[4] BOT STATUS")
code, data = test_endpoint("bots", "get", f"{VPS}/api/bot/status", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
bots = []
if isinstance(data, dict):
    bots = data.get("bots", [])
    print(f"    Active: {data.get('activeBots')} | Total: {len(bots)}")
    for b in bots[:3]:
        bid = b.get("botId", "?")
        print(f"    -> {bid[:25]} | {b.get('strategy')} | Enabled:{b.get('enabled')} | P&L:${b.get('totalProfit',0):.2f} | Trades:{b.get('totalTrades',0)}")
        print(f"       Open positions: {len(b.get('openPositions',[]))} | Balance: ${b.get('accountBalance',0):.2f}")
        if b.get("stopReason"):
            print(f"       Stop reason: {b.get('stopReason')}")
            add_finding("warning", f"Bot {bid} has stopReason: {b.get('stopReason')}")
        if b.get("pauseReason"):
            print(f"       Pause reason: {b.get('pauseReason')}")
            add_finding("warning", f"Bot {bid} has pauseReason: {b.get('pauseReason')}")
    if not bots:
        add_finding("warning", "No active bots were returned by /api/bot/status.")
        add_recommendation("Start one demo bot and one live bot with minimal risk, then rerun the evaluator.")

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

# 9. Accounts overview (mode-aware)
print("\n[9] ACCOUNT DETAILS (DEMO/LIVE)")
mode_account_results = {}
for mode in ["DEMO", "LIVE"]:
    code, data = test_endpoint("account-detailed", "get", f"{VPS}/api/account/detailed?mode={mode}", headers=headers)
    ok = code == 200
    print(f"    {mode}: Status {code} | {outcome_label(ok)}")
    if isinstance(data, dict) and data.get("success"):
        account = data.get("account", {})
        mode_account_results[mode] = account
        print(
            f"       Account: {account.get('accountNumber')} | Currency: {account.get('currency')} | "
            f"Balance: {account.get('balance')} | Source: {account.get('dataSource')}"
        )
        if account.get("warning"):
            print(f"       Warning: {account.get('warning')}")
            add_finding("warning", f"{mode} account warning: {account.get('warning')}")
        if account.get("dataSource") in {"not_connected", "stale_cache"}:
            add_finding("warning", f"{mode} account is not warm/connected (source={account.get('dataSource')}).")
            add_recommendation(f"Warm the {mode.lower()} session by opening that mode in the app or running a small bot before trusting balances.")
    else:
        add_finding("warning", f"{mode} account details were unavailable for this user.")

# 10. Dashboard balances endpoint
print("\n[10] ACCOUNT BALANCES")
code, data = test_endpoint("balances", "get", f"{VPS}/api/accounts/balances", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict):
    print(f"    Accounts: {len(data.get('accounts', []))} | TotalBalance: {data.get('totalBalance')} | TotalEquity: {data.get('totalEquity')}")
    if len(data.get('accounts', [])) == 0:
        add_finding("warning", "No accounts were returned by /api/accounts/balances.")

# 11. Commission summary (current endpoint)
print("\n[11] COMMISSION SUMMARY")
code, data = test_endpoint("commission-summary", "get", f"{VPS}/api/user/commission-summary", headers=headers)
print(f"    Status: {code} | {'PASS' if code == 200 else 'FAIL'}")
if isinstance(data, dict) and data.get("success"):
    summary = data.get("summary", {})
    print(f"    Total earned: {summary.get('total_earned')} | Last 30 days: {summary.get('last_30_days_earned')}")

# 12. Bot summary and analytics snapshots
print("\n[12] BOT SUMMARY / ANALYTICS")
code, data = test_endpoint("bot-summary", "get", f"{VPS}/api/bot/summary?mode=", headers=headers)
print(f"    Summary status: {code} | {outcome_label(code == 200)}")
summary_bots = []
mode_summary_bots = {"DEMO": [], "LIVE": []}
if isinstance(data, dict) and data.get("success"):
    summary_bots = data.get("bots", [])
    print(f"    Summary bots: {len(summary_bots)}")
    for bot in summary_bots[:3]:
        bot_id = bot.get("botId", "?")
        print(
            f"    -> {bot_id[:25]} | mode:{bot.get('mode')} | profit:{bot.get('currentProfit')} | "
            f"daily:{bot.get('dailyProfit')} | trades:{bot.get('totalTrades')}"
        )
    if not summary_bots:
        add_finding("warning", "No bots were returned by /api/bot/summary.")
else:
    add_finding("warning", "Bot summary endpoint did not return a successful payload.")

for mode in ["DEMO", "LIVE"]:
    code, mode_data = test_endpoint("bot-summary-mode", "get", f"{VPS}/api/bot/summary?mode={mode}", headers=headers)
    print(f"    {mode} summary status: {code} | {outcome_label(code == 200)}")
    if isinstance(mode_data, dict) and mode_data.get("success"):
        mode_summary_bots[mode] = mode_data.get("bots", [])
        print(f"       Bots: {len(mode_summary_bots[mode])}")

analytics_checked = 0
for bot in summary_bots[:2]:
    bot_id = bot.get("botId")
    if not bot_id:
        continue
    analytics_checked += 1
    code, analytics = test_endpoint("analytics", "get", f"{VPS}/api/bot/{bot_id}/analytics-snapshot", headers=headers)
    print(f"    Analytics {bot_id[:16]}...: Status {code} | {outcome_label(code == 200)}")
    if isinstance(analytics, dict) and analytics.get("success"):
        payload = analytics.get("bot", {})
        trade_history = payload.get("tradeHistory") or []
        daily_profits = payload.get("dailyProfits") or {}
        print(
            f"       tradeHistory={len(trade_history)} | dailyProfits={len(daily_profits)} | "
            f"currentProfit={payload.get('currentProfit')} | dailyProfit={payload.get('dailyProfit')}"
        )
        if len(daily_profits) == 0 and int(payload.get("totalTrades") or 0) > 0:
            add_finding("warning", f"Bot {bot_id} has trades but empty dailyProfits in analytics snapshot.")
        if payload.get("pauseReason"):
            add_finding("warning", f"Bot {bot_id} analytics reports pauseReason: {payload.get('pauseReason')}")
    else:
        add_finding("warning", f"Analytics snapshot failed for bot {bot_id}.")

if analytics_checked == 0:
    add_finding("warning", "No bot analytics snapshots were checked because no bot IDs were available.")

print("\n[13] DEMO VS LIVE BOT COMPARISON")
demo_bots = mode_summary_bots["DEMO"]
live_bots = mode_summary_bots["LIVE"]
print(f"    Demo bots: {len(demo_bots)} | Live bots: {len(live_bots)}")

ranked_demo_bots = sorted(demo_bots, key=bot_score, reverse=True)
best_demo_bot = ranked_demo_bots[0] if ranked_demo_bots else None

if ranked_demo_bots:
    print("    Top demo bots:")
    for index, bot in enumerate(ranked_demo_bots[:3], start=1):
        print(
            f"      {index}. {bot.get('strategy')} | {short_symbols(bot)} | "
            f"trades:{int(bot.get('totalTrades') or 0)} | winRate:{float(bot.get('winRate') or 0):.1f}% | "
            f"profit:{float(bot.get('currentProfit') or bot.get('profit') or 0):.2f}"
        )

live_by_key = {bot_key(bot): bot for bot in live_bots}
matched_pairs = []
for demo_bot in demo_bots:
    key = bot_key(demo_bot)
    live_bot = live_by_key.get(key)
    if live_bot:
        matched_pairs.append((demo_bot, live_bot))

if not matched_pairs:
    print("    No matching demo/live bot pairs found by strategy + symbols")
    if demo_bots and live_bots:
        add_finding("warning", "Demo and live bots exist but do not share the same strategy/symbol configuration.")
        add_recommendation("Clone the best-performing demo bot configuration exactly into a minimal-risk live bot before comparing performance.")
    elif demo_bots and not live_bots:
        add_finding("warning", "Demo bots exist but no live bots were found for comparison.")
        add_recommendation("Start one live bot with the same strategy and symbols as the best demo bot, then rerun the evaluator.")
else:
    for demo_bot, live_bot in matched_pairs[:5]:
        demo_profit = float(demo_bot.get("currentProfit") or demo_bot.get("profit") or 0)
        live_profit = float(live_bot.get("currentProfit") or live_bot.get("profit") or 0)
        demo_trades = int(demo_bot.get("totalTrades") or 0)
        live_trades = int(live_bot.get("totalTrades") or 0)
        demo_win_rate = float(demo_bot.get("winRate") or 0)
        live_win_rate = float(live_bot.get("winRate") or 0)
        print(
            f"    {demo_bot.get('strategy')} | {short_symbols(demo_bot)}\n"
            f"       Demo -> trades:{demo_trades} winRate:{demo_win_rate:.1f}% profit:{demo_profit:.2f}\n"
            f"       Live -> trades:{live_trades} winRate:{live_win_rate:.1f}% profit:{live_profit:.2f}"
        )
        if live_bot.get("pauseReason"):
            add_finding("warning", f"Live bot {live_bot.get('botId')} is paused: {live_bot.get('pauseReason')}")
        if live_trades == 0 and demo_trades > 0:
            add_finding("warning", f"Live bot {live_bot.get('botId')} has not executed trades while the matching demo bot has.")
            add_recommendation("Check live MT5 AutoTrading, symbol availability, and broker credential warmup for the matching live bot.")
        if live_trades > 0 and demo_trades > 0 and live_win_rate + 20 < demo_win_rate:
            add_finding("warning", f"Live bot {live_bot.get('botId')} is materially underperforming its matching demo bot on win rate.")
            add_recommendation("Reduce live risk and compare execution logs for spread, slippage, and skipped signals before scaling up.")

print("    Best demo -> live candidate:")
if not best_demo_bot:
    print("      No demo bot available to rank.")
elif not live_bots:
    print(
        f"      Best demo bot is {best_demo_bot.get('strategy')} | {short_symbols(best_demo_bot)}; no live candidate exists yet."
    )
    add_recommendation("Create one live bot from the top-ranked demo bot configuration before scaling live trading.")
else:
    scored_live_candidates = sorted(
        live_bots,
        key=lambda live_bot: (live_similarity_score(best_demo_bot, live_bot), bot_score(live_bot)),
        reverse=True,
    )
    best_live_candidate = scored_live_candidates[0]
    print(
        f"      Demo: {best_demo_bot.get('strategy')} | {short_symbols(best_demo_bot)} | "
        f"trades:{int(best_demo_bot.get('totalTrades') or 0)} | winRate:{float(best_demo_bot.get('winRate') or 0):.1f}% | "
        f"profit:{float(best_demo_bot.get('currentProfit') or best_demo_bot.get('profit') or 0):.2f}"
    )
    print(
        f"      Live: {best_live_candidate.get('strategy')} | {short_symbols(best_live_candidate)} | "
        f"trades:{int(best_live_candidate.get('totalTrades') or 0)} | winRate:{float(best_live_candidate.get('winRate') or 0):.1f}% | "
        f"profit:{float(best_live_candidate.get('currentProfit') or best_live_candidate.get('profit') or 0):.2f}"
    )
    if bot_key(best_demo_bot) != bot_key(best_live_candidate):
        add_finding("warning", "The closest live candidate does not exactly match the best-performing demo bot configuration.")
        add_recommendation("Mirror the top-ranked demo bot's strategy and symbols exactly on live before concluding demo and live behavior align.")

# 14. Optional destructive endpoint existence check
print("\n[14] DELETE-ALL-BOTS ENDPOINT")
if not ALLOW_DESTRUCTIVE:
    print("    SKIPPED | Destructive checks disabled by default")
else:
    code, data = test_endpoint("delete-bots", "post", f"{VPS}/api/bots/delete-all", headers=headers)
    print(f"    Status: {code} | Endpoint exists: {'PASS' if code != 404 else 'FAIL'}")
    if isinstance(data, dict):
        print(f"    Deleted: {data.get('deleted_count', 0)} bots")

print("\n[15] LIVE READINESS SUMMARY")
critical_findings = [message for level, message in findings if level == "critical"]
warning_findings = [message for level, message in findings if level == "warning"]

if critical_findings:
    readiness = "NOT READY"
elif warning_findings:
    readiness = "CONDITIONALLY READY"
else:
    readiness = "READY"

print(f"    Verdict: {readiness}")
if findings:
    for level, message in findings:
        print(f"    [{level.upper()}] {message}")
else:
    print("    No blocking findings from the evaluated account.")

if not recommendations and readiness != "READY":
    add_recommendation("Rerun this evaluator with the actual funded live user and at least one active live bot.")

if recommendations:
    print("    Recommendations:")
    for idx, message in enumerate(recommendations, start=1):
        print(f"      {idx}. {message}")

print("\n" + "=" * 60)
print("EVALUATION COMPLETE")
print("=" * 60)
