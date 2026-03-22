import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Check if we can insert a test bot
test_bot_id = "test_bot_12345"
user_id = "3a8f7a0c-4c68-4ace-97b3-221c1f971e29"
try:
    cursor.execute('''
        INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (test_bot_id, user_id, "TestBot", "Trend Following", "active", 1, "Exness_298997455", "ETHUSDm", "2026-03-21T15:00:00", "2026-03-21T15:00:00"))
    conn.commit()
    print("✅ Test INSERT successful")
    
    # Verify it was inserted
    cursor.execute("SELECT bot_id FROM user_bots WHERE bot_id = ?", (test_bot_id,))
    result = cursor.fetchone()
    if result:
        print(f"✅ Verified bot in database: {result[0]}")
    else:
        print("❌ Bot NOT found after insert - commit didn't work?")
        
    # Check total bots now
    cursor.execute("SELECT COUNT(*) FROM user_bots")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total bots in database now: {total}")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
