#!/usr/bin/env python
"""Update demo account passwords"""
import sqlite3
import hashlib
import os

db_path = os.path.join(os.path.dirname(__file__), 'zwesta_trading.db')
db = sqlite3.connect(db_path)
cursor = db.cursor()

passwords = {
    'demo': 'demo',
    'newuser': 'newuser',
    'Zwesta': 'Zwesta',
    'Zwesta1': 'Zwesta',
}

print('=== Updating Passwords ===')
for username, password in passwords.items():
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (pwd_hash, username))
    print(f'✓ {username}: password="{password}"')

db.commit()

# Verify
print('\n=== Verification ===')
cursor.execute('SELECT username, password_hash FROM users')
for username, hash_val in cursor.fetchall():
    # Test the hash
    test_hash = hashlib.sha256(username.encode()).hexdigest()
    print(f'{username}: {hash_val[:20]}...')

db.close()
print('\n✓ Database updated!')
