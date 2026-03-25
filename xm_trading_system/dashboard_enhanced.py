"""
Zwesta Trading System - Hybrid Flask Backend with Auth Support
"""
import os
import sqlite3
import json
from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime, timedelta
import hashlib
import secrets
import time
import uuid

# Import MT5 data provider for live trading data
try:
    from mt5_data_provider import mt5_provider, init_mt5_provider
    MT5_ENABLED = True
except ImportError:
    MT5_ENABLED = False
    print("[WARN] MT5 data provider not available")

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = secrets.token_hex(32)
# Disable all caching
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
DB_PATH = os.path.join(os.path.dirname(__file__), "zwesta_trading.db")

# CORS configuration
@app.after_request
def handle_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    # Force NO caching on ANY response
    response.headers['Cache-Control'] = 'no-store, no-cache, no-transform, must-revalidate, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    response.headers['Vary'] = '*'
    return response

@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        return ('', 200)
    
    # Log all requests
    if request.path.startswith('/api/'):
        print(f"[API] {request.method} {request.path} from {request.remote_addr}")

# Initialize database
def init_db():
    """Initialize SQLite database - create tables if they don't exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            is_active BOOLEAN DEFAULT 1
        )''')
        
        # Add reset token columns if they don't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'reset_token' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token TEXT')
        if 'reset_token_expiry' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN reset_token_expiry TIMESTAMP')
        if 'phone_number' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN phone_number TEXT')
        if 'alert_threshold' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN alert_threshold REAL DEFAULT 500')
        if 'alert_enabled' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN alert_enabled BOOLEAN DEFAULT 1')
        
        # Accounts table
        cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_type TEXT,
            account_name TEXT,
            initial_balance REAL,
            current_balance REAL,
            currency TEXT DEFAULT 'USD',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        
        # Trades table
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            symbol TEXT,
            entry_price REAL,
            exit_price REAL,
            quantity REAL,
            status TEXT DEFAULT 'open',
            open_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            close_date TIMESTAMP,
            profit_percent REAL,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )''')
        
        # Withdrawals
        cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            amount REAL,
            method TEXT,
            status TEXT DEFAULT 'pending',
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )''')
        
        # MT5 Credentials - Store each user's MT5 account details
        cursor.execute('''CREATE TABLE IF NOT EXISTS mt5_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            mt5_account INTEGER,
            mt5_password TEXT,
            mt5_server TEXT,
            mt5_path TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_connected TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        
        # Profit Alerts - Track sent alerts to avoid duplicates
        cursor.execute('''CREATE TABLE IF NOT EXISTS profit_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profit_amount REAL,
            alert_type TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        
        conn.commit()
        
        # Create demo user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username='demo'")
        if cursor.fetchone()[0] == 0:
            pwd_hash = hashlib.sha256('demo123'.encode()).hexdigest()
            cursor.execute('''INSERT INTO users (username, email, password_hash, full_name)
                VALUES (?, ?, ?, ?)''', ('demo', 'demo@zwesta.com', pwd_hash, 'Demo User'))
            user_id = cursor.lastrowid
            
            # Demo account
            cursor.execute('''INSERT INTO accounts (user_id, account_type, account_name, initial_balance, current_balance)
                VALUES (?, ?, ?, ?, ?)''', (user_id, 'demo', 'Demo Account', 10000, 12543.50))
            
            # Live account
            cursor.execute('''INSERT INTO accounts (user_id, account_type, account_name, initial_balance, current_balance)
                VALUES (?, ?, ?, ?, ?)''', (user_id, 'live', 'Live Account', 50000, 52750.25))
            
            conn.commit()
        
        conn.close()
        print("[database_init_complete]")
    except Exception as e:
        print(f"Database init error: {e}")

# ==================== AUTH ENDPOINTS ====================
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate user - check database"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Missing credentials'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, full_name FROM users WHERE username=? OR email=?', 
                      (username, username))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        user_id, pwd_hash, full_name = user
        pwd_check = hashlib.sha256(password.encode()).hexdigest()
        
        if pwd_check != pwd_hash:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        token = hashlib.sha256(f"{user_id}{secrets.token_hex(16)}".encode()).hexdigest()
        return jsonify({
            'success': True,
            'token': token,
            'user_id': user_id,
            'full_name': full_name
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user with phone number"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    phone_number = data.get('phone_number', '').strip()
    
    if not username or not email or not password or not full_name or not phone_number:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be 6+ characters'}), 400
    
    conn = None
    try:
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''INSERT INTO users (username, email, password_hash, full_name, phone_number, is_active)
            VALUES (?, ?, ?, ?, ?, 1)''', (username, email, pwd_hash, full_name, phone_number))
        user_id = cursor.lastrowid
        
        cursor.execute('''INSERT INTO accounts (user_id, account_type, account_name, initial_balance, current_balance)
            VALUES (?, ?, ?, ?, ?)''', (user_id, 'demo', 'Demo Account', 10000.0, 10000.0))
        
        conn.commit()
        return jsonify({'success': True, 'user_id': user_id, 'message': 'Account created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Username or email already in use'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': 'Registration failed'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    email = data.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email=?', (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': True, 'message': 'If email exists, reset link sent'}), 200
        
        user_id = user[0]
        reset_token = secrets.token_urlsafe(32)
        expiry_time = datetime.utcnow() + timedelta(hours=24)
        reset_expiry = expiry_time.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('UPDATE users SET reset_token=?, reset_token_expiry=? WHERE id=?',
                      (reset_token, reset_expiry, user_id))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Reset link sent',
            'reset_token': reset_token
        }), 200
    except Exception as e:
        print(f"Forgot password error: {str(e)}")
        return jsonify({'success': False, 'error': 'Request failed'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    reset_token = data.get('reset_token', '')
    new_password = data.get('new_password', '')
    
    if not reset_token or not new_password:
        return jsonify({'success': False, 'error': 'Token and password required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Password must be 6+ characters'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, reset_token_expiry FROM users WHERE reset_token=?', (reset_token,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Invalid token'}), 400
        
        user_id, expiry_str = user
        expiry_time = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
        
        if expiry_time < datetime.utcnow():
            return jsonify({'success': False, 'error': 'Token expired'}), 400
        
        new_pwd_hash = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute('UPDATE users SET password_hash=?, reset_token=NULL, reset_token_expiry=NULL WHERE id=?',
                      (new_pwd_hash, user_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Password reset successful'}), 200
    except Exception as e:
        print(f"Reset password error: {str(e)}")
        return jsonify({'success': False, 'error': 'Reset failed'}), 500
    finally:
        if conn:
            conn.close()

# ==================== ACCOUNT ENDPOINTS ====================
@app.route('/api/user/accounts', methods=['GET'])
def get_user_accounts():
    """Get all user accounts"""
    user_id = request.args.get('user_id', 1)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, account_type, account_name, initial_balance, current_balance, currency
        FROM accounts WHERE user_id=?''', (int(user_id),))
    rows = cursor.fetchall()
    conn.close()
    
    accounts = [{
        'id': row[0],
        'account_type': row[1],
        'account_name': row[2],
        'initial_balance': row[3],
        'current_balance': row[4],
        'currency': row[5]
    } for row in rows]
    
    return jsonify({'data': accounts})

@app.route('/api/account', methods=['GET'])
def get_account():
    """Get account (backward compatible)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, account_name, current_balance FROM accounts LIMIT 1''')
    account = cursor.fetchone()
    conn.close()
    
    if account:
        return jsonify({'data': {
            'id': account[0],
            'name': account[1],
            'balance': account[2],
            'currency': 'USD'
        }})
    return jsonify({'data': {'balance': 0}})

@app.route('/api/accounts/<int:account_id>/dashboard', methods=['GET'])
def get_account_dashboard(account_id):
    """Get account dashboard data - pulls from MT5 if available"""
    try:
        # Try to get live MT5 data first
        if MT5_ENABLED and mt5_provider.initialized:
            account_info = mt5_provider.get_account_info()
            if account_info:
                trades = mt5_provider.get_closed_trades(30)
                winning_trades = len([t for t in trades if t['profit'] > 0])
                total_trades = len(trades)
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                return jsonify({
                    'data': {
                        'current_balance': account_info['equity'],
                        'initial_balance': account_info['balance'],
                        'profit_loss': account_info['profit'],
                        'return_percent': (account_info['profit'] / account_info['balance'] * 100) if account_info['balance'] > 0 else 0,
                        'total_trades': total_trades,
                        'win_rate': round(win_rate, 2),
                        'margin_level': account_info['margin_level']
                    }
                }), 200
        
        # Fallback to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get account info
        cursor.execute('SELECT current_balance, initial_balance FROM accounts WHERE id=?', (account_id,))
        account = cursor.fetchone()
        
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        current_balance = account[0]
        initial_balance = account[1]
        profit_loss = current_balance - initial_balance
        return_percent = (profit_loss / initial_balance * 100) if initial_balance > 0 else 0
        
        # Get trade count
        cursor.execute('SELECT COUNT(*) FROM trades WHERE account_id=?', (account_id,))
        total_trades = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'data': {
                'current_balance': current_balance,
                'initial_balance': initial_balance,
                'profit_loss': profit_loss,
                'return_percent': return_percent,
                'total_trades': total_trades,
                'win_rate': 75.0  # Placeholder
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== POSITIONS & TRADES ====================
@app.route('/api/positions', methods=['GET'])
@app.route('/api/positions/<int:account_id>', methods=['GET'])
def get_positions(account_id=None):
    """Get open positions - pulls from MT5 if available"""
    try:
        # Try to get live MT5 data first
        if MT5_ENABLED and mt5_provider.initialized:
            positions = mt5_provider.get_positions()
            if positions:
                return jsonify({'data': positions})
        
        # Fallback to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if account_id:
            cursor.execute('''SELECT symbol, entry_price, quantity, status FROM trades WHERE account_id=? AND status='open' LIMIT 20''', (account_id,))
        else:
            cursor.execute('''SELECT symbol, entry_price, quantity, status FROM trades WHERE status='open' LIMIT 20''')
        rows = cursor.fetchall()
        conn.close()
        
        positions = [{
            'symbol': row[0],
            'entry_price': row[1],
            'quantity': row[2],
            'status': row[3]
        } for row in rows]
        
        return jsonify({'data': positions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades', methods=['GET'])
@app.route('/api/trades/<int:account_id>', methods=['GET'])
def get_trades(account_id=None):
    """Get closed trades - pulls from MT5 if available"""
    try:
        # Try to get live MT5 data first
        if MT5_ENABLED and mt5_provider.initialized:
            trades = mt5_provider.get_closed_trades(days=30)
            if trades:
                return jsonify({'data': trades})
        
        # Fallback to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if account_id:
            cursor.execute('''SELECT symbol, entry_price, exit_price, quantity, open_date
                FROM trades WHERE account_id=? AND status='closed' ORDER BY open_date DESC LIMIT 50''', (account_id,))
        else:
            cursor.execute('''SELECT symbol, entry_price, exit_price, quantity, open_date
                FROM trades WHERE status='closed' ORDER BY open_date DESC LIMIT 50''')
        rows = cursor.fetchall()
        conn.close()
        
        trades = [{
            'symbol': row[0],
            'entry_price': row[1],
            'exit_price': row[2],
            'quantity': row[3],
            'profit_percent': round(((row[2] - row[1]) / row[1] * 100) if row[1] != 0 else 0, 2),
            'open_date': row[4]
        } for row in rows]
        
        return jsonify({'data': trades})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== STATISTICS ====================
@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get trading statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN profit_percent > 0 THEN profit_percent ELSE 0 END) as total_profit,
        COUNT(CASE WHEN profit_percent > 0 THEN 1 END) as wins
        FROM trades WHERE status='closed' ''')
    stats = cursor.fetchone()
    conn.close()
    
    total = stats[0] or 0
    wins = stats[2] or 0
    win_rate = (wins / total * 100) if total > 0 else 0
    
    return jsonify({'data': {
        'total_trades': total,
        'winning_trades': wins,
        'win_rate': win_rate,
        'total_profit': stats[1] or 0
    }})

# ==================== WITHDRAWALS ====================
@app.route('/api/withdrawals/request', methods=['POST'])
def request_withdrawal():
    """Request withdrawal"""
    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    method = data.get('method', '')
    account_id = int(data.get('account_id', 1))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO withdrawals (account_id, amount, method, status)
        VALUES (?, ?, ?, ?)''', (account_id, amount, method, 'pending'))
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'withdrawal_id': withdrawal_id,
        'status': 'pending'
    }), 201

@app.route('/api/withdrawals', methods=['GET'])
def get_withdrawals():
    """Get withdrawal history"""
    account_id = request.args.get('account_id', 1)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''SELECT id, amount, method, status, request_date FROM withdrawals
        WHERE account_id=? ORDER BY request_date DESC''', (int(account_id),))
    rows = cursor.fetchall()
    conn.close()
    
    withdrawals = [{
        'id': row[0],
        'amount': row[1],
        'method': row[2],
        'status': row[3],
        'request_date': row[4]
    } for row in rows]
    
    return jsonify({'data': withdrawals})

# ==================== STATEMENTS & PDF ====================
@app.route('/api/statements/generate', methods=['POST'])
def generate_statement():
    """Generate PDF statement with ReportLab"""
    try:
        data = request.get_json() or {}
        account_id = data.get('account_id', 1)
        period_type = data.get('period_type', 'monthly')
        
        # Get account info
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT account_name, current_balance FROM accounts WHERE id=?', (account_id,))
        account = cursor.fetchone()
        
        if not account:
            return jsonify({'error': 'Account not found'}), 404
        
        # Get trades
        cursor.execute('SELECT symbol, entry_price, exit_price, open_quantity, profit_percent FROM trades WHERE account_id=? LIMIT 50', (account_id,))
        trades = cursor.fetchall()
        conn.close()
        
        # Generate PDF using ReportLab
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from io import BytesIO
        
        # Create PDF in memory
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=30, bottomMargin=30)
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0096ff'),
            spaceAfter=30,
            alignment=1
        )
        
        # Build elements
        elements = []
        elements.append(Paragraph("ZWESTA TRADING STATEMENT", title_style))
        elements.append(Spacer(1, 12))
        
        # Account info
        account_info = f"Account: <b>{account[0]}</b> | Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Period: {period_type.upper()}"
        elements.append(Paragraph(account_info, styles['Normal']))
        elements.append(Spacer(1, 12))
        
        balance_info = f"Current Balance: <b>${account[1]:.2f}</b>"
        elements.append(Paragraph(balance_info, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Trade table
        if trades:
            elements.append(Paragraph("Trade History", styles['Heading2']))
            elements.append(Spacer(1, 12))
            
            trade_data = [['Symbol', 'Entry Price', 'Exit Price', 'Qty', 'P&L %']]
            for trade in trades:
                trade_data.append([
                    trade[0],
                    f"${trade[1]:.4f}",
                    f"${trade[2]:.4f}",
                    str(int(trade[3])),
                    f"{trade[4]:+.2f}%"
                ])
            
            trade_table = Table(trade_data, colWidths=[80, 100, 100, 60, 80])
            trade_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0096ff')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(trade_table)
        
        elements.append(Spacer(1, 20))
        footer = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Zwesta Trading System"
        elements.append(Paragraph(footer, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        
        filename = f"statement_{period_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/statements', methods=['GET'])
def get_statements():
    """Get statement history"""
    return jsonify({'data': []})

@app.route('/api/withdrawals/<int:account_id>', methods=['GET'])
def get_withdrawals_by_account(account_id):
    """Get withdrawal history for specific account"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''SELECT id, amount, method, status, request_date, completion_date FROM withdrawals
            WHERE account_id=? ORDER BY request_date DESC LIMIT 50''', (account_id,))
        rows = cursor.fetchall()
        conn.close()
        
        withdrawals = [{
            'id': row[0],
            'amount': row[1],
            'method': row[2],
            'status': row[3],
            'request_date': row[4],
            'completion_date': row[5]
        } for row in rows]
        
        return jsonify({'data': withdrawals})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/withdrawals/<int:account_id>/request', methods=['POST'])
def request_withdrawal_account(account_id):
    """Request withdrawal for specific account"""
    try:
        data = request.get_json() or {}
        amount = float(data.get('amount', 0))
        method = data.get('method', '')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO withdrawals (account_id, amount, method, status)
            VALUES (?, ?, ?, ?)''', (account_id, amount, method, 'pending'))
        withdrawal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'status': 'pending'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/statements/<int:account_id>', methods=['GET'])
def get_statements_by_account(account_id):
    """Get statements for specific account"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''SELECT id, period_type, opening_balance, closing_balance, profit_loss, 
                         win_rate, total_trades FROM statements WHERE account_id=? ORDER BY created_at DESC LIMIT 50''', (account_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            # Return empty list but with proper structure
            return jsonify({'data': []})
        
        statements = [{
            'id': row[0],
            'period_type': row[1],
            'opening_balance': row[2],
            'closing_balance': row[3],
            'profit_loss': row[4],
            'win_rate': row[5],
            'total_trades': row[6]
        } for row in rows]
        
        return jsonify({'data': statements})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== SYSTEM ====================
@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    return jsonify({'data': {'status': 'online'}})

@app.route('/api/symbols', methods=['GET'])
def get_symbols():
    """Get trading symbols"""
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD']
    return jsonify({'data': symbols})

@app.route('/api/candlesticks', methods=['GET'])
def get_candlesticks():
    """Get candlestick data"""
    return jsonify({'data': []})

@app.route('/api/mt5/refresh', methods=['POST'])
def refresh_mt5_data():
    """Force refresh of MT5 data - attempt to reconnect"""
    if not MT5_ENABLED:
        return jsonify({'error': 'MT5 not available'}), 503
    
    try:
        # Try to reconnect
        if not mt5_provider.initialized:
            init_mt5_provider()
        
        if mt5_provider.initialized:
            # Pull fresh data
            account_info = mt5_provider.get_account_info()
            positions = mt5_provider.get_positions()
            trades = mt5_provider.get_closed_trades(30)
            
            return jsonify({
                'success': True,
                'data': {
                    'account': account_info,
                    'positions_count': len(positions),
                    'trades_count': len(trades),
                    'positions': positions,
                    'trades': trades
                }
            }), 200
        else:
            return jsonify({'error': 'MT5 connection failed'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mt5/status', methods=['GET'])
def mt5_status():
    """Get current MT5 connection status and account info"""
    if not MT5_ENABLED:
        return jsonify({'mt5_enabled': False, 'connected': False}), 200
    
    try:
        if MT5_ENABLED and not mt5_provider.initialized:
            init_mt5_provider()
        
        if mt5_provider.initialized:
            account_info = mt5_provider.get_account_info()
            return jsonify({
                'mt5_enabled': True,
                'connected': True,
                'account': account_info
            }), 200
        else:
            return jsonify({
                'mt5_enabled': True,
                'connected': False,
                'error': 'MT5 terminal not responding'
            }), 200
    except Exception as e:
        return jsonify({
            'mt5_enabled': True,
            'connected': False,
            'error': str(e)
        }), 200

@app.route('/api/dashboard/health', methods=['GET'])
def health():
    """Health check - includes MT5 connection status"""
    mt5_status = 'unavailable'
    if MT5_ENABLED:
        if not mt5_provider.initialized:
            # Try to reconnect
            mt5_provider.connect()
        mt5_status = 'connected' if mt5_provider.initialized else 'disconnected'
    
    return jsonify({
        'data': {
            'healthy': True,
            'status': 'Zwesta Trading System Online',
            'mt5_status': mt5_status,
            'mt5_enabled': MT5_ENABLED
        }
    })

# ==================== MARKETS ====================
@app.route('/api/markets/symbols', methods=['GET'])
def get_market_symbols():
    """Get all tradable symbols with current prices and data"""
    try:
        # Try to get live MT5 data first
        if MT5_ENABLED and mt5_provider.initialized:
            try:
                symbols_data = []
                symbols = ['GOLD', 'XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD']
                for symbol in symbols:
                    info = mt5_provider.get_symbol_info(symbol)
                    if info:
                        symbols_data.append(info)
                if symbols_data:
                    return jsonify({'data': symbols_data})
            except Exception as e:
                print(f"[MT5] Failed to get symbols: {e}")
        
        # Fallback to demo data
        demo_symbols = [
            {
                'symbol': 'GOLD',
                'bid': 2074.50,
                'ask': 2074.65,
                'change_percent': 1.25,
                'high': 2080.00,
                'low': 2065.00,
                'description': 'Gold Spot'
            },
            {
                'symbol': 'XAUUSD',
                'bid': 2074.48,
                'ask': 2074.63,
                'change_percent': 1.24,
                'high': 2079.98,
                'low': 2064.95,
                'description': 'XAU/USD'
            },
            {
                'symbol': 'EURUSD',
                'bid': 1.08132,
                'ask': 1.08134,
                'change_percent': 0.45,
                'high': 1.08250,
                'low': 1.07950,
                'description': 'Euro/Dollar'
            },
            {
                'symbol': 'GBPUSD',
                'bid': 1.27450,
                'ask': 1.27470,
                'change_percent': 0.62,
                'high': 1.27650,
                'low': 1.27100,
                'description': 'Sterling/Dollar'
            },
            {
                'symbol': 'USDJPY',
                'bid': 149.85,
                'ask': 149.95,
                'change_percent': -0.35,
                'high': 150.50,
                'low': 149.20,
                'description': 'Dollar/Yen'
            },
            {
                'symbol': 'USDCAD',
                'bid': 1.35680,
                'ask': 1.35700,
                'change_percent': 0.18,
                'high': 1.36000,
                'low': 1.35300,
                'description': 'Dollar/Canadian'
            }
        ]
        
        return jsonify({'data': demo_symbols}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== USER SETTINGS ====================
@app.route('/api/user/settings', methods=['GET'])
def get_user_settings():
    """Get user settings including MT5 credentials and alerts"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing token'}), 401
    
    token = auth_header.replace('Bearer ', '')
    # Token validation would go here in production
    
    try:
        # Extract user_id from request or token (simplified for now)
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('SELECT full_name, email, phone_number, alert_threshold, alert_enabled FROM users WHERE id=?', (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({'error': 'User not found'}), 404
        
        # Get MT5 credentials
        cursor.execute('SELECT mt5_account, mt5_server, mt5_password, is_active FROM mt5_credentials WHERE user_id=?', (user_id,))
        mt5_data = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'data': {
                'full_name': user_data[0],
                'email': user_data[1],
                'phone_number': user_data[2],
                'alert_threshold': user_data[3],
                'alert_enabled': user_data[4],
                'mt5_account': mt5_data[0] if mt5_data else None,
                'mt5_server': mt5_data[1] if mt5_data else None,
                'mt5_configured': mt5_data is not None and mt5_data[3]
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/settings/mt5', methods=['POST'])
def update_mt5_credentials():
    """Save or update user's MT5 credentials"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing token'}), 401
    
    data = request.get_json()
    user_id = data.get('user_id')
    mt5_account = data.get('mt5_account')
    mt5_password = data.get('mt5_password')
    mt5_server = data.get('mt5_server', 'MetaQuotes-Demo')
    mt5_path = data.get('mt5_path', '')
    
    if not all([user_id, mt5_account, mt5_password, mt5_server]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if MT5 credentials exist
        cursor.execute('SELECT id FROM mt5_credentials WHERE user_id=?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''UPDATE mt5_credentials 
                SET mt5_account=?, mt5_password=?, mt5_server=?, mt5_path=?, is_active=1
                WHERE user_id=?''', (mt5_account, mt5_password, mt5_server, mt5_path, user_id))
        else:
            cursor.execute('''INSERT INTO mt5_credentials (user_id, mt5_account, mt5_password, mt5_server, mt5_path, is_active)
                VALUES (?, ?, ?, ?, ?, 1)''', (user_id, mt5_account, mt5_password, mt5_server, mt5_path))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'MT5 credentials saved'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/user/settings/alerts', methods=['POST'])
def update_alert_settings():
    """Update user's profit alert settings"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing token'}), 401
    
    data = request.get_json()
    user_id = data.get('user_id')
    alert_threshold = data.get('alert_threshold', 500)
    alert_enabled = data.get('alert_enabled', True)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''UPDATE users SET alert_threshold=?, alert_enabled=? WHERE id=?''',
                      (alert_threshold, alert_enabled, user_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Alert settings updated'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/', methods=['GET'])
def index():
    """Serve dashboard with aggressive cache-busting"""
    try:
        # Generate unique version for every request
        import uuid
        import time as time_module
        version = str(uuid.uuid4())
        timestamp = str(int(time_module.time() * 1000))
        response = app.make_response(render_template('index.html', cache_version=version, timestamp=timestamp))
        # Aggressive cache-busting headers
        response.headers['Cache-Control'] = 'no-store, no-cache, no-transform, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        response.headers['ETag'] = version
        response.headers['X-Accel-Buffering'] = 'no'
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        print(f"[ERROR] Failed to render index.html: {e}")
        return jsonify({'error': 'Dashboard not available', 'details': str(e)}), 500

if __name__ == '__main__':
    init_db()
    
    # Initialize MT5 connection if available
    if MT5_ENABLED:
        print("[MT5] Initializing MT5 data provider...")
        init_mt5_provider()
        if mt5_provider.initialized:
            print("[MT5] MT5 provider ready - dashboard will show live trading data")
        else:
            print("[MT5] MT5 provider initialization failed - using fallback demo data")
    else:
        print("[MT5] MT5 library not available - using demo data")
    
    # Start the multi-user trading bot in background
    try:
        from main import start_bot
        print("[BOT] Starting multi-user trading bot...")
        start_bot()
        print("[BOT] Trading bot running in background")
    except ImportError:
        print("[BOT] Warning: Could not import trading bot - install MetaTrader5: pip install MetaTrader5")
    except Exception as e:
        print(f"[BOT] Warning: Failed to start trading bot: {str(e)}")
    
    # Use HTTP only - no SSL certificates needed
    # Flask development server for dashboard - HTTP is fine for local/VPS network
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)

