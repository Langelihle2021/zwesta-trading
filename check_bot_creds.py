#!/usr/bin/env python3
"""Check bot-credential linkage"""

import sqlite3

db_path = r"C:\backend\zwesta_trading.db"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== CHECKING BOT CREDENTIALS LINKAGE ===\n")

# Check user_bots
cursor.execute("SELECT bot_id, broker_account_id FROM user_bots")
bots = cursor.fetchall()
print("User Bots:")
for bot in bots:
    print(f"  {bot['bot_id']:30s} | broker_account_id: {bot['broker_account_id']}")

# Check bot_credentials
cursor.execute("SELECT bot_id, credential_id, user_id FROM bot_credentials")
bot_creds = cursor.fetchall()
print(f"\nBot Credentials Links:")
if bot_creds:
    for bc in bot_creds:
        print(f"  {bc['bot_id']:30s} -> {bc['credential_id']}")
else:
    print("  ❌ NO LINKS FOUND")

# Check broker_credentials
cursor.execute("SELECT credential_id, broker_name, account_number FROM broker_credentials")
creds = cursor.fetchall()
print(f"\nBroker Credentials:")
for cred in creds:
    print(f"  {cred['credential_id'][:10]:10s} | {cred['broker_name']:15s} | Account: {cred['account_number']}")

conn.close()

print("\n=== ANALYSIS ===")
print("✓ If bot_credentials table is EMPTY → bots won't find their credentials")
print("✓ If credentialId in bots isn't in broker_credentials → credentials not found")
