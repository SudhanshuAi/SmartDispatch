# SmartDispatch Design Document

Brief design deliverable for the technical assessment: matching approach, key trade-offs, and what we deliberately simplified.

---

## 1. Problem framing

SmartDispatch assigns a **private, event-scoped fleet** to guests moving between airport/station, hotels, and venue. Guests never browse drivers; ops approve ad-hoc requests; drivers only see their own trip. Matching must respect **seats, luggage, deadlines, live traffic ETAs**, and stay responsive at roughly **10–100 drivers / a few hundred guests**.

Automation boundary (locked in `PLAN.md`):

| Automated | Manual |
| --- | --- |
| Driver↔guest allocation (batch, greedy, detour, reopt) | Driver onboarding, guest travel corrections, ride-request approve/decline, emergency override |

---

## 2. Matching architecture

The matching engine is a **pure module** (`backend/app/matching_engine/`) with no HTTP or SQLAlchemy. The API/service layer builds snapshots, calls the engine, then persists with `route_version` optimistic locking.

```
Guest / Ops / Driver API
        │
        ▼
   services/*  (ORM, RBAC, Redis, notify)
        │
        ▼
 matching_engine  (batch | greedy match_one | detour | reopt | priority queue)
        │
        ▼
 CachedTravelProvider  (haversine + OD cache; Maps-ready fetcher hook)
```

### 2.1 Pre-day batch (OR-Tools)

**When:** Guests with known `travel_eta` before the surge window.

**Approach:** Capacity-aware packing into an assignment MIP/heuristic via Google OR-Tools (`batch.py`): minimize guest wait / lateness while respecting vehicle seats/luggage and allowing same-destination sharing. Oversized parties are split (`party_group_id`) or escalated.

**Why batch + solver:** Overnight / known arrivals are a classic assignment problem; a single optimization pass beats greedy churn when the full guest set is known and drivers are mostly idle.

### 2.2 Real-time greedy (`match_one`)

**When:** Admin-approved on-demand requests, post-batch leftovers, driver rejects, queue drains.

**Approach:** Score feasible drivers by wait + travel-to-pickup (VIP slightly preferred), prefer idle/`available`, then try **opportunistic detour** onto `en_route` / `in_trip` vehicles. Target: **p95 ≤ 500 ms** with mocked/cached routing (asserted in tests + peak sim).

**Why greedy here:** New requests arrive one-at-a-time between batches; a full OR-Tools rebuild per request would be latency- and Maps-cost prohibitive. Greedy + detour is “good enough” at this scale and keeps the hot path under half a second.

### 2.3 Priority queue (Redis sorted set)

Unmatched / waiting guests sit in a **Redis ZSET** (in-memory fallback if Redis is down). Score = VIP base (capped) + wait aging + deadline urgency so long-waiters are not starved by a trickle of VIPs.

### 2.4 Detour insertion

**Eligible driver states:** `en_route`, `in_trip` only — **not** `at_pickup` (halt/boarding must not be interrupted).

**Hard rules:**

- Use **live driver position**, not trip origin.
- Added path time ≤ **`MAX_DETOUR_INSERTION_MINUTES = 8`**.
- Existing guests keep deadlines; capacity must fit.
- Persist with `route_version` CAS; conflict → 409, leave request queued.

Detour is engine-only; guests still do not choose drivers.

### 2.5 Live re-optimization

GPS pings do **not** call Maps every tick. Flow:

1. Location → Redis hot key + dirty trip set.
2. Debounced reopt (~45 s, or dirty-count flush).
3. Batch OD pairs through `CachedTravelProvider`.
4. Default action: **refresh ETA** and notify; **rematch** only on deadline risk / severe drift and only if guests are not boarded.

**Why these triggers:** Continuous rematch would thrash assignments and Maps quota. Debounce + drift threshold keeps maps usage bounded while still correcting traffic-driven ETA error.

### 2.6 Capacity / split / escalation

1. Fit one vehicle → assign / share.
2. Party larger than any vehicle → **split-and-coordinate** linked trips.
3. Still insufficient fleet in window → `needs_escalation` for admin override (peak sim shows these as the only unmatched bucket at healthy fleet size).

---

## 3. Key trade-offs

| Decision | Chose | Rejected / deferred | Why |
| --- | --- | --- | --- |
| Batch vs realtime | OR-Tools batch + greedy `match_one` | Full solver on every request | Latency & cost at event scale |
| Queue store | Redis ZSET sole queue (memory fallback) | Postgres queue table | PLAN lock; aging scores need cheap re-rank |
| Detour budget | Hard 8 minutes | Soft / ML scoring | Predictable ops constraint, easy to test |
| Detour eligibility | Exclude `at_pickup` | Allow any active status | Protect boarding halt time |
| Reopt | ETA refresh first | Rematch on every drift | Stability for boarded guests; fewer Maps calls |
| Routing | Cached haversine (+ optional fetcher) | Live Google on every OD | Demo reliability; cache hits dominate peak sim |
| Break | Fixed **10 min** after drop | Flexible labor rules | Spec constant; keeps free-time predictable |
| Auth | Header stub (`X-Role` + scoped ids) | Full JWT in-scope | Enough to prove RBAC; swap later |
| Admin+Driver | One React portal, role shells | Separate driver app | Assignment guidance |
| Guest | Separate Expo app | Embedded in portal | Guest-only binary |

---

## 4. Role separation

**Authoritative gate is the API**, not the UI.

| Surface | Guard |
| --- | --- |
| `/admin/**` | `require_admin` — **explicit** `X-Role: admin` (no default-role bypass) |
| `/driver/**` | `require_driver` + `X-Driver-Id`; all queries scoped to that driver |
| `/guest/**` | `require_guest` + `X-Guest-Id`; own record / own trip only |
| WebSocket `/ws` | Channel list derived from role + subject id (no cross-role admin ops for drivers/guests) |

Portal defense-in-depth: AdminShell vs DriverShell routing; Guest app is a separate codebase. Integration tests assert driver/guest tokens get **403** on admin endpoints even by direct HTTP.

---

## 5. Reliability & graceful degradation

| Failure | Behavior |
| --- | --- |
| Matching engine exception / disabled | `match_one` / batch return **503**; **in-progress trips untouched**; location, status updates, guest match poll, admin dashboard keep working |
| Redis down | In-memory queue + skip hot location/push log; API still serves Postgres |
| Maps / travel fetcher down | Haversine estimates + cache |
| Admin override | Pure DB (`reassign`, `force-match`, `vehicle-down`) — **does not require** the matching engine |

Approved ride requests that cannot match are **queued** for later rematch rather than failing the approve action.

---

## 6. Simplifications (out of scope / demo)

- **No payments**, public marketplace, or multi-tenant events.
- **Auth stub** instead of production JWT/OIDC (headers mirror future claims).
- **Travel times** mocked/cached rather than mandatory live Google Distance Matrix (hook present).
- **Push:** Expo HTTP + Redis log; full background push UX is optional for demo.
- **Web map** in Guest app falls back to coordinates (`react-native-maps` is native-only).
- Single-event seed (~25 drivers / ~150 guests); peak script scales to 100×250 without DB.

---

## 7. Evidence of responsiveness

`python -m scripts.peak_arrival_sim` (default 100 drivers / 250 guests / 25 min peak):

- Capacity violations: **0**
- Starved (`no_feasible_driver`): **0** at default scale (residual unmatched = `needs_escalation` oversized parties)
- `match_one` p95: **≪ 500 ms** with cached routing

---

## 8. How to read the code

| Concern | Location |
| --- | --- |
| Batch / greedy / detour / reopt / queue | `backend/app/matching_engine/` |
| Persist + notify | `backend/app/services/matching_service.py`, `realtime/` |
| Ops / override | `backend/app/services/ops_service.py` |
| Driver / guest scoped APIs | `api/routes/driver.py`, `guest.py` |
| Peak metrics | `backend/scripts/peak_arrival_sim.py` |
| Locked plan | `PLAN.md` |

---

*Design deliverable: matching approach, trade-offs, RBAC, and degradation notes for SmartDispatch.*
