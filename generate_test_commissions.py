#!/usr/bin/env python3
"""
Commission Test Data Generator for Zwesta Trading Backend

This script generates realistic test commission data to populate the SQLite database.
It creates:
- 20 commission transactions with various profit amounts
- 5 withdrawal requests in different statuses
- Commission configuration records

Usage:
    python generate_test_commissions.py

Requirements:
    - SQLite database at c:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db
    - Python 3.7+
"""

import sqlite3
import uuid
import random
from datetime import datetime, timedelta
import json
import sys

DB_PATH = r'c:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db'

# Test data configuration
TEST_CONFIG = {
    'users': ['user-001', 'user-002', 'user-003'],
    'bots': [
        {'id': 'bot-scalper-001', 'name': 'Scalper Bot 1'},
        {'id': 'bot-momentum-001', 'name': 'Momentum Trader'},
        {'id': 'bot-swing-001', 'name': 'Swing Trading Bot'},
        {'id': 'bot-arb-001', 'name': 'Arbitrage Bot'},
        {'id': 'bot-grid-001', 'name': 'Grid Trading Bot'},
    ],
    'profit_amounts': [25, 50, 75, 100, 150, 200, 250, 300, 400, 500],
    'commission_rates': [0.20, 0.15, 0.10, 0.05],  # 20%, 15%, 10%, 5%
}

def connect_db():
    """Connect to SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def generate_commission_id():
    """Generate unique commission ID"""
    return f"comm-{uuid.uuid4().hex[:8].upper()}"

def generate_withdrawal_id():
    """Generate unique withdrawal ID"""
    return f"wd-{uuid.uuid4().hex[:8].upper()}"

def create_commission_record(conn, user_id, bot_id, profit_amount, rate, days_ago=0):
    """Create a commission transaction record"""
    commission_id = generate_commission_id()
    commission_amount = profit_amount * rate
    created_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
    
    try:
        cursor = conn.cursor()
        
        # Insert commission record with all required fields
        cursor.execute('''
            INSERT INTO commissions (
                commission_id, earner_id, client_id, bot_id, 
                profit_amount, commission_rate, commission_amount, 
                created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            commission_id,
            user_id,  # earner_id
            user_id,  # client_id (simplified - user earns on own trades)
            bot_id,
            profit_amount,
            rate,
            commission_amount,
            created_at,
            'completed'
        ))
        
        print(f"✓ Commission {commission_id}: \${commission_amount:.2f} from \${profit_amount:.2f} profit")
        return commission_id
    except sqlite3.Error as e:
        print(f"❌ Failed to create commission: {e}")
        return None

def create_withdrawal_request(conn, user_id, amount, status_value, days_ago=0):
    """Create a withdrawal request record"""
    withdrawal_id = generate_withdrawal_id()
    created_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
    processed_at = None
    
    if status_value in ['approved', 'completed']:
        processed_at = (datetime.now() - timedelta(days=days_ago-1)).isoformat()
    
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO commission_withdrawals (
                withdrawal_id, user_id, amount, status, 
                created_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            withdrawal_id,
            user_id,
            amount,
            status_value,
            created_at,
            processed_at
        ))
        
        status_emoji = {
            'pending': '⏳',
            'approved': '✓',
            'completed': '✓✓',
            'rejected': '❌'
        }.get(status_value, '?')
        
        print(f"{status_emoji} Withdrawal {withdrawal_id}: \${amount:.2f} ({status_value})")
        return withdrawal_id
    except sqlite3.Error as e:
        print(f"❌ Failed to create withdrawal: {e}")
        return None

def setup_commission_config(conn):
    """Initialize commission configuration"""
    try:
        cursor = conn.cursor()
        
        # Check if config already exists
        cursor.execute('SELECT COUNT(*) as count FROM commission_config')
        count = cursor.fetchone()['count']
        
        if count > 0:
            print("✓ Commission config already initialized")
            return
        
        config_id = f"config-{uuid.uuid4().hex[:8].upper()}"
        rates = {
            'developer_cut': 0.20,
            'referrer_cut': 0.05,
            'trader_cut': 0.75
        }
        
        cursor.execute('''
            INSERT INTO commission_config (
                config_id, developer_id, rates, updated_at
            ) VALUES (?, ?, ?, ?)
        ''', (
            config_id,
            'system',
            json.dumps(rates),
            datetime.now().isoformat()
        ))
        
        print(f"✓ Commission config initialized with rates: {rates}")
    except sqlite3.Error as e:
        print(f"⚠️  Commission config creation: {e}")

def verify_tables(conn):
    """Verify required tables exist"""
    try:
        cursor = conn.cursor()
        
        required_tables = ['commissions', 'commission_withdrawals', 'commission_config']
        
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                print(f"❌ Required table '{table}' not found")
                return False
        
        print("✓ All required tables verified")
        return True
    except sqlite3.Error as e:
        print(f"❌ Table verification failed: {e}")
        return False

def get_table_stats(conn):
    """Get statistics about commission data"""
    try:
        cursor = conn.cursor()
        
        stats = {}
        
        # Commission stats
        cursor.execute('SELECT COUNT(*) as count, SUM(commission_amount) as total FROM commissions')
        row = cursor.fetchone()
        stats['commission_count'] = row['count']
        stats['total_commissions'] = row['total'] or 0
        
        # Withdrawal stats
        cursor.execute('''
            SELECT status, COUNT(*) as count, SUM(amount) as total 
            FROM commission_withdrawals 
            GROUP BY status
        ''')
        stats['withdrawals_by_status'] = {row['status']: {'count': row['count'], 'total': row['total']} 
                                         for row in cursor.fetchall()}
        
        return stats
    except sqlite3.Error as e:
        print(f"⚠️  Failed to get stats: {e}")
        return {}

def generate_test_data():
    """Main function to generate all test data"""
    
    print("\n" + "="*60)
    print("COMMISSION TEST DATA GENERATOR")
    print("="*60 + "\n")
    
    conn = connect_db()
    
    try:
        # Verify tables exist
        if not verify_tables(conn):
            print("\n❌ Cannot proceed - required tables not found")
            sys.exit(1)
        
        print("\n📝 Setting up commission configuration...")
        setup_commission_config(conn)
        
        # Generate commission transactions
        print("\n💰 Generating 20 commission transactions...")
        for i in range(20):
            user = random.choice(TEST_CONFIG['users'])
            bot = random.choice(TEST_CONFIG['bots'])
            profit = random.choice(TEST_CONFIG['profit_amounts'])
            rate = random.choice(TEST_CONFIG['commission_rates'])
            days_ago = random.randint(0, 30)  # Spread over last 30 days
            
            create_commission_record(conn, user, bot['id'], profit, rate, days_ago)
        
        # Generate withdrawal requests
        print("\n🏦 Generating 5 withdrawal requests...")
        
        # Recent pending withdrawal
        create_withdrawal_request(
            conn,
            TEST_CONFIG['users'][0],
            150.00,
            'pending',
            days_ago=1
        )
        
        # Recent approved withdrawal
        create_withdrawal_request(
            conn,
            TEST_CONFIG['users'][1],
            300.00,
            'approved',
            days_ago=3
        )
        
        # Completed withdrawal
        create_withdrawal_request(
            conn,
            TEST_CONFIG['users'][0],
            200.00,
            'completed',
            days_ago=7
        )
        
        # Rejected withdrawal
        create_withdrawal_request(
            conn,
            TEST_CONFIG['users'][2],
            500.00,
            'rejected',
            days_ago=5
        )
        
        # Old completed withdrawal
        create_withdrawal_request(
            conn,
            TEST_CONFIG['users'][1],
            100.00,
            'completed',
            days_ago=15
        )
        
        conn.commit()
        
        # Show summary
        print("\n" + "="*60)
        print("DATA GENERATION COMPLETE")
        print("="*60)
        
        stats = get_table_stats(conn)
        
        print(f"\n📊 Summary:")
        print(f"   Commissions: {stats.get('commission_count', 0)} transactions")
        print(f"   Total earned: \${stats.get('total_commissions', 0):.2f}")
        
        if 'withdrawals_by_status' in stats:
            print(f"\n   Withdrawals by status:")
            for status, data in stats['withdrawals_by_status'].items():
                print(f"      • {status}: {data['count']} requests, \${data['total']:.2f}")
        
        print(f"\n✅ All test data generated successfully!")
        print(f"   Database: {DB_PATH}\n")
        
    except Exception as e:
        print(f"\n❌ Error generating test data: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    generate_test_data()
