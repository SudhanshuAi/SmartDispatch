# SmartDispatch — Deploy / go live

The assignment expects a **working Guest app + Admin Portal + backend matching system**.  
It does **not** name a cloud vendor.

| Piece | Host | Notes |
| --- | --- | --- |
| API + matching | Railway **or** Render | Monorepo: Root Directory must be `backend` |
| Postgres | Railway DB / Neon / Render | |
| Redis | Railway Redis / Upstash / Render Key Value | |
| Admin Portal | Vercel | Root = `admin-portal` |
| Guest app | Vercel (Expo web) | Root = `guest-app` |

---

## 0. Before you deploy

1. Code on GitHub: `https://github.com/SudhanshuAi/SmartDispatch`
2. Local stack works
3. Accounts: Railway (or Render) + Vercel
4. Planned URLs for API / Admin / Guest

**Commit first** (so Railway sees `backend/Dockerfile` + `backend/railway.toml`):

```powershell
git add backend/Dockerfile backend/railway.toml DEPLOY.md
git commit -m "Fix Railway monorepo build: backend Dockerfile and config"
git push origin main
```

---

## 1. Deploy backend on Railway (fix the build error)

### Why your build failed

Railpack scanned the **repo root** and saw `admin-portal/`, `backend/`, `guest-app/` — not a single Python app.  
You must set **Root Directory = `backend`** (or Railway will keep failing the same way).

There is **no “plugin” menu** on newer Railway. Databases are separate services via **+ New**.

### 1.1 Create project the right way

1. [railway.app](https://railway.app) → **New Project** → **Empty Project** (or open your existing one).
2. Click **+ Create** / **+ New** → **GitHub Repo** → `SmartDispatch`.
3. **Immediately** open that service → **Settings**:
   - **Source → Root Directory** → set to `backend` (type `backend`, save)
   - **Build → Builder** → **Dockerfile** (uses `backend/Dockerfile`)
   - Optional **Custom Start Command**:
     ```bash
     sh -c "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
     ```
4. **Redeploy** (Deployments → ⋮ → Redeploy, or push a new commit).

If Root Directory was empty when the first deploy ran, that failed deploy is expected — fix Root Directory, then redeploy.

### 1.2 Where is “build settings”?

Open the **API service card** (not the project canvas alone):

| UI path | What to set |
| --- | --- |
| Service → **Settings** → **Source** | Root Directory = `backend` |
| Service → **Settings** → **Build** | Dockerfile / Railpack |
| Service → **Settings** → **Deploy** | Start command, healthcheck `/health` |
| Service → **Variables** | Env vars (below) |
| Service → **Settings** → **Networking** | Generate domain |

### 1.3 Add Postgres + Redis (not plugins)

1. In the same project: **+ Create** → **Database** → **PostgreSQL**.
2. **+ Create** → **Database** → **Redis** (or Key Value / Redis).
3. Open your **API** service → **Variables** → **Add variable** / **Reference**:
   - Prefer Railway’s variable reference UI: connect `DATABASE_URL` / `REDIS_URL` from the DB services.
4. Convert Postgres URL scheme if needed:
   - Railway may give `postgres://...` or `postgresql://...`
   - App needs: `postgresql+psycopg://...`
   - Example: replace the prefix only:
     ```text
     postgresql+psycopg://user:pass@host:port/railway
     ```

Also set:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `MATCHING_ENGINE_ENABLED` | `true` |
| `CORS_ORIGINS` | Admin + Guest HTTPS origins (after frontends deploy) |

### 1.4 Migrate + seed

After a successful deploy, open the API service → **Shell** (or one-off command):

```bash
alembic upgrade head
python -m scripts.seed
```

### 1.5 Verify

- `https://YOUR-API.up.railway.app/health` → `{"status":"ok"}`
- `https://YOUR-API.up.railway.app/docs`

### 1.6 Still failing?

| Symptom | Fix |
| --- | --- |
| “Railpack could not determine how to build” + lists `admin-portal/`, `backend/` | Root Directory is still empty → set `backend`, redeploy |
| No Dockerfile option | Confirm `backend/Dockerfile` is on `main` on GitHub |
| Build OK, app crashes | Check Variables: `DATABASE_URL` / `REDIS_URL`; check Deploy logs |
| Trial / $5 credit | Use §1b Render stack below instead |

---

## 1b. Alternative backend: Render + Neon + Upstash ($0 demo)

If Railway trial is a problem:

1. **Neon** → create Postgres → copy connection string → use `postgresql+psycopg://...`
2. **Upstash** → create Redis → copy Redis URL
3. **Render** → New **Web Service** → connect GitHub → **Root Directory** = `backend` → Dockerfile → free instance
4. Env: `DATABASE_URL`, `REDIS_URL`, `APP_ENV`, `MATCHING_ENGINE_ENABLED`, `CORS_ORIGINS`
5. After deploy: Shell → `alembic upgrade head` && `python -m scripts.seed`

Cold start on free Render is normal after idle.

---

## 2. Deploy Admin Portal (Vercel)

1. [vercel.com](https://vercel.com) → import `SmartDispatch`.
2. Settings:

| Setting | Value |
| --- | --- |
| Root Directory | `admin-portal` |
| Framework | Vite |
| Build | `npm run build` |
| Output | `dist` |

Include `admin-portal/vercel.json` (SPA rewrite) so routes like `/login` don’t 404 on refresh.

3. Env: `VITE_API_BASE` = `https://YOUR-API` (no trailing slash).  
   Rebuild after setting it — Vite bakes this in at build time.
4. Deploy → add Admin URL to API `CORS_ORIGINS` → redeploy API.
5. Login: `admin@smartdispatch.local` (Ops Admin) / driver: `driver01@…` (**Ravi Menon**).

---

## 3. Deploy Guest app (Expo web on Vercel)

```powershell
cd guest-app
npm install
$env:EXPO_PUBLIC_API_BASE="https://YOUR-API"
npx expo export --platform web
```

Or Vercel project: Root `guest-app`, build `npx expo export --platform web`, output `dist`, env `EXPO_PUBLIC_API_BASE`.

Add Guest URL to `CORS_ORIGINS`. Login: `guest001@smartdispatch.local` (**Priya Kapoor**).

Phone: same `EXPO_PUBLIC_API_BASE` + `npx expo start` → Expo Go.

---

## 4. CORS (required)

```text
CORS_ORIGINS=https://YOUR-ADMIN.vercel.app,https://YOUR-GUEST.vercel.app
```

Redeploy API after setting this.

---

## 5. Post-deploy demo script

1. Guest → request ride → pending  
2. Admin → approve → matching assigns driver  
3. Guest → driver + ETA  
4. Driver portal → accept / status / location  

Share: Admin URL, Guest URL, API `/docs`, seed emails, GitHub docs.

---

## 6. Alternative: single VPS + Docker Compose

One Hetzner / DigitalOcean / Oracle Always Free VM:

```text
Internet → Caddy/nginx (TLS)
            ├─ Admin static
            ├─ Guest web static
            └─ /api → uvicorn
         Postgres + Redis (compose)
```

Set `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS` to your HTTPS origins.

---

## 7. Production notes

| Topic | Demo tip |
| --- | --- |
| Auth | Header stub after email login — OK for assessment |
| Maps | Haversine/cache — enough for demo |
| Secrets | Env only — never commit `.env` |
| Matching kill-switch | `MATCHING_ENGINE_ENABLED=false` |

---

## Quick fix for your current Railway error

1. Push latest `backend/Dockerfile` + `backend/railway.toml` to GitHub.  
2. API service → **Settings → Source → Root Directory** = `backend`.  
3. Builder = **Dockerfile**.  
4. Redeploy.  
5. Add Postgres/Redis via **+ Create → Database** (not plugins).  
6. Set Variables, migrate, seed.

When `/health` works and Admin/Guest point at that API with CORS set, SmartDispatch is live for the assignment.
