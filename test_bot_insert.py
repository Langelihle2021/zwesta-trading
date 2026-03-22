import sqlite3
from datetime import datetime
import uuid

# Test database connection and insert
db_path = r"zwesta_trading.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Test bot insert
bot_id = f"test_bot_{int(datetime.now().timestamp() * 1000)}"
user_id = "3a8f7a0c-4c68-4ace-97b3-221c1f971e29"
account_id = "Exness_298997455"
symbols = "ETHUSDm"
created_at = datetime.now().isoformat()

try:
    cursor.execute('''
        INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (bot_id, user_id, "TestBot", "Trend Following", "active", 1, account_id, symbols, created_at, created_at))
    conn.commit()
    print(f"✅ INSERT SUCCESS - bot_id: {bot_id}")
    
    # Verify it was inserted
    cursor.execute("SELECT COUNT(*) FROM user_bots WHERE bot_id = ?", (bot_id,))
    count = cursor.fetchone()[0]
    print(f"✅ VERIFICATION - bot found in DB: {count}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    conn.rollback()
finally:
    conn.close()

# Now check total bots
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM user_bots")
total = cursor.fetchone()[0]
print(f"📊 Total bots in database: {total}")
conn.close()
