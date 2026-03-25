# Zwesta Trading System - Quick Start Guide

**Goal**: Get multi-user trading with WhatsApp alerts and mobile app running in 30 minutes.

## ⚡ 30-Minute Quick Start

### Step 1: Verify Flask is Running (2 min)

```powershell
# Check if Python is running
Get-Process python -ErrorAction SilentlyContinue

# If not running, start it:
cd C:\zwesta-trader\xm_trading_system
python dashboard_enhanced.py

# Wait for output:
# [MT5] Initializing MT5 data provider...
# [BOT] Starting multi-user trading bot...
# [BOT] Trading bot running in background
# Running on https://0.0.0.0:5000
```

### Step 2: Test Web Dashboard (3 min)

```powershell
# Open browser
https://192.168.0.137:5000

# Login with:
# Username: demo
# Password: demo123

# Verify you see:
# ✅ Dashboard overview
# ✅ Markets tab (6 commodities)
# ✅ Settings tab (NEW)
# ✅ User profile menu
```

### Step 3: Test Registration with Phone (5 min)

```
1. Click "Register" tab
2. Fill form:
   - Full Name: Test User
   - Company: Test Corp
   - Email: test@example.com
   - WhatsApp Number: +1YOUR_REAL_PHONE (or +12025551234 for demo)
   - Username: testuser
   - Password: testpass123
3. Click "Create Account"
4. You should see: "✓ Account created! Please login."
```

### Step 4: Configure MT5 Credentials (5 min)

```
1. Login with your new account
2. Click Settings tab (in navbar)
3. Fill "MetaTrader5 Account" section:
   - MT5 Account Number: 103672035 (demo)
   - MT5 Password: your_password
   - MT5 Server: MetaQuotes-Demo
   - Terminal Path: (optional)
4. Click "Save MT5 Account"
5. You should see green "✓ Configured" status
```

### Step 5: Setup Twilio Alerts (10 min)

**A) Create Twilio Account:**
```
1. Go to https://www.twilio.com/console
2. Sign up for free ($15 trial credit)
3. Verify phone number
4. Go to Messaging → WhatsApp Sandbox
5. Copy your Sandbox number (e.g., whatsapp:+1415xxx5xxx)
```

**B) Set Environment Variables (Windows):**
```powershell
# In PowerShell (as Administrator):
$env:TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TWILIO_AUTH_TOKEN = "57xxxxxxxxxxxxxxxxxxxxxxxxxxx89"
$env:TWILIO_WHATSAPP_NUMBER = "whatsapp:+1415xxx5xxx"

# To make permanent:
[Environment]::SetEnvironmentVariable("TWILIO_ACCOUNT_SID", "ACxxxxxx...", "User")
[Environment]::SetEnvironmentVariable("TWILIO_AUTH_TOKEN", "57xxxx...", "User")
[Environment]::SetEnvironmentVariable("TWILIO_WHATSAPP_NUMBER", "whatsapp:+...", "User")

# Restart PowerShell
```

**C) Install Twilio SDK:**
```powershell
pip install twilio
```

**D) Verify Twilio Setup:**
```powershell
python
>>> import os
>>> print(os.getenv('TWILIO_ACCOUNT_SID'))  # Should print your SID
>>> exit()
```

### Step 6: Configure Profit Alerts (3 min)

```
1. Go back to Settings tab
2. Scroll to "WhatsApp Profit Alerts" section
3. Set:
   - Profit Alert Threshold: 500 (default)
   - Enable WhatsApp Alerts: ✓ (checked)
4. Click "Save Alert Settings"
5. Phone number should display your number from registration
```

### Step 7: Test WhatsApp Alert (Optional, 5 min)

```powershell
# Create test script: test_alert.py
python
>>> from main import UserTradingSession
>>> # System will send test alert when profit detected
>>> exit()

# Or manually test via Twilio:
python
>>> from twilio.rest import Client
>>> import os
>>> client = Client(
...     os.getenv('TWILIO_ACCOUNT_SID'),
...     os.getenv('TWILIO_AUTH_TOKEN')
... )
>>> msg = client.messages.create(
...     from_=os.getenv('TWILIO_WHATSAPP_NUMBER'),
...     to='whatsapp:+1YOUR_REAL_PHONE',
...     body='🎉 Zwesta Trading Alert - Test Message'
... )
>>> print(f"Message sent! SID: {msg.sid}")
>>> exit()
```

**You will receive the WhatsApp message on your phone!**

### Step 8: Build Mobile APK (10 min)

```powershell
# Prerequisites check
node --version                    # Must be v16+
npm install -g capacitor

# Navigate to your Capacitor project:
cd C:\zwesta-trader\Zwesta-Trader-App

# If no project, create one:
# npx create-capacitor-app ZwestaTrader cd ZwestaTrader

# Update config for your server
# Edit capacitor.config.json:
# "server": { "url": "https://192.168.0.137:5000" }

# Build
npx cap add android
npx cap sync android
cd android
.\gradlew assembleDebug

# APK ready at:
# app/build/outputs/apk/debug/app-debug.apk

# Install on device/emulator:
# adb install app/build/outputs/apk/debug/app-debug.apk
```

### Verification Checklist ✅

```
After completing steps above, verify:

□ Flask running (https://192.168.0.137:5000 loads UI)
□ Can login (demo / demo123 works)
□ Settings tab visible in navbar
□ New user registration accepting phone number
□ MT5 credentials saving to Settings
□ Profit alert settings appearing
□ Twilio environment variables set
□ Twilio SDK installed (pip list | grep twilio)
□ WhatsApp test message received
□ Trading bot running (check logs for "User sessions")
□ Mobile APK built successfully
```

## 🔧 Configuration Files Reference

### 1. Flask Config (dashboard_enhanced.py)
```python
# Line ~1050
if __name__ == '__main__':
    init_db()  # Creates database tables
    
    # Trading bot starts here:
    from main import start_bot
    start_bot()  # ← Manages multi-user trading
```

### 2. Bot Config (main.py)
```python
# Line ~30-40
DB_PATH = "zwesta_trading.db"
SCAN_INTERVAL = 5                    # Scan every 5 seconds
SYMBOLS_TO_TRADE = [                 # What to trade
    'GOLD', 'XAUUSD', 'EURUSD', 
    'GBPUSD', 'USDJPY', 'USDCAD'
]

# Line ~50-55 - Twilio configuration (from environment)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', '')
```

### 3. Capacitor Config (capacitor.config.json)
```json
{
  "appId": "com.zwesta.trading",
  "appName": "Zwesta Trader",
  "webDir": "build",
  "server": {
    "url": "https://192.168.0.137:5000",  // ← Your server URL
    "cleartext": true,
    "androidScheme": "https"
  }
}
```

## 📱 Testing Multi-User System

### Test Case 1: Two Users, Two Accounts
```
User 1: Register with phone +1202-555-1234, MT5 account A
User 2: Register with phone +1202-555-5678, MT5 account B

Result:
✅ User 1 trades account A independently
✅ User 2 trades account B independently
✅ User 1 receives alerts for account A only
✅ User 2 receives alerts for account B only
```

### Test Case 2: Same User, Different Devices
```
User 1: Login on web dashboard
User 1: Login on mobile app (same credentials)

Result:
✅ Both see same account data (synced via database)
✅ Updates on web show on mobile after page refresh
✅ Can trade from either device
```

### Test Case 3: WhatsApp Alert Delivery
```
Setup:
1. User registered with valid WhatsApp number
2. MT5 account adding profit
3. Profit threshold set to $500

Trigger:
- Wait for bot to detect profit > $500
- Check WhatsApp phone for message

Result:
✅ Receive message: "🎉 Your account has reached $XXX profit!"
✅ Timestamp included
✅ Only sent when threshold exceeded (no duplicates)
```

## 🚨 Troubleshooting Quick Ref

| Problem | Solution |
|---------|----------|
| Flask won't start | `pip install Flask` or check for port conflict |
| Settings tab missing | Clear browser cache, restart Flask |
| MT5 credentials not saving | Check database (check_schema.py), verify token |
| WhatsApp not receiving messages | Verify phone in Twilio Sandbox, check SID/token |
| Trading bot not running | Check `trading_bot.log`, verify MT5 installed |
| Mobile APK won't build | Verify Android Studio, Java 17, Node.js v16+ |
| API returns 401 | Must login first to get token |

## 🎯 Recommended Order of Implementation

**Phase 1** (Already Done):
1. ✅ Database schema (multi-user support)
2. ✅ Registration with phone number
3. ✅ Settings tab UI
4. ✅ MT5 credential storage
5. ✅ Multi-user trading bot

**Phase 2** (Follow above):
1. Install Twilio SDK
2. Create Twilio account
3. Setup WhatsApp Sandbox
4. Configure environment variables
5. Test WhatsApp alerts

**Phase 3** (Optional):
1. Build Capacitor project
2. Configure API server URL
3. Build APK
4. Test on Android device
5. Deploy to Play Store (if desired)

## 📊 Live System Monitoring

### Check Bot Status
```powershell
# View bot logs (last 20 lines)
Get-Content C:\zwesta-trader\xm_trading_system\trading_bot.log -Tail 20

# Search for user sessions
Select-String "User sessions:" C:\zwesta-trader\xm_trading_system\trading_bot.log

# Watch logs in real-time
Get-Content -Path trading_bot.log -Wait
```

### Check Flask Logs
```powershell
Get-Content C:\zwesta-trader\xm_trading_system\flask.log -Tail 20
```

### Check Database
```powershell
cd C:\zwesta-trader\xm_trading_system
python
>>> import sqlite3
>>> conn = sqlite3.connect('zwesta_trading.db')
>>> c = conn.cursor()
>>> c.execute("SELECT COUNT(*) FROM mt5_credentials")
>>> print("Users with MT5:", c.fetchone()[0])
>>> exit()
```

## 🎓 Learning Resources

**To customize the system:**

1. **Add new symbols to trade**: Edit `main.py` line 40
2. **Change alert threshold logic**: Edit `UserTradingSession.check_profit_threshold()`
3. **Modify alert message**: Edit `_send_alert_async()` message body
4. **Add new API endpoints**: Add routes to `dashboard_enhanced.py`
5. **Customize dashboard UI**: Edit `templates/index.html`

**To scale the system:**

1. **Support more users**: Upgrade to PostgreSQL (SQLite limit ~1000 concurrent)
2. **Support more trades**: Add background job queue (Celery + Redis)
3. **Better alerts**: Add email, SMS, Slack notifications
4. **Performance**: Add caching layer (Redis)
5. **Redundancy**: Deploy bot on multiple servers with load balancer

## ✅ Deployment Checklist

Before going live:

- [ ] Flask running on production VPS
- [ ] Database backed up daily
- [ ] SSL certificates valid (not self-signed)
- [ ] Twilio account upgraded from Sandbox
- [ ] Trading bot logging to file for audit
- [ ] Monitoring alerts set up
- [ ] User documentation created
- [ ] Privacy policy updated
- [ ] Terms of service covering risks
- [ ] Compliance reviewed (regional trading regulations)

## 📞 Quick Links

- **Twilio Setup**: [TWILIO_SETUP.md](TWILIO_SETUP.md)
- **APK Build**: [CAPACITOR_APK_BUILD.md](CAPACITOR_APK_BUILD.md)
- **Full Summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Trading Bot Code**: [main.py](main.py)
- **API Server**: [dashboard_enhanced.py](dashboard_enhanced.py)
- **Dashboard UI**: [templates/index.html](templates/index.html)

---

**You're ready to go!** 🚀

Follow the 8 steps above to have a fully functional multi-user trading system with WhatsApp alerts.

Questions? Check the troubleshooting section or review the detailed setup guides.
