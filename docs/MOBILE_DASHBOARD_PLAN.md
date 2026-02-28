# Mobile Dashboard Implementation Plan

This document outlines the plan to implement a mobile-friendly online dashboard for TrackAttendance.

**Created**: 2026-02-27
**Status**: Planning

---

## Executive Summary

Build a Progressive Web App (PWA) dashboard that allows managers to view attendance statistics from any device (mobile, tablet, desktop) without needing the desktop kiosk app.

---

## Current State Analysis

### Existing Infrastructure

| Component | Technology | Status |
|-----------|------------|--------|
| **Backend API** | Cloud Run (trackattendance-api) | Production |
| **Database** | PostgreSQL (Neon) | Production |
| **Authentication** | Bearer Token (API Key) | Production |
| **Desktop App** | PyQt6 + QWebEngineView | Production |

### Available API Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/` | GET | None | Health check |
| `/v1/dashboard/stats` | GET | Bearer | Multi-station statistics |
| `/v1/dashboard/export` | GET | Bearer | Detailed scan records |
| `/v1/scans/batch` | POST | Bearer | Upload scans (kiosk only) |

### Current Dashboard Data

```json
{
  "total_scans": 350,
  "unique_badges": 285,
  "stations": [
    {"name": "Main Gate", "scans": 180, "unique": 150, "last_scan": "2025-12-15T08:45:30Z"}
  ],
  "last_updated": "2025-12-15T09:00:00Z"
}
```

---

## Proposed Architecture

### Option A: Static PWA (Recommended)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Mobile PWA    │────▶│   Cloud Run API  │────▶│  PostgreSQL     │
│  (Static Host)  │     │  (Existing)      │     │  (Neon)         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       │
       ▼
┌─────────────────┐
│  Cloudflare     │
│  Pages/Vercel   │
└─────────────────┘
```

**Pros:**
- Zero backend changes needed
- Free hosting (Cloudflare Pages, Vercel, Netlify)
- Automatic HTTPS, CDN, edge caching
- Simple deployment (git push)

**Cons:**
- API key exposed in browser (need API changes for user auth)
- No server-side rendering

### Option B: Add Web Auth to Existing API

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Mobile PWA    │────▶│   Cloud Run API  │────▶│  PostgreSQL     │
│                 │     │  + Auth Routes   │     │  + Users Table  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Pros:**
- Proper user authentication (email/password or SSO)
- Per-user permissions possible
- API key stays secure on server

**Cons:**
- Requires backend changes
- Need to manage user accounts

### Option C: BFF (Backend for Frontend)

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Mobile PWA    │────▶│   BFF Service    │────▶│   Cloud Run API  │
│                 │     │  (Auth + Proxy)  │     │   (Existing)     │
└─────────────────┘     └──────────────────┘     └──────────────────┘
```

**Pros:**
- No changes to existing API
- Clean separation of concerns
- Can add caching, rate limiting

**Cons:**
- Additional service to maintain
- More infrastructure cost

---

## Recommended Approach: Option A (Static PWA)

Since there's no confidential data, we can deploy a simple static PWA that calls the existing API directly. No authentication needed.

### Single Phase: Static PWA with Existing API

Deploy a read-only dashboard that uses the existing API. The API key can be embedded at build time since the data is not sensitive.

---

## Technology Stack

### Frontend (PWA)

| Category | Technology | Rationale |
|----------|------------|-----------|
| **Framework** | React 18 + TypeScript | Industry standard, great mobile support |
| **Styling** | Tailwind CSS | Mobile-first, utility classes |
| **State** | Zustand | Lightweight, simple API |
| **Charts** | Recharts | React-native, responsive |
| **Build** | Vite | Fast builds, PWA plugin |
| **PWA** | vite-plugin-pwa | Service worker, offline |

### Hosting Options

| Provider | Free Tier | Custom Domain | Build Time |
|----------|-----------|---------------|------------|
| **Cloudflare Pages** | Unlimited | Yes | Fast |
| **Vercel** | 100GB/mo | Yes | Very Fast |
| **Netlify** | 100GB/mo | Yes | Fast |
| **GitHub Pages** | Unlimited | Yes | Slow |
| **Firebase Hosting** | 10GB/mo | Yes | Medium |

**Recommendation**: **Cloudflare Pages** for best performance and free tier.

---

## Feature Specification

### MVP Features (Phase 1)

#### 1. Dashboard View
- [ ] Total registered employees
- [ ] Total scanned (unique badges)
- [ ] Attendance rate percentage
- [ ] Real-time last updated timestamp

#### 2. Station Breakdown
- [ ] List all stations
- [ ] Scans per station
- [ ] Unique badges per station
- [ ] Last scan time per station
- [ ] Visual bar/pie chart

#### 3. Business Unit View
- [ ] BU-level attendance rates
- [ ] Registered vs scanned per BU
- [ ] Sort by attendance rate

#### 4. Mobile-First UI
- [ ] Responsive design (320px - 1920px)
- [ ] Touch-friendly (44px tap targets)
- [ ] Pull-to-refresh
- [ ] Bottom navigation

#### 5. PWA Features
- [ ] Installable (Add to Home Screen)
- [ ] Offline indicator
- [ ] App-like experience

### Phase 2 Features

#### 6. Export
- [ ] Download Excel report
- [ ] Share via native share API
- [ ] Email report option

#### 8. Real-time Updates
- [ ] Auto-refresh interval (30s/60s/5m)
- [ ] Push notifications for milestones
- [ ] Live scan counter

### Phase 3 Features (Future)

#### 9. Advanced Analytics
- [ ] Historical trends (daily/weekly)
- [ ] Comparison with previous events
- [ ] Peak hour analysis

#### 10. Multi-Event Support
- [ ] Switch between events
- [ ] Archive past events

---

## UI/UX Design

### Mobile Layout (< 768px)

```
┌────────────────────────┐
│  TrackAttendance   ☰  │  ← Header with menu
├────────────────────────┤
│                        │
│   ┌────────────────┐   │
│   │    285/500     │   │  ← Main stat card
│   │   Attendance   │   │
│   │     57.0%      │   │
│   └────────────────┘   │
│                        │
│   ┌──────┐ ┌──────┐   │
│   │ 350  │ │  3   │   │  ← Secondary stats
│   │Scans │ │Stns  │   │
│   └──────┘ └──────┘   │
│                        │
│   ── Stations ──       │
│   ┌────────────────┐   │
│   │ Main Gate  150 │   │  ← Station cards
│   │ Last: 08:45    │   │
│   └────────────────┘   │
│   ┌────────────────┐   │
│   │ Side Gate   80 │   │
│   │ Last: 08:30    │   │
│   └────────────────┘   │
│                        │
├────────────────────────┤
│  📊   🏢   📤   ⚙️    │  ← Bottom nav
└────────────────────────┘
```

### Tablet/Desktop Layout (≥ 768px)

```
┌─────────────────────────────────────────────┐
│  TrackAttendance          Last: 09:00  ⚙️  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │  285    │ │  350    │ │  57.0%  │       │
│  │Attended │ │ Scans   │ │  Rate   │       │
│  └─────────┘ └─────────┘ └─────────┘       │
│                                             │
│  ┌──────────────────┐ ┌──────────────────┐ │
│  │    Stations      │ │  Business Units  │ │
│  │  ┌────┐ ┌────┐   │ │  IT: 85%         │ │
│  │  │Main│ │Side│   │ │  HR: 72%         │ │
│  │  │150 │ │ 80 │   │ │  Sales: 45%      │ │
│  │  └────┘ └────┘   │ │                  │ │
│  └──────────────────┘ └──────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

---

## API Changes Required

### New Endpoint: Dashboard PIN Auth (Phase 2)

```
POST /v1/dashboard/auth
Content-Type: application/json

{
  "pin": "1234"
}

Response (200):
{
  "token": "eyJ...",
  "expires_in": 1800
}

Response (401):
{
  "error": "Invalid PIN"
}
```

### Environment Variable

```env
DASHBOARD_VIEW_PIN=1234
DASHBOARD_TOKEN_EXPIRY_SECONDS=1800
```

---

## Project Structure

```
trackattendance-dashboard/
├── public/
│   ├── manifest.json      # PWA manifest
│   ├── icons/             # App icons (192, 512)
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── Dashboard.tsx
│   │   ├── StationCard.tsx
│   │   ├── BUChart.tsx
│   │   ├── StatCard.tsx
│   │   └── Layout.tsx
│   ├── hooks/
│   │   ├── useDashboard.ts
│   │   └── useAuth.ts
│   ├── services/
│   │   └── api.ts
│   ├── stores/
│   │   └── dashboardStore.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

---

## Implementation Timeline

### Week 1: Setup & Basic Dashboard

| Day | Task |
|-----|------|
| 1 | Create Vite + React + TypeScript project |
| 2 | Setup Tailwind, Zustand, API service |
| 3 | Build StatCard, Layout components |
| 4 | Implement Dashboard with mock data |
| 5 | Connect to real API, test mobile |

### Week 2: Polish & Deploy

| Day | Task |
|-----|------|
| 6 | Add StationCard, BU breakdown |
| 7 | Implement charts (Recharts) |
| 8 | Add PWA manifest, service worker |
| 9 | Deploy to Cloudflare Pages |
| 10 | Testing, bug fixes |

### Week 3: Auth & Features (Phase 2)

| Day | Task |
|-----|------|
| 11 | Add PIN auth endpoint to API |
| 12 | Implement auth UI in dashboard |
| 13 | Add auto-refresh, pull-to-refresh |
| 14 | Add Excel export via API |
| 15 | Final testing, documentation |

---

## Hosting Setup (Cloudflare Pages)

### 1. Create Project

```bash
# In new repo: trackattendance-dashboard
npm create vite@latest . -- --template react-ts
npm install
```

### 2. Configure Build

```toml
# wrangler.toml (optional)
name = "trackattendance-dashboard"
compatibility_date = "2024-01-01"

[site]
bucket = "./dist"
```

### 3. Deploy

```bash
# Connect to Cloudflare Pages via GitHub
# Auto-deploys on push to main

# Or manual deploy:
npx wrangler pages deploy dist
```

### 4. Environment Variables

Set in Cloudflare Pages dashboard:
```
VITE_API_URL=https://trackattendance-api-xxx.run.app
VITE_API_KEY=xxx  # Only for MVP, remove in Phase 2
```

---

## Security Considerations

### MVP (Phase 1)
- API key stored in environment variable (build-time)
- Dashboard is read-only (no mutations)
- Consider: Rate limiting on API
- Consider: IP allowlist for dashboard

### Phase 2 (With Auth)
- PIN hashed with bcrypt on server
- JWT tokens with short expiry (30 min)
- CSRF protection
- Audit logging for dashboard access

### Phase 3 (Production)
- SSO integration (Google Workspace, Azure AD)
- Role-based access (admin, viewer)
- Per-event permissions

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time to First Paint | < 1.5s |
| Lighthouse Performance | > 90 |
| Lighthouse PWA | 100 |
| Mobile Usability | 100 |
| API Response Time | < 500ms |
| Offline Capability | Basic (cached stats) |

---

## Cost Estimate

| Item | Monthly Cost |
|------|--------------|
| Cloudflare Pages | $0 (free tier) |
| Domain (optional) | ~$1/month |
| Cloud Run API | Existing |
| Neon PostgreSQL | Existing |
| **Total** | **~$0-1/month** |

---

## Next Steps

1. [ ] Approve this plan
2. [ ] Create new repo: `Jarkius/trackattendance-dashboard`
3. [ ] Initialize Vite + React + TypeScript project
4. [ ] Set up Cloudflare Pages deployment
5. [ ] Implement MVP dashboard
6. [ ] Test on mobile devices
7. [ ] Deploy to production

---

## Appendix: API Response Examples

### GET /v1/dashboard/stats

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
      "name": "Side Gate",
      "scans": 120,
      "unique": 100,
      "last_scan": "2025-12-15T08:30:00Z"
    },
    {
      "name": "VIP Entrance",
      "scans": 50,
      "unique": 35,
      "last_scan": "2025-12-15T07:15:00Z"
    }
  ],
  "last_updated": "2025-12-15T09:00:00Z"
}
```

### GET /v1/dashboard/export

```json
{
  "scans": [
    ["ABC123", "Main Gate", "2025-12-15T08:45:30Z", true],
    ["DEF456", "Side Gate", "2025-12-15T08:30:00Z", true],
    ["UNKNOWN", "Main Gate", "2025-12-15T08:00:00Z", false]
  ],
  "total": 350,
  "page": 1,
  "per_page": 100
}
```

---

*Document generated by Claude Code*
