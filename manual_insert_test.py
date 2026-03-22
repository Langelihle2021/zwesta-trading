import sqlite3
import json
from datetime import datetime

# Manually insert test bot exactly like the backend does
conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

bot_id = "manual_test_bot_001"
user_id = "3a8f7a0c-4c68-4ace-97b3-221c1f971e29"
credential_id = "some_cred_id"
account_id = "Exness_298997455"
symbols = "ETHUSDm"
created_at = datetime.now().isoformat()

print(f"Attempting INSERT...")
print(f"  bot_id: {bot_id}")
print(f"  user_id: {user_id}")

try:
    cursor.execute('''
        INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (bot_id, user_id, "Manual Test", "Trend Following", "active", 1, account_id, symbols, created_at, created_at))
    
    cursor.execute('''
        INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
    ''', (bot_id, credential_id, user_id, created_at))
    
    print("✅ INSERTs successful, committing...")
    conn.commit()
    print("✅ COMMIT successful")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM user_bots")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total bots after INSERT: {total}")
    
    cursor.execute("SELECT bot_id FROM user_bots WHERE bot_id = ?", (bot_id,))
    result = cursor.fetchone()
    if result:
        print(f"✅ Bot found: {result[0]}")
    else:
        print(f"❌ Bot NOT found!")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    conn.rollback()
finally:
    conn.close()
