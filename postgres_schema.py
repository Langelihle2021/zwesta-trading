from typing import Iterable, Optional

from runtime_infrastructure import get_sqlalchemy_engine


POSTGRES_SCHEMA_SQL = [
    '''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT,
        referrer_id TEXT,
        referral_code TEXT UNIQUE,
        created_at TEXT,
        total_commission DOUBLE PRECISION DEFAULT 0,
        internal_balance DOUBLE PRECISION DEFAULT 0,
        FOREIGN KEY (referrer_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS commissions (
        commission_id TEXT PRIMARY KEY,
        earner_id TEXT NOT NULL,
        client_id TEXT NOT NULL,
        bot_id TEXT,
        profit_amount DOUBLE PRECISION,
        commission_rate DOUBLE PRECISION DEFAULT 0.05,
        commission_amount DOUBLE PRECISION,
        created_at TEXT,
        FOREIGN KEY (earner_id) REFERENCES users(user_id),
        FOREIGN KEY (client_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS referrals (
        referral_id TEXT PRIMARY KEY,
        referrer_id TEXT NOT NULL,
        referred_user_id TEXT NOT NULL,
        created_at TEXT,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (referrer_id) REFERENCES users(user_id),
        FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS withdrawals (
        withdrawal_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        method TEXT NOT NULL,
        account_details TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        processed_at TEXT,
        fee DOUBLE PRECISION DEFAULT 0,
        net_amount DOUBLE PRECISION,
        admin_notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_monitoring (
        monitoring_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        last_heartbeat TEXT,
        uptime_seconds BIGINT DEFAULT 0,
        health_check_count BIGINT DEFAULT 0,
        errors_count BIGINT DEFAULT 0,
        last_error TEXT,
        last_error_time TEXT,
        auto_restart_count BIGINT DEFAULT 0,
        created_at TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS auto_withdrawal_settings (
        setting_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        target_profit DOUBLE PRECISION NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        withdrawal_method TEXT DEFAULT 'fixed',
        withdrawal_mode TEXT DEFAULT 'manual',
        min_profit DOUBLE PRECISION DEFAULT 0,
        max_profit DOUBLE PRECISION DEFAULT 0,
        volatility_threshold DOUBLE PRECISION DEFAULT 0.02,
        win_rate_min DOUBLE PRECISION DEFAULT 50,
        trend_strength_min DOUBLE PRECISION DEFAULT 0.5,
        time_between_withdrawals_hours BIGINT DEFAULT 24,
        last_withdrawal_at TEXT,
        milestone_config TEXT,
        baseline_equity DOUBLE PRECISION DEFAULT 0,
        last_milestone_pct DOUBLE PRECISION DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS auto_withdrawal_history (
        withdrawal_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        triggered_profit DOUBLE PRECISION NOT NULL,
        withdrawal_amount DOUBLE PRECISION NOT NULL,
        fee DOUBLE PRECISION DEFAULT 0,
        net_amount DOUBLE PRECISION,
        reinvested_amount DOUBLE PRECISION DEFAULT 0,
        withdrawal_mode TEXT,
        withdrawal_reason TEXT,
        milestone_pct DOUBLE PRECISION DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_bots (
        bot_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        strategy TEXT,
        status TEXT DEFAULT 'active',
        enabled BOOLEAN DEFAULT TRUE,
        daily_profit DOUBLE PRECISION DEFAULT 0,
        total_profit DOUBLE PRECISION DEFAULT 0,
        broker_account_id TEXT,
        symbols TEXT DEFAULT 'EURUSD',
        created_at TEXT,
        updated_at TEXT,
        runtime_state TEXT,
        is_live BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        method TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        reason TEXT,
        stripe_transfer_id TEXT,
        bank_reference TEXT,
        crypto_tx_hash TEXT,
        fee DOUBLE PRECISION DEFAULT 0,
        net_amount DOUBLE PRECISION,
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_payment_methods (
        method_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        primary_method BOOLEAN DEFAULT FALSE,
        stripe_account_id TEXT,
        bank_name TEXT,
        account_holder TEXT,
        account_number TEXT,
        routing_number TEXT,
        swift_code TEXT,
        crypto_wallet TEXT,
        crypto_type TEXT,
        verified BOOLEAN DEFAULT FALSE,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS commission_ledger (
        entry_id TEXT PRIMARY KEY,
        commission_id TEXT,
        user_id TEXT NOT NULL,
        source_user_id TEXT,
        type TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        payout_status TEXT DEFAULT 'pending',
        payout_method TEXT,
        payout_date TEXT,
        bot_id TEXT,
        trading_profit DOUBLE PRECISION,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS broker_credentials (
        credential_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        broker_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        password TEXT NOT NULL,
        server TEXT,
        is_live BOOLEAN DEFAULT FALSE,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TEXT,
        updated_at TEXT,
        api_key TEXT,
        username TEXT,
        cached_balance DOUBLE PRECISION DEFAULT 0,
        cached_equity DOUBLE PRECISION DEFAULT 0,
        cached_margin_free DOUBLE PRECISION DEFAULT 0,
        last_update TEXT,
        cached_margin DOUBLE PRECISION DEFAULT 0,
        cached_margin_level DOUBLE PRECISION DEFAULT 0,
        cached_profit DOUBLE PRECISION DEFAULT 0,
        account_currency TEXT DEFAULT 'USD',
        mt5_terminal_path TEXT,
        UNIQUE(user_id, broker_name, account_number),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_credentials (
        bot_id TEXT NOT NULL,
        credential_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        created_at TEXT,
        PRIMARY KEY (bot_id, credential_id),
        FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
        FOREIGN KEY (credential_id) REFERENCES broker_credentials(credential_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS commission_withdrawals (
        withdrawal_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        processed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS exness_withdrawals (
        withdrawal_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        broker_account_id TEXT NOT NULL,
        withdrawal_type TEXT NOT NULL,
        source_type TEXT,
        profit_from_trades DOUBLE PRECISION DEFAULT 0,
        commission_earned DOUBLE PRECISION DEFAULT 0,
        total_amount DOUBLE PRECISION NOT NULL,
        fee DOUBLE PRECISION DEFAULT 0,
        net_amount DOUBLE PRECISION,
        status TEXT DEFAULT 'pending',
        withdrawal_method TEXT,
        payment_details TEXT,
        created_at TEXT,
        submitted_at TEXT,
        completed_at TEXT,
        admin_notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS exness_trade_profits (
        profit_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        broker_account_id TEXT NOT NULL,
        order_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        entry_price DOUBLE PRECISION NOT NULL,
        exit_price DOUBLE PRECISION NOT NULL,
        volume DOUBLE PRECISION NOT NULL,
        side TEXT,
        profit_loss DOUBLE PRECISION NOT NULL,
        commission DOUBLE PRECISION DEFAULT 0,
        pnl_percentage DOUBLE PRECISION,
        trade_duration_seconds BIGINT,
        closed_at TEXT,
        withdrawal_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (withdrawal_id) REFERENCES exness_withdrawals(withdrawal_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_wallets (
        wallet_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL UNIQUE,
        balance DOUBLE PRECISION DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        last_updated TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS wallet_transactions (
        transaction_id TEXT PRIMARY KEY,
        wallet_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        transaction_type TEXT,
        source_withdrawal_id TEXT,
        status TEXT DEFAULT 'completed',
        created_at TEXT,
        FOREIGN KEY (wallet_id) REFERENCES user_wallets(wallet_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (source_withdrawal_id) REFERENCES exness_withdrawals(withdrawal_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token TEXT UNIQUE,
        created_at TEXT,
        expires_at TEXT,
        ip_address TEXT,
        user_agent TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_activation_pins (
        pin_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        pin TEXT NOT NULL,
        attempts BIGINT DEFAULT 0,
        created_at TEXT,
        expires_at TEXT,
        FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_deletion_tokens (
        token_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        deletion_token TEXT NOT NULL,
        bot_stats TEXT,
        created_at TEXT,
        expires_at TEXT,
        confirmed BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS vps_config (
        vps_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        vps_name TEXT NOT NULL,
        vps_ip TEXT NOT NULL,
        vps_port BIGINT DEFAULT 3389,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        rdp_port BIGINT DEFAULT 3389,
        api_port BIGINT DEFAULT 5000,
        mt5_path TEXT DEFAULT 'C:\\Program Files\\MetaTrader 5\\terminal64.exe',
        notes TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        last_connection TEXT,
        status TEXT DEFAULT 'disconnected',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS vps_monitoring (
        monitoring_id TEXT PRIMARY KEY,
        vps_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        last_heartbeat TEXT,
        mt5_status TEXT DEFAULT 'offline',
        backend_running BOOLEAN DEFAULT FALSE,
        cpu_usage DOUBLE PRECISION DEFAULT 0,
        memory_usage DOUBLE PRECISION DEFAULT 0,
        uptime_hours BIGINT DEFAULT 0,
        active_bots BIGINT DEFAULT 0,
        total_value_locked DOUBLE PRECISION DEFAULT 0,
        last_check TEXT,
        created_at TEXT,
        FOREIGN KEY (vps_id) REFERENCES vps_config(vps_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS commission_config (
        config_id TEXT PRIMARY KEY,
        developer_id TEXT DEFAULT 'developer',
        developer_direct_rate DOUBLE PRECISION DEFAULT 0.25,
        developer_referral_rate DOUBLE PRECISION DEFAULT 0.25,
        recruiter_rate DOUBLE PRECISION DEFAULT 0.05,
        ig_commission_enabled BOOLEAN DEFAULT TRUE,
        ig_developer_rate DOUBLE PRECISION DEFAULT 0.25,
        ig_recruiter_rate DOUBLE PRECISION DEFAULT 0.05,
        multi_tier_enabled BOOLEAN DEFAULT FALSE,
        tier2_rate DOUBLE PRECISION DEFAULT 0.02,
        updated_at TEXT,
        updated_by TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS ig_withdrawal_notifications (
        notification_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        realized_profit DOUBLE PRECISION DEFAULT 0,
        positions_closed BIGINT DEFAULT 0,
        balance_available DOUBLE PRECISION DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS broker_withdrawal_notifications (
        notification_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        broker_name TEXT NOT NULL,
        amount DOUBLE PRECISION DEFAULT 0,
        message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        completed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS trading_symbols (
        symbol_id TEXT PRIMARY KEY,
        symbol TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        symbol_type TEXT NOT NULL,
        broker TEXT,
        min_price DOUBLE PRECISION,
        max_price DOUBLE PRECISION,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TEXT,
        updated_at TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS bot_strategies (
        strategy_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        bot_id TEXT,
        strategy_name TEXT NOT NULL,
        description TEXT,
        strategy_type TEXT,
        parameters TEXT,
        symbols TEXT,
        risk_level TEXT,
        profit_target DOUBLE PRECISION,
        stop_loss DOUBLE PRECISION,
        is_active BOOLEAN DEFAULT TRUE,
        performance_stats TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_accounts (
        account_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        account_type TEXT,
        broker TEXT,
        account_number TEXT,
        account_balance DOUBLE PRECISION DEFAULT 0,
        available_balance DOUBLE PRECISION DEFAULT 0,
        total_profit DOUBLE PRECISION DEFAULT 0,
        is_primary BOOLEAN DEFAULT FALSE,
        is_verified BOOLEAN DEFAULT FALSE,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS user_trading_settings (
        setting_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        risk_profile TEXT,
        daily_loss_limit DOUBLE PRECISION,
        max_position_size DOUBLE PRECISION,
        leverage BIGINT DEFAULT 1,
        auto_trade_enabled BOOLEAN DEFAULT FALSE,
        notifications_enabled BOOLEAN DEFAULT TRUE,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS trades (
        trade_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        order_type TEXT NOT NULL,
        volume DOUBLE PRECISION DEFAULT 0,
        price DOUBLE PRECISION DEFAULT 0,
        profit DOUBLE PRECISION DEFAULT 0,
        commission DOUBLE PRECISION DEFAULT 0,
        swap DOUBLE PRECISION DEFAULT 0,
        ticket BIGINT,
        time_open TEXT,
        time_close TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT,
        updated_at TEXT,
        trade_data TEXT,
        timestamp BIGINT,
        FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS pause_events (
        pause_id TEXT PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        pause_type TEXT NOT NULL,
        retcode BIGINT,
        error_message TEXT,
        reason TEXT,
        market_session TEXT,
        duration_minutes BIGINT,
        pause_start TEXT,
        pause_end TEXT,
        detected_at TEXT,
        created_at TEXT,
        FOREIGN KEY (bot_id) REFERENCES user_bots(bot_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS pxbt_orders (
        order_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL,
        order_type TEXT NOT NULL,
        limit_price DOUBLE PRECISION,
        stop_price DOUBLE PRECISION,
        tp_price DOUBLE PRECISION,
        sl_price DOUBLE PRECISION,
        trailing BOOLEAN DEFAULT FALSE,
        trailing_pips BIGINT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS binance_orders (
        order_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        quantity DOUBLE PRECISION NOT NULL,
        order_type TEXT NOT NULL,
        limit_price DOUBLE PRECISION,
        stop_price DOUBLE PRECISION,
        tp_price DOUBLE PRECISION,
        sl_price DOUBLE PRECISION,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS worker_pool (
        worker_id BIGINT PRIMARY KEY,
        pid BIGINT,
        status TEXT DEFAULT 'stopped',
        account_group TEXT,
        mt5_path TEXT,
        heartbeat_at TEXT,
        started_at TEXT,
        stopped_at TEXT,
        bot_count BIGINT DEFAULT 0,
        error_message TEXT
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS worker_bot_queue (
        id BIGSERIAL PRIMARY KEY,
        bot_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        worker_id BIGINT,
        command TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        bot_config TEXT,
        credentials TEXT,
        created_at TEXT,
        processed_at TEXT,
        FOREIGN KEY (worker_id) REFERENCES worker_pool(worker_id)
    )
    ''',
    '''
    CREATE TABLE IF NOT EXISTS worker_bot_assignments (
        bot_id TEXT PRIMARY KEY,
        worker_id BIGINT NOT NULL,
        account_number TEXT,
        broker_name TEXT,
        assigned_at TEXT,
        FOREIGN KEY (worker_id) REFERENCES worker_pool(worker_id)
    )
    ''',
]


def create_postgres_schema(sql_statements: Iterable[str] = POSTGRES_SCHEMA_SQL, database_url: Optional[str] = None) -> None:
    engine = get_sqlalchemy_engine(database_url)
    if engine is None:
        raise RuntimeError('DATABASE_URL is not configured or SQLAlchemy could not create a PostgreSQL engine.')

    with engine.begin() as connection:
        for statement in sql_statements:
            connection.exec_driver_sql(statement)


if __name__ == '__main__':
    create_postgres_schema()
    print('PostgreSQL schema created successfully.')