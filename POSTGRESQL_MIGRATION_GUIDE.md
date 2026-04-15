# PostgreSQL Migration Guide

This guide covers the first PostgreSQL implementation slice for the current Zwesta backend.

## If You Only Have SQLite Configured

That is fine for the current production backend.

Use this configuration and leave PostgreSQL disabled:

```env
DATABASE_BACKEND=sqlite
DATABASE_PATH=C:\backend\zwesta_trading.db
DATABASE_URL=
REDIS_URL=
```

In that mode:

1. the backend keeps reading and writing SQLite
2. the PostgreSQL files are inactive until you set `DATABASE_URL`
3. the new runtime endpoint still helps verify what database mode the VPS is using

## What Is Implemented

1. Runtime configuration support for `DATABASE_BACKEND`, `DATABASE_PATH`, `DATABASE_URL`, and `REDIS_URL`
2. PostgreSQL schema bootstrap via `postgres_schema.py`
3. SQLite-to-PostgreSQL data migration via `migrate_sqlite_to_postgres.py`
4. Admin verification endpoint: `/api/admin/runtime-infrastructure`

## Important Limitation

The backend is not fully PostgreSQL-native yet.

Many runtime queries still assume SQLite semantics in parts of the codebase. This slice gives you:

1. a real PostgreSQL schema
2. a real data migration path
3. env-driven runtime configuration

It does not yet mean you should switch production writes to PostgreSQL without completing the remaining query refactors.

## Local Preparation

Set your local `.env` or terminal variables:

```env
DATABASE_BACKEND=sqlite
DATABASE_PATH=C:\zwesta-trader\Zwesta Flutter App\zwesta_trading.db
DATABASE_URL=postgresql://zwesta:strongpassword@127.0.0.1:5432/zwesta_trading
REDIS_URL=redis://127.0.0.1:6379/0
```

## Create PostgreSQL Schema

```powershell
python .\postgres_schema.py
```

## Migrate SQLite Data To PostgreSQL

```powershell
python .\migrate_sqlite_to_postgres.py --truncate-existing
```

Optional: migrate a subset first.

```powershell
python .\migrate_sqlite_to_postgres.py --truncate-existing --tables users user_sessions broker_credentials user_bots bot_credentials trades
```

## Verify Runtime Configuration

After deploying the updated backend, call:

```http
GET /api/admin/runtime-infrastructure
Authorization: Bearer <API_KEY>
```

This confirms:

1. database backend mode
2. database path
3. whether `DATABASE_URL` is configured
4. whether Redis is configured

## Recommended Rollout Order

1. Stand up PostgreSQL locally
2. Run `postgres_schema.py`
3. Run `migrate_sqlite_to_postgres.py`
4. Validate row counts in key tables
5. Keep production on SQLite for now
6. Refactor remaining SQLite-specific queries
7. Only then switch production to PostgreSQL

## Highest Priority Tables To Validate First

1. `users`
2. `user_sessions`
3. `broker_credentials`
4. `user_bots`
5. `bot_credentials`
6. `trades`

## Next Implementation Slice

After this migration slice, the next engineering step should be:

1. replace SQLite-specific writes in hot paths
2. remove direct `sqlite3.connect(...)` calls from runtime logic
3. introduce a queue-backed Binance worker runtime