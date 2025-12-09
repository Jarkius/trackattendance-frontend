# TrackAttendance Cloud API Documentation

**API Repository**: https://github.com/Jarkius/trackattendance-api
**Endpoint**: `https://trackattendance-api-969370105809.asia-southeast1.run.app`
**Hosting**: Google Cloud Run (asia-southeast1 region)

## Overview

The TrackAttendance API is a RESTful backend service that receives and stores attendance scan records from desktop clients. It uses bearer token authentication and provides idempotency guarantees to prevent duplicate processing.

## Authentication

All API requests (except health checks) require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <API_KEY>
```

The API key is configured in `config.py`:
```python
CLOUD_API_KEY = "your-api-key-here"
```

## Endpoints

### 1. Health Check

**Endpoint**: `GET /`

**Purpose**: Test connectivity to the API without authentication.

**Request**:
```bash
curl -i https://trackattendance-api-969370105809.asia-southeast1.run.app/
```

**Response** (Success):
```
HTTP/1.1 200 OK
```

**Response** (Failure):
```
HTTP/1.1 5xx Server Error
```

**Timeout**: 3 seconds (configurable in `sync.py`)

---

### 2. Batch Upload Scans

**Endpoint**: `POST /v1/scans/batch`

**Purpose**: Upload a batch of attendance scans to the cloud. Supports idempotency to prevent duplicate processing.

**Authentication**: Required (Bearer token)

**Request Headers**:
```
Content-Type: application/json; charset=utf-8
Authorization: Bearer <API_KEY>
```

**Request Body**:
```json
{
  "events": [
    {
      "idempotency_key": "string",
      "badge_id": "string",
      "station_name": "string",
      "scanned_at": "2025-12-09T15:30:45Z",
      "meta": {
        "matched": boolean,
        "local_id": integer
      }
    }
  ]
}
```

**Request Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `idempotency_key` | string | Unique key for this scan. Format: `{station_name}-{badge_id}-{local_id}`. Prevents duplicates if batch is processed twice. Example: `MainGate-101117-1234` |
| `badge_id` | string | The barcode/badge ID scanned by the employee. Example: `"101117"` |
| `station_name` | string | Name of the scanning station. Example: `"Main Gate"` |
| `scanned_at` | string (ISO 8601) | Timestamp when scan occurred, in UTC with `Z` suffix. Example: `"2025-12-09T15:30:45Z"` |
| `meta.matched` | boolean | `true` if badge was found in employee roster, `false` if unmatched |
| `meta.local_id` | integer | Internal database ID from the local SQLite instance (for reconciliation) |

**Response** (Success - HTTP 200):
```json
{
  "saved": 98,
  "duplicates": 2
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `saved` | integer | Number of new scans saved to the database |
| `duplicates` | integer | Number of duplicate scans rejected (matched by `idempotency_key`) |

**Response** (Failure - HTTP 4xx/5xx):
```json
{
  "error": "Invalid request format or server error"
}
```

**Timeout**: 10 seconds (configurable in `sync.py`)

**Batch Size**: Default 100 scans per request (configurable in `config.py` as `CLOUD_SYNC_BATCH_SIZE`)

**Example Using curl**:
```bash
curl -X POST https://trackattendance-api-969370105809.asia-southeast1.run.app/v1/scans/batch \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "events": [
      {
        "idempotency_key": "MainGate-101117-1",
        "badge_id": "101117",
        "station_name": "Main Gate",
        "scanned_at": "2025-12-09T15:30:45Z",
        "meta": {
          "matched": true,
          "local_id": 1
        }
      }
    ]
  }'
```

---

## Data Sync Flow

The desktop client (`sync.py`) orchestrates the following flow:

```
1. Test Connection
   └─ GET / (3s timeout)
   └─ If fails → abort sync, keep scans as "pending"

2. Fetch Pending Scans
   └─ Query SQLite for scans with sync_status = "pending"
   └─ Limit to batch_size (default 100)

3. Build Request Payload
   └─ Generate idempotency_key for each scan
   └─ Ensure UTC Z-format timestamp
   └─ Include matched flag and local ID

4. Upload Batch
   └─ POST /v1/scans/batch (10s timeout)
   └─ Include Bearer token

5. Process Response
   ├─ If 200 OK
   │  ├─ Mark all scans as synced in SQLite
   │  ├─ Log: "saved: X, duplicates: Y"
   │  └─ Return control
   │
   └─ If 4xx/5xx Error
      ├─ Mark all scans as failed in SQLite
      ├─ Log error and scan IDs
      └─ Return control

6. Repeat (if sync_all=True)
   └─ Fetch next batch and repeat from step 2
```

---

## Error Handling

### Connection Test Failures

| Error | Cause | Client Action |
|-------|-------|---------------|
| Cannot connect | Network unreachable | Sync skipped; scans stay `pending` |
| Connection timeout | API not responding | Sync skipped; scans stay `pending` |
| Status != 200 | API error | Sync skipped; scans stay `pending` |

### Batch Upload Failures

| Error | Cause | Client Action |
|-------|-------|---------------|
| 401 Unauthorized | Invalid/expired API key | Scans marked `failed`; must fix key in `config.py` |
| 400 Bad Request | Invalid request format | Scans marked `failed`; check timestamp format |
| 5xx Server Error | API server issue | Scans marked `failed`; may retry later manually |
| Timeout (>10s) | Network slow/broken | Scans marked `failed` |

**Recovery**: Failed scans remain in SQLite with `sync_status = "failed"`. Use `tests/reset_failed_scans.py` to reset them back to `pending` for retry.

---

## Idempotency Guarantees

The API uses idempotency keys to guarantee that duplicate batch uploads won't create duplicate records:

**Scenario**: Network connection drops after client sends batch, then reconnects and resends the same batch.

**Without Idempotency**: Same 100 scans saved twice (200 total).

**With Idempotency**: First batch saved (100), second batch rejected as duplicates (0 new, 100 duplicates).

**Key Format**: `{station_name}-{badge_id}-{local_id}`
- `station_name`: Station where scan occurred
- `badge_id`: Employee badge ID
- `local_id`: Unique ID from client's SQLite (ensures uniqueness even for same badge at same station)

---

## Sync Status Lifecycle (Client-Side Database)

Each scan in the client's SQLite has a `sync_status` field:

```
pending → synced
       ↘ failed
```

| Status | Meaning | Sync Behavior |
|--------|---------|--------------|
| `pending` | Not yet uploaded | Included in next batch |
| `synced` | Successfully uploaded | Skipped in future syncs |
| `failed` | Upload failed (network/API error) | Not retried automatically; manual retry required |

---

## Configuration (client/config.py)

```python
# Cloud API Endpoint
CLOUD_API_URL = "https://trackattendance-api-969370105809.asia-southeast1.run.app"

# API Authentication Key
CLOUD_API_KEY = "your-api-key-here"

# Batch size (scans per upload)
CLOUD_SYNC_BATCH_SIZE = 100

# Connection timeout (seconds)
AUTO_SYNC_CONNECTION_TIMEOUT = 5
```

---

## Testing

### Manual API Test

```bash
# Test connectivity
python -c "from sync import SyncService; from config import *; s = SyncService(None, CLOUD_API_URL, CLOUD_API_KEY); print(s.test_connection())"

# Should output: (True, 'Connected to cloud API')
```

### Automated Test Scripts

```bash
# Test connectivity scenarios
python tests/test_connection_scenarios.py

# Test batch sync
python tests/test_batch_sync.py

# Test production sync (live)
python tests/test_production_sync.py

# Debug sync performance
python tests/debug_sync_performance.py
```

---

## Version & Status

- **Current API Version**: v1
- **Status**: Production (Live on Cloud Run)
- **Last Updated**: December 2025

---

## Related Documentation

- **Desktop Client**: See [README.md](README.md) — Cloud Synchronization section
- **Stress Testing**: See [README.md](README.md) — Testing & Utilities section
- **Backend Code**: https://github.com/Jarkius/trackattendance-api
- **Local Development**: Edit `config.py` to point to local API (`http://localhost:5000`)
