# Binance 10,000 User Roadmap

This document maps the current Zwesta backend to a production design that can support very large Binance growth safely.

It distinguishes three different numbers because they are not the same problem:

1. Registered users
2. Connected Binance accounts
3. Concurrently active trading bots

You can store 10,000 users and 10,000 Binance credential records much earlier than you can run 10,000 active bots.

## Current Reality

The current backend can support Binance at moderate scale, but it is not a 10,000-active-user architecture yet.

Current bottlenecks in the codebase:

1. Global active-bot cap is enforced by `MAX_CONCURRENT_ACTIVE_BOTS` in `multi_broker_backend_updated.py`.
2. Active bots still run in background threads inside the web process.
3. SQLite is still the primary system database.
4. The Flask app and trading runtime are still tightly coupled in one process tree.
5. Some legacy Binance routes are still exposed through `binance_service.py`, which is better suited for admin or legacy access than mass multi-tenant trading.

## Capacity Targets

Use these as realistic milestones.

### Phase 0: Current System

Safe for:

1. 1000-10000 registered users
2. 100-1000 connected Binance credentials stored in the database
3. Low double-digit active bots, depending on VPS size and strategy frequency

Not safe for:

1. 1000+ simultaneously active Binance bots
2. High-frequency polling from thousands of users in one Flask process
3. SQLite-heavy concurrent writes under sustained bot load

### Phase 1: 200-500 Active Binance Bots

Target:

1. 10,000 registered users
2. 2,000 connected Binance accounts
3. 200-500 active Binance bots

Required changes:

1. Move bot execution out of the web process
2. Replace SQLite with PostgreSQL
3. Add Redis for queues, locks, caching, and rate limiting
4. Split REST API from trading worker execution
5. Add centralized metrics and structured logging

### Phase 2: 1,000-2,000 Active Binance Bots

Target:

1. 25,000+ registered users
2. 5,000 connected Binance accounts
3. 1,000-2,000 active bots

Required changes:

1. Queue-based bot scheduling
2. Horizontally scalable worker fleet
3. Per-user and per-IP rate limiting
4. Broker-aware throttling for Binance endpoints
5. Dedicated market-data fanout service

### Phase 3: 10,000 Users With Large Active Trading Population

Target:

1. 10,000+ registered users
2. 10,000 connected Binance accounts
3. Hundreds to a few thousand active bots, depending on strategy frequency and polling model

Important:

10,000 users does not mean 10,000 active bots at the same instant. A strong design can support 10,000 users while only a smaller percentage are actively trading at a given moment.

## Required Architecture Changes

### 1. Separate Web API From Bot Execution

Current state:

1. The Flask app starts background bot threads directly.
2. Bot lifecycle is still controlled inside the app process.

Target state:

1. API service only handles auth, broker linking, bot CRUD, dashboards, and command submission.
2. Worker service consumes bot start and stop jobs from a queue.
3. Scheduler service coordinates recurring bot cycles.

Recommended components:

1. `api-service`
2. `bot-scheduler`
3. `binance-worker`
4. `market-data-service`
5. `notification-service`

### 2. Replace SQLite With PostgreSQL

Current state:

1. SQLite is hardcoded in many places.
2. This will become the first major stability limit under concurrent writes.

Target state:

1. PostgreSQL for users, sessions, broker credentials, bots, bot assignments, trades, balances, and audit logs.
2. SQLAlchemy or another central data access layer to remove scattered direct `sqlite3.connect` calls.

Tables that should move first:

1. `users`
2. `user_sessions`
3. `broker_credentials`
4. `user_bots`
5. `bot_credentials`
6. `trades`
7. `worker_*` tables

### 3. Add Redis

Redis should be used for:

1. Session cache
2. Bot command queue
3. Distributed locks
4. Binance rate-limit tokens
5. Balance and market-data cache
6. Worker heartbeats

Without Redis or an equivalent queue/cache layer, scaling active Binance bots becomes operationally fragile.

### 4. Introduce A Queue-Based Trading Model

Current state:

1. One bot roughly maps to one in-process thread.

Target state:

1. One bot is a logical record in the database.
2. The scheduler places due work onto a queue.
3. Workers process queue messages and emit results.
4. State transitions are persisted independently of the web server.

Recommended queue options:

1. Redis Streams
2. RabbitMQ
3. Azure Service Bus if you want cloud-managed messaging

### 5. Broker-Aware Binance Limits

For Binance scale, you must assume:

1. Different endpoints have different request weights.
2. Bursts across many users can trigger bans if not coordinated.
3. You need key-level and IP-level throttling.

Required controls:

1. Shared rate-limit registry in Redis
2. Per-account cool-down windows
3. Adaptive backoff on `429` and exchange throttle responses
4. Market-data caching so bots do not individually pull the same symbols repeatedly

### 6. Market Data Fanout

Do not let every bot independently fetch the same ticker and candle data.

Target model:

1. A market-data service maintains a small set of Binance streams for tracked symbols.
2. Workers read cached latest prices and candles.
3. Bot decisions are computed from shared data snapshots.

This is one of the biggest cost and scale improvements for crypto workloads.

### 7. Multi-Tenant Security

For 10,000 users, client isolation must be explicit.

Required controls:

1. One Binance API key per client account
2. No shared master trading key for clients
3. Encrypted credential storage at rest
4. Audit trail for credential creation, rotation, and bot actions
5. IP-restricted Binance keys where possible
6. Key-rotation flows in the UI and backend

### 8. Frontend Changes For Scale

The frontend is already moving toward per-client Binance credentials, but the large-scale product should also include:

1. Bulk onboarding for staff or agents
2. Clear client-owned API key UX
3. Credential health status
4. Rate-limit and exchange-error messaging
5. Bot queue status rather than assuming immediate thread startup

## Recommended Technical Stack For 10,000 Users

### Minimum serious production stack

1. Python API service behind Nginx
2. PostgreSQL
3. Redis
4. Separate worker deployment
5. Background scheduler
6. Prometheus and Grafana or an equivalent monitoring stack
7. Sentry or centralized error tracking

### Better long-run option

1. FastAPI for API layer
2. PostgreSQL
3. Redis
4. Celery, Dramatiq, RQ, or a custom Redis Streams worker system
5. WebSocket or SSE market-data gateway
6. Kubernetes or container-based deployment for worker scaling

## Proposed Migration Plan

### Step 1: Stabilize Current Multi-Tenant Model

Do now:

1. Keep per-user Binance credentials only
2. Remove any reliance on shared Binance `.env` trading keys
3. Keep withdrawals disabled by default
4. Add CSV-based onboarding for Binance users

Status:

1. Per-user onboarding helper exists
2. Bulk CSV onboarding now exists

### Step 2: Database Migration

Build next:

1. Introduce a repository or ORM layer
2. Port SQLite tables to PostgreSQL
3. Stop opening raw SQLite connections throughout the codebase

### Step 3: Extract Bot Runtime

Build next:

1. A queue-backed Binance worker service
2. A scheduler loop that creates jobs instead of threads
3. A bot-state machine in the database

### Step 4: Add Shared Market Data

Build next:

1. Shared ticker and candle collectors
2. Redis-backed data snapshots
3. Reduced duplicate Binance calls

### Step 5: Scale Horizontally

Build next:

1. Multiple API instances
2. Multiple worker instances
3. Independent autoscaling by queue depth and latency

## Practical Numbers

If you stay on the current design:

1. 10,000 registered users is possible as stored accounts
2. 10,000 connected Binance credentials is possible as stored records with proper database migration
3. 10,000 simultaneously active Binance bots is not realistic on one Flask plus SQLite plus thread-based backend

If you complete the redesign:

1. 10,000 registered users is realistic
2. 10,000 connected Binance accounts is realistic
3. Active trading scale depends on bot frequency, symbol count, and market-data design, but hundreds to low thousands becomes feasible

## Immediate Recommendation

Short term:

1. Use the new per-user Binance onboarding path
2. Keep Binance keys client-owned
3. Do not put shared client trading keys in `.env`
4. Treat the current backend as a foundation, not the final 10,000-user engine

Next engineering phase:

1. PostgreSQL migration
2. Redis queue and cache layer
3. Extract Binance workers out of the Flask process
4. Shared market-data service

## Suggested Next Deliverables

If you want to continue implementation, the best next sequence is:

1. Database migration plan: SQLite to PostgreSQL
2. Worker extraction plan for Binance bots
3. Redis queue and rate-limit design
4. API and worker service boundaries
5. Infrastructure deployment plan for 500, 2000, and 10000 users