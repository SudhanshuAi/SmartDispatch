# SmartDispatch Admin Portal

React + TypeScript + Vite app for **Admin/Operations** and **Driver** roles (one codebase, role-gated shells).

Full stack setup lives in the repo root [`README.md`](../README.md).

## Run

Prerequisites: backend API on `http://127.0.0.1:8000` (see root README).

```bash
cd admin-portal
npm install
copy .env.example .env    # optional
npm run dev
```

Open http://localhost:5173

| Email | Role |
| --- | --- |
| `admin@smartdispatch.local` | Dashboard, fleet map, ride requests, onboarding, overrides |
| `driver01@smartdispatch.local` | Own trip only — accept/reject, status, live GPS, break |

Guest emails are rejected here; use the Guest app.

## Env

| Variable | Default |
| --- | --- |
| `VITE_API_BASE` | `http://127.0.0.1:8000` |

## Scripts

```bash
npm run dev      # Vite dev server
npm run build    # production build
```