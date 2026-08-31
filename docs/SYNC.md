# Cloud Synchronization

**For API endpoint documentation**, see [API.md](API.md).

## Sync Mechanism

The sync system is **offline-first**. All scans are recorded locally to SQLite with a `sync_status` field.

### Status Tracking

Each scan record has a `sync_status`:
- `pending` — Not yet uploaded to cloud
- `synced` — Successfully uploaded (with idempotency key)
- `failed` — Upload attempt failed (network error, API rejection)

### Batch Processing

- Syncs in configurable batches (default 100 scans per batch)
- Each batch uploaded atomically; if any record fails, entire batch marked `failed`
- Each batch generates a unique idempotency key (SHA256) to prevent cloud duplicates

### Sync Flow

```
Query pending scans → Check connectivity → Upload batch → Mark synced/failed → Repeat
```

## Manual Sync

- User clicks sync button on dashboard
- Tests connectivity (5-second timeout)
- If online: uploads one batch, updates counters
- If offline: shows error; scans remain `pending`
- Spinning blue icon (#00A3E0) while syncing

## Auto-Sync (v1.2.0+)

**Trigger conditions** (all must be true):
- Idle for ≥ `AUTO_SYNC_IDLE_SECONDS` (default 30s)
- At least `AUTO_SYNC_MIN_PENDING_SCANS` pending (default 1)
- No sync in progress
- `AUTO_SYNC_ENABLED = True`

**Configuration**:
```ini
AUTO_SYNC_ENABLED=True
AUTO_SYNC_IDLE_SECONDS=30
AUTO_SYNC_CHECK_INTERVAL_SECONDS=60
AUTO_SYNC_MIN_PENDING_SCANS=1
AUTO_SYNC_CONNECTION_TIMEOUT=5
AUTO_SYNC_SHOW_START_MESSAGE=True
AUTO_SYNC_SHOW_COMPLETE_MESSAGE=True
AUTO_SYNC_MESSAGE_DURATION_MS=3000
```

## Shutdown Flow

1. **Sync**: Tests API → uploads all pending batches → shows overlay
2. **Export**: All records to XLSX in `exports/`
3. **Close**: Final status → window closes after 1.5s

## Offline Scenarios

| Scenario | Behavior |
|----------|----------|
| Start offline | Scans save locally; auto-sync checks fail silently |
| Go offline mid-session | Pending scans wait; auto-sync resumes when connection returns |
| Intermittent connection | Idempotency keys prevent duplicates; no partial batches |
| API error (5xx) | Batch marked `failed`; use `tests/reset_failed_scans.py` to retry |

## Sync-All (Admin)

```python
# One batch (default)
result = sync_service.sync_pending_scans()

# All pending until done
result = sync_service.sync_pending_scans(sync_all=True, max_batches=50)
```

## Live Sync (Real-Time Cross-Station Duplicate Check)

Live Sync is a separate mechanism from batch/auto-sync above — it runs **synchronously, per scan**, not on the idle-triggered batch schedule.

**Configuration**:
```ini
LIVE_SYNC_ENABLED=False           # off by default
LIVE_SYNC_TIMEOUT_SECONDS=2.0     # 0.5-10.0
LIVE_SYNC_DUP_WINDOW_MINUTES=5    # 1-1440
```

When enabled (and `CLOUD_READ_ONLY=False`), every `register_scan()` call does two things:

1. **Duplicate check (blocking, gates the scan)** — `GET /v1/scans/check-duplicate` asks the cloud API whether this badge was scanned at a *different* station within `LIVE_SYNC_DUP_WINDOW_MINUTES`. If `DUPLICATE_BADGE_ACTION=block`, a hit rejects the scan before it's recorded locally. This call runs off the Qt main thread via `qt_bridge.call_without_freezing_ui()` (see [ARCHITECTURE.md](ARCHITECTURE.md)) so the UI doesn't freeze while waiting, but the app still waits for the result before continuing — this is a deliberate design choice; see the alternative considered below.
2. **Immediate upload (fire-and-forget, does not block)** — after the scan is written to local SQLite, it's handed to the shared `BackgroundSyncCoordinator`'s worker thread for an immediate `POST /v1/scans/batch` upload. This is **not** queued for idle time — the coordinator's worker thread is already running continuously in the background, so the upload fires within moments of the scan, not after `AUTO_SYNC_IDLE_SECONDS` like the batch path above. If the coordinator's bounded queue (max 8 jobs) is full, the enqueue is skipped and the scan simply falls back to the normal idle-triggered batch sync — no scan is ever lost, only its real-time visibility is delayed.

**Fail-open**: if the duplicate-check call errors (timeout, network error, HTTP error, rate limit) it returns "not a duplicate" rather than blocking the scan — a Live Sync outage degrades cross-station duplicate detection, it never stops scanning.

### Traffic and rate-limit impact

Both calls above count against the cloud API's per-IP rate limiter (`RATE_LIMIT_MAX`, default 60 requests/minute — see `trackattendance-api`'s `.env`). With Live Sync on, **each scan is 2 API calls**, on top of periodic connection-health-check/heartbeat traffic (~1 request/minute/station). At multi-station events where all stations share one office egress IP, this adds up fast — e.g. 10 stations scanning once every 10 seconds is already 120 calls/minute, double the default limit. Consider raising `RATE_LIMIT_MAX` on the cloud API before a high-traffic multi-station event; a 429 fails open (see above) rather than freezing the app, but it does mean cross-station duplicate catching becomes less reliable exactly when traffic is highest.

### Alternative considered: fully-async duplicate check

An alternative design would accept the scan immediately and only retroactively flag a cross-station duplicate after the check comes back, removing all per-scan wait time. This was considered and rejected for the current implementation: it would mean `DUPLICATE_BADGE_ACTION=block` could no longer truly block a cross-station duplicate before it's recorded — it would become closer to `warn`-after-the-fact for the cross-station case specifically. The current implementation keeps today's blocking semantics and instead moves the *wait* off the UI thread (see [ARCHITECTURE.md § Threading Model](ARCHITECTURE.md#55-threading-model--keeping-the-qt-main-thread-unblocked)), rather than changing what gets blocked.

## Business Unit Sync

Each scan record synced to the cloud includes a `business_unit` field derived from the `sl_l1_desc` column in the employee roster. This field is populated at scan time and included in the batch payload sent to `POST /v1/scans/batch`.

```json
{
  "badge_id": "ABC123",
  "station": "Main Gate",
  "scanned_at": "2026-02-27T08:45:30Z",
  "business_unit": "Engineering"
}
```

If the employee is not matched or the roster does not contain `sl_l1_desc`, the field is omitted or `null`.

## Roster Summary Sync

The desktop app syncs a roster summary to the cloud so the mobile dashboard can display per-BU registered counts and attendance rates without access to the local SQLite database.

### Trigger

The first successful health check response from the cloud API triggers an automatic roster summary sync. Subsequent syncs use **hash-based deduplication**: the app computes a SHA256 hash of the summary payload and only re-POSTs if the hash differs from the last accepted hash.

### Endpoint

```
POST /v1/roster/summary
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "total_registered": 500,
  "business_units": [
    {"name": "Engineering", "registered": 120},
    {"name": "Sales", "registered": 95},
    {"name": "HR", "registered": 40}
  ],
  "payload_hash": "sha256:<hex>"
}
```

The cloud API returns `200` (accepted) or `204` (hash unchanged, no update needed).

### Implementation: `sync_roster_summary_from_data()`

Located in `sync.py`, this function:

1. Reads the current roster from SQLite (employees table, grouped by `business_unit`).
2. Builds the summary payload (total count + per-BU breakdown).
3. Computes a SHA256 hash of the serialised payload.
4. Compares against the cached hash from the previous sync.
5. If the hash is new or changed, POSTs to `/v1/roster/summary` and caches the accepted hash.
6. Called from the health check thread after the first successful API ping.

```python
# Called from health check thread after first successful ping
sync_service.sync_roster_summary_from_data()
```

The main thread populates the in-memory BU cache from SQLite at startup; the health check thread reads from that cache when building the summary payload, keeping the sync non-blocking.

## Duplicate Badge Detection (v1.3.0+)

Prevents accidental duplicate scans within a configurable time window.

### Action Modes

| Mode | Behavior | UI |
|------|----------|----|
| `warn` (default) | Accept scan, show alert | Yellow overlay |
| `block` | Reject scan | Red overlay |
| `silent` | Accept scan, no alert | None |

### Configuration

```ini
DUPLICATE_BADGE_DETECTION_ENABLED=True
DUPLICATE_BADGE_TIME_WINDOW_SECONDS=60
DUPLICATE_BADGE_ACTION=block
DUPLICATE_BADGE_ALERT_DURATION_MS=3000
```
