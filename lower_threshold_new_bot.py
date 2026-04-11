import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('C:\\backend\\zwesta_trading.db')
cursor = conn.cursor()

# User ID from log
user_id = 'e342365e-915a-49d9-93d2-a5ce951281f2'

# Find the bot
cursor.execute("SELECT bot_id, name, runtime_state FROM user_bots WHERE user_id = ? AND name = ?", (user_id, 'Zwesta Bot 1'))
bot = cursor.fetchone()

if bot:
    bot_id, name, runtime_state_str = bot
    state = json.loads(runtime_state_str)

    # Lower the signalThreshold to 40 for more trading
    state['signalThreshold'] = 40

    # Reset adaptive offset
    state['adaptiveSignalThresholdOffset'] = 0
    state['adaptiveSignalMissCount'] = 0
    state['adaptiveSignalThresholdReason'] = None

    # Update the config
    new_state_str = json.dumps(state)
    cursor.execute("UPDATE user_bots SET runtime_state = ? WHERE bot_id = ?", (new_state_str, bot_id))

    conn.commit()
    print(f"Updated bot '{name}' (ID: {bot_id}) signalThreshold to 40")
else:
    print("Bot not found")

conn.close()