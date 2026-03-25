import sqlite3
import hashlib

# Calculate the correct hash for "demo"
password = "demo"
pwd_hash = hashlib.sha256(password.encode()).hexdigest()

# Update database
conn = sqlite3.connect("zwesta_trading.db")
cursor = conn.cursor()
cursor.execute("UPDATE users SET password_hash=? WHERE username='demo'", (pwd_hash,))
conn.commit()
print(f"Updated demo user password to: {pwd_hash}")

# Verify
cursor.execute("SELECT username, password_hash FROM users WHERE username='demo'")
user = cursor.fetchone()
print(f"Verified: {user[0]} now has hash: {user[1]}")

# Also fix other users
users_to_fix = [
    ('newuser', 'newuser'),
    ('Zwesta', 'password123'),
    ('Zwesta1', 'password123'),
]

for username, pwd in users_to_fix:
    new_hash = hashlib.sha256(pwd.encode()).hexdigest()
    cursor.execute("UPDATE users SET password_hash=? WHERE username=?", (new_hash, username))
    print(f"Updated {username} password to: {new_hash}")

conn.commit()
conn.close()
print("\nAll passwords reset successfully!")
