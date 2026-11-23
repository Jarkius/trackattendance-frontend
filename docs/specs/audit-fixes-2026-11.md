# Audit Fixes 2026-11: Data Capture, Sync Integrity, Reporting, Responsiveness

## Problem and Goal
A November 2026 audit found defects that cause wrong or lost attendance data in the cloud, wrong people recorded at the kiosk, misleading report numbers, and GUI-thread stalls. They are filed as GitHub issues #101–#112, each with evidence, a reproduction and acceptance criteria.

Goal: every scan the operator makes is captured once, attributed to the right person, eventually reaches the cloud with the same event content, and is counted correctly in reports. None of this may regress the offline-first contract or the sync coordinator/barrier design from PR #64.

## Scope
### In scope
| Ticket | Issue | Area |
|---|---|---|
| 01 | #101 | Sync: transient vs permanent errors, batch bisection, failed-scan recovery |
| 02 | #110 | Sync: verify 200 response counts before marking synced |
| 03 | #102 | Immediate Write uses the batch event builder |
| 04 | #104 | Scanner keystrokes never lost to overlay/focus state |
| 05 | #103 | Lookup overlay ignores scanner bursts |
| 06 | #105 | Roster header normalisation, and every import abort is surfaced |
| 07 | #106 | Single badge/Legacy ID normalisation rule |
| 08 | #107, #108 | Duplicate config validation and alert message |
| 09 | #109 | Attendance rate counts matched employees only |
| 10 | #111 | GUI-thread blocking hygiene |
| 11 | #112 | Export API documentation drift |
| 12 | #109 | API (`trackattendance-api`): matched / walk-in / unknown-badge counts in both stats endpoints and the public mobile dashboard |

### Non-goals
- API changes beyond ticket 12's additive stats fields.
- Backfilling cloud rows already stored without `meta` (ticket 03 documents the operator remedy instead).
- Re-architecting the `BackgroundSyncCoordinator`, or fixing open issues #65–#70, except where a ticket touches the same lines.
- A JS unit-test framework. UI tickets verify through a disposable `QWebEngineView` harness, per `.claude/rules/project-verification.md`.
- Porting to `trackattendance-saas`. Do that afterwards with `scripts/sync-to-saas.sh`.

## Domain and Contracts

**Sync result dict** (`sync_scan_batch_network_only`, consumed by `main.py:462-492` and `:1016`). Callers key off `synced_ids`, `failed_ids`, `pending_ids`, `synced_count` and `error`. This shape is **LOCKED**, and new behavior must fit in it.
- `failed_ids` means the server has said *this specific event* is unacceptable. Use it only after bisection reduces a 400/422 to a single event.
- `pending_ids` means anything transient: transport errors, 403/404/408/413, 5xx, 429, an unparseable 200, or a 200 whose counts don't cover the batch.

**Server batch semantics** (verified in `server.ts`):
- The insert is one transaction with `on conflict (idempotency_key) do nothing`.
- One event with invalid `meta` causes a 400 for the whole batch.
- On a 200, `saved + duplicates == len(events)`.

**Idempotency key:** `{station}-{badge_id}-{local_id}`. This format is unchanged.

**Event builder:** `_build_batch_events(scans, station_name)` is the single source of truth for an uploaded event (ticket 03).

**Badge ID normalisation** (ticket 07): one function, `normalize_badge_id(value) -> str`, used at roster import, scan lookup, duplicate checks and reporting joins.
- It strips whitespace, including NBSP and zero-width characters.
- It applies the case rule, **ASSUMED**: case-insensitive matching via upper-casing the lookup key. The stored `badge_id` keeps exactly what was scanned.

**Attendance buckets** (tickets 09 and 12). These definitions are LOCKED by the user on 2026-11-24.

| Bucket | Rule | Counted as a person? |
|---|---|---|
| **Registered attended** | Distinct `COALESCE(meta->>'legacy_id', badge_id)` over scans with `business_unit IS NOT NULL` | Yes, and it is the attendance-rate numerator |
| **Walk-ins** | Distinct normalised (trim, lower-case, collapse spaces) `badge_id` over unmatched scans with `scan_source = 'manual'`, i.e. names typed for people missing from the roster | Yes, shown separately, never in the rate |
| **Unknown badge scans** | Distinct `badge_id` over unmatched scans with `scan_source <> 'manual'` | No, shown as "needs review" |

- Attendance rate = registered attended ÷ total registered, which is at most 100%.
- Total present = registered attended + walk-ins.
- API fields (additive, ticket 12): `matched_unique`, `walkin_unique`, `unknown_badge_unique` on `/v1/dashboard/stats` and `/v1/dashboard/public/stats`.
- The kiosk falls back to the sum of `business_units[].unique` (excluding `Unmatched`) when `matched_unique` is absent, so the deploy order doesn't matter.

## User Behavior and Acceptance Criteria
Per-issue acceptance criteria live in each GitHub issue and are restated testably in each ticket. Cross-cutting scenarios:

### Scenario: one bad event does not strand the batch
- **Given** 100 pending scans, one of which the server rejects with 400
- **When** sync runs
- **Then** 99 scans are synced, 1 is `failed`, and nothing else is `failed`.

### Scenario: transient failure self-heals
- **Given** a sync attempt hits a 404 or a `ChunkedEncodingError`
- **When** the server recovers and the next sync cycle runs
- **Then** all scans are synced with no manual script.

### Scenario: queue of people during a duplicate alert
- **Given** a duplicate alert is showing in warn mode
- **When** the next badge is scanned 500 ms later
- **Then** that scan is recorded in full and the alert is replaced.

### Scenario: scan while the lookup overlay is open
- **Given** the lookup overlay is showing results
- **When** a badge is scanned (a character burst followed by Enter)
- **Then** the overlay closes, the badge is processed as a fresh scan, and no lookup result is recorded.

### Scenario: broken roster header
- **Given** `employee.xlsx` has a `"Legacy ID "` header
- **When** the app starts
- **Then** the roster loads correctly, or the operator sees a roster error. It never silently loads nothing.

## UX Contract
- The duplicate alert stays informational. It no longer disables input, and a new scan replaces it.
- Deliberate lookup selection (ArrowUp/ArrowDown, then Enter) is unchanged.
- No new UI elements, except that ticket 09 may add an "Unmatched" figure where the dashboard already shows counts.

## Failure and Edge Cases
- **Bisection bound:** a 400 batch of N is split in halves until single events, so one bad event costs about 2·log2(N) requests. Stop bisecting and keep the remainder `pending` if a split hits a transient error. Mind the server's 60 req/min rate limit.
- **Failed-scan recovery, ASSUMED:** at application start, `failed` rows are reset to `pending` once, keeping `sync_error` in the log. Poison events re-fail after bisection, so the cost is bounded to one retry per app start. No schema column is added.
- **Coordinator barrier:** ticket 01 must not move `mark_*` calls off the main thread or bypass the generation barrier (see `tests/test_barrier_reset_integration.py`).
- **Numeric Legacy ID cells, ASSUMED:**
  - If the cell number format is all zeros (e.g. `00000`), zero-pad to that width.
  - Otherwise record a roster warning that names the count of numeric IDs.
  - The workbook value is never silently rewritten in any other way.

## Security and Operations
- Privacy (LOCKED by the user, 2026-11-24): manually typed walk-in names keep syncing to the cloud as `badge_id`. The multi-station export needs them.
  - Roster names (`full_name`) still stay local.
  - Ticket 11 corrects the `CLAUDE.md` Privacy line to state this.
- Do not log full rosters. Bisection logs only event counts and keys.
- Performance (ticket 10): record before/after timings with `tests/test_performance.py`.

## Decisions and Assumptions
- **LOCKED:** sync result dict shape. Idempotency key format. Offline-first: write locally before any network call. Sync logic is network-only and SQLite stays on the main thread (PR #64).
- **LOCKED (user, 2026-11-24):**
  - All tickets approved.
  - The three attendance buckets, fixed in both the kiosk and the API (ticket 12).
  - Walk-in names sync to the cloud.
  - Ticket 11 may edit `docs/API.md` and `CLAUDE.md`.
- **ASSUMED (approved with the plan):**
  - Failed scans are reset to pending once at startup, with no new column.
  - Badge IDs match case-insensitively.
  - Numeric IDs are zero-padded only when the cell's number format says so.
- **DEFERRED:** cloud `meta` backfill. Pushing, deploying and opening PRs all need confirmation.

## Verification
Activate `.venv` first. No `.venv` exists on this machine yet, so create it per `CLAUDE.md`.

CI suite:
```bash
python -m pytest tests/ \
  --ignore=tests/test_ui_bridge.py --ignore=tests/test_validation_ui.py \
  --ignore=tests/test_camera_plugin.py --ignore=tests/test_proximity_detector.py \
  --ignore=tests/stress_full_app.py --ignore=tests/simulate_scans.py \
  --ignore=tests/simulate_multi_station.py -v --tb=short
```

Focused checks are listed per ticket. The UI tickets (04, 05, 08) also need a disposable `QWebEngineView` harness run plus a manual kiosk check with a real scanner. Build check: `pyinstaller TrackAttendance.spec`.
