# Symbol Mapping & Validation Guide

## What's Happening

When you create a bot with symbols like `EURUSD` or `XAUUSD`, they are **automatically normalized** to `EURUSDm` and `XAUUSDm` respectively.

**This is intentional.** Exness (and most MT5 brokers) use the "m" suffix for symbols to differentiate them from other accounts/servers.

## Current Symbol Processing

### 1. **Valid Symbols (VALID_SYMBOLS)** — Line 7371
These are the ONLY symbols that work without mapping:
```python
VALID_SYMBOLS = {
    'BTCUSDm', 'ETHUSDm', 'EURUSDm', 'USDJPYm', 'XAUUSDm',
    'AAPLm', 'AMDm', 'MSFTm', 'NVDAm', 'JPMm', 'BACm',
    'WFCm', 'GOOGLm', 'METAm', 'ORCLm', 'TSMm'
}
```

### 2. **Symbol Mapping (SYMBOL_MAPPING)** — Line 7413
Automatically converts standard names to Exness format:
```python
SYMBOL_MAPPING = {
    'EURUSD': 'EURUSDm',      # ← This is why EURUSD becomes EURUSDm
    'XAUUSD': 'XAUUSDm',      # ← This is why XAUUSD becomes XAUUSDm
    'USDJPY': 'USDJPYm',
    'BTCUSD': 'BTCUSDm',
    'ETHUSD': 'ETHUSDm',
    # ... and so on
}
```

### 3. **Symbol Validation Logic** — Line 7568-7600
When you create/update a bot:
```
1. Check if symbol in VALID_SYMBOLS → Use as-is
2. Check if symbol in SYMBOL_MAPPING → Map to Exness format
3. Otherwise → Default to 'EURUSDm'
```

## Examples

| You Send | Backend Does | Result | Reason |
|----------|--------------|--------|--------|
| `EURUSD` | Not in VALID_SYMBOLS | Maps via SYMBOL_MAPPING | Converts to standard Exness format |
| ↓ | → Looks in SYMBOL_MAPPING | Maps to `EURUSDm` | This is the valid Exness symbol |
| `XAUUSD` | Not in VALID_SYMBOLS | Maps via SYMBOL_MAPPING | Converts to standard Exness format |
| ↓ | → Looks in SYMBOL_MAPPING | Maps to `XAUUSDm` | This is the valid Exness symbol |
| `EURUSDm` | Is in VALID_SYMBOLS | ✅ Accepted as-is | Already in correct format |
| `UNKNOWN` | Not in either | ❌ Defaults to `EURUSDm` | Fallback for invalid symbols |

## How to Fix / Customize

### Option 1: Always Use Exness Format
If you know the broker, send symbols with the "m" suffix:
```json
{
  "symbols": ["EURUSDm", "XAUUSDm", "BTCUSDm"]
}
```

### Option 2: Add New Broker Support
To support symbols without the "m" suffix or a different broker:

1. **Update VALID_SYMBOLS** (line 7371):
```python
VALID_SYMBOLS = {
    'EURUSD',  '← Add this for custom broker
    'EURUSD',  # Your symbols here
    # keep existing Exness symbols too
}
```

2. **Create a broker-specific validation function**:
```python
def validate_symbols_for_broker(symbols, broker_name):
    """Broker-specific symbol validation instead of hardcoded mapping"""
    if broker_name == 'Exness':
        return validate_exness_symbols(symbols)  
    elif broker_name == 'XM':
        return validate_xm_symbols(symbols)
    else:
        return symbols  # No mapping
```

3. **Update line 7470 `validate_and_correct_symbols()` to use broker logic**

### Option 3: Disable Symbol Mapping Temporarily
For testing, modify the function (line 7568):
```python
# TEMPORARY: Skip mapping, use symbols as-is
corrected = []
for symbol in symbols:
    # Just return what user sent
    if symbol:
        corrected.append(symbol)
    else:
        corrected.append('EURUSDm')
return corrected
```

## Where Symbols Are Used

| Location | Purpose | Impact |
|----------|---------|--------|
| Line 10970 in `create_bot()` | Initial bot creation | Symbols stored with "m" suffix |
| Line 11002 | Symbol list stored in DB | Database contains mapped symbols |
| Line 5341-5392 | Symbol validation | Falls back if symbol invalid |
| Line 8781 | Bot state restoration | Converts saved symbols |
| Line 12913 | Trading loop | Uses mapped symbols for trades |

## Database Storage

When a bot is created, symbols are stored in [user_bots](user_bots) table:
```sql
INSERT INTO user_bots (..., symbols, ...)
VALUES (..., 'EURUSDm,XAUUSDm,BTCUSDm', ...)
```

So the **database will show the mapped symbols**, not the ones you sent.

## Verification Steps

To verify symbol mapping is working:

1. **Create a bot with non-m symbols**:
```bash
curl -X POST http://localhost:5000/api/bot/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbols": ["EURUSD", "XAUUSD"],
    "credentialId": "...",
    ...
  }'
```

2. **Check the response** - It should show `["EURUSDm", "XAUUSDm"]`

3. **Query the database**:
```sql
SELECT symbols FROM user_bots WHERE bot_id = 'your_bot_id';
-- Result: 'EURUSDm,XAUUSDm'
```

4. **Check the logs** - Look for:
```
🔄 Auto-correcting symbol EURUSD -> EURUSDm based on configured Exness symbol mappings
```

## Troubleshooting

### Symptom: "Symbol not found" error on broker
- **Cause**: Symbol mapping maps to invalid symbol for your broker
- **Fix**: Check if broker actually has the "m" suffix symbol
- **Solution**: Add broker-specific handling (see Option 2 above)

### Symptom: Symbols don't match what I sent
- **Cause**: Intentional mapping (expected behavior)
- **Fix**: Request with "m" suffix or update SYMBOL_MAPPING
- **Solution**: This is by design for Exness compatibility

### Symptom: I want different symbols per broker
- **Cause**: Current code assumes all non-Binance/PXBT/XM brokers use Exness format
- **Fix**: Implement broker-specific symbol validation
- **Solution**: Refactor `validate_and_correct_symbols()` to dispatch by broker

## Next Steps

1. **Understand your broker's symbol format** — What does it actually require?
2. **Update the validation function** if you're using a different broker
3. **Log symbol changes in bot responses** so users see what happened
4. **Document this in API docs** so frontend developers know to expect mapped symbols

## Code Locations Reference

| File | Line | Purpose |
|------|------|---------|
| multi_broker_backend_updated.py | 7345-7435 | Symbol constants and mapping |
| multi_broker_backend_updated.py | 7470-7600 | Validation logic |
| multi_broker_backend_updated.py | 10970 | Bot creation (uses validation) |
| multi_broker_backend_updated.py | 11002 | Saves mapped symbols to DB |

---

**tl;dr**: Symbols are auto-mapped to Exness format (`EURUSD` → `EURUSDm`). This is intentional. If you want different behavior, either:
1. Send symbols already with "m" suffix
2. Update VALID_SYMBOLS and SYMBOL_MAPPING for your broker
3. Refactor validation logic to be broker-aware
