import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('C:\\backend\\zwesta_trading.db')
cursor = conn.cursor()

# User ID from context
user_id = '1323553f-1294-4280-9932-1c21a9c41879'

# Find the bot
cursor.execute("SELECT id, name, config FROM user_bots WHERE user_id = ? AND name = ?", (user_id, 'Zwesta Bot'))
bot = cursor.fetchone()

if bot:
    bot_id, name, config_str = bot
    config = json.loads(config_str)

    # Lower the signalThreshold to 35 to allow signals of 30-35
    config['signalThreshold'] = 35

    # Reset adaptive offset to allow fresh adaptation
    config['adaptiveSignalThresholdOffset'] = 0
    config['adaptiveSignalMissCount'] = 0
    config['adaptiveSignalThresholdReason'] = None

    # Update the config
    new_config_str = json.dumps(config)
    cursor.execute("UPDATE user_bots SET config = ? WHERE id = ?", (new_config_str, bot_id))

    conn.commit()
    print(f"Updated bot '{name}' (ID: {bot_id}) signalThreshold to 35")
else:
    print("Bot not found")

conn.close()