import sqlite3
import json

conn = sqlite3.connect('C:\\backend\\zwesta_trading.db')
cursor = conn.cursor()

user_id = '1323553f-1294-4280-9932-1c21a9c41879'
bot_name = 'Zwesta Bot'

cursor.execute('SELECT bot_id, name, runtime_state FROM user_bots WHERE user_id = ? AND name = ?', (user_id, bot_name))
bot = cursor.fetchone()

if bot:
    bot_id, name, runtime_state_str = bot
    state = json.loads(runtime_state_str)
    print('Bot ID:', bot_id)
    print('Current signalThreshold:', state.get('signalThreshold'))
    print('Adaptive offset:', state.get('adaptiveSignalThresholdOffset', 0))
else:
    print('Bot not found')

conn.close()