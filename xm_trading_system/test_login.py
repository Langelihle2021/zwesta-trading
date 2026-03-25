import hashlib
import sqlite3

password = "demo"
hash_result = hashlib.sha256(password.encode()).hexdigest()
print(f"Hash of 'demo': {hash_result}")

# Check database
conn = sqlite3.connect(r"C:\zwesta-trader\xm_trading_system\zwesta_trading.db")
cursor = conn.cursor()
cursor.execute("SELECT id, username, password_hash FROM users WHERE username='demo' OR email='demo@zwesta.com'")
user = cursor.fetchone()
if user:
    print(f"\nFound user: ID={user[0]}, Username={user[1]}")
    print(f"Stored hash: {user[2]}")
    print(f"Match: {user[2] == hash_result}")
else:
    print("User not found")
conn.close()
