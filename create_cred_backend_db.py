import sqlite3
from datetime import datetime
import uuid

# Use the CORRECT database that backend uses!
conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Create a broker credential for test user with Exness demo account
credential_id = str(uuid.uuid4())
user_id = "test-user-001"
broker_name = "Exness"
account_number = "298997455"
password = "Zwesta@1985"
server = "Exness-MT5Trial9"
is_live = 0  # Demo mode

try:
    # First check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='broker_credentials'")
    if not cursor.fetchone():
        print("❌ broker_credentials table doesn't exist!")
    else:
        cursor.execute('''
            INSERT INTO broker_credentials (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (credential_id, user_id, broker_name, account_number, password, server, is_live, datetime.now().isoformat()))
        
        conn.commit()
        print(f"✅ Broker credential created in C:/backend/zwesta_trading.db!")
        print(f"credential_id: {credential_id}")
        print(f"broker_name: {broker_name}")
        print(f"account_number: {account_number}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    conn.close()
