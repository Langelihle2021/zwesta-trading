import sqlite3
import uuid
from datetime import datetime

conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check existing users
print("📋 Existing users in backend database:")
cursor.execute('SELECT id, username, email FROM users LIMIT 10')
users = cursor.fetchall()
if users:
    for user in users:
        print(f"  ID: {user['id']}")
        print(f"  Username: {user['username']}")
        print(f"  Email: {user['email']}")
        print()
else:
    print("  No users found!")

# Create test-user-001 if needed
print("\n🆕 Creating test-user-001...")
try:
    user_id = 'test-user-001'
    cursor.execute('''
        INSERT INTO users (id, username, email, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, 'test_user_001', 'test@example.com', 'hashed_pass', datetime.now().isoformat()))
    
    conn.commit()
    print(f"✅ User created: {user_id}")
except sqlite3.IntegrityError as e:
    print(f"ℹ️ User already exists or error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

conn.close()
