# Mobile Dashboard Implementation Plan

This document outlines the plan to implement a mobile-friendly online dashboard for TrackAttendance with real-time updates via Server-Sent Events (SSE).

**Created**: 2026-02-27
**Updated**: 2026-02-28
**Status**: Planning

---

## Executive Summary

Build a lightweight static dashboard (HTML + vanilla JS) that displays real-time attendance statistics. Updates are pushed via SSE when new scans arrive - no polling needed.

---

## Architecture

```
┌──────────────┐        ┌──────────────────┐        ┌────────────────┐
│   KIOSKS     │        │    CLOUD API     │        │   DASHBOARD    │
│              │        │                  │        │                │
│  Station 1   │──sync──▶ POST /v1/scans  │        │  Cloudflare    │
│  Station 2   │──sync──▶    /batch       │        │    Pages       │
│  Station 3   │        │        │         │        │                │
└──────────────┘        │        ▼         │        │  index.html    │
                        │  ┌──────────┐    │   SSE  │  dashboard.js  │
                        │  │ Postgres │    │◀───────│  style.css     │
                        │  └──────────┘    │        │                │
                        │        │         │        └────────────────┘
                        │        ▼         │               ▲
                        │  broadcast_update│               │
                        │        │         │               │
                        │        ▼         │               │
                        │ GET /v1/dashboard│               │
                        │     /events      │───────────────┘
                        └──────────────────┘      (real-time push)
```

### Data Flow

1. **Kiosk scans badge** → saves locally → syncs to Cloud API
2. **Cloud API receives batch** → saves to PostgreSQL → **broadcasts SSE event**
3. **Dashboard receives SSE** → updates UI instantly (< 1 second latency)

---

## Technology Stack

### Frontend (Simple HTML)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Structure** | HTML5 | No build step, instant deploy |
| **Styling** | Materialize CSS | Same as kiosk app, consistent look |
| **Logic** | Vanilla JS | No dependencies, fast load |
| **Real-time** | EventSource (SSE) | Native browser API, auto-reconnect |
| **Hosting** | Cloudflare Pages | Free, global CDN, fast in Thailand |

### Backend (API Changes)

| Component | Technology | Purpose |
|-----------|------------|---------|
| **SSE Endpoint** | FastAPI + sse-starlette | Push events to dashboards |
| **Event Bus** | In-memory or Redis | Broadcast to all connections |

---

## Project Structure

```
mobile-dashboard/
├── index.html          # Single page dashboard
├── css/
│   └── style.css       # Custom styles (extends Materialize)
├── js/
│   └── dashboard.js    # SSE connection + UI updates
├── manifest.json       # PWA support (add to home screen)
├── icons/
│   ├── icon-192.png
│   └── icon-512.png
└── _headers            # Cloudflare headers (CORS, cache)
```

---

## SSE Implementation

### API Endpoint (trackattendance-api)

```python
# Add to trackattendance-api/app/routes/dashboard.py

from sse_starlette.sse import EventSourceResponse
import asyncio
from typing import Set

# Connected dashboard clients
connected_clients: Set[asyncio.Queue] = set()

@router.get("/v1/dashboard/events")
async def dashboard_events():
    """SSE endpoint for real-time dashboard updates."""
    queue = asyncio.Queue()
    connected_clients.add(queue)

    async def event_generator():
        try:
            # Send initial stats immediately
            stats = await get_dashboard_stats()
            yield {
                "event": "init",
                "data": json.dumps(stats)
            }

            # Wait for updates
            while True:
                data = await queue.get()
                yield {
                    "event": "update",
                    "data": json.dumps(data)
                }
        except asyncio.CancelledError:
            connected_clients.discard(queue)
            raise

    return EventSourceResponse(event_generator())


async def broadcast_update(data: dict):
    """Broadcast update to all connected dashboards."""
    for queue in connected_clients:
        await queue.put(data)


# Modify existing batch endpoint
@router.post("/v1/scans/batch")
async def receive_scans(scans: List[ScanCreate]):
    # ... existing save logic ...

    # NEW: Broadcast to dashboards
    stats = await get_dashboard_stats()
    await broadcast_update(stats)

    return {"ok": True, "synced": len(scans)}
```

### Dashboard JavaScript

```javascript
// mobile-dashboard/js/dashboard.js

class DashboardSSE {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
        this.eventSource = null;
        this.reconnectDelay = 1000;
    }

    connect() {
        this.eventSource = new EventSource(`${this.apiUrl}/v1/dashboard/events`);

        this.eventSource.addEventListener('init', (e) => {
            const data = JSON.parse(e.data);
            this.updateUI(data);
            this.setStatus('connected');
        });

        this.eventSource.addEventListener('update', (e) => {
            const data = JSON.parse(e.data);
            this.updateUI(data);
            this.flashUpdate();
        });

        this.eventSource.onerror = () => {
            this.setStatus('reconnecting');
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
        };

        this.eventSource.onopen = () => {
            this.reconnectDelay = 1000;
        };
    }

    updateUI(data) {
        document.getElementById('total-scanned').textContent =
            data.unique_badges.toLocaleString();
        document.getElementById('total-scans').textContent =
            data.total_scans.toLocaleString();
        document.getElementById('attendance-rate').textContent =
            data.attendance_rate + '%';
        document.getElementById('last-updated').textContent =
            new Date().toLocaleTimeString();

        this.updateStations(data.stations);
    }

    updateStations(stations) {
        const container = document.getElementById('stations-list');
        container.innerHTML = stations.map(s => `
            <div class="col s12 m6 l4">
                <div class="card-panel">
                    <span class="station-name">${s.name}</span>
                    <span class="station-count">${s.unique}</span>
                    <span class="station-time">Last: ${this.formatTime(s.last_scan)}</span>
                </div>
            </div>
        `).join('');
    }

    flashUpdate() {
        document.body.classList.add('flash');
        setTimeout(() => document.body.classList.remove('flash'), 300);
    }

    setStatus(status) {
        const el = document.getElementById('connection-status');
        el.className = `status-${status}`;
        el.textContent = status === 'connected' ? '● Live' : '○ Reconnecting...';
    }

    formatTime(iso) {
        if (!iso) return '--';
        return new Date(iso).toLocaleTimeString();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardSSE(window.CONFIG.API_URL);
    dashboard.connect();
});
```

---

## Dashboard HTML

```html
<!-- mobile-dashboard/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrackAttendance Dashboard</title>
    <link rel="manifest" href="manifest.json">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css">
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <nav class="green darken-2">
        <div class="nav-wrapper container">
            <span class="brand-logo">TrackAttendance</span>
            <span id="connection-status" class="right status-connecting">○ Connecting...</span>
        </div>
    </nav>

    <div class="container">
        <!-- Main Stats -->
        <div class="row">
            <div class="col s6 m4">
                <div class="card-panel center-align">
                    <i class="material-icons medium green-text">people</i>
                    <h4 id="total-scanned">--</h4>
                    <p>Scanned</p>
                </div>
            </div>
            <div class="col s6 m4">
                <div class="card-panel center-align">
                    <i class="material-icons medium blue-text">qr_code_scanner</i>
                    <h4 id="total-scans">--</h4>
                    <p>Total Scans</p>
                </div>
            </div>
            <div class="col s12 m4">
                <div class="card-panel center-align">
                    <i class="material-icons medium orange-text">trending_up</i>
                    <h4 id="attendance-rate">--%</h4>
                    <p>Attendance Rate</p>
                </div>
            </div>
        </div>

        <!-- Stations -->
        <h5>Stations</h5>
        <div class="row" id="stations-list">
            <!-- Populated by JavaScript -->
        </div>

        <!-- Footer -->
        <p class="grey-text center-align">
            Last updated: <span id="last-updated">--</span>
        </p>
    </div>

    <script>
        window.CONFIG = {
            API_URL: 'https://your-api.run.app'  // Set at deploy time
        };
    </script>
    <script src="js/dashboard.js"></script>
</body>
</html>
```

---

## API Changes Required

### 1. Add SSE Dependency

```bash
# In trackattendance-api
pip install sse-starlette
```

### 2. Add SSE Endpoint

Add `/v1/dashboard/events` endpoint (code shown above).

### 3. Modify Batch Endpoint

Call `broadcast_update()` after saving scans.

### 4. CORS Configuration

```python
# Allow SSE connections from dashboard domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.trackattendance.app"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

---

## Deployment

### Dashboard (Cloudflare Pages)

```bash
# Create repo and push
git init mobile-dashboard
cd mobile-dashboard
# ... add files ...
git add .
git commit -m "Initial dashboard"
git push origin main

# Connect to Cloudflare Pages
# Settings:
#   Build command: (none)
#   Output directory: /
#   Environment: API_URL=https://your-api.run.app
```

### API (Cloud Run)

```bash
# Update trackattendance-api
pip install sse-starlette
# Add SSE endpoint
# Deploy to Cloud Run
```

---

## Performance Impact

| Component | Impact | Mitigation |
|-----------|--------|------------|
| Kiosk | None | SSE is server-side only |
| API CPU | +5% per 50 connections | Async non-blocking |
| API Memory | ~10KB per connection | Limit max connections |
| Database | None | Broadcast from memory |
| Network | Minimal | SSE is text-based |

### Connection Limits

```python
MAX_SSE_CONNECTIONS = 100

@router.get("/v1/dashboard/events")
async def dashboard_events():
    if len(connected_clients) >= MAX_SSE_CONNECTIONS:
        raise HTTPException(503, "Too many connections")
    # ... rest of code
```

---

## Fallback: Polling Mode

If SSE fails, dashboard falls back to polling:

```javascript
// In dashboard.js
connect() {
    try {
        this.eventSource = new EventSource(...);
    } catch (e) {
        // Fallback to polling
        this.startPolling();
    }
}

startPolling() {
    setInterval(async () => {
        const res = await fetch(`${this.apiUrl}/v1/dashboard/stats`);
        const data = await res.json();
        this.updateUI(data);
    }, 15000);
}
```

---

## Timeline

| Day | Task |
|-----|------|
| 1 | Create mobile-dashboard repo with HTML/CSS/JS |
| 2 | Add SSE endpoint to trackattendance-api |
| 3 | Test SSE connection locally |
| 4 | Deploy dashboard to Cloudflare Pages |
| 5 | Deploy API changes to Cloud Run |
| 6 | End-to-end testing |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Update latency | < 1 second |
| Page load time | < 2 seconds |
| Lighthouse score | > 90 |
| Max concurrent dashboards | 100 |
| Reconnect time | < 5 seconds |

---

## Next Steps

1. [x] Approve SSE approach
2. [ ] Create `mobile-dashboard/` folder with static files
3. [ ] Add SSE endpoint to `trackattendance-api`
4. [ ] Deploy and test
5. [ ] Create GitHub repo for dashboard

---

*Document updated by Claude Code*
