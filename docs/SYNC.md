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
| API error (5xx) | Batch marked `failed`; use `scripts/reset_failed_scans.py` to retry |

## Sync-All (Admin)

```python
# One batch (default)
result = sync_service.sync_pending_scans()

# All pending until done
result = sync_service.sync_pending_scans(sync_all=True, max_batches=50)
```

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
