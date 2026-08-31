# Research: Redis-Locked Multi-Lane Dedup Architecture — Under Review, Not Adopted

**Date**: 2026-09-01
**Status**: Research proposal received from user, logged for review. Not implemented, not scheduled.

## Where this came from

After the 2-laptop live test of v2.1.1 (the Qt-main-thread-freeze fix), the
user reported it's working well but **occasionally slow on the cross-station
duplicate detection, which let a duplicate badge scan through** — i.e. the
Live Sync check-duplicate call was slow/late enough that both stations
accepted the same badge before either learned about the other's scan. In the
same message, the user shared a set of AI-agent implementation prompts
(Backend/Frontend/DevOps) proposing a from-scratch multi-lane check-in
system built on FastAPI + Upstash Redis + Neon Postgres + React/Next.js on
Cloud Run, as external research to review — not a decision to build it.

## What was proposed

Three "agent prompt" specs, summarized:

- **Backend (FastAPI)**: `POST /api/attendance/scan` using Upstash Redis
  `SETNX` (`redis.set(key, value, nx=True, ex=86400)`) as an atomic
  distributed lock for dedup, returning `409 Conflict` on a hit. Successful
  scans persisted to Neon Postgres asynchronously via `BackgroundTasks` +
  `ON CONFLICT DO NOTHING`, so the lock check response is never gated by the
  SQL write. Plus a `POST /api/attendance/sync/batch` endpoint for offline
  batch upload via `execute_values`.
- **Frontend (React/Next.js)**: a global keydown listener for scanner input
  (keystroke-timing heuristic to distinguish scanner bursts from manual
  typing), Web-Audio-synthesized success/error tones, full-screen
  color-coded status (green/red/amber), and an IndexedDB-backed offline
  queue that retries against the batch endpoint on reconnect.
- **DevOps**: multi-stage `python:3.11-slim` Docker build, Cloud Run deploy
  with `--min-instances 1 --max-instances 3 --concurrency 80
  --execution-environment gen2`, secrets via env vars/Secret Manager, and a
  k6/locust load test simulating 10 lanes × 15 scans/sec.

## How this maps onto what's actually running today

Worth being explicit about this, since the proposal describes a *new*
system, not a patch to the existing one — a straight "should we build this"
comparison needs the current architecture stated plainly first:

| Proposed | Existing (this repo + `trackattendance-api`) |
|---|---|
| FastAPI (Python) backend | Fastify (Node/TypeScript) backend, different repo (`trackattendance-api`) |
| Upstash Redis `SETNX` lock, 24h TTL | `GET /v1/scans/check-duplicate` — a Postgres `SELECT` against `scans`, windowed by `LIVE_SYNC_DUP_WINDOW_MINUTES` (default 5 min, not 24h) |
| Neon Postgres, async `BackgroundTasks` write | Neon Postgres already in use (confirmed same provider) via `POST /v1/scans/batch`, `ON CONFLICT (idempotency_key) DO NOTHING` — same conflict-safe pattern, already implemented |
| React/Next.js scanner-lane client | PyQt6 + QWebEngineView desktop kiosk (`attendance.py`/`main.py`/`web/script.js`) — this *is* the "client check-in" layer already, just a different stack |
| Cloud Run, `--min-instances 1` | Already Cloud Run, `asia-southeast1`; min-instances currently 0 outside event days (see 2026-08-31 session — calendar reminder set for 2026-09-03 10:30 to bump to 1) |
| Offline IndexedDB queue + batch resync | Already offline-first: local SQLite (`sync_status: pending/synced/failed`), `BackgroundSyncCoordinator` worker thread, idle-triggered batch sync — different storage, same shape |

**The actual reported bug — slow dup detection letting a duplicate through
— is a latency problem in the existing check, not a missing mechanism.**
`check_duplicate_cloud()` (`sync.py:787`) already does the right kind of
thing conceptually (ask the cloud before accepting), it's just apparently
not always fast/consistent enough at 2-laptop-test load. The proposed
Redis-`SETNX` design's real advantage is that a `SETNX` typically resolves
in low single-digit milliseconds regardless of Postgres connection-pool
contention or query latency — but that advantage only matters if Postgres
query/connection latency is actually the bottleneck. Worth stating plainly,
not assumed: nobody has profiled *why* the current check was slow during
the test session (query plan, connection pool state, network hop count,
Cloud Run cold-start-adjacent latency, etc.) — that root cause is unknown as
of this writing.

## Open questions before any implementation decision

- Is the actual root cause of the observed slow detection latency, connection-pool
  contention, or something else? Not diagnosed yet.
- The proposal is written as a **new** service (FastAPI, not Fastify;
  implicitly a new client, not the existing PyQt6 kiosk) — is the intent to
  replace `trackattendance-api`/the kiosk app, or to bolt a Redis lock
  *into* the existing Fastify `check-duplicate` endpoint as a targeted fix?
  These are very different scopes (rewrite vs. one new dependency).
- If it's the targeted-fix framing: could `check-duplicate` in
  `trackattendance-api`'s `server.ts` add a Redis (or even in-memory/Cloud
  Run Memorystore) fast-path lock ahead of the Postgres check, without
  touching the desktop client or its sync model at all? Untested, but a much
  smaller change than the proposed 3-agent full-stack rebuild.
- Cost/ops tradeoff of adding Upstash as a new managed dependency, on top of
  Neon Postgres and Cloud Run, hasn't been evaluated.

## Why this is logged as "under review," not scheduled

Same posture as
[[2026-08-23_multi-station-lockout-overlay-deferred]]: a real signal
surfaced from live testing (a duplicate badge did get through), but the
proposed fix is a large, largely-different-stack rewrite proposal received
as external research, not yet diagnosed against the actual root cause or
evaluated against a smaller targeted fix. Recording it now so the reasoning
and the specific prompts aren't lost, without committing to the rewrite.

## When to revisit

- If the root cause of the slow duplicate-check is profiled and turns out to
  be something a lightweight fix (indexing, connection pool tuning, a fast
  in-process cache, or a targeted Redis lock added to the existing
  `check-duplicate` endpoint) can't resolve.
- If duplicate-lets-through becomes frequent/costly enough in practice
  (not just observed once during a 2-laptop test) to justify a larger
  architecture change.
- If there's an appetite to evaluate replacing `trackattendance-api`
  (Fastify) with a FastAPI service outright — a much bigger decision than
  the dedup mechanism alone, and shouldn't be decided as a side effect of
  fixing one latency bug.
