#!/usr/bin/env python
"""Check password hashes in database"""
import sqlite3
import hashlib

db_path = r'C:\zwesta-trader\xm_trading_system\zwesta_trading.db'
db = sqlite3.connect(db_path)
cursor = db.cursor()

print("=== Stored User Passwords ===")
cursor.execute('SELECT username, password_hash FROM users')
users = cursor.fetchall()

for username, hash_val in users:
    print(f'User: {username}')
    print(f'Stored Hash: {hash_val[:16]}...')
    
# Test password hashes
test_passwords = {
    'demo': 'demo',
    'newuser': 'newuser',
    'Zwesta': 'Zwesta',
    'Zwesta1': 'Zwesta1',
}

print("\n=== Calculated Hashes ===")
for desc, password in test_passwords.items():
    calculated = hashlib.sha256(password.encode()).hexdigest()
    print(f'Password "{password}": {calculated[:16]}...')

print("\n=== Checking Demo Account ===")
cursor.execute('SELECT id, username, password_hash FROM users WHERE username=?', ('demo',))
demo = cursor.fetchone()
if demo:
    user_id, username, stored_hash = demo
    pwd_check = hashlib.sha256('demo'.encode()).hexdigest()
    print(f'Stored hash: {stored_hash}')
    print(f'Calculated:  {pwd_check}')
    print(f'Match: {pwd_check == stored_hash}')

db.close()
