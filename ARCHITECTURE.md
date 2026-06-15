# Architecture

## System shape

The platform is split into a FastAPI API, a React/Vite web UI and PostgreSQL. The API owns authentication, wallet balances, exchange snapshots and transaction history. The frontend calls the API directly with a bearer token.

Deployment is intended as a split platform: the API and PostgreSQL run on Render, while the static React/Vite frontend runs on Vercel with `VITE_API_URL` pointing at the Render API.

## Domain model

- `User`: authentication identity and editable profile preferences.
- `Wallet`: one balance per user/currency with a version counter.
- `ExchangeRate`: append-only snapshots keyed by provider, base currency, target currency and fetch time.
- `Transaction`: immutable ledger-style records for credits, debits, transfer outs and transfer ins.

Balances are operational read models backed by transaction records. Each money-moving operation writes both the balance update and transaction record in one database transaction.

## API design

- `POST /auth/signup`
- `POST /auth/login`
- `GET/PATCH /profile`
- `GET /wallets`
- `POST /wallets/credit`
- `POST /wallets/debit`
- `POST /transfers`
- `GET /transactions`
- `GET /exchange/rates`
- `POST /exchange/refresh`
- `GET /exchange/quote`
- `GET /health`, `GET /ready`, `GET /metrics`

## Consistency controls

Credit, debit and transfer operations run through one SQLAlchemy session and commit once. PostgreSQL row locks protect wallet rows during balance changes. Optional idempotency keys prevent accidental double submission for client retries.

For transfers, the sender transaction and recipient transaction are linked through `related_transaction_id`. The sender balance is checked before mutation, and both wallets are updated before commit.

## Exchange traceability

Every transaction stores:

- input amount/currency
- wallet currency and signed wallet amount
- exchange rate value
- provider name
- provider fetch timestamp
- exchange-rate snapshot id when present

If the third-party provider is unavailable, existing snapshots remain usable and seeded fallback rates keep local development functional.

## Security and validation

- JWT bearer authentication.
- PBKDF2 password hashing with per-password salt.
- Pydantic request validation for email, amount, currency and string lengths.
- CORS allow-list from configuration.
- Ownership enforced by authenticated user dependencies.
- Secrets configured through environment variables.

## Error handling and reliability

- 400 for invalid transfer targets such as self-transfer.
- 401 for invalid credentials.
- 404 for missing recipients.
- 409 for duplicate signup or insufficient balance.
- 503 for exchange-provider refresh failure.
- Structured request logs include latency and status code.

## Scale exercise

Assumptions: 500k registered users, 20k DAU, 100 TPS and exchange-provider downtime.

### Scaling approach

Run the API as stateless containers behind a load balancer. Scale horizontally on CPU, latency and queue depth. Keep JWT validation local and avoid sticky sessions. Serve the frontend through CDN-backed static hosting.

### Database strategy

Use managed PostgreSQL with automated backups, PITR and read replicas. Keep wallet mutations on the primary database. Add indexes for `users.email`, `(wallets.user_id, currency)` and `(transactions.user_id, created_at)`. For higher write volumes, partition transactions by month and archive cold partitions.

### Caching

Cache latest exchange rates in Redis with a TTL slightly longer than the refresh cadence. Cache profile reads conservatively, invalidating on profile update. Do not cache wallet balances for writes; use the database as the source of truth.

### Async processing

Move exchange refresh, alert fan-out, notification emails and heavy analytics to background workers. Money movement remains synchronous so the client receives a definitive posted/rejected result.

### Exchange provider downtime

Keep the latest good snapshot and expose rate age. Stop refresh retries from overwhelming the provider with exponential backoff and circuit breaking. Alert when rates exceed the freshness SLA.

### Cost optimisation

Use autoscaling with minimum container counts outside peak hours, managed Postgres right-sizing, CDN static hosting and log retention policies. Keep Redis optional until rate-cache load justifies it.

### Operational considerations

Track 4XX/5XX rates, p95 latency, exchange-rate age, failed transfers and database saturation. Use deploy health checks and rollback on readiness failures.
