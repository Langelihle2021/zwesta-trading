"""
Authentication and User Management System for Zwesta Trading
"""
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
import jwt
from functools import wraps
from flask import request, jsonify

SECRET_KEY = secrets.token_hex(32)
DB_PATH = "zwesta_trading.db"

class AuthSystem:
    @staticmethod
    def hash_password(password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"
    
    @staticmethod
    def verify_password(stored_hash, password):
        """Verify password against hash"""
        try:
            salt, pwd_hash = stored_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return new_hash.hex() == pwd_hash
        except:
            return False
    
    @staticmethod
    def register_user(username, email, password, full_name, company_name):
        """Register new user"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email))
            if cursor.fetchone():
                return {"success": False, "error": "User already exists"}
            
            pwd_hash = AuthSystem.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name, company_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, pwd_hash, full_name, company_name))
            
            user_id = cursor.lastrowid
            
            # Create default demo account
            cursor.execute('''
                INSERT INTO accounts (user_id, account_type, account_name, initial_balance, current_balance)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 'demo', f'{full_name} Demo Account', 10000, 10000))
            
            conn.commit()
            conn.close()
            return {"success": True, "user_id": user_id}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def login_user(username, password):
        """Authenticate user and return token"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, password_hash, full_name, email FROM users WHERE username=?", (username,))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return {"success": False, "error": "Invalid credentials"}
            
            user_id, pwd_hash, full_name, email = user
            
            if not AuthSystem.verify_password(pwd_hash, password):
                return {"success": False, "error": "Invalid credentials"}
            
            # Create JWT token
            payload = {
                'user_id': user_id,
                'username': username,
                'full_name': full_name,
                'email': email,
                'exp': datetime.utcnow() + timedelta(days=30)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
            
            return {"success": True, "token": token, "user_id": user_id, "full_name": full_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def verify_token(token):
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return payload
        except:
            return None

def token_required(f):
    """Decorator to require authentication token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        
        payload = AuthSystem.verify_token(token)
        if not payload:
            return jsonify({'error': 'Invalid token'}), 401
        
        request.user_id = payload['user_id']
        request.username = payload['username']
        return f(*args, **kwargs)
    
    return decorated
