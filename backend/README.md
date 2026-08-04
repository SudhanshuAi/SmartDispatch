# SmartDispatch Backend

FastAPI API + matching engine + Postgres/Redis.

Full stack setup: root [`README.md`](../README.md). Deploy: [`DEPLOY.md`](../DEPLOY.md).

## Run

```bash
# From repo root first:
docker compose up -d

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate           # macOS/Linux

pip install -r requirements.txt
copy .env.example .env                # or: cp .env.example .env
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --port 8000
```

- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Tests & peak sim

```bash
.\.venv\Scripts\python -m pytest tests -v
.\.venv\Scripts\python -m scripts.peak_arrival_sim
```

## Env (`backend/.env.example`)

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Postgres (`postgresql+psycopg://…`) |
| `REDIS_URL` | Redis (queue + realtime) |
| `CORS_ORIGINS` | Comma-separated Admin/Guest origins |
| `MATCHING_ENGINE_ENABLED` | `false` = engine down drill; trips/overrides still work |

Auth stub: `X-Role: admin|driver|guest` plus `X-Driver-Id` / `X-Guest-Id`. Portal login: `POST /auth/login`.
