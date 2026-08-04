# SmartDispatch Admin Portal

React + TypeScript + Vite app for **Admin/Operations** and **Driver** roles (one codebase, role-gated shells).

Full stack: root [`README.md`](../README.md). Deploy: [`DEPLOY.md`](../DEPLOY.md).

## Run

Prerequisites: backend API on `http://127.0.0.1:8000`.

```bash
cd admin-portal
npm install
copy .env.example .env    # optional
npm run dev
```

Open http://localhost:5173

| Email | Role | Seed name |
| --- | --- | --- |
| `admin@smartdispatch.local` | Dashboard, fleet map, ride requests, onboarding, overrides | Ops Admin |
| `driver01@smartdispatch.local` | Own trip only — accept/reject, status, live GPS, break | **Ravi Menon** (DL-1C-1000) |

Guest emails are rejected here; use the Guest app (`guest001@…` → **Priya Kapoor**).

## Env

| Variable | Default |
| --- | --- |
| `VITE_API_BASE` | `http://127.0.0.1:8000` |

## Scripts

```bash
npm run dev      # Vite dev server
npm run build    # production build
```

Production needs `admin-portal/vercel.json` (SPA rewrite for `/login`).
