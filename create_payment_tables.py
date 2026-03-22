import sqlite3

conn = sqlite3.connect('zwesta_trading.db')
cursor = conn.cursor()

# Create payment-related tables
print("Creating payment system tables...")

try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT,
            status TEXT DEFAULT "pending",
            reason TEXT,
            stripe_transfer_id TEXT,
            bank_reference TEXT,
            crypto_tx_hash TEXT,
            fee REAL DEFAULT 0,
            net_amount REAL,
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    print("  ✓ Created 'transactions' table")
except Exception as e:
    print(f"  ! transactions table: {e}")

try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_payment_methods (
            method_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            primary_method BOOLEAN DEFAULT 0,
            stripe_account_id TEXT,
            bank_name TEXT,
            account_holder TEXT,
            account_number TEXT,
            routing_number TEXT,
            swift_code TEXT,
            crypto_wallet TEXT,
            crypto_type TEXT,
            verified BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    print("  ✓ Created 'user_payment_methods' table")
except Exception as e:
    print(f"  ! user_payment_methods table: {e}")

try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_ledger (
            entry_id TEXT PRIMARY KEY,
            commission_id TEXT,
            user_id TEXT NOT NULL,
            source_user_id TEXT,
            type TEXT,
            amount REAL,
            payout_status TEXT DEFAULT "pending",
            payout_method TEXT,
            payout_date TEXT,
            bot_id TEXT,
            trading_profit REAL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (commission_id) REFERENCES commissions(commission_id)
        )
    ''')
    print("  ✓ Created 'commission_ledger' table")
except Exception as e:
    print(f"  ! commission_ledger table: {e}")

conn.commit()
conn.close()

print("\nAll payment tables created successfully!")
