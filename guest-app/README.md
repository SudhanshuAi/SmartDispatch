# SmartDispatch Guest App

Expo (React Native) client for **guests only** — separate from the Admin Portal.

Full stack setup lives in the repo root [`README.md`](../README.md).

## Run

Prerequisites: backend API on `http://127.0.0.1:8000` (migrated + seeded).

```bash
cd guest-app
npm install
copy .env.example .env    # optional
npx expo start --web
```

Login: `guest001@smartdispatch.local`

## Features

- Pickup details (travel ETA, pickup point, accommodation)
- Passive match view (driver name, plate, ETA) — no browsing/choosing drivers
- Live tracking (map on native; ETA/coords fallback on web)
- On-demand ride request → pending until admin approves

## Env

| Variable | Default |
| --- | --- |
| `EXPO_PUBLIC_API_BASE` | `http://127.0.0.1:8000` |

On a physical device, set this to your PC LAN IP (e.g. `http://192.168.1.3:8000`).