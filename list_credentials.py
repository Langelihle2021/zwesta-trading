import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Check broker credentials for test users
cursor.execute('SELECT broker_name FROM broker_credentials GROUP BY broker_name')
brokers = [row[0] for row in cursor.fetchall()]
print("Broker types available:", brokers)

# Get credentials for the test user
cursor.execute(''' 
    SELECT credential_id, broker_name, account_number 
    FROM broker_credentials 
    WHERE user_id IN ("test-user-001", "test-user-payment-001", "test_user_payment_001")
    LIMIT 10
''')

print("\nAvailable credentials:")
for row in cursor.fetchall():
    print(f"  ID: {row[0]}")
    print(f"    Broker: {row[1]}, Account: {row[2]}")

conn.close()
