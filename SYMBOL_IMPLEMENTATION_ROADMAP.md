# Symbol Processing - Implementation Roadmap

## Files Affected
- `multi_broker_backend_updated.py`
  - Line 7345-7650 (Symbol validation constants and functions)
  - Line 10900-11100 (Bot creation endpoint)
  - Line 8780-8800 (Bot update endpoint)
  - Line 12910-12940 (Trading loop)

## Step-by-Step Implementation

### STEP 1: Refactor Symbol Validator Classes (15 min)

**File**: `multi_broker_backend_updated.py`  
**Location**: After line 7431 (after SYMBOL_MAPPING definition)  
**Action**: Replace the `validate_and_correct_symbols()` function

Replace lines 7470-7637 with:

```python
# ==================== BROKER-SPECIFIC SYMBOL VALIDATORS ====================

class SymbolValidator:
    """Base class for broker-specific symbol validation"""
    
    def __init__(self, broker_name):
        self.broker_name = broker_name
        self.valid_symbols = set()
        self.symbol_mapping = {}
    
    def validate(self, symbols):
        """
        Validate and correct symbols for this broker
        
        Args:
            symbols: List of symbol names
            
        Returns:
            tuple: (validated_symbols_list, mapping_dict)
                   mapping_dict shows which symbols were mapped and how
        """
        raise NotImplementedError


class ExnessSymbolValidator(SymbolValidator):
    """Validator for Exness/MT5 symbols"""
    
    def __init__(self):
        super().__init__('Exness')
        self.valid_symbols = VALID_SYMBOLS
        self.symbol_mapping = SYMBOL_MAPPING
    
    def validate(self, symbols):
        """Validate Exness symbols - map old/standard format to 'm' suffix"""
        if not symbols:
            return (['EURUSDm'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            if symbol in self.valid_symbols:
                # Symbol is already in correct format
                corrected.append(symbol)
            elif symbol in self.symbol_mapping:
                # Symbol needs mapping (e.g., EURUSD -> EURUSDm)
                new_symbol = self.symbol_mapping[symbol]
                corrected.append(new_symbol)
                mappings[symbol] = new_symbol
                logger.info(f"📊 Exness symbol mapping: {symbol} → {new_symbol}")
            else:
                # Unknown symbol - use fallback
                logger.warning(f"⚠️ Unknown Exness symbol '{symbol}' → defaulting to EURUSDm")
                corrected.append('EURUSDm')
                mappings[symbol] = 'EURUSDm'
        
        # Remove duplicates while preserving order
        seen = set()
        final = []
        for s in corrected:
            if s not in seen:
                final.append(s)
                seen.add(s)
        
        # Limit to 5 symbols max
        return (final[:5], mappings)


class BinanceSymbolValidator(SymbolValidator):
    """Validator for Binance symbols"""
    
    def __init__(self):
        super().__init__('Binance')
        self.valid_symbols = BINANCE_VALID_SYMBOLS
        self.symbol_mapping = {
            'BTCUSD': 'BTCUSDT', 'BTC/USDT': 'BTCUSDT', 'BTC_USDT': 'BTCUSDT',
            'ETHUSD': 'ETHUSDT', 'ETH/USDT': 'ETHUSDT', 'ETH_USDT': 'ETHUSDT',
            'BNBUSD': 'BNBUSDT', 'BNB/USDT': 'BNBUSDT',
            'SOLUSD': 'SOLUSDT', 'SOL/USDT': 'SOLUSDT',
            'XRPUSD': 'XRPUSDT', 'XRP/USDT': 'XRPUSDT',
            'ADAUSD': 'ADAUSDT', 'ADA/USDT': 'ADAUSDT',
            'DOGEUSD': 'DOGEUSDT', 'DOGE/USDT': 'DOGEUSDT',
        }
    
    def validate(self, symbols):
        """Validate Binance symbols - normalize to USDT pairs"""
        if not symbols:
            return (['BTCUSDT'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            normalized = str(symbol).upper().replace('/', '').replace('_', '')
            
            if normalized in self.valid_symbols:
                if normalized not in corrected:
                    corrected.append(normalized)
            elif normalized in self.symbol_mapping:
                new_symbol = self.symbol_mapping[normalized]
                if new_symbol not in corrected:
                    corrected.append(new_symbol)
                    mappings[symbol] = new_symbol
                    logger.info(f"📊 Binance symbol mapping: {symbol} → {new_symbol}")
            else:
                logger.warning(f"⚠️ Unsupported Binance symbol '{symbol}' → skipping")
                mappings[symbol] = None
        
        return (corrected if corrected else ['BTCUSDT'], mappings)


class PXBTSymbolValidator(SymbolValidator):
    """Validator for PXBT symbols"""
    
    def __init__(self):
        super().__init__('PXBT')
        self.valid_symbols = PXBT_VALID_SYMBOLS
        self.symbol_mapping = {
            'EURUSDM': 'EURUSD', 'GBPUSDM': 'GBPUSD', 'USDJPYM': 'USDJPY',
            'USDCHFM': 'USDCHF', 'XAUUSDM': 'XAUUSD', 'XAGUSDM': 'XAGUSD',
            'US30M': 'US30', 'EUR50M': 'EUR50', 'BRENTUSD': 'BRENT',
            'BTCUSDM': 'BTCUSDT', 'BTCUSD': 'BTCUSDT',
            'ETHUSDM': 'ETHUSDT', 'ETHUSD': 'ETHUSDT',
        }
    
    def validate(self, symbols):
        """Validate PXBT symbols"""
        if not symbols:
            return (['EURUSD'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            normalized = str(symbol).upper().replace('/', '').replace('_', '')
            normalized_sym = self.symbol_mapping.get(normalized, normalized)
            
            if normalized_sym in self.valid_symbols:
                if normalized_sym not in corrected:
                    corrected.append(normalized_sym)
                    if normalized != normalized_sym:
                        mappings[symbol] = normalized_sym
                        logger.info(f"📊 PXBT symbol mapping: {symbol} → {normalized_sym}")
            else:
                logger.warning(f"⚠️ Unknown PXBT symbol '{symbol}' → defaulting to EURUSD")
                if 'EURUSD' not in corrected:
                    corrected.append('EURUSD')
                mappings[symbol] = 'EURUSD'
        
        return (corrected[:5] if corrected else ['EURUSD'], mappings)


class XMSymbolValidator(SymbolValidator):
    """Validator for XM Global symbols"""
    
    def __init__(self):
        super().__init__('XM')
        self.valid_symbols = VALID_SYMBOLS  # XM uses similar format to Exness
        self.symbol_mapping = SYMBOL_MAPPING
    
    def validate(self, symbols):
        """Validate XM symbols - strip server suffixes (.r, .stp, .ecn)"""
        if not symbols:
            return (['EURUSDm'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            # Strip XM server suffixes (.r, .stp, .ecn, etc.)
            base = str(symbol).split('.')[0].upper()
            
            if base in self.valid_symbols:
                if base not in corrected:
                    corrected.append(base)
            elif base in SYMBOL_MAPPING:
                # Try to map old/standard symbol names
                new_symbol = SYMBOL_MAPPING[base]
                if new_symbol not in corrected:
                    corrected.append(new_symbol)
                    mappings[symbol] = new_symbol
                    logger.info(f"📊 XM symbol mapping: {symbol} → {new_symbol}")
            else:
                logger.warning(f"⚠️ Unknown XM symbol '{symbol}' → defaulting to EURUSDm")
                if 'EURUSDm' not in corrected:
                    corrected.append('EURUSDm')
                mappings[symbol] = 'EURUSDm'
        
        return (corrected[:5] if corrected else ['EURUSDm'], mappings)


# ==================== GLOBAL VALIDATOR REGISTRY ====================

SYMBOL_VALIDATORS = {
    'Exness': ExnessSymbolValidator(),
    'Binance': BinanceSymbolValidator(),
    'PXBT': PXBTSymbolValidator(),
    'XM': XMSymbolValidator(),
    'XM Global': XMSymbolValidator(),
}


def validate_and_correct_symbols(symbols, broker_name=None):
    """
    Validate and normalize symbols based on broker type
    
    Args:
        symbols: List of symbol names (e.g., ['EURUSD', 'XAUUSD'])
        broker_name: Broker name (Exness, Binance, PXBT, XM, etc.)
    
    Returns:
        tuple: (validated_symbols_list, symbol_mappings_dict)
        
    Example:
        symbols, mappings = validate_and_correct_symbols(['EURUSD'], 'Exness')
        # symbols = ['EURUSDm']
        # mappings = {'EURUSD': 'EURUSDm'}
    """
    broker_name = canonicalize_broker_name(broker_name or 'Exness')
    
    # Get broker-specific validator
    validator = SYMBOL_VALIDATORS.get(broker_name)
    if not validator:
        logger.warning(f"⚠️ No validator for broker '{broker_name}', using Exness defaults")
        validator = SYMBOL_VALIDATORS['Exness']
    
    # Validate symbols
    validated_symbols, mappings = validator.validate(symbols)
    
    return validated_symbols
```

### STEP 2: Update Bot Creation to Track Mappings (10 min)

**File**: `multi_broker_backend_updated.py`  
**Location**: Line 11000-11005  
**Action**: Capture and store symbol mappings

Find:
```python
            symbols = validate_and_correct_symbols(raw_symbols, broker_name)
            strategy = data.get('strategy', 'Trend Following')
```

Replace with:
```python
            symbols = validate_and_correct_symbols(raw_symbols, broker_name)
            
            # Log symbol changes if symbols were normalized
            if raw_symbols != symbols:
                logger.info(f"ℹ️ Symbol normalization applied: {raw_symbols} → {symbols}")
            else:
                logger.info(f"✅ Symbols validated: {symbols}")
            
            strategy = data.get('strategy', 'Trend Following')
```

### STEP 3: Update Bot Response to Show Mappings (5 min)

**File**: `multi_broker_backend_updated.py`  
**Location**: Near the end of `create_bot()` function (around line 11150)  
**Action**: Include normalized symbols in response

Find:
```python
            return jsonify({
                'success': True,
                'botId': bot_id,
                ...
```

Update to:
```python
            return jsonify({
                'success': True,
                'botId': bot_id,
                'symbols': symbols,  # ← Include actual symbols being used
                'requestedSymbols': raw_symbols,  # ← Show what was requested
                'note': 'Symbols have been normalized to match broker format' if raw_symbols != symbols else None,
                ...
```

### STEP 4: Update Bot GET Endpoint (5 min)

**File**: `multi_broker_backend_updated.py`  
**Location**: `/api/bot/<bot_id>` endpoint (search for it)  
**Action**: Show actual vs requested symbols

Find the response for getting bot details:
```python
return jsonify({
    'botId': bot_id,
    'symbols': bot['symbols'],
    ...
})
```

Update to:
```python
return jsonify({
    'botId': bot_id,
    'symbols': bot['symbols'],
    'note': 'Symbols returned in broker format. Request with broker-format symbols to avoid normalization.',
    ...
})
```

### STEP 5: Update Trading Loop (5 min)

**File**: `multi_broker_backend_updated.py`  
**Location**: Trading loop (around line 12910)  
**Action**: Log which symbols are being used

Find:
```python
            corrected_symbols = validate_and_correct_symbols(original_symbols, bot_type)
```

Update to:
```python
            corrected_symbols = validate_and_correct_symbols(original_symbols, bot_type)
            
            if original_symbols != corrected_symbols:
                logger.info(f"🔄 Trading with normalized symbols: {original_symbols} → {corrected_symbols}")
            else:
                logger.info(f"📊 Trading with symbols: {corrected_symbols}")
```

## Testing the Changes

### Test 1: Create Bot with non-m Symbols

```bash
curl -X POST http://localhost:5000/api/bot/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbols": ["EURUSD", "XAUUSD"],
    "credentialId": "your-cred-id",
    "strategy": "Test Strategy"
  }'
```

**Expected response**:
```json
{
  "success": true,
  "botId": "bot_...",
  "symbols": ["EURUSDm", "XAUUSDm"],
  "requestedSymbols": ["EURUSD", "XAUUSD"],
  "note": "Symbols have been normalized to match broker format",
  ...
}
```

**Expected logs**:
```
ℹ️ Symbol normalization applied: ['EURUSD', 'XAUUSD'] → ['EURUSDm', 'XAUUSDm']
```

### Test 2: Create Bot with Already-Correct Symbols

```bash
curl -X POST http://localhost:5000/api/bot/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbols": ["EURUSDm", "XAUUSDm"],
    "credentialId": "your-cred-id",
    "strategy": "Test Strategy"
  }'
```

**Expected response**:
```json
{
  "success": true,
  "botId": "bot_...",
  "symbols": ["EURUSDm", "XAUUSDm"],
  "requestedSymbols": ["EURUSDm", "XAUUSDm"],
  ...
}
```

**Expected logs**:
```
✅ Symbols validated: ['EURUSDm', 'XAUUSDm']
```

### Test 3: Create Bot with Binance Credentials

```bash
curl -X POST http://localhost:5000/api/bot/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "symbols": ["BTCUSD", "ETHUSD"],  # Non-USDT format
    "credentialId": "binance-cred-id",
    "strategy": "Test Strategy"
  }'
```

**Expected response**:
```json
{
  "success": true,
  "botId": "bot_...",
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "requestedSymbols": ["BTCUSD", "ETHUSD"],
  "note": "Symbols have been normalized to match broker format",
  ...
}
```

## Rollback Plan

If something breaks:

1. **Revert function** — Replace `validate_and_correct_symbols()` back to original (lines 7470-7637 in your backup)
2. **Remove response changes** — Revert response JSON to not include `requestedSymbols` and `note`
3. **Restart backend** — Kill and restart Flask app
4. **Test basic bot creation** — Ensure bots still get created

## Verification Checklist

- [ ] Symbol validation function classes created
- [ ] `validate_and_correct_symbols()` refactored to use validators
- [ ] Bot creation logs symbol normalization
- [ ] Bot creation response includes actual vs requested symbols
- [ ] Bot GET endpoint shows symbols clearly
- [ ] Trading loop logs which symbols are used
- [ ] Test with Exness symbols (m suffix)
- [ ] Test with Binance symbols (USDT suffix)
- [ ] Verify backward compatibility (old bots still work)
- [ ] Check logs for mapping messages
- [ ] Verify no errors in stderr

---

**Estimated time**: ~40 minutes total  
**Risk level**: Low (changes are additive, don't break existing logic)  
**Testing effort**: Medium (need to test with real credentials)

