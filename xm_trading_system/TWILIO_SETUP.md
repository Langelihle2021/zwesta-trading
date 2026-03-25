# Zwesta Trading System - Twilio WhatsApp Setup Guide

This guide explains how to set up WhatsApp profit alerts using Twilio.

## 📋 Prerequisites

- [Twilio Account](https://www.twilio.com) (Free trial available)
- Active WhatsApp account
- Python environment with required packages installed

## 🚀 Step 1: Create Twilio Account

1. Go to https://www.twilio.com/console
2. Sign up for a free trial account
3. Verify your phone number
4. You'll get initial free trial credits ($15)

## 🔑 Step 2: Get Twilio Credentials

### Find your Account SID and Auth Token:
1. Log in to [Twilio Console](https://www.twilio.com/console)
2. Look at the dashboard - you'll see:
   - **Account SID**: Found at the top of the page
   - **Auth Token**: Click "eye icon" to reveal (keep this SECRET)

Example values (these are fake - use your real ones):
```
Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Auth Token: 57xxxxxxxxxxxxxxxxxxxxxxxxxxx89
```

## 💬 Step 3: Enable WhatsApp Sandbox (Trial Account)

For trial accounts, you need to enable the WhatsApp Sandbox:

1. Go to **Messaging** → **Whatsapp Sandbox**
2. You'll see your WhatsApp Sandbox Number (e.g., `+1415xxx5xxx`)
3. To enable: Send a WhatsApp message from YOUR phone to the Sandbox Number with: `join XXXX-XXXX` (code shown on screen)
4. You'll receive confirmation: "You are connected to the Twilio WhatsApp Sandbox"

**IMPORTANT**: In the Sandbox, you can ONLY message numbers that have joined the sandbox.

## 🎯 Step 4: Configure Environment Variables

Set the following environment variables on your system:

### Windows (Command Prompt):
```cmd
setx TWILIO_ACCOUNT_SID "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
setx TWILIO_AUTH_TOKEN "57xxxxxxxxxxxxxxxxxxxxxxxxxxx89"
setx TWILIO_WHATSAPP_NUMBER "whatsapp:+1415xxx5xxx"
```

### Windows (PowerShell):
```powershell
$env:TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:TWILIO_AUTH_TOKEN = "57xxxxxxxxxxxxxxxxxxxxxxxxxxx89"
$env:TWILIO_WHATSAPP_NUMBER = "whatsapp:+1415xxx5xxx"
```

### Linux/Mac:
```bash
export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TWILIO_AUTH_TOKEN="57xxxxxxxxxxxxxxxxxxxxxxxxxxx89"
export TWILIO_WHATSAPP_NUMBER="whatsapp:+1415xxx5xxx"
```

Add these to your shell profile (`.bashrc`, `.zshrc`) to persist across sessions.

## 📦 Step 5: Install Required Package

```bash
pip install twilio
```

## ✅ Step 6: Test WhatsApp Integration

Create a test script `test_twilio.py`:

```python
import os
from twilio.rest import Client

account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_whatsapp = os.getenv('TWILIO_WHATSAPP_NUMBER')

if not all([account_sid, auth_token, twilio_whatsapp]):
    print("❌ Missing Twilio environment variables")
    print(f"  ACCOUNT_SID: {bool(account_sid)}")
    print(f"  AUTH_TOKEN: {bool(auth_token)}")
    print(f"  WHATSAPP_NUMBER: {bool(twilio_whatsapp)}")
    exit(1)

client = Client(account_sid, auth_token)

# YOUR PHONE NUMBER (must be in sandbox or have active WhatsApp Business Account)
your_phone = "whatsapp:+1YOUR_ACTUAL_PHONE"  # e.g., whatsapp:+12025551234

try:
    message = client.messages.create(
        from_=twilio_whatsapp,
        to=your_phone,
        body="🎉 Zwesta Trading Alert Test\n\nIf you see this, WhatsApp integration is working! 💰"
    )
    print(f"✓ Test message sent! SID: {message.sid}")
except Exception as e:
    print(f"❌ Failed to send test message: {str(e)}")
```

Run it:
```bash
python test_twilio.py
```

## 🔄 Step 7: Register Users with Phone Numbers

When users register in Zwesta:

1. They provide their WhatsApp phone number (format: +12025551234 or 2025551234)
2. If using Twilio Sandbox: their number must be added to the Sandbox
3. System stores encrypted phone number in database

## 📈 Step 8: Configure Profit Alerts

Users access **Settings** tab in dashboard to:

1. **Configure MT5 Account**:
   - MT5 Account Number
   - MT5 Password
   - MT5 Server (MetaQuotes-Demo, MetaQuotes-Live, etc.)
   - Terminal Path (optional)

2. **Configure WhatsApp Alerts**:
   - Set Profit Alert Threshold (e.g., $500)
   - Enable/Disable alerts
   - Phone number shown (from registration)

When trading bot detects profit ≥ threshold:
- Sends WhatsApp message with profit amount
- Records alert in database
- Won't send duplicate alerts at same level

## 📝 Alert Message Format

Users receive WhatsApp messages like:

```
🎉 *Zwesta Trading Alert*

Your account has reached $537.50 profit! 💰

Keep trading smart!

Timestamp: 2026-03-01 14:32:15
```

## 🚀 Production Setup (Premium Twilio)

For production, upgrade from Sandbox:

1. **Purchase WhatsApp Business Account** through Twilio
2. **Update TWILIO_WHATSAPP_NUMBER** to your business number
3. **No longer need to add numbers to sandbox** - can message any WhatsApp number
4. **Billing**: Pay per message sent (typically $0.0075-0.015 per message)

### Cost Example:
- 1000 alerts per month = ~$7.50-15
- Can set per-user alert thresholds to control volume

## 🔐 Security Best Practices

1. **Never commit credentials to git**:
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use `.env` files** for local development:
   ```bash
   pip install python-dotenv
   ```
   
   Create `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=57xxxxxxxxxxxxxxxxxxxxxxxxxxx89
   TWILIO_WHATSAPP_NUMBER=whatsapp:+1415xxx5xxx
   ```
   
   Load in Python:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

3. **Store in VPS environment variables** (never in code):
   - Use system environment variables
   - Use Docker secrets for containerized deployment
   - Use cloud provider secret management (Azure Key Vault, AWS Secrets Manager, etc.)

4. **Phone numbers are encrypted** before storage in database

## 🐛 Troubleshooting

### "Missing token" error
- Verify environment variables are set: `echo $TWILIO_ACCOUNT_SID`
- Restart Flask after setting environment variables
- Check `trading_bot.log` for detailed messages

### "Authorization failed"
- Double-check Account SID and Auth Token are correct
- Verify they're copied WITHOUT extra spaces

### "Message not sent"
- Check recipient phone is in Sandbox (if using trial)
- Verify phone number format: `whatsapp:+1XXXXXXXXXX`
- Check Twilio account has credits available
- Review Twilio Console → Messages → Logs for error details

### "User not found in Sandbox"
- Add number again to Sandbox
- Send `join XXXX-XXXX` message from that phone number
- Wait for confirmation from Twilio

## 📞 Support

- **Twilio Docs**: https://www.twilio.com/docs/whatsapp
- **Trading Bot Logs**: Check `trading_bot.log` in project directory
- **Flask Logs**: Check `flask.log` for API requests

## 📊 Monitoring WhatsApp Alerts

View sent alerts in Zwesta dashboard:
- **Settings** tab shows alert status
- Database tracks all sent alerts in `profit_alerts` table
- Can filter by date/user/profit level

Check Twilio logs:
1. Go to Twilio Console
2. **Messaging** → **Logs** → **Messages**
3. View delivery status for each message
4. Troubleshoot failed deliveries
