import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Update Exness credential password to ensure it's correct
c.execute("UPDATE broker_credentials SET password = 'Zwesta@1985' WHERE broker_name = 'Exness' AND account_number = '298997455'")
conn.commit()
print(f"Updated {c.rowcount} credential(s)")

# Verify
c.execute("SELECT credential_id, broker_name, account_number, server, password FROM broker_credentials")
for cr in c.fetchall():
    d = dict(cr)
    print(f"  Broker: {d['broker_name']} | Account: {d['account_number']} | Server: {d['server']} | Password: {'***' + d['password'][-4:] if d.get('password') else 'NONE'}")

conn.close()
