# Zwesta Trader - Real Data Integration Guide

## Current State
✅ Dashboard is working with **mock data** from Python functions
✅ All values are hardcoded in `dashboard_enhanced.py`
✅ Timezone is set to **SAST (UTC+2)**

## Option 1: Connect to XM Trading API (Recommended)

If you're using **XM broker**, use their API:

### Step 1: Get API Credentials
```
1. Log into your XM account at https://xmtrading.com
2. Go to Settings > API Connections
3. Generate API Key and API Secret
4. Save these credentials securely
```

### Step 2: Install XM Python Library
```bash
pip install xm-trading-api
# OR if available, use their REST API directly with requests
pip install requests
```

### Step 3: Update Flask to Fetch Real Data

Replace your endpoint in `dashboard_enhanced.py`:

```python
import requests
from datetime import datetime, timedelta, timezone

# Your XM API credentials
XM_API_KEY = "YOUR_API_KEY"
XM_API_SECRET = "YOUR_API_SECRET"
XM_API_URL = "https://api.xmtrading.com/v1"  # Check actual URL

@app.route('/api/account')
def get_account():
    """Fetch REAL account data from XM API"""
    try:
        headers = {
            'Authorization': f'Bearer {XM_API_KEY}',
            'Content-Type': 'application/json'
        }
        response = requests.get(f'{XM_API_URL}/account/info', headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'data': {
                    'balance': data['balance'],
                    'equity': data['equity'],
                    'profit': data['equity'] - data['balance'],
                    'open_positions': len(data.get('positions', [])),
                    'margin_used': data['margin_used'],
                    'margin_free': data['margin_free'],
                    'margin_level': data['margin_level'],
                    'currency': data['currency'],
                    'leverage': data['leverage'],
                    'account_type': data['account_type']
                }
            })
    except Exception as e:
        print(f"[ERROR] Failed to fetch account data: {e}")
        # Return mock data as fallback
        return jsonify({
            'data': {
                'balance': 0.0,
                'equity': 0.0,
                'profit': 0.0,
                'error': f'API Error: {str(e)}'
            }
        }), 500

@app.route('/api/positions')
def get_positions():
    """Fetch REAL open positions from XM API"""
    try:
        headers = {'Authorization': f'Bearer {XM_API_KEY}'}
        response = requests.get(f'{XM_API_URL}/positions/open', headers=headers, timeout=5)
        
        if response.status_code == 200:
            positions = response.json().get('positions', [])
            
            formatted_positions = []
            for pos in positions:
                formatted_positions.append({
                    'id': pos['ticket'],
                    'symbol': pos['symbol'],
                    'type': 'BUY' if pos['type'] == 0 else 'SELL',
                    'volume': pos['volume'],
                    'entry_price': pos['open_price'],
                    'current_price': pos['current_price'],
                    'profit': pos['profit'],
                    'profit_percent': (pos['profit'] / (pos['open_price'] * pos['volume'])) * 100,
                    'timestamp': pos['open_time']
                })
            
            return jsonify({'data': formatted_positions})
    except Exception as e:
        print(f"[ERROR] Failed to fetch positions: {e}")
        return jsonify({'data': []}), 500
```

---

## Option 2: Connect to Database (PostgreSQL/MySQL)

If you have a database storing trading data:

### Step 1: Install Database Driver
```bash
# For PostgreSQL
pip install psycopg2-binary

# For MySQL
pip install mysql-connector-python

# For SQLite (no install needed)
```

### Step 2: Update Flask with Database

```python
import psycopg2
from psycopg2.extras import RealDictCursor

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'trading_db',
    'user': 'trading_user',
    'password': 'your_password'
}

def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return None

@app.route('/api/account')
def get_account():
    """Fetch account data from database"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT balance, equity, margin_used, margin_free, currency 
            FROM accounts WHERE account_id = %s
        """, (12345678,))  # Replace with your account ID
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({'data': dict(result)})
        return jsonify({'error': 'Account not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Option 3: Connect to REST API (Generic)

If your broker provides REST API:

```python
import requests
import json

BROKER_API_URL = "https://api.yourbroker.com"
API_TOKEN = "your_api_token"

@app.route('/api/account')
def get_account():
    """Fetch data from any REST API"""
    try:
        headers = {
            'Authorization': f'Bearer {API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'{BROKER_API_URL}/account/summary',
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return jsonify({'data': response.json()})
        else:
            return jsonify({'error': f'API returned {response.status_code}'}), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
```

---

## Option 4: CSV/Local Data Files

If you're reading from local trading files:

```python
import pandas as pd

@app.route('/api/positions')
def get_positions():
    """Read positions from CSV file"""
    try:
        # Read positions from CSV
        df = pd.read_csv('C:/zwesta-trader/data/positions.csv')
        
        # Convert to JSON format
        positions = []
        for _, row in df.iterrows():
            positions.append({
                'id': int(row['id']),
                'symbol': row['symbol'],
                'type': row['type'],
                'volume': float(row['volume']),
                'entry_price': float(row['entry_price']),
                'current_price': float(row['current_price']),
                'profit': float(row['profit']),
                'profit_percent': float(row['profit_percent']),
                'timestamp': row['timestamp']
            })
        
        return jsonify({'data': positions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Option 5: MetaTrader 5 Integration

If using MetaTrader 5:

```python
import MetaTrader5 as mt5

# Connect to MT5
if not mt5.initialize():
    print("Failed to initialize MT5")

@app.route('/api/account')
def get_account():
    """Fetch live data from MetaTrader 5"""
    try:
        # Get account info
        account_info = mt5.account_info()
        
        if account_info is None:
            return jsonify({'error': 'MT5 connection failed'}), 500
        
        # Get open positions
        positions = mt5.positions_get()
        
        return jsonify({
            'data': {
                'balance': account_info.balance,
                'equity': account_info.equity,
                'profit': account_info.profit,
                'margin': account_info.margin,
                'margin_free': account_info.margin_free,
                'open_positions': len(positions) if positions else 0,
                'commission': account_info.commission,
                'name': account_info.name
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

Install: `pip install MetaTrader5`

---

## Quick Start: Update Your Mock Data

**Easiest option** - just update the hardcoded values in `dashboard_enhanced.py`:

### Current (Mock):
```python
'balance': 50000.00,
'equity': 48500.00,
'profit': 1250.50,
```

### With Your Real Values:
```python
# Replace with YOUR actual account balance
'balance': 75000.00,  # Change this
'equity': 72500.00,   # Change this
'profit': 2500.00,    # Change this
```

Then restart Flask - data updates immediately!

---

## Integration Checklist

- [ ] Choose your data source (API, Database, CSV, MT5, etc.)
- [ ] Get necessary credentials (API keys, database credentials, etc.)
- [ ] Install required Python library
- [ ] Update `dashboard_enhanced.py` with your data source
- [ ] Test endpoint: `curl http://127.0.0.1:5000/api/account`
- [ ] Restart Flask
- [ ] Refresh dashboard browser to see real data

---

## Troubleshooting

**"undefined" values on dashboard?**
- Check if API/database is returning correct JSON structure
- Verify field names match what dashboard expects
- Check Flask logs: `type C:\zwesta-trader\flask.log`

**API connection fails?**
- Verify credentials are correct
- Check firewall/network access
- Test API separately: `curl https://api.yourbroker.com/account`
- Add timeout to requests: `timeout=5`

**Database connection fails?**
- Verify database credentials
- Check database is running
- Confirm table names and column names
- Test connection: `psql -h localhost -U user -d database`

---

## Next Steps

1. **Choose your integration method** (API, Database, MT5, etc.)
2. **Get your credentials** (API keys, database password, etc.)
3. **Update `dashboard_enhanced.py`** with your data source
4. **Restart Flask**
5. **Test the dashboard** - you'll see real data instead of "undefined"

Need help? Check your Flask logs:
```bash
type C:\zwesta-trader\flask.log
```
