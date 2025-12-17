# TrackAttendance Cloud API Documentation

**API Repository**: https://github.com/Jarkius/trackattendance-api (Private Repository)
**API Status**: Production (Deployed on Google Cloud Run)
**Endpoint**: `https://trackattendance-api-969370105809.asia-southeast1.run.app`
**Hosting**: Google Cloud Run (asia-southeast1 region)
**Access**: Private repository — requires GitHub access permissions to view backend code

## Overview

The TrackAttendance API is a RESTful backend service that receives and stores attendance scan records from desktop clients. It uses bearer token authentication and provides idempotency guarantees to prevent duplicate processing.

## Security

**Backend Code Access**:
- Source code is stored in a private GitHub repository
- Only authorized team members can view/modify backend code
- Production API is deployed on Google Cloud Run with industry-standard security

**API Endpoint Security**:
- Health check endpoint (`GET /`) is public (no authentication required)
- All data upload endpoints (`POST /v1/scans/batch`) require Bearer token authentication
- Invalid or missing tokens will receive a `401 Unauthorized` response
- API keys are stored securely in `config.py` and never committed to the desktop client repository

**Data Protection**:
- Only badge ID, station name, timestamp, and matched flag are synced (no employee names or personal data)
- All communication uses HTTPS (TLS encryption in transit)
- Idempotency keys prevent duplicate records even if network requests are retried

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

## Deployment: Updating API Key on Cloud Run

When rotating or updating the API key (e.g., when using a new service account), the backend's `API_KEY` environment variable must be updated on Google Cloud Run:

### Update via gcloud CLI

```bash
gcloud run deploy trackattendance-api \
  --update-env-vars API_KEY=trackattendance-api-service-ac@trackattendance-20251014.iam.gserviceaccount.com
```

### Update via Cloud Console

1. Go to https://console.cloud.google.com/run
2. Click on the "trackattendance-api" service
3. Click "Edit & Deploy New Revision"
4. Find the "Environment variables" section
5. Update the `API_KEY` value
6. Click "Deploy"

### Verify the Update

```bash
# Check that the environment variable is set correctly
gcloud run services describe trackattendance-api \
  --format='value(spec.template.spec.containers[0].env[name=API_KEY].value)'

# Test with the new key
curl -X POST https://trackattendance-api-969370105809.asia-southeast1.run.app/v1/scans/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer trackattendance-api-service-ac@trackattendance-20251014.iam.gserviceaccount.com" \
  -d '{"events":[]}'

# Expected response: 200 OK
```

### Important Security Notes

- **Never hardcode API keys** in the backend code
- **Always use environment variables** for credentials (Cloud Run automatically supports this)
- **Rotate keys periodically** and update both the backend and client configuration
- **Ensure the old key is revoked** after deploying with the new key
- Desktop clients will receive `401 Unauthorized` until they are updated with the new key

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

---

### 3. Dashboard Stats

**Endpoint**: `GET /v1/dashboard/stats`

**Purpose**: Retrieve multi-station attendance statistics for dashboard display.

**Authentication**: Required (Bearer token)

**Request Headers**:
```
Authorization: Bearer <API_KEY>
```

**Response** (Success - HTTP 200):
```json
{
  "total_scans": 350,
  "unique_badges": 285,
  "stations": [
    {
      "name": "Main Gate",
      "scans": 180,
      "unique": 150,
      "last_scan": "2025-12-15T08:45:30Z"
    },
    {
      "name": "Side Entrance",
      "scans": 170,
      "unique": 135,
      "last_scan": "2025-12-15T08:44:15Z"
    }
  ]
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `total_scans` | integer | Total number of scan events across all stations |
| `unique_badges` | integer | Number of unique badge IDs scanned (deduplicated across all stations) |
| `stations` | array | Per-station breakdown |
| `stations[].name` | string | Station name |
| `stations[].scans` | integer | Total scans at this station |
| `stations[].unique` | integer | Unique badges at this station |
| `stations[].last_scan` | string (ISO 8601) | Timestamp of most recent scan at this station |

---

### 4. Dashboard Export

**Endpoint**: `GET /v1/dashboard/export`

**Purpose**: Retrieve detailed scan records for Excel export functionality.

**Authentication**: Required (Bearer token)

**Request Headers**:
```
Authorization: Bearer <API_KEY>
```

**Response** (Success - HTTP 200):
```json
{
  "scans": [
    ["101117", "Main Gate", "2025-12-15T08:30:00Z", true],
    ["102345", "Side Entrance", "2025-12-15T08:31:15Z", true],
    ["999999", "Main Gate", "2025-12-15T08:32:00Z", false]
  ]
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `scans` | array of arrays | Each inner array represents one scan record with 4 elements |
| `scans[][0]` | string | Badge ID that was scanned |
| `scans[][1]` | string | Station name where scan occurred |
| `scans[][2]` | string (ISO 8601) | Timestamp when scan occurred (UTC) |
| `scans[][3]` | boolean | Whether badge was matched in employee roster |

**Note**: The client matches badge IDs against the local employee database to enrich with employee names, Business Units (SL L1 Desc), and positions before exporting to Excel.

---

## Version & Status

- **Current API Version**: v1
- **Status**: Production (Live on Cloud Run)
- **Last Updated**: December 2025

---

## Related Documentation

- **Desktop Client**: See [README.md](README.md) — Cloud Synchronization section
- **Stress Testing**: See [README.md](README.md) — Testing & Utilities section
- **Backend Repository** (Private): https://github.com/Jarkius/trackattendance-api
  - To request access, contact the repository owner (@Jarkius)
  - Contains: API server code, database schema, deployment configuration
- **Local Development**: Edit `config.py` to point to local API (`http://localhost:5000`)

## Troubleshooting API Access

**Cannot access the backend repository?**
1. You likely don't have GitHub permissions yet
2. Contact the repository owner to request access
3. Once access is granted, you can clone and run locally

**Connecting to a local API instance:**
```python
# In config.py, change:
CLOUD_API_URL = "http://localhost:5000"  # Local development
# or
CLOUD_API_URL = "https://trackattendance-api-969370105809.asia-southeast1.run.app"  # Production
```
