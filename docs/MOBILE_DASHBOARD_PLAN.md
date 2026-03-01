# Mobile Dashboard

**Updated**: 2026-03-01
**Status**: Implemented

> This document supersedes the original planning document (created 2026-02-27). It reflects what was actually built.

---

## What Was Built

The mobile dashboard is a **single static HTML file** served directly by the cloud API. There is no separate frontend project, no React/Vite stack, and no external hosting provider required.

| Decision | Chosen approach | Rationale |
|----------|----------------|-----------|
| Hosting | Served from Cloud Run via `@fastify/static` | No separate deployment, zero extra cost |
| Auth | None | Data is non-sensitive; rate limiting is sufficient |
| Tech | Vanilla HTML/CSS/JS | No build step, no dependencies, easy to maintain |
| Refresh | Polling every 30 seconds | Simple, reliable, no WebSocket complexity |

---

## File Location

```
cloud-api/
└── public/
    └── index.html    ← The entire mobile dashboard
```

Served by `@fastify/static` at the root of the Cloud Run API. Accessible at:

```
https://<cloud-run-url>/
```

---

## Data Source

The dashboard polls a single public endpoint:

```
GET /v1/dashboard/public/stats
```

- **Auth required**: No
- **Rate limit**: 30 requests per minute (per IP)
- **Poll interval**: Every 30 seconds (client-side `setInterval`)

### Response shape

```json
{
  "attendance_rate": 72.4,
  "scanned": 362,
  "total_registered": 500,
  "business_units": [
    {"name": "Engineering", "registered": 120, "scanned": 95},
    {"name": "Sales", "registered": 95, "scanned": 61},
    {"name": "HR", "registered": 40, "scanned": 32}
  ],
  "stations": [
    {"name": "Main Gate", "scans": 210},
    {"name": "Side Gate", "scans": 152}
  ],
  "last_updated": "2026-02-27T09:15:00Z"
}
```

---

## What the Dashboard Shows

| Section | Detail |
|---------|--------|
| Attendance rate | Percentage of registered employees scanned |
| Scanned / total | Absolute counts (e.g. 362 / 500) |
| Per-BU breakdown | Each business unit: registered count + scanned count |
| Per-station counts | Scan count per kiosk station |
| Last updated | Timestamp from API response |

The BU registered counts come from the **roster summary** synced by the desktop kiosk (see below). Without a roster summary sync the BU registered counts will be absent or zero.

---

## Roster Summary Sync

The desktop kiosk syncs a roster summary to the cloud so the dashboard has registered-employee counts per BU. This is the only way the public stats endpoint knows how many people are expected per business unit.

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

**Deduplication**: The kiosk computes a SHA256 hash of the payload before POSTing. If the hash matches the last accepted hash, the POST is skipped. The cloud API also returns `204` (no change) if the hash is unchanged.

**Trigger**: The first successful health check response from the cloud API triggers the initial sync. Subsequent syncs happen whenever the roster changes (new import) or the hash changes.

See [SYNC.md](SYNC.md) for the full `sync_roster_summary_from_data()` flow.

---

## Security

- No authentication required to view the dashboard.
- Rate limited at **30 requests per minute** per IP on the `/v1/dashboard/public/stats` endpoint.
- The dashboard is **read-only** — no mutations are possible through this interface.
- No API key is embedded in the HTML.
- Email addresses from the roster are **never included** in any synced payload and never appear in the dashboard.

---

## Original Plan vs What Was Built

The original plan (2026-02-27) proposed a React 18 + TypeScript PWA deployed to Cloudflare Pages. The following changes were made during implementation:

| Original plan | What was built |
|--------------|----------------|
| React 18 + TypeScript + Vite | Vanilla HTML/JS (no build step) |
| Cloudflare Pages hosting | Served by `@fastify/static` from Cloud Run |
| Separate `trackattendance-dashboard` repo | Single `public/index.html` in the API repo |
| PIN auth (Phase 2) | Not needed — rate limiting is sufficient |
| PWA with service worker | Not implemented — polling is sufficient |
| Multiple phases (3 weeks) | Delivered in a single iteration |

The simplified approach eliminates a separate deployment pipeline, removes all frontend build tooling, and keeps the entire mobile experience inside the existing Cloud Run service.

---

*Document updated by Claude Code — reflects implemented state as of 2026-03-01*
