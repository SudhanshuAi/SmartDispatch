# SmartDispatch — Implementation Plan

> Status: **Approved** (with decisions below). Awaiting next build prompt — do not start implementation until then.

This plan covers tech stack, data model, architecture, matching engine design, RBAC, and phased milestones for the Smart Cab / Vehicle Dispatch System. Scope is a **single private event**, pre-registered fleet, no payments / marketplace / multi-tenant.

### Approved decisions (locked)

1. **Priority queue:** Redis sorted set is the **sole** real-time match queue — no Postgres `SKIP LOCKED` fallback for now.
2. **`match_one` latency:** p95 **≤ 500 ms** (routing mocked/cached; fixture scale up to ~100 drivers) — asserted in M2 tests.
3. **Detour eligibility:** drivers in `at_pickup` are **excluded**; only `en_route` and `in_trip`.
4. **Concurrency:** `Trip.route_version` is an **optimistic lock** for concurrent admin override / detour / apply writes (`UPDATE … WHERE route_version = ?`; conflict → reload & retry or abort).
5. **Timing constants:** mandatory break = **10 minutes** (fixed); max detour insertion budget = **8 minutes** (added travel vs pre-insert route).

---

## 1. Tech Stack Decision

| Layer | Choice | One-line reason |
| --- | --- | --- |
| **Backend language/framework** | **Python 3.12 + FastAPI** | Fast async HTTP/WebSocket APIs, excellent fit for OR-Tools, and fast to unit-test the matching engine in isolation. |
| **Database (core)** | **PostgreSQL** | Relational model for guests, drivers, vehicles, trips, schedules, and auditable assignment history; strong constraints for capacity and RBAC. |
| **Live location + queueing** | **Redis** | Sub-second driver location pings, pub/sub for real-time fan-out, and the **sole** real-time priority queue (sorted set) for match jobs — no Postgres queue fallback. |
| **Guest app** | **React Native (Expo)** | True mobile-first guest UX (maps, push, background-friendly location display) with one codebase for iOS/Android; Expo speeds maps + push setup for a demo. |
| **Admin Portal** | **Web (React + TypeScript), responsive / PWA-capable** | Admin/ops needs a dense multi-driver map + queues best on a large screen; Driver role uses the same app on a phone via role-gated views — one portal codebase as the assignment prefers. |
| **Real-time transport** | **WebSockets (FastAPI native) + Redis pub/sub** | Direct control over trip/ETA/location events without Firebase lock-in; Socket.io not required if we own both clients; polling only as a degraded fallback. |
| **Maps / routing** | **Google Maps Platform** (Directions + Distance Matrix; Maps SDK in clients) behind a **server-side Routing Service** with cache | Matches the assignment's guidance; server-side batching/caching keeps cost and rate limits under control while clients only render polylines/ETA. |
| **Batch optimizer location** | **Matching Engine worker process** (separate from API), OR-Tools CP-SAT / assignment solver | Heavy pre-day / rebatch work must not block HTTP; Hungarian/OR-Tools belongs in a dedicated module/worker. |
| **Lightweight greedy matcher** | **Same Matching Engine module**, invoked synchronously (or short async job) from the API/worker for one-off / approved on-demand requests | Near-real-time path between batch rounds with **p95 ≤ 500 ms** for `match_one` (see §4.2); still not tangled into route handlers — API enqueues or calls a clean `match_one()` interface. |
| **Auth / RBAC** | **JWT (access + refresh) with role claims** (`admin`, `driver`, `guest`) | Simple, portable enforcement at API middleware; UI hides, API denies. |
| **Push notifications** | **Expo Push (guest + driver clients) / web push optional for Admin web** | Minimal onboarding for non-technical users; assignment requires push for match/status updates. |

**Not chosen (and why, briefly):** Flutter — equally viable for Guest, but RN + React Admin Portal keep one language/team stack. Firebase Realtime DB as primary transport — couples matching/state to a BaaS and fights a clean "Matching Engine as distinct module" boundary. Admin Portal as a second native app — extra codebase with no benefit given the assignment's "one portal, two roles" guidance.

---

## 2. Data Model

### 2.1 Entities and key fields

```
User (id, email, role, password_hash)
  | 1:1                    | 1:1
  v                        v
Guest                    Driver ----------------1:1----> Vehicle
- party_size             - status                        - plate_number
- luggage_count          - break_until                   - seat_capacity
- flight/train_eta       - predicted_free_at             - luggage_capacity
- pickup_location_id     - predicted_free_lat/lng
- accommodation_id       (break duration = system const
- priority (VIP)          MANDATORY_BREAK_MINUTES = 10)
- attendance_status
  |
  | N:M via TripGuest
  v
Trip <---------------- N:1 ---------------- Driver
- trip_type (arrival | to_venue | from_venue | departure | on_demand)
- status, origin/dest refs, scheduled_*, eta_*
- seats_used, luggage_used
- route_version  (optimistic lock for override/detour/apply)
  |
  | 1:N
  v
TripStop / TripGuest
- guest_id, sequence, stop_type (pickup|drop)
- deadline_at, boarded_at, dropped_at

EventSchedule          LocationPing           RideRequest
- phase                - driver_id            - guest_id
- window_start/end     - lat, lng, heading    - origin/dest
- default OD locs      - recorded_at          - party_size, luggage
- trip_type            (Redis hot store;      - status: pending_admin
                         Postgres cold)         | approved | queued
Location                                        | matched | declined
- name, type                                  - wait_started_at
  (airport|station|                           - priority_score
   venue|hotel)                               - approved_by, trip_id
- lat, lng, address
```

### 2.2 Entity field notes

| Entity | Key fields | Purpose |
| --- | --- | --- |
| **User** | `id`, `email`, `role` in {admin, driver, guest}, credentials | Auth identity; RBAC root. |
| **Guest** | `party_size`, `luggage_count`, travel ETA, `pickup_location_id`, `accommodation_id`, `priority` (VIP flag), `attendance_status` | Capacity + schedule inputs; manual travel corrections by admin. |
| **Driver** | `status` in {offline, available, en_route, at_pickup, in_trip, on_break}, `break_until`, `predicted_free_at`, `predicted_free_location` | Halt/break tracking; after drop, `break_until = now + 10 min` (fixed `MANDATORY_BREAK_MINUTES`). |
| **Vehicle** | `seat_capacity`, `luggage_capacity`, `plate_number` | Hard constraints for matching. |
| **Trip** | `trip_type`, `status`, `driver_id`, route polyline ref, `seats_used`, `luggage_used`, `eta_pickup`, `eta_drop`, `route_version` | Active assignment unit; `route_version` is the optimistic-lock token for concurrent writes. |
| **TripGuest / TripStop** | `guest_id`, `sequence`, stop type (pickup/drop), `deadline_at`, timestamps for boarded/dropped | Shared rides, detours, split groups. |
| **EventSchedule** | phase windows + default OD pairs + trip_type | Drives which destinations are "current" across the event timeline. |
| **LocationPing** | `driver_id`, lat/lng, `recorded_at` | Live tracking; Redis holds latest, Postgres stores sampled history if needed. |
| **RideRequest** | guest OD, capacity needs, `status` (pending_admin -> approved -> queued -> matched / declined), `wait_started_at`, `priority_score` | On-demand path with **manual** approve/decline, then **auto** match. |

Supporting tables (light): `AssignmentEvent` (audit: auto vs override), `DistanceCache` (OD hash -> duration/distance/traffic_ttl), `MatchJob` (batch/reopt job status).

### 2.3 Relationships (summary)

- User 1—1 Guest | User 1—1 Driver | Driver 1—1 Vehicle
- Guest N—M Trip via TripGuest (shared rides / splits)
- Trip N—1 Driver; Trip 1—N TripStop
- RideRequest N—1 Guest; RideRequest 0—1 Trip (after match)
- EventSchedule references Location rows for phase defaults
- LocationPing N—1 Driver

### 2.4 Fields that specifically unlock matching features

| Feature | Fields / structures used |
| --- | --- |
| **Capacity-aware matching** | `Vehicle.seat_capacity`, `Vehicle.luggage_capacity`; `Guest.party_size`, `Guest.luggage_count`; running `Trip.seats_used` / `luggage_used`; reject if `used + request > capacity`. |
| **Opportunistic detour insertion** | Live `LocationPing` (current position as route start); existing `TripStop` sequence + per-guest `deadline_at`; remaining capacity; incremental ETA; hard cap **MAX_DETOUR_INSERTION_MINUTES = 8**; apply under `route_version` optimistic lock. |
| **Priority queueing** | `RideRequest.wait_started_at`, `priority` / VIP, trip `deadline_at`, time-in-queue aging; **Redis sorted set only** (sole queue — no Postgres fallback). |
| **Halt-time / break tracking** | Trip status timestamps (`arrived_pickup`, `boarded`, `arrived_drop`); `Driver.break_until` set to drop time + **10 min**; `predicted_free_at` / free location after mandatory break before next assign. |

---

## 3. System Architecture (component boundaries)

Text/ASCII — components, not classes:

```
+--------------------------- Guest App (React Native) --------------------------+
| Register / pickup details | Match notification | Live map + ETA               |
| On-demand RideRequest -> "pending" until admin approves                       |
+---------------+----------------------------------+----------------------------+
                | HTTPS REST                       | WSS (trip + location)
                v                                  v
+-------------------------------------------------------------------------------+
|                          Backend API (FastAPI)                                 |
| Auth / RBAC middleware | Guest APIs | Admin APIs | Driver APIs                 |
| Does NOT embed solver logic -- calls Matching Engine interface / queue         |
+---+-----------------------------+-----------------------------+---------------+
    | commands/events             | read/write                  | pub/sub
    v                             v                             v
+-------------------+   +--------------+   +-----------------------------------+
| Matching Engine   |   |  PostgreSQL  |   | Real-time Location / Tracking     |
| (distinct module  |   |  core domain |   | Redis: last ping, geohash,        |
|  + worker)        |   |  + audit     |   | pub/sub channels                  |
|                   |   +--------------+   +------------------+----------------+
| * BatchOptimizer  |                                         |
|   (OR-Tools)      |          +------------------------------+
| * GreedyMatcher   |          | WSS fan-out to clients
| * DetourInserter  |          v
| * ReoptScheduler  |   +----------------------------------+
+---------+---------+   | Admin Portal (React web)         |
          |             | Admin role: fleet map, guests,   |
          |             | approve requests, manual override|
          |             | Driver role: own trip only,      |
          |             | status updates, live GPS         |
          |             +----------------------------------+
          v
+-------------------------+
| External Maps API       |
| Google Distance Matrix  |
| + Directions            |
| (only via Routing Svc   |
|  cache / batch layer)   |
+-------------------------+
```

**Boundary rules**

1. **API layer** = auth, validation, persistence orchestration, push triggers, WebSocket auth.
2. **Matching Engine** = pure decisioning (batch, greedy, detour, reopt); reads driver/guest/trip snapshots; writes proposed assignments via a narrow apply API.
3. **Realtime layer** = location ingest + fan-out; not a second source of truth for assignments (Postgres remains authoritative for trips).
4. **Maps API** = never called ad hoc from mobile clients for matching math; clients may use Maps SDK for display only.

**Graceful degradation:** if Matching Engine worker is down, in-progress trips continue (status + GPS still work); Admin manual override remains on the API; new auto-matches queue and retry.

---

## 4. Matching Engine Design

### 4.1 Pre-day batch assignment

**When:** Night before / when travel ETAs stabilize; also on large schedule imports or admin "Run batch" for a time window.

**Algorithm:** Google **OR-Tools** assignment / CP-SAT (scale 10–100 drivers, few hundred guests fits comfortably). Classic Hungarian alone is a bipartite cost matrix; we prefer OR-Tools so we can encode **capacity, shared-ride clustering, and time windows** in one model. Fallback simpler path: cluster by destination + time bucket, then solve bipartite assignment on cluster-to-vehicle with capacity packing.

**Inputs**

- Guests with known arrival/pickup windows, `party_size`, luggage, pickup & drop locations, deadlines, priority.
- Drivers/vehicles: capacity, shift windows, start depot / overnight location; post-trip break always **10 minutes**.
- EventSchedule phase -> allowed OD patterns.
- Travel-time matrix from Routing Service (cached; traffic-aware where available for the window).

**Cost function (illustrative weights)**

- Guest wait / lateness vs deadline (hard constraint if beyond max wait).
- Driver idle / empty reposition.
- Shared-ride detour penalty vs separate vehicles.
- Prefer same-destination clustering.
- Soft VIP priority boost.

**Outputs**

- Set of Trips with ordered TripStops, assigned `driver_id`, planned ETAs, `seats_used` / `luggage_used`.
- Unmatched guests list -> enter real-time priority queue with reason (`no_capacity`, `infeasible_eta`, ...).
- Persist as `AssignmentEvent` source=`batch`.

**Apply path:** Engine proposes -> transactional write of trips -> notify drivers/guests. Admin can later override individual rows without re-running the full batch.

### 4.2 Real-time priority queue (on-demand / unscheduled)

**Entry points**

1. Admin **approves** a RideRequest -> request enters match queue (not before).
2. Guest with no feasible batch match, or reject/requeue after driver reject.
3. Mid-event unscheduled pickups after manual guest record update.

**Queue semantics**

- **Redis sorted set is the sole priority queue** (no Postgres job-table fallback). Ordered by **priority score**:
  `score = base_priority + wait_aging_factor * minutes_waiting + deadline_urgency`
  so long-waiting guests are not starved by a stream of new VIPs (VIP boost capped).
- Worker pops head, runs **GreedyMatcher.match_one(request, snapshot)**.
- **Latency target:** `match_one` p95 **≤ 500 ms** at expected scale (≤ ~100 drivers in the candidate set), with Routing Service mocked or served from cache in tests. Wall-clock end-to-end including cold Maps calls is out of scope for this p95; M7 separately measures surge behavior.
- If no feasible driver: remain in queue with backoff; surface on Admin "unmatched" panel; never silently drop.

**Greedy matcher (lightweight)**

1. Filter drivers: not on break (`now < break_until`), remaining capacity >= need, status in {available} or detour-eligible {en_route, in_trip} — **never** `at_pickup` for detours.
2. Score candidates: ETA to pickup from **live position** (or predicted free location if finishing current trip + 10 min break), deadline slack, destination affinity, idle time.
3. Pick best feasible; create/assign Trip (or hand to DetourInserter). Persist under `route_version` optimistic lock when updating an existing trip.
4. Driver accept/reject: reject -> guest re-queued (ZADD back into the same Redis sorted set) with wait time preserved; driver may get brief cool-down to avoid thrash.

### 4.3 Opportunistic detour insertion (mid-trip, live position)

**Eligibility:** Driver status in **{en_route, in_trip} only** with an active Trip — **`at_pickup` is excluded** (driver is committed to the current pickup handshake; no mid-halt inserts). Remaining seat/luggage capacity >= request; new guest OD compatible with trip type / EventSchedule phase.

**Constants:** `MAX_DETOUR_INSERTION_MINUTES = 8` — added travel time vs the pre-insert route must be ≤ 8 minutes; also no existing guest may miss their deadline.

**Algorithm sketch**

1. Snapshot: driver **live lat/lng** (not trip origin), remaining stops `[S1...Sn]`, capacities, per-guest deadlines, current `route_version`.
2. Candidate insert positions for new pickup (and drop) in the stop sequence (O(n^2) is fine for small n).
3. For each candidate, ask Routing Service for incremental path time using **current position -> new sequence** (batched; see 4.5).
4. Accept insert only if:
   - Incremental detour ≤ **8 minutes**.
   - Every existing guest's projected arrival still within deadline.
   - New guest meets their deadline.
   - Capacity OK.
5. On accept: `UPDATE Trip SET …, route_version = route_version + 1 WHERE id = ? AND route_version = ?`. If 0 rows updated → concurrent override/detour won; reload snapshot and retry once or abort and leave request in Redis queue. On success, rewrite TripStops and push updated ETA/polyline to affected guests + driver + admin map.

**Explicit non-goal:** Guests never browse drivers; detour is engine-only.

### 4.4 Capacity limits and split-group / fleet escalation

1. **Single vehicle fit:** `party_size <= seat_cap` and `luggage <= luggage_cap` -> normal match / shared ride packing.
2. **Exceeds largest vehicle:** **Split-and-coordinate**
   - Partition party into sub-groups that fit available vehicles (prefer same destination, minimize vehicles, keep splits time-aligned).
   - Create linked trips with shared `party_group_id`; Admin UI shows coordinated ETA.
3. **Fleet escalation:** If not enough free capacity in time window -> mark `needs_escalation`; Admin notified for manual override / external vehicle; engine keeps trying as capacity frees.
4. **Shared rides:** Pack multiple small parties with same (or near) destination if detours within the **8-minute** insertion budget — uses same capacity accounting as detours.

### 4.5 Re-optimization on traffic / ETA change (without Maps spam)

| Technique | Behavior |
| --- | --- |
| **Distance cache** | Key = normalized OD pair (+ departure time bucket). TTL shorter under traffic (e.g. 2–5 min for active corridors), longer for static overnight planning. |
| **Batch Matrix calls** | Reopt builds one OD set for all active trips/candidates; one Distance Matrix round-trip, not N Directions calls. |
| **Dirty flag / debounce** | Location or traffic tick sets `trip.needs_eta_refresh`; ReoptScheduler runs every T seconds (e.g. 30–60s) or when dirty count exceeds threshold — not on every GPS ping. |
| **Selective reopt** | Only trips whose ETA drift > threshold (e.g. 3–5 min) or risk deadline breach enter full rematch consideration. |
| **Rematch vs ETA-only** | Default: refresh ETAs + notify. Full re-assign only if infeasible or large systemic drift; prefer not to yank a guest already boarded. |
| **Client display** | Maps SDK for map tiles/polylines; matching math never depends on client-side Google calls. |

### 4.6 Automation boundary

| Automated (Matching Engine) | Manual (outside engine) |
| --- | --- |
| Which driver serves which guest and when (batch + realtime + detour) | Driver onboarding / vehicle capacity entry |
| Allocation after admin **approves** an on-demand request | Approve / decline of ad-hoc RideRequests |
| Requeue + rematch after driver reject | Guest travel/attendance corrections (flight changes, walk-ins) |
| Capacity packing, splits proposal, ETA-driven reopt | Manual override in edge cases (VIP, breakdown, no feasible auto-match) |
| Push of match result (name, vehicle, ETA) — guest does not choose | — |

**Admin override:** Admin may force-assign or cancel; engine treats override as authoritative and excludes those trips from greedy steal unless released. Override writes must pass the same **`route_version` optimistic lock** as detours — stale admin UI versions fail with a conflict response so the admin reloads before forcing again.

**Fixed timing constants (system-wide)**

| Constant | Value | Use |
| --- | --- | --- |
| `MANDATORY_BREAK_MINUTES` | **10** | After trip drop, driver enters `on_break` until `break_until`; not assignable until then. |
| `MAX_DETOUR_INSERTION_MINUTES` | **8** | Hard cap on added travel time for opportunistic insert. |
| `MATCH_ONE_P95_MS` | **500** | Asserted in M2 automated tests (mocked/cached routing). |

---

## 5. Role Separation Approach (RBAC)

### 5.1 API layer (authoritative)

- JWT includes `sub` (user id) + `role`.
- Middleware maps route groups:
  - `/admin/**` -> role `admin` only.
  - `/driver/**` -> role `driver` only; **every** query scoped by `driver_id = current_user.driver_id` (trips, pings, guests on **own** trip only).
  - `/guest/**` -> role `guest`; own guest record / own trip only.
- Deny by default: no "list all guests" or "fleet map" endpoints reachable with driver token.
- Object-level checks: even if a trip UUID is guessed, server verifies ownership / admin role before return.
- WebSocket channels: subscribe only to `driver:{id}`, `trip:{id}` if member, or `admin:ops` if admin — server validates on subscribe.
- Audit log for overrides and approve/decline.

### 5.2 UI layer (defense in depth, not security alone)

- Single Admin Portal SPA: after login, router loads **AdminShell** vs **DriverShell** from role claim.
- DriverShell routes: Active Trip, Status actions, break indicator — **no** nav links to fleet/guest queue/request approval.
- Admin components and API client modules not mounted for drivers (code-splitting) to reduce accidental leakage; still assume API is the real gate.
- Guest app is a separate binary/app id — no admin routes compiled in.

### 5.3 Invariants

- Driver cannot list RideRequests pending admin review.
- Driver cannot see other drivers' locations or unmatched guest queue.
- Guest cannot enumerate drivers.
- Manual override and approve/decline are admin-only.

---

## 6. Phased Build Plan

Each milestone is **independently demoable**.

| Milestone | Deliverable | Demo script |
| --- | --- | --- |
| **M1 — Data model + API skeleton** | Postgres schema/migrations, FastAPI CRUD for User/Guest/Driver/Vehicle/Location/EventSchedule/Trip/RideRequest, JWT auth with roles, seed script for one event. | Create admin, add drivers/guests, show role-denied responses for cross-role GETs. |
| **M2 — Matching engine core + tests** | Matching Engine package: OR-Tools batch, greedy `match_one`, capacity + split logic, Redis sorted-set priority queue, detour rules (`en_route`/`in_trip` only, 8 min cap), `route_version` lock helpers; **no UI**. Fixture tests + **assert `match_one` p95 ≤ 500 ms** (mocked routing, ~100-driver fixture). | Run batch on seed data; inject on-demand approved request; show assignments + unmatched; latency bench test green; conflict on stale `route_version`. |
| **M3 — Admin Portal (Admin role)** | React web: fleet/guest lists, pending RideRequests approve/decline, upcoming trips, manual override, trigger batch. | Approve a request -> see auto-assigned trip appear; override a trip; decline a request. |
| **M4 — Driver role (same portal)** | DriverShell: one active trip, accept/reject, status machine, break/halt timestamps; RBAC UI + API proof. | Login as driver A — see only A's trip; reject -> guest requeues into Redis ZSET; complete trip -> `break_until` = now+10m, then predicted free. |
| **M5 — Guest app** | Expo app: pickup details, match notification payload, request ride -> pending state, view assigned driver/ETA (map can be stubbed then wired). | Guest requests ride -> admin approves (M3) -> guest receives match; cannot pick driver. |
| **M6 — Real-time layer + detour logic** | Redis location ingest, WebSockets to Guest/Admin/Driver, live map, DetourInserter using live position (exclude `at_pickup`), 8-min budget + `route_version` apply, push notifications. | Driver `en_route`/`in_trip` gets detour; `at_pickup` does not; concurrent override loses on version conflict; both guests see updated ETA. |
| **M7 — Integration + simulated peak-load** | Routing Service cache/batch, reopt debounce, scripted peak arrival (tens of drivers, hundreds of guests), latency metrics for `match_one`. | Simulate surge; show wait bounds, capacity respect, Maps call count bounded; engine-down drill leaves in-trip intact + admin override works. |
| **M8 — Design doc** | Short design document: algorithm approach, trade-offs (OR-Tools vs greedy, cache TTLs, automation boundary), how to run demo. | Review doc against scoring criteria; final end-to-end walkthrough. |

**Suggested sequencing dependency:** M1 -> M2 -> (M3 in parallel with early M5 stubs) -> M4 -> finish M5 -> M6 -> M7 -> M8.

---

## Confirmed stack & constants

- **Stack:** Python/FastAPI + Postgres + Redis + RN Expo Guest + React web Admin Portal + Google Maps + OR-Tools worker.
- **Admin Portal:** responsive web (Admin on desktop, Driver on phone).
- **Maps:** Google Maps Platform.
- **Break / detour / latency:** 10 min break, 8 min max detour, `match_one` p95 ≤ 500 ms (M2).
- **Queue:** Redis sorted set only.

---

*Plan locked. No implementation until the next build prompt.*
