# Symbol Processing Refactoring Guide

## Problem Statement

The current `validate_and_correct_symbols()` function (line 7470) has these issues:

1. **Assumes all unknown brokers are Exness** — Falls back to `EURUSDm` for non-Binance/PXBT/XM brokers
2. **Hardcoded symbol mappings** — Can't easily support brokers with different symbol formats
3. **Silent symbol changes** — Users don't know their symbols got mapped
4. **Broker-specific code scattered** — Different logic for Binance/PXBT/XM/Exness mixed together
5. **No validation against actual broker** — Assumes mapped symbol exists on broker

## Current Code Flow

```
validate_and_correct_symbols(symbols=['EURUSD'], broker_name='Exness')
  ↓
if broker_name == 'Binance':
  ↓ (No, skip)
if broker_name == 'PXBT':
  ↓ (No, skip)
if broker_name in ('XM', 'XM Global'):
  ↓ (No, skip)
if not symbols:
  ↓ (No, skip)
corrected = []
for symbol in symbols:
  if symbol in VALID_SYMBOLS:
    ↓ ('EURUSD' NOT in VALID_SYMBOLS, skip)
  elif symbol in SYMBOL_MAPPING:
    ↓ ('EURUSD' IS in SYMBOL_MAPPING)
    new_symbol = SYMBOL_MAPPING[symbol]  # 'EURUSDm'
    corrected.append('EURUSDm')
  else:
    ↓ (Not reached)
return ['EURUSDm']  # Silently returns mapped symbol
```

**Result**: User sent `EURUSD`, gets back `EURUSDm` — Silent change!

## Solution 1: Add Logging + Transparency

**Minimal change** — Just add better feedback:

```python
def validate_and_correct_symbols(symbols, broker_name=None):
    """Validate symbols and provide transparent mapping feedback"""
    broker_name = canonicalize_broker_name(broker_name or '')
    
    # [existing broker-specific code...]
    
    # For Exness/default handling:
    if not symbols:
        return ['EURUSDm']
    
    corrected = []
    symbol_mappings_applied = {}  # ← NEW: Track what was mapped
    
    for symbol in symbols:
        if symbol in VALID_SYMBOLS:
            corrected.append(symbol)
        elif symbol in SYMBOL_MAPPING:
            new_symbol = SYMBOL_MAPPING[symbol]
            corrected.append(new_symbol)
            symbol_mappings_applied[symbol] = new_symbol  # ← NEW: Log it
            logger.warning(f"🔄 Symbol normalization: {symbol} → {new_symbol}")
        else:
            logger.warning(f"⚠️  Unknown symbol {symbol} - using EURUSDm fallback")
            if 'EURUSDm' not in corrected:
                corrected.append('EURUSDm')
                symbol_mappings_applied[symbol] = 'EURUSDm'
    
    # ← NEW: Return both corrected symbols AND mapping info
    return corrected[:5], symbol_mappings_applied
```

**Update bot creation** (line 10970) to capture mapping:
```python
symbols, symbol_mappings = validate_and_correct_symbols(raw_symbols, broker_name)

# Log mappings in response
logger.info(f"Symbol mappings applied: {symbol_mappings}")

# Store in response
return jsonify({
    'success': True,
    'botId': bot_id,
    'symbols': symbols,
    'symbolMappings': symbol_mappings,  # ← NEW: Tell user what changed
    ...
})
```

## Solution 2: Broker-Specific Symbol Validators (Recommended)

**Better architecture** — Separate concern by broker:

```python
# ==================== BROKER-SPECIFIC SYMBOL VALIDATORS ====================

class SymbolValidator:
    """Base class for broker-specific symbol validation"""
    
    def __init__(self, broker_name):
        self.broker_name = broker_name
        self.valid_symbols = set()
        self.symbol_mapping = {}
    
    def validate(self, symbols):
        """Return (validated_symbols, mapping_info)"""
        raise NotImplementedError
    
    def get_symbol_info(self, symbol):
        """Return symbol details: type, min_lot, max_lot, digits, etc."""
        raise NotImplementedError


class ExnessSymbolValidator(SymbolValidator):
    """Validate symbols for Exness/MT5"""
    
    VALID_SYMBOLS = {
        'BTCUSDm', 'ETHUSDm', 'EURUSDm', 'USDJPYm', 'XAUUSDm',
        'AAPLm', 'AMDm', 'MSFTm', 'NVDAm', 'JPMm', 'BACm',
        'WFCm', 'GOOGLm', 'METAm', 'ORCLm', 'TSMm'
    }
    
    SYMBOL_MAPPING = {
        'BTCUSD': 'BTCUSDm',
        'ETHUSD': 'ETHUSDm',
        'EURUSD': 'EURUSDm',
        'USDJPY': 'USDJPYm',
        'XAUUSD': 'XAUUSDm',
        # ... more mappings
    }
    
    def __init__(self):
        super().__init__('Exness')
        self.valid_symbols = self.VALID_SYMBOLS
        self.symbol_mapping = self.SYMBOL_MAPPING
    
    def validate(self, symbols):
        """Validate Exness symbols"""
        if not symbols:
            return (['EURUSDm'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            if symbol in self.valid_symbols:
                corrected.append(symbol)
            elif symbol in self.symbol_mapping:
                new_symbol = self.symbol_mapping[symbol]
                corrected.append(new_symbol)
                mappings[symbol] = new_symbol
                logger.info(f"📊 Exness symbol mapping: {symbol} → {new_symbol}")
            else:
                logger.warning(f"❌ Unknown Exness symbol: {symbol} → defaulting to EURUSDm")
                corrected.append('EURUSDm')
                mappings[symbol] = 'EURUSDm'
        
        # Deduplicate
        seen = set()
        final = []
        for s in corrected:
            if s not in seen:
                final.append(s)
                seen.add(s)
        
        return (final[:5], mappings)


class BinanceSymbolValidator(SymbolValidator):
    """Validate symbols for Binance"""
    
    VALID_SYMBOLS = {
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
        # ... all Binance symbols
    }
    
    SYMBOL_MAPPING = {
        'BTCUSD': 'BTCUSDT',
        'ETHUSD': 'ETHUSDT',
        # ... binance mappings
    }
    
    def __init__(self):
        super().__init__('Binance')
        self.valid_symbols = self.VALID_SYMBOLS
        self.symbol_mapping = self.SYMBOL_MAPPING
    
    def validate(self, symbols):
        """Validate Binance symbols"""
        if not symbols:
            return (['BTCUSDT'], {})
        
        corrected = []
        mappings = {}
        
        for symbol in symbols:
            normalized = str(symbol).upper().replace('/', '').replace('_', '')
            
            if normalized in self.valid_symbols:
                corrected.append(normalized)
            elif normalized in self.symbol_mapping:
                new_symbol = self.symbol_mapping[normalized]
                corrected.append(new_symbol)
                mappings[symbol] = new_symbol
                logger.info(f"📊 Binance symbol mapping: {symbol} → {new_symbol}")
            else:
                logger.warning(f"❌ Unknown Binance symbol: {symbol} → skipping")
                mappings[symbol] = None
        
        return (corrected if corrected else ['BTCUSDT'], mappings)


# ==================== GLOBAL VALIDATOR REGISTRY ====================

SYMBOL_VALIDATORS = {
    'Exness': ExnessSymbolValidator(),
    'Binance': BinanceSymbolValidator(),
    'PXBT': PXBTSymbolValidator(),  # Define similarly
    'XM': XMSymbolValidator(),       # Define similarly
}


def validate_and_correct_symbols(symbols, broker_name=None):
    """
    Dispatcher function that routes to broker-specific validator
    
    Returns:
        tuple: (validated_symbols_list, mapping_dict)
    """
    broker_name = canonicalize_broker_name(broker_name or 'Exness')
    
    validator = SYMBOL_VALIDATORS.get(broker_name)
    if not validator:
        logger.warning(f"⚠️ No validator for {broker_name}, using Exness defaults")
        validator = SYMBOL_VALIDATORS['Exness']
    
    return validator.validate(symbols)
```

**Update bot creation** to use new return format:

```python
# Line 11002 - OLD CODE:
symbols = validate_and_correct_symbols(raw_symbols, broker_name)

# NEW CODE:
symbols, symbol_mappings = validate_and_correct_symbols(raw_symbols, broker_name)

# Store mapping info in bot state for transparency
active_bots[bot_id] = {
    'botId': bot_id,
    'symbols': symbols,
    'symbolMappings': symbol_mappings,  # ← NEW
    ...
}
```

## Solution 3: Query Broker for Valid Symbols (Ultimate)

**Most robust** — Validate against actual broker:

```python
class ExnessSymbolValidator(SymbolValidator):
    """Validate by querying actual MT5 broker"""
    
    def validate(self, symbols, mt5_connection=None):
        """
        Validate symbols against actual broker
        
        Args:
            symbols: List of symbol names to validate
            mt5_connection: Optional MT5Connection for live validation
        
        Returns:
            tuple: (validated_symbols, symbol_info, mappings)
        """
        if not mt5_connection:
            # Fall back to static validation
            return self._validate_static(symbols)
        
        # Query actual broker
        valid_symbols = mt5_connection.get_symbols()
        corrected = []
        symbol_info = {}
        mappings = {}
        
        for symbol in symbols:
            # Try exact match first
            if symbol in valid_symbols:
                corrected.append(symbol)
                symbol_info[symbol] = mt5_connection.get_symbol_info(symbol)
            # Try mapped version
            elif symbol in self.symbol_mapping:
                new_symbol = self.symbol_mapping[symbol]
                if new_symbol in valid_symbols:
                    corrected.append(new_symbol)
                    symbol_info[new_symbol] = mt5_connection.get_symbol_info(new_symbol)
                    mappings[symbol] = new_symbol
                else:
                    logger.error(f"❌ Mapped symbol {new_symbol} not found on broker")
            else:
                logger.warning(f"❌ Symbol {symbol} not found on broker")
        
        return (corrected or ['EURUSDm'], symbol_info, mappings)
```

**Usage in bot creation**:
```python
# Get MT5 connection for validation
mt5_conn = establish_mt5_connection(credential_data)

# Validate against actual broker
symbols, symbol_info, mappings = validate_and_correct_symbols(
    raw_symbols,
    broker_name,
    mt5_connection=mt5_conn  # ← Pass actual broker connection
)

# Now you KNOW these symbols exist on the broker!
logger.info(f"✅ Validated symbols against broker: {symbols}")
for sym, info in symbol_info.items():
    logger.info(f"  {sym}: spread={info['spread']}, digits={info['digits']}")
```

## Implementation Priority

1. **Quick fix** (5 min) → Solution 1: Add logging + transparency
2. **Better fix** (30 min) → Solution 2: Refactor with broker validators
3. **Best fix** (1-2 hours) → Solution 3: Query actual broker for validation

## Testing Each Solution

### Test Solution 1 (Logging):
```python
# Create bot with EURUSD
response = requests.post('/api/bot/create', json={
    'symbols': ['EURUSD'],
    'credentialId': '...'
})

# Check response
assert response.json()['symbols'] == ['EURUSDm']
assert response.json()['symbolMappings'] == {'EURUSD': 'EURUSDm'}
assert 'Symbol normalization: EURUSD → EURUSDm' in logs
```

### Test Solution 2 (Validators):
```python
# Create bot with various symbols
response = requests.post('/api/bot/create', json={
    'symbols': ['EURUSD', 'UNKNOWN', 'XAUUSDm'],
    'credentialId': '...'
})

# Check response
assert response.json()['symbols'] == ['EURUSDm', 'XAUUSDm']
assert response.json()['symbolMappings'] == {
    'EURUSD': 'EURUSDm',
    'UNKNOWN': 'EURUSDm' (fallback)
}
```

### Test Solution 3 (Broker query):
```python
# Create bot - validates against actual broker
response = requests.post('/api/bot/create', json={
    'symbols': ['EURUSD', 'XYZABC'],  # XYZABC doesn't exist
    'credentialId': '...'
})

# Should reject invalid symbol
assert response.status_code == 400
assert 'XYZABC not found on broker' in response.json()['error']
```

## Recommendation

**Use Solution 2** (Broker-specific validators) because:
- ✅ Clear separation of concerns
- ✅ Easy to add new brokers
- ✅ Transparent mapping with feedback
- ✅ Testable in isolation
- ✅ Doesn't require MT5 connection during bot creation
- ❌ Symbol validation still static (wouldn't catch broker symbol deletions)

Then upgrade to **Solution 3** later if needed for production safety.

---

**Next**: Pick a solution, implement it, then test with your actual broker credentials.
