import argparse
import sqlite3
from typing import Iterable, List, Sequence

from postgres_schema import create_postgres_schema
from runtime_infrastructure import build_sqlite_connection, get_database_path, get_database_url, get_sqlalchemy_engine


DEFAULT_TABLES = [
    'users',
    'commissions',
    'referrals',
    'withdrawals',
    'bot_monitoring',
    'auto_withdrawal_settings',
    'auto_withdrawal_history',
    'user_bots',
    'transactions',
    'user_payment_methods',
    'commission_ledger',
    'broker_credentials',
    'bot_credentials',
    'commission_withdrawals',
    'exness_withdrawals',
    'exness_trade_profits',
    'user_wallets',
    'wallet_transactions',
    'user_sessions',
    'bot_activation_pins',
    'bot_deletion_tokens',
    'vps_config',
    'vps_monitoring',
    'commission_config',
    'ig_withdrawal_notifications',
    'broker_withdrawal_notifications',
    'trading_symbols',
    'bot_strategies',
    'user_accounts',
    'user_trading_settings',
    'trades',
    'pause_events',
    'pxbt_orders',
    'binance_orders',
    'worker_pool',
    'worker_bot_queue',
    'worker_bot_assignments',
]


def chunked(rows: Sequence[tuple], size: int) -> Iterable[Sequence[tuple]]:
    for index in range(0, len(rows), size):
        yield rows[index:index + size]


def fetch_rows(sqlite_conn: sqlite3.Connection, table_name: str) -> tuple[List[str], List[tuple]]:
    cursor = sqlite_conn.cursor()
    cursor.execute(f'SELECT * FROM {table_name}')
    column_names = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    return column_names, rows


def truncate_table(pg_conn, table_name: str) -> None:
    pg_conn.exec_driver_sql(f'TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE')


def insert_rows(pg_conn, table_name: str, columns: List[str], rows: Sequence[tuple]) -> None:
    if not rows:
        return

    placeholders = ', '.join(f':{index}' for index in range(len(columns)))
    columns_sql = ', '.join(columns)
    statement = f'INSERT INTO {table_name} ({columns_sql}) VALUES ({placeholders})'

    payload = []
    for row in rows:
        payload.append({str(index): value for index, value in enumerate(row)})

    pg_conn.exec_driver_sql(statement, payload)


def migrate_table(sqlite_conn: sqlite3.Connection, pg_conn, table_name: str, truncate_existing: bool, batch_size: int) -> int:
    columns, rows = fetch_rows(sqlite_conn, table_name)
    if truncate_existing:
        truncate_table(pg_conn, table_name)

    total_inserted = 0
    for batch in chunked(rows, batch_size):
        insert_rows(pg_conn, table_name, columns, batch)
        total_inserted += len(batch)
    return total_inserted


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Create PostgreSQL schema and migrate data from the current SQLite Zwesta database.'
    )
    parser.add_argument('--sqlite-path', default=get_database_path(), help='Source SQLite database path')
    parser.add_argument('--database-url', default=get_database_url(), help='Target PostgreSQL DATABASE_URL')
    parser.add_argument('--tables', nargs='*', default=DEFAULT_TABLES, help='Subset of tables to migrate')
    parser.add_argument('--batch-size', type=int, default=500, help='Insert batch size')
    parser.add_argument('--truncate-existing', action='store_true', help='Truncate PostgreSQL tables before inserting data')
    args = parser.parse_args()

    if not args.database_url:
        print('DATABASE_URL or --database-url is required for PostgreSQL migration.')
        return 1

    sqlite_conn = build_sqlite_connection(timeout=30.0, row_factory=False, database_path=args.sqlite_path)

    engine = get_sqlalchemy_engine(args.database_url)
    if engine is None:
        print('Could not create PostgreSQL engine. Check DATABASE_URL and installed drivers.')
        sqlite_conn.close()
        return 1

    create_postgres_schema(database_url=args.database_url)

    migrated = {}
    with engine.begin() as pg_conn:
        for table_name in args.tables:
            try:
                inserted = migrate_table(sqlite_conn, pg_conn, table_name, args.truncate_existing, args.batch_size)
                migrated[table_name] = inserted
                print(f'{table_name}: migrated {inserted} rows')
            except Exception as exc:
                print(f'{table_name}: FAILED -> {exc}')
                sqlite_conn.close()
                raise

    sqlite_conn.close()
    print('Migration complete.')
    print(migrated)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())