# Symbol Processing - Quick Troubleshooting Guide

## TL;DR - What's Happening

| What | Where | Why |
|------|-------|-----|
| EURUSD → EURUSDm | Line 7413 in SYMBOL_MAPPING | Exness requires "m" suffix |
| XAUUSD → XAUUSDm | Line 7413 in SYMBOL_MAPPING | Exness requires "m" suffix |
| Symbol changed in DB | Line 11002 in create_bot() | Normalized symbols stored |
| Unknown symbols → EURUSDm | Line 7600 in validate_and_correct_symbols() | Fallback for invalid symbols |

**This IS intentional behavior.**

---

## Common Issues & Solutions

### Issue 1: "I sent EURUSD but the bot shows EURUSDm"

**Root Cause**: `validate_and_correct_symbols()` maps standard symbols to broker format

**Quick Fix**:
1. Send symbol with "m" suffix: `["EURUSDm"]` instead of `["EURUSD"]`
2. Or update SYMBOL_MAPPING to disable mapping (temporary)

**Permanent Fix**: See [SYMBOL_IMPLEMENTATION_ROADMAP.md](SYMBOL_IMPLEMENTATION_ROADMAP.md) - Step 1

---

### Issue 2: "Symbol not found" error when trading

**Root Cause**: Mapped symbol doesn't exist on your broker

**Diagnosis**:
```bash
# Check what symbol was actually mapped
curl -X GET http://localhost:5000/api/bot/{bot_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# Look at returned symbols field
```

**Solution**:
1. Check if your broker has the mapped symbol (e.g., does Binance have BTCUSD or only BTCUSDT?)
2. Update SYMBOL_MAPPING to map to correct symbol:
   ```python
   SYMBOL_MAPPING = {
       'BTCUSD': 'BTCUSDT',  # ← Your broker's actual symbol
   }
   ```
3. Verify with broker documentation

---

### Issue 3: "Different symbols in request vs database"

**Root Cause**: Expected - symbols are normalized before storage

**Verification**:
```bash
# What you send
{"symbols": ["EURUSD", "XAUUSD"]}

# What database stores
"EURUSDm,XAUUSDm"

# This is CORRECT - see SYMBOL_MAPPING at line 7413
```

**Why this happens**:
```
validate_and_correct_symbols(['EURUSD', 'XAUUSD'], 'Exness')
  → Checks VALID_SYMBOLS (line 7371) ✗ NOT found
  → Checks SYMBOL_MAPPING (line 7413) ✓ FOUND
  → Maps: EURUSD → EURUSDm, XAUUSD → XAUUSDm
  → Returns: ['EURUSDm', 'XAUUSDm']
  → Stores in database
```

---

### Issue 4: "How do I know which symbols my broker supports?"

**For Exness/MT5**:
```
Supported symbols: EURUSDm, XAUUSDm, BTCUSDm, AAPLm, etc.
(See VALID_SYMBOLS at line 7371)

Use these in API requests - or send without "m" and they'll be mapped.
```

**For Binance**:
```
Supported symbols: BTCUSDT, ETHUSDT, BNBUSDT, etc.
(See BINANCE_VALID_SYMBOLS at line 7391)

The backend will map BTCUSD → BTCUSDT automatically.
```

**For your broker**:
1. Check broker documentation for supported symbols
2. Look at the validation constants (VALID_SYMBOLS, BINANCE_VALID_SYMBOLS, etc.)
3. Create bot with symbol - check response and logs for mappings applied

---

### Issue 5: "I added a new broker but symbols keep defaulting to EURUSDm"

**Root Cause**: No validator for your broker - falls back to Exness

**Diagnosis**:
1. Check if broker is in SYMBOL_VALIDATORS (line 7543):
   ```python
   SYMBOL_VALIDATORS = {
       'Exness': ExnessSymbolValidator(),
       'Binance': BinanceSymbolValidator(),
       'PXBT': PXBTSymbolValidator(),
       'XM': XMSymbolValidator(),
       # ← Your broker NOT here
   }
   ```

2. Check logs:
   ```
   ⚠️ No validator for broker 'YourBroker', using Exness defaults
   ```

**Solution**: Add validator for your broker (see [SYMBOL_IMPLEMENTATION_ROADMAP.md](SYMBOL_IMPLEMENTATION_ROADMAP.md) - Step 1)

---

### Issue 6: "Symbols work locally but fail in trading"

**Root Cause**: Local MT5 has different symbols than VPS MT5

**Diagnosis**:
```bash
# Check which MT5 you're connected to
tail -f backend.log | grep "MT5 " | head -5
# Look for: "Exness-Real", "Exness-MT5Trial9", "localhost:18554", etc.
```

**Common causes**:
1. Demo vs Live account symbols differ
2. Local PC MT5 vs VPS MT5 symbols differ
3. Symbol recently delisted on broker

**Solution**:
1. Verify you're connected to the right MT5 server
2. Check `DEPLOYMENT_MODE` env var (LOCAL vs VPS)
3. Query actual broker for list of valid symbols:
   ```python
   # Add this to bot creation
   mt5_conn = establish_mt5_connection(credential_data)
   available_symbols = mt5_conn.get_symbols()
   logger.info(f"Broker has symbols: {available_symbols}")
   ```

---

## Debugging Checklist

When symbols aren't working:

- [ ] Check backend logs for mapping messages:
  ```

  🔄 Auto-correcting symbol EURUSD → EURUSDm
  ⚠️ Unknown symbol XYZ → defaulting to EURUSDm
  ℹ️ Symbol normalization applied
  ```

- [ ] Query the database:
  ```sql
  SELECT bot_id, symbols FROM user_bots WHERE bot_id = 'your_bot_id';
  ```

- [ ] Check bot details via API:
  ```bash
  curl http://localhost:5000/api/bot/your_bot_id
  ```

- [ ] Verify credential broker name:
  ```sql
  SELECT broker_name FROM broker_credentials WHERE credential_id = 'your_cred_id';
  ```

- [ ] Check which validator is being used:
  ```python
  # Add to code temporarily
  broker_name = canonicalize_broker_name(credential_data['broker_name'])
  logger.info(f"Broker: {broker_name}")
  validator = SYMBOL_VALIDATORS.get(broker_name)
  logger.info(f"Validator: {validator.__class__.__name__}")
  ```

- [ ] Test symbol against broker directly:
  ```python
  mt5_conn = establish_mt5_connection(credential_data)
  if mt5_conn.connect():
      symbols = mt5_conn.get_symbols()
      logger.info(f"Broker symbols: {symbols}")
      mt5_conn.disconnect()
  ```

---

## Code Locations Reference

| Issue | File | Line | Function |
|-------|------|------|----------|
| Symbol mapping | multi_broker_backend_updated.py | 7413 | SYMBOL_MAPPING dict |
| Valid symbols | multi_broker_backend_updated.py | 7371 | VALID_SYMBOLS dict |
| Symbol validation | multi_broker_backend_updated.py | 7470 | validate_and_correct_symbols() |
| Bot creation | multi_broker_backend_updated.py | 10910 | create_bot() |
| Symbol storage | multi_broker_backend_updated.py | 11002 | INSERT into user_bots |
| Trading loop | multi_broker_backend_updated.py | 12910 | execute_trades() |

---

## When to Escalate

Contact support/open issue if:

1. **Symbol is in VALID_SYMBOLS but still fails**
   - Indicates broker doesn't actually have the symbol
   - Solution: Query broker directly, update VALID_SYMBOLS

2. **Multiple brokers need different symbol formats**
   - Current architecture assumes one format per broker
   - Solution: Implement [SYMBOL_REFACTORING_GUIDE.md](SYMBOL_REFACTORING_GUIDE.md) - Solution 2

3. **Symbol mapping is losing user data**
   - E.g., two different symbols map to same one
   - Solution: Implement [SYMBOL_REFACTORING_GUIDE.md](SYMBOL_REFACTORING_GUIDE.md) - Solution 3

4. **Broker delists symbols dynamically**
   - Hardcoded VALID_SYMBOLS won't catch changes
   - Solution: Implement [SYMBOL_REFACTORING_GUIDE.md](SYMBOL_REFACTORING_GUIDE.md) - Solution 3

---

## Quick Testing

### Test 1: Verify symbol mapping
```bash
# Make a bot creation request with non-m symbols
curl -X POST http://localhost:5000/api/bot/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "symbols": ["EURUSD"],
    "credentialId": "cred_id",
    "strategy": "Test"
  }'

# Expected: symbols in response should be ["EURUSDm"]
```

### Test 2: Check logs
```bash
# Watch logs for symbol messages
tail -f backend.log | grep -i symbol

# You should see:
# 🔄 Auto-correcting symbol EURUSD → EURUSDm
# ℹ️ Symbol normalization applied
```

### Test 3: Query database
```bash
# Check what was actually stored
sqlite3 /path/to/zwesta.db
SELECT bot_id, symbols FROM user_bots ORDER BY created_at DESC LIMIT 1;

# Should show normalized symbols:
# bot_12345 | EURUSDm,XAUUSDm
```

---

## Related Documentation

- [SYMBOL_MAPPING_GUIDE.md](SYMBOL_MAPPING_GUIDE.md) — Detailed explanation of what's happening
- [SYMBOL_REFACTORING_GUIDE.md](SYMBOL_REFACTORING_GUIDE.md) — Three solutions with pros/cons
- [SYMBOL_IMPLEMENTATION_ROADMAP.md](SYMBOL_IMPLEMENTATION_ROADMAP.md) — Step-by-step implementation

---

**Last Updated**: March 2025  
**Status**: Current symbol handling works as designed, but improvements recommended

