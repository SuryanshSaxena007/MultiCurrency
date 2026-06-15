# Multi-Currency Wallet Platform

Production-minded wallet challenge implementation with FastAPI, SQLAlchemy, React and Docker Compose.

## Live deployment

- Web: https://multi-currency-psi.vercel.app
- API: https://multicurrency-production.up.railway.app
- API docs: https://multicurrency-production.up.railway.app/docs
- Health: https://multicurrency-production.up.railway.app/health

Backend runs on Railway with a persistent volume backing SQLite; frontend is built and served by Vercel pointing at the Railway API via `VITE_API_URL`.

## Features

- Signup, login and JWT-protected profile management.
- Editable display name, photo URL and default currency.
- Wallet credit/debit with currency conversion and idempotency keys.
- User-to-user transfers across currencies in a single database transaction.
- Exchange-rate provider integration with background refresh and conversion traceability.
- Transaction history with filters and pagination.
- Health, readiness, structured logs and Prometheus-style status counters.
- Backend integration tests and frontend production build.

## Setup

Requirements:

- Python 3.12
- Node 20+
- Docker and Docker Compose

Backend local setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
WALLET_JWT_SECRET=local-development-secret uvicorn app.main:app --app-dir backend --reload
```

Frontend local setup:

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

## Run with Docker Compose

```bash
docker compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Web: http://localhost:5173
- Metrics: http://localhost:8000/metrics

## Tests

```bash
pip install -r backend/requirements.txt
pytest
cd frontend && npm install && npm run build
```

## Deployment

The repo includes:

- `.github/workflows/ci.yml` for test/build/compose validation.
- `railway.json` for Railway API deployment.
- `vercel.json` (repo root) for the Vercel monorepo build that targets `frontend/`.
- Dockerfiles for API and web artifacts.

Public deployment URL: not provisioned from this local environment because publishing requires account credentials. Use this split deployment path:

**Backend on Railway (SQLite on a persistent volume):**

1. Push the repository to GitHub.
2. In Railway, create a project from the GitHub repo. It auto-detects `railway.json` and builds `backend/Dockerfile`.
3. In the API service → **Settings → Volumes**, add a volume mounted at `/data` (default size is fine).
4. In **Variables**, set:
   - `WALLET_DATABASE_URL` = `sqlite:////data/wallet.db` (four slashes — absolute path)
   - `WALLET_JWT_SECRET` = a long random value (`openssl rand -hex 32`)
   - `WALLET_CORS_ORIGINS` = the Vercel frontend URL (use `*` temporarily before Vercel exists)
5. Railway sets `PORT` automatically; the Dockerfile honours it. The volume keeps `wallet.db` across redeploys.

**Frontend on Vercel:**

6. In Vercel, import the same GitHub repo with root directory `frontend`.
7. Set `VITE_API_URL` to the Railway public URL (for example `https://wallet-api.up.railway.app`).
8. Redeploy after URLs are known and update `WALLET_CORS_ORIGINS` on Railway with the final Vercel URL.

Deployment environment variables:

| Platform | Variable | Required | Notes |
|---|---|---:|---|
| Railway API | `WALLET_DATABASE_URL` | yes | `sqlite:////data/wallet.db` paired with a `/data` volume mount. |
| Railway API | `WALLET_JWT_SECRET` | yes | Long random string; never commit a real value. |
| Railway API | `WALLET_CORS_ORIGINS` | yes | Must include the Vercel frontend URL. |
| Railway API | `WALLET_ENABLE_EXTERNAL_RATES` | no | Defaults to enabled; keep enabled for provider refresh. |
| Vercel web | `VITE_API_URL` | yes | Must be set at build time to the Railway API URL. |

## Assumptions

- Currencies supported in the MVP: USD, EUR, GBP, INR, AUD, CAD, JPY.
- Photo support is represented by a profile `photo_url`; binary uploads would normally go to object storage.
- Money is rounded to 2 decimal places and exchange rates to 8 decimal places.
- SQLite is the default local database for low-friction review; Docker Compose uses PostgreSQL.

## Trade-offs

- Tables are created on startup for challenge simplicity. Production would use Alembic migrations.
- Exchange rates seed from deterministic fallback values, then refresh from Frankfurter when enabled.
- Transfers use row locks where the database supports them. PostgreSQL honours these locks; SQLite is only for local tests.
- Passwords use PBKDF2-HMAC-SHA256 to avoid native hashing dependencies in a portable challenge repo.

## Known limitations

- No binary photo upload or object-storage lifecycle.
- No full fraud/risk engine.
- No multi-region deployment automation.
- No websocket/live updates.
