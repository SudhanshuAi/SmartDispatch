# SmartDispatch

Event-scoped vehicle dispatch: **Guest app** + **Admin Portal** (Admin & Driver roles) + **matching engine**.

| Doc | Purpose |
| --- | --- |
| [`PLAN.md`](PLAN.md) | Architecture & milestones |
| [`DESIGN.md`](DESIGN.md) | Matching approach & trade-offs |

After cloning this repo you can run the **full stack locally** with the steps below.

---

## Prerequisites

| Tool | Notes |
| --- | --- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Postgres + Redis |
| Python **3.12+** | 3.14 OK (`psycopg` v3) |
| Node.js **20+** | Admin Portal + Guest app |

Verify:

```bash
docker --version
python --version
node --version
```

---

## Quick start (full stack)

From the **repo root**:

### 1. Start databases

```bash
docker compose up -d
```

Wait until healthy (Postgres `5432`, Redis `6379`).

### 2. Backend API

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
# Windows:
copy .env.example .env
# macOS/Linux:
# cp .env.example .env

alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --port 8000
```

Leave this terminal running.

- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Seed logins (email-only login in UIs):

| Email | App | Seed name |
| --- | --- | --- |
| `admin@smartdispatch.local` | Admin Portal | Ops Admin |
| `driver01@smartdispatch.local` | Admin Portal (Driver) | Ravi Menon |
| `guest001@smartdispatch.local` | Guest app | Priya Kapoor |

### 3. Admin Portal

New terminal:

```bash
cd admin-portal
npm install
copy .env.example .env    # optional; defaults to http://127.0.0.1:8000
npm run dev
```

Open http://localhost:5173 → sign in as admin or driver.

### 4. Guest app

New terminal:

```bash
cd guest-app
npm install
copy .env.example .env    # optional; defaults to http://127.0.0.1:8000
npx expo start --web
```

Browser opens the guest UI (or press `w`). Sign in as `guest001@smartdispatch.local`.

**Phone (Expo Go):** same Wi-Fi as your PC, set API to your LAN IP:

```powershell
# Windows
$env:EXPO_PUBLIC_API_BASE="http://192.168.x.x:8000"
npx expo start
```

---

## End-to-end demo

1. Guest app → **Request** → submit on-demand ride (pending).
2. Admin Portal → **Ride requests** → **Approve** (matching assigns a driver).
3. Guest app → **Ride** → driver name / plate / ETA + map.
4. Driver portal (`driver01@…`) → accept → status updates → live location while on trip.

---

## Tests & peak simulation

```bash
cd backend
.\.venv\Scripts\Activate.ps1   # if not already active
.\.venv\Scripts\python -m pytest tests -v
.\.venv\Scripts\python -m scripts.peak_arrival_sim
```

Expect: **0** capacity violations, `match_one` p95 much less than 500 ms.

---

## Troubleshooting

| Issue | Fix |
| --- | --- |
| GitHub shows empty README | File must be **UTF-8** (not UTF-16). Re-save without BOM. |
| DB connection timeout | `docker compose up -d` and wait for healthchecks |
| Portal/Guest can't reach API | Confirm uvicorn on `:8000`; check `.env` `VITE_API_BASE` / `EXPO_PUBLIC_API_BASE` |
| `pytest` / `uvicorn` not found | Activate `.venv` first |
| Port 5432 busy | Stop local Postgres or change compose port mapping |
| Matching "down" drill | `MATCHING_ENGINE_ENABLED=false` in `backend/.env` — trips + admin overrides still work |

Realtime (optional): with Redis up, driver GPS feeds Redis + WebSockets; push tokens via `POST /guest/push-token` or `/driver/push-token`.

See **DESIGN.md** for algorithm detail and trade-offs.
