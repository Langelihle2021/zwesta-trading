#!/usr/bin/env python3
"""
Clear all trading bots to start fresh, while preserving users and broker credentials.

Run on the VPS after stopping the backend process.
"""

import os
import shutil
import sqlite3
import traceback
from datetime import datetime

DB_PATH = r"C:\backend\zwesta_trading.db"
BOT_TABLES = [
    "worker_bot_assignments",
    "worker_bot_queue",
    "bot_deletion_tokens",
    "bot_activation_pins",
    "bot_monitoring",
    "bot_credentials",
    "trades",
    "user_bots",
]


def backup_database() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.pre_bot_reset.{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def count_rows(cursor, table_name: str) -> int:
    if not table_exists(cursor, table_name):
        return 0
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def clear_all_bots():
    """Remove all persisted bot state from the VPS database."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False

    conn = None
    try:
        backup_path = backup_database()

        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        print("=" * 70)
        print("CLEARING ALL BOTS - FRESH START")
        print("=" * 70)
        print(f"Backup created: {backup_path}")

        print("\nCurrent bot-related state:")
        table_counts = {}
        for table_name in BOT_TABLES:
            count = count_rows(cursor, table_name)
            table_counts[table_name] = count
            print(f"  {table_name}: {count}")

        credential_count = count_rows(cursor, "broker_credentials")
        print(f"  broker_credentials: {credential_count} (preserved)")

        if all(count == 0 for count in table_counts.values()):
            print("\nDatabase already has no bot records.")
            conn.close()
            return True

        print("\nDeleting bot-owned records...")
        for table_name in BOT_TABLES:
            if table_exists(cursor, table_name):
                cursor.execute(f"DELETE FROM {table_name}")
                print(f"  cleared {table_name}")

        conn.commit()

        print("\nVerification after cleanup:")
        for table_name in BOT_TABLES:
            print(f"  {table_name}: {count_rows(cursor, table_name)}")
        print(f"  broker_credentials: {count_rows(cursor, 'broker_credentials')} (preserved)")

        try:
            cursor.execute("VACUUM")
            print("\nVACUUM complete")
        except sqlite3.OperationalError as vacuum_error:
            print(f"\nVACUUM skipped: {vacuum_error}")

        conn.close()
        print("\nFresh start complete. Restart the backend and it should load 0 bots.")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    clear_all_bots()
