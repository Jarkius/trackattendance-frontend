# TrackAttendance Commercialization Plan

> From internal tool to sellable product with licensing, payments, and anti-piracy.

---

## Market Analysis & Opportunity

### The Problem We Solve

| Pain Point | Who Feels It | Current "Solution" | Why It Fails |
|------------|-------------|-------------------|-------------|
| **Manual sign-in sheets** | Event managers, HR | Paper + Excel | Slow, error-prone, no real-time visibility |
| **Buddy punching** | Factories, warehouses | Biometric ($$$) | Expensive hardware, privacy concerns, queue bottlenecks |
| **No offline capability** | Remote/outdoor events | Cloud-only apps | Dead zones = lost data, no scanning |
| **Multi-site attendance gaps** | Training orgs, schools | Separate systems per site | No unified view, duplicates across locations |
| **Expensive attendance kiosks** | SMBs, nonprofits | Enterprise solutions ($500+/mo) | Overkill for simple badge-in/badge-out |
| **IT setup complexity** | Non-technical admins | Custom dev or spreadsheets | No out-of-box solution that "just works" |

### Market Size & Sales Potential

| Segment | TAM (Est.) | Our Niche | Why We Win |
|---------|-----------|-----------|-----------|
| **Event check-in** | $2.1B global (events tech) | Badge/QR kiosk check-in | Offline-first, instant setup, $19/station vs $200+ competitors |
| **Workforce attendance** | $4.3B (time & attendance) | Factory/warehouse shift logging | No biometrics needed, works in dead zones, per-badge tracking |
| **Training & education** | $890M (LMS/attendance) | Class/session attendance | Auto-reports, multi-room sync, Excel export |
| **Coworking & membership** | $380M (space mgmt) | Member presence tracking | Real-time dashboard, mobile-friendly, low cost |

**Realistic Year 1 target**: 50-100 paying customers × 3-5 stations avg × $15-19/station/mo = **$27K-$114K ARR**

### Competitive Landscape

| Competitor | Price | Offline? | Multi-Station? | Our Advantage |
|-----------|-------|---------|---------------|--------------|
| **CodeREADr** | ~$25/device/mo | Limited | Yes | We're cheaper, offline-first, simpler |
| **EventMobi** | $1,500+/event | No | Yes | We're 10x cheaper, works without WiFi |
| **Clockify** | $4-12/user/mo | No | No | We're per-station not per-user, offline |
| **Fully Kiosk** | €8 perpetual | Yes | No | We have cloud sync + multi-station |
| **BambooHR** | $8/employee/mo | No | No | We're specialized, not bloated HR suite |
| **Envoy** | $119-359/location/mo | No | Yes | We're 6-18x cheaper per location |
| **ProxyClick/Eptura** | $100-300/location/mo | No | Yes | We're 5-15x cheaper |
| **SwipedOn** | $55-169/mo | No | No | We have multi-station + offline |
| **Bizzabo** | ~$15K-18K/year | No | Yes | We're 15-20x cheaper for SMBs |
| **Cvent** | ~$19K-150K/year | No | Yes | Enterprise-only; we serve SMBs |
| **Swoogo** | ~$7.8K-11.8K/year | No | Yes | Seat-based; we're per-station |
| **nunify** | $500-8,000/event | No | Yes | We're per-station not per-event |
| **Deputy** | $4.50-6/user/mo | No | No | Per-user pricing doesn't scale |
| **Kisi** | $199/mo + $599-899 hardware | No | Yes | Expensive hardware required |
| **Jibble** | Free kiosk + paid tiers | Yes | No | No multi-station sync |
| **Manual (paper)** | Free | Yes | No | We're digital with instant reports |

**Key insight**: The market is bifurcated — free/basic tools vs $7,800+/year enterprise. There is **no strong mid-market option at $20-$100/month** with offline + multi-site + badge scanning. That's our gap.

### Buyer Personas

| Persona | Role | Budget Authority | Discovery Channel | Decision Speed |
|---------|------|-----------------|-------------------|----------------|
| **Event Manager** | Plans corporate events, conferences | $500-5,000/event | Google, Capterra, peer referral | Same-day to 1 week |
| **HR Manager** | Employee attendance, compliance | $200-1,000/mo | G2, LinkedIn, vendor outreach | 2-4 weeks |
| **IT Admin** | Deploys/manages kiosk systems | $100-500/mo | Reddit, Stack Overflow, GitHub | 1-2 weeks |
| **Operations Manager** | Factory/warehouse shift tracking | $300-2,000/mo | Industry forums, trade shows | 2-4 weeks |
| **School Administrator** | Student/class attendance | $50-200/mo | Ed-tech forums, peer referral | 1-3 months |

**Buying process**: 73% start with Google search → Capterra/G2 comparison → free trial → purchase. Average evaluation cycle: 2-3 weeks for SMB, 1-3 months for enterprise.

### Customer Pain Points (from market research)

| # | Pain Point | Source | How We Solve It |
|---|-----------|--------|-----------------|
| 1 | **Internet dependency** — most systems crash or lose data without WiFi | G2/Capterra reviews | Offline-first: scans save locally, sync when online |
| 2 | **Expensive per-location pricing** — Envoy at $119-359/location/mo | Competitor pricing | $19/station/mo (6-18x cheaper) |
| 3 | **Complex setup** — weeks of IT integration, custom API work | User reviews | Plug in scanner, run exe, start scanning in 5 minutes |
| 4 | **Per-employee pricing doesn't scale** — $8/employee × 500 employees = $4,000/mo | BambooHR model | Per-station pricing: 5 stations = $95/mo regardless of employee count |
| 5 | **No real-time visibility** — data locked in kiosk until exported | Manual system users | Live mobile dashboard, auto-sync, real-time BU breakdown |
| 6 | **Facial recognition failures** — false positives, registration hassle | Envoy/SwipedOn reviews | Badge scanning: reliable, no biometrics, no privacy concerns |
| 7 | **Per-event pricing too expensive** — $500-8,000 per event | nunify, Cvent | $99-299 per event pack, or subscribe monthly |
| 8 | **Multi-site blind spots** — separate systems, no unified view | Enterprise users | Multi-station sync with cross-station duplicate detection |
| 9 | **Pricing opacity** — actual costs 80% higher than quoted; hidden fees | Bizzabo/Cvent/vFairs reviews | Transparent pricing, no hidden fees, Stripe self-serve |
| 10 | **Steep learning curves** — months of testing + support chat to learn | Cvent users (SpotMe blog) | 5-minute setup: plug scanner, run exe, scan |
| 11 | **Multi-device sync failures** — guest lists break when shared | Grupio blog | Built-in cross-station sync with idempotency keys |
| 12 | **67% of event orgs switching vendors** — dissatisfaction is high | G2 event industry stats | Low switching cost: just change API key |

**Market size**: $3.06-4.53B (2024) → $8.75B by 2032 (6.55% CAGR). SME segment is fastest-growing but least served.

### Key Differentiators (Positioning Statement)

> **TrackAttendance is the only attendance kiosk that works offline, syncs across stations, and costs less than $20/month per station.** No cloud dependency. No per-employee pricing. No biometric hardware. Just plug in a scanner and go.

**Why now**: 67% of event organizers plan to switch vendors within the next year (G2). The $3-9B market is growing at 6.55% CAGR. The gap between free tools and $7,800+/year enterprise platforms has no strong competitor. Offline + affordable + simple setup — no one has nailed all three together.

---

## Market Position

| Aspect | TrackAttendance | Competitors |
|--------|----------------|-------------|
| **Model** | Hybrid: per-station subscription + per-event option | CodeREADr ~$25/device/mo, Fully Kiosk €8 perpetual |
| **Niche** | Offline-first badge kiosk + cloud dashboard | Most competitors are cloud-only |
| **Differentiator** | Works without internet, multi-station sync, mobile dashboard, voice + camera |

### Pricing Strategy

**Subscription (recurring customers)**:

| Tier | Stations | Price | Features |
|------|----------|-------|----------|
| **Free** | 1 | $0 | Local-only, no cloud sync, 500 scans/day |
| **Pro** | 1-5 | $19/station/mo | Cloud sync, dashboard, duplicate detection |
| **Business** | 6-20 | $15/station/mo | + Cross-station dup, priority support |
| **Enterprise** | 21+ | Custom | + SLA, custom branding, on-prem option |

Annual discount: 20% (2 months free).

**Per-event (one-time customers)**:

| Pack | Stations | Price | Duration | Use Case |
|------|----------|-------|----------|----------|
| **Starter Event** | 1-2 | $99 | 7 days | Small meeting, workshop |
| **Standard Event** | 3-5 | $199 | 14 days | Conference, training day |
| **Large Event** | 6-10 | $299 | 30 days | Multi-day expo, company event |

Per-event keys auto-expire. Converts to subscription at 20% discount if they buy within 30 days.

### Regional Pricing (PPP-adjusted)

| Region | Multiplier | Pro Price | Rationale |
|--------|-----------|-----------|-----------|
| **US / EU / AU** | 1.0x | $19/station/mo | Base price |
| **Japan / Korea / Singapore** | 0.8x | $15/station/mo | High GDP but price-sensitive B2B |
| **ASEAN (TH, VN, PH, ID, MY)** | 0.30-0.35x | $6-7/station/mo (฿199-249) | Local purchasing power |
| **India** | 0.25x | $5/station/mo | Volume play |
| **LATAM / Africa** | 0.30x | $6/station/mo | Emerging markets |

Implement via Stripe Checkout `locale` + pricing tiers per currency.

### Trial Strategy

| Element | Detail |
|---------|--------|
| **Type** | 14-day opt-in free trial (requires email, no credit card) |
| **What's included** | Full Pro features, 3 stations, cloud sync |
| **Conversion target** | 18% (B2B SaaS benchmark for low-touch) |
| **Trial → Paid flow** | Day 7: email "halfway through" + key features used. Day 12: "trial ending" + pricing. Day 14: auto-downgrade to Free tier |
| **Why opt-in (no CC)** | Lower friction in ASEAN market where CC penetration is low |

---

## Phase 0: Documentation & API Discovery

### Already Verified (from codebase audit)

**Leverage points — code that already exists and can be extended:**

| Feature | File | What It Does |
|---------|------|-------------|
| Heartbeat timer | `main.py:1396` | Every station phones home regularly — add license check to response |
| Auth middleware | `server.ts:216-236` | Global `onRequest` hook, timing-safe key compare — extend for per-org keys |
| `CLOUD_READ_ONLY` mode | `config.py:99`, `sync.py` guards | Disables all writes — perfect degraded mode for expired licenses |
| `station_heartbeat` table | `server.ts:866` | Tracks all active stations with `last_seen_at` — enforce station limits here |
| `admin_set_monitoring_mode()` | `main.py:1221` | Runtime toggle already wired — server can trigger via heartbeat response |
| Station identity | `database.py:111-122` | Local SQLite station name, no hardware fingerprint yet |

**Stripe APIs to use:**

| API | Purpose | Docs |
|-----|---------|------|
| Stripe Checkout (hosted) | Payment collection | stripe.com/docs/checkout |
| Stripe Subscriptions + Quantities | Per-station billing | stripe.com/docs/billing/subscriptions/quantities |
| Stripe Webhooks (`checkout.session.completed`) | License provisioning | stripe.com/docs/webhooks |
| Stripe Pricing Table (embed) | Zero-code pricing page | stripe.com/docs/payments/checkout/pricing-table |
| Stripe Customer Portal | Self-service upgrades/cancels | stripe.com/docs/customer-management |

**Anti-patterns to avoid:**
- Do NOT use metered billing (station counts don't change hourly)
- Do NOT node-lock to hardware fingerprint (kiosks get replaced, causes support burden)
- Do NOT store license keys in the binary (decompilable)
- Do NOT make licensing block the scan flow (offline-first must still work)

---

## Phase 1: License Database & Server-Side Enforcement

**Goal:** API validates licenses and enforces station limits on every heartbeat.

### 1.1 Add `licenses` table to Postgres

```sql
CREATE TABLE licenses (
    api_key         TEXT PRIMARY KEY,          -- the Bearer token (generated on purchase)
    org_name        TEXT NOT NULL,
    tier            TEXT NOT NULL DEFAULT 'free',  -- free, pro, business, enterprise
    max_stations    INT NOT NULL DEFAULT 1,
    max_scans_day   INT DEFAULT NULL,          -- NULL = unlimited
    expires_at      TIMESTAMPTZ,               -- NULL = perpetual (enterprise)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    stripe_customer TEXT,                       -- Stripe customer ID
    stripe_sub      TEXT,                       -- Stripe subscription ID
    active          BOOLEAN DEFAULT TRUE
);
```

### 1.2 Modify auth middleware in `server.ts`

Current: compares Bearer token against single `API_KEY` env var.
Change to: look up Bearer token in `licenses` table.

```
onRequest hook:
  1. Skip exempt routes (healthz, public dashboard, etc.)
  2. Extract Bearer token
  3. SELECT * FROM licenses WHERE api_key = $token AND active = TRUE
  4. If not found → 401
  5. If expired (expires_at < NOW()) → 403 { error: "license_expired" }
  6. Attach license object to request context (req.license)
```

Keep backward compat: if `API_KEY` env is set, treat it as a master/dev key that bypasses license table.

### 1.3 Enforce station limits on heartbeat

In `POST /v1/stations/heartbeat`:
```
1. Count distinct station_name in station_heartbeat WHERE last_seen_at > NOW() - 5min
2. If incoming station_name is new AND count >= license.max_stations:
   → Return { status: "license_exceeded", max_stations: N, active_stations: N }
3. Otherwise: upsert heartbeat as normal
4. Return { status: "ok", license: { tier, expires_at, stations_used, stations_max } }
```

### 1.4 Frontend reads license status from heartbeat response

In `main.py` `_handle_clear_epoch_and_heartbeat_slot`:
- Parse `license` object from heartbeat response
- If `status == "license_expired"` or `"license_exceeded"`:
  - Set `config.CLOUD_READ_ONLY = True` (uses existing guards)
  - Show status message: "License expired — running in read-only mode"
- If `status == "ok"` and was previously degraded:
  - Restore `config.CLOUD_READ_ONLY = False`

### Verification
- [ ] New station with valid license → heartbeat succeeds, sync works
- [ ] 6th station on a 5-station license → heartbeat returns `license_exceeded`
- [ ] Expired license → heartbeat returns `license_expired`, app enters read-only
- [ ] Renew license → next heartbeat restores full access
- [ ] Master `API_KEY` env var still works (dev/testing)

---

## Phase 2: Stripe Integration & License Provisioning

**Goal:** Customer pays → API key auto-generated → emailed to customer.

### 2.1 Stripe setup (Dashboard, no code)

1. Create Products in Stripe Dashboard:
   - "TrackAttendance Pro" (per-station, $19/mo)
   - "TrackAttendance Business" (per-station, $15/mo)
2. Create Prices with `recurring.usage_type = "licensed"` and quantity enabled
3. Create Pricing Table in Stripe Dashboard → get embed snippet
4. Configure Stripe Webhook endpoint → `POST /v1/webhooks/stripe`

### 2.2 Webhook handler in `server.ts`

New route `POST /v1/webhooks/stripe` (exempt from auth middleware):

```
checkout.session.completed:
  1. Extract customer email, tier from session metadata
  2. Generate API key: crypto.randomBytes(32).toString('hex')
  3. INSERT INTO licenses (api_key, org_name, tier, max_stations, expires_at, stripe_customer, stripe_sub)
  4. Email API key to customer (use Stripe receipt or a simple email service)

invoice.paid:
  1. Find license by stripe_sub
  2. Extend expires_at by 1 month
  3. Update max_stations from subscription quantity

customer.subscription.deleted:
  1. Find license by stripe_sub
  2. Set active = FALSE
```

### 2.3 Idempotency

Store processed `event.id` in a `stripe_events` table to prevent duplicate license generation on webhook retries.

### Verification
- [ ] Test checkout with Stripe test mode → webhook fires → license created in DB
- [ ] License key works as Bearer token for heartbeat
- [ ] Subscription cancellation → license deactivated → station enters read-only
- [ ] Subscription renewal → `expires_at` extended

---

## Phase 3: Landing Page & Sales Site

**Goal:** Single-page site where customers learn about and purchase the product.

### 3.1 Static landing page

Structure (single HTML file, can host on GitHub Pages or Cloudflare Pages):

```
1. Hero: "Badge Attendance Made Simple" + kiosk screenshot
2. Features: 4 cards (Offline-First, Multi-Station Sync, Mobile Dashboard, Voice + Camera)
3. Pricing: Stripe Pricing Table embed (<stripe-pricing-table>)
4. How It Works: 3 steps (Buy → Download → Scan)
5. FAQ: Common questions
6. Footer: Support email, GitHub link
```

### 3.2 Post-purchase flow

After Stripe checkout:
1. Stripe shows success page with receipt
2. Webhook generates license key
3. Customer receives email with:
   - API key
   - Download link for `.exe` (hosted on GitHub Releases or S3)
   - Quick-start guide: "Copy API key into .env, run the app"

### 3.3 Customer portal

Embed Stripe Customer Portal for self-service:
- Add/remove stations (quantity changes)
- Update payment method
- Cancel subscription
- View invoices

### Verification
- [ ] Landing page loads, pricing table renders
- [ ] Checkout flow works end-to-end in test mode
- [ ] Customer can access portal and change station count
- [ ] Download link works after purchase

---

## Phase 4: Binary Compilation & Distribution

**Goal:** Ship a compiled binary that can't easily be reverse-engineered.

### 4.1 Nuitka compilation

```bash
# Install
pip install nuitka

# Compile (Windows target)
nuitka --standalone --onefile \
  --include-data-dir=web=web \
  --include-data-dir=voices=voices \
  --windows-icon-from-ico=web/icon.ico \
  --company-name="TrackAttendance" \
  --product-name="TrackAttendance" \
  --product-version="1.0.0" \
  main.py
```

### 4.2 Distribution

| Channel | Method |
|---------|--------|
| GitHub Releases | Upload `.exe` per version, link from landing page |
| Direct download | S3/R2 bucket with signed URLs (expires after X downloads) |
| Auto-updater | Future: check GitHub releases API on startup for new versions |

### 4.3 Free tier binary

Same binary, but without `CLOUD_API_KEY` in `.env`:
- App runs in local-only mode
- Cloud features are locked (sync, dashboard, cross-station dup)
- Admin panel shows "Upgrade to Pro" message

### Verification
- [ ] Nuitka compiles successfully on Windows
- [ ] Compiled binary starts and scans work
- [ ] `.env` with valid API key enables cloud features
- [ ] Without API key, app runs local-only (no crash)

---

## Phase 5: Free Tier & Graceful Degradation

**Goal:** App works without any license for basic local attendance.

### 5.1 Remove `sys.exit(1)` on missing API key

In `config.py`:
- Change from hard exit to warning
- Set `CLOUD_API_KEY = None` if not provided
- All sync code already checks for API key presence

### 5.2 Feature gates

| Feature | Free | Pro | Business |
|---------|------|-----|----------|
| Local scanning | ✅ | ✅ | ✅ |
| Excel export | ✅ | ✅ | ✅ |
| Cloud sync | ❌ | ✅ | ✅ |
| Mobile dashboard | ❌ | ✅ | ✅ |
| Cross-station dup | ❌ | ❌ | ✅ |
| Camera proximity | ❌ | ✅ | ✅ |
| Voice feedback | ✅ | ✅ | ✅ |

### 5.3 Admin panel upgrade prompt

When running without API key or on free tier:
- Settings panel shows current tier and station count
- "Upgrade" button links to landing page
- Cloud-related settings are greyed out with "Pro feature" labels

### Verification
- [ ] App starts without CLOUD_API_KEY (no crash)
- [ ] Local scanning and export work offline
- [ ] Cloud settings show "Pro feature" label
- [ ] Entering a valid API key unlocks cloud features without restart

---

## Phase 6: Marketing & Go-to-Market

### 6.1 Sales channels (priority order)

| Channel | Action | Cost | Expected Impact |
|---------|--------|------|-----------------|
| **Capterra / G2** | Create free product listing with screenshots | Free | Long-tail SEO, buyer trust |
| **Product Hunt** | Launch post with demo video | Free | Initial buzz, early adopters |
| **LinkedIn** | Target HR managers, event coordinators | Organic + $50-200/mo ads | Direct B2B leads |
| **Google Ads** | "attendance kiosk software", "badge scanner attendance" | $200-500/mo | High-intent buyers |
| **YouTube** | Demo video showing setup + scanning | Free | "How to" search traffic |
| **Reddit** | r/eventplanning, r/humanresources, r/sysadmin | Free | Community credibility |
| **AppSumo** | Lifetime deal launch (limited qty) | Revenue share | Volume + reviews |
| **Local events (TH)** | Demo at Thailand tech/HR expos | $200-500 booth | Regional first customers |

### 6.2 Target verticals (expanded)

| Vertical | Pain Point | Pitch | Est. Deal Size | Sales Cycle |
|----------|-----------|-------|----------------|-------------|
| **Corporate events** | Manual sign-in sheets, no real-time count | "Badge scan → instant headcount on your phone" | $199-599/event | Same-day |
| **Factories / warehouses** | Buddy punching, dead zone WiFi | "Per-badge tracking in areas with no internet" | $95-285/mo (5-15 stations) | 1-2 weeks |
| **Coworking spaces** | Member presence unknown | "Know who's in the building, live dashboard" | $57-95/mo (3-5 stations) | 1 week |
| **Schools / training centers** | Class attendance is manual drudgery | "Scan in, auto-report to admin + parents" | $38-95/mo (2-5 stations) | 2-4 weeks |
| **Healthcare** | Staff check-in compliance, audit trails | "Audit trail for every shift, multi-floor sync" | $190-380/mo (10-20 stations) | 2-4 weeks |
| **Religious organizations** | Congregation attendance tracking | "Know who came, generate reports for leadership" | $19-57/mo (1-3 stations) | Same-day |
| **Construction sites** | Worker sign-in for safety compliance | "Badge everyone on-site, export to safety officer" | $57-190/mo (3-10 stations) | 1-2 weeks |
| **Government / military** | Event attendance verification | "Offline-capable, tamper-proof audit trail" | Custom/enterprise | 1-3 months |

### 6.3 Content strategy

- Blog posts: "How to Set Up Badge Attendance in 5 Minutes"
- Case study template: Before/After with a real client
- Demo video: 60-second walkthrough of scan → dashboard flow
- Comparison pages: "TrackAttendance vs EventMobi", "TrackAttendance vs Clockify"
- SEO landing pages: "Best offline attendance kiosk", "Badge scanner for events"
- Localized content: Thai-language landing page for ASEAN market

### 6.4 SEO keywords (high-intent)

**Tier 1: High-intent buyer keywords**

| Keyword | Intent | Competition | Our Angle |
|---------|--------|------------|-----------|
| "attendance kiosk software" | Buy | Low | Direct match |
| "badge scanner attendance" | Buy | Low | Direct match |
| "offline attendance tracking" | Buy | Very Low | **Our killer feature** |
| "event check-in app" | Buy | Medium | Price + offline angle |
| "visitor check-in kiosk" | Buy | Medium | 5-15x cheaper than Envoy/ProxyClick |
| "QR code event check-in" | Buy | Medium | Works with any USB scanner |

**Tier 2: Comparison keywords**

| Keyword | Intent | Competition | Our Angle |
|---------|--------|------------|-----------|
| "Cvent alternative" | Compare | Medium | 15-20x cheaper |
| "Envoy alternative" | Compare | Low | 6x cheaper, offline-first |
| "best event check-in software 2026" | Compare | Medium | Price + simplicity |
| "free attendance tracking software" | Trial | Medium | Free tier landing page |
| "cheap event check-in app" | Compare | Low | $99/event vs $500+ |

**Tier 3: Problem-aware keywords**

| Keyword | Intent | Competition | Our Angle |
|---------|--------|------------|-----------|
| "offline event check-in app" | Buy | Very Low | Zero competitors do this well |
| "event check-in without wifi" | Buy | Very Low | Our #1 differentiator |
| "simple event check-in setup" | Buy | Low | 5-minute setup story |
| "multi-site attendance tracking" | Buy | Low | Cross-station sync |
| "affordable visitor management" | Buy | Low | $19/station vs $119+/location |

**Tier 4: Vertical-specific**

| Keyword | Use Case |
|---------|----------|
| "church attendance software" | Religious orgs |
| "school attendance kiosk" | Education |
| "trade show badge scanner" | Events |
| "factory attendance system" | Manufacturing |
| "coworking visitor management" | Coworking |
| "nonprofit event check-in" | Nonprofits |

Capterra lists 680+ products in time clock, 1,069 in time tracking. SEO opportunity is massive in long-tail vertical keywords.

### 6.5 Customer acquisition cost (CAC) targets

| Channel | Target CAC | Payback Period |
|---------|-----------|----------------|
| Organic (SEO, Product Hunt) | $0-10 | Immediate |
| LinkedIn organic | $20-50 | 1-2 months |
| Google Ads | $50-100 | 2-3 months |
| AppSumo | $0 (revenue share) | Immediate |
| Referral program | $25 (1 month free) | 1 month |

### 6.5 Hardware guidance (no inventory)

| Approach | Details |
|----------|---------|
| **Certified hardware list** | Publish tested barcode scanners ($15-40 USB), tablets, mini PCs on landing page |
| **Affiliate links** | Amazon/Lazada affiliate links for recommended hardware (passive revenue) |
| **"Kiosk in a box" guide** | Blog post: "Build a $100 attendance kiosk" (mini PC + scanner + monitor) |
| **No bundling at launch** | Avoid inventory risk. Let customers buy their own hardware. |

### 6.6 White-label & reseller roadmap

| Phase | Timeline | What |
|-------|---------|------|
| **Direct only** | Launch → 6 months | All sales direct via website |
| **Reseller program** | 6 months | 30% margin for IT integrators who sell to their clients |
| **White-label** | 12-18 months | Rebrandable version for HR/event platforms to embed |

---

## Offline Grace Period

**Problem**: Offline-first product needs to work without internet — but license validation requires the cloud.

| Scenario | Behavior |
|----------|----------|
| **Normal operation** | Heartbeat validates license every cycle (~60s). Last valid response cached locally. |
| **Internet goes down** | App continues with last-known license state. Scans save locally. |
| **Offline for < 30 days** | Full functionality. Cached license trusted. Scans queue for sync. |
| **Offline for > 30 days** | Degrade to Free tier (local-only). Warning shown. Scans still saved locally. |
| **Internet returns** | Heartbeat re-validates. If license still active, restore full access + sync queued scans. |

Implementation: Store `license_validated_at` timestamp in local SQLite. Check age on each scan. Signed license blob (HMAC with server secret) prevents clock tampering.

---

## Anti-Piracy Summary

**"Can they just copy the .exe and use it at the next event?"**

| Scenario | What Happens |
|----------|-------------|
| Copy .exe, same API key | Works until key expires or station limit hit |
| Copy .exe, no API key | Local-only mode (free tier) — no cloud, no dashboard |
| Copy .exe, expired key | Read-only mode on first heartbeat — can't sync scans |
| Share API key with others | Station limit enforced — extra stations get read-only |
| Decompile binary | Nuitka C compilation makes this very difficult |
| Bypass license check | All enforcement is server-side — can't bypass without the cloud |
| Use same key on different laptops | Works — license is station-count-based, not device-locked |

**The value is in the cloud service, not the binary.** The desktop app without a valid subscription is just a basic scanner with no sync, no dashboard, no cross-station features. That's the free tier — let them use it. It's your best marketing tool.

### License Key Design

```
Key format: ta_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (32 hex chars)
Key encodes: nothing — it's a random token. All metadata lives server-side.
Why: No client-side validation to crack. Server is the single source of truth.
```

Each key maps to one row in the `licenses` table with: `tier`, `max_stations`, `expires_at`, `stripe_sub`. Customer uses the same key across all their laptops/kiosks. Station limit enforced by counting distinct `station_name` in heartbeat table.

---

## Implementation Priority

```
Phase 1 (License DB + enforcement)     ████████ ~2 days
Phase 2 (Stripe webhooks)              ████████ ~2 days
Phase 5 (Free tier / graceful degrade) ████     ~1 day
Phase 4 (Nuitka compilation)           ████     ~1 day
Phase 3 (Landing page)                 ████     ~1 day
Phase 6 (Marketing launch)             ████████ ~ongoing
                                       ─────────────────
                                       Total: ~7 days to sellable product
```

## Revenue Projections (Conservative)

| Month | Customers | Avg Stations | Monthly Revenue | Cumulative |
|-------|----------|-------------|-----------------|-----------|
| 1-3 | 5-10 | 2 | $190-$380 | ~$900 |
| 4-6 | 15-30 | 3 | $855-$1,710 | ~$5,600 |
| 7-12 | 30-60 | 4 | $2,280-$4,560 | ~$24,000 |
| **Year 1** | **50-100** | **3-5** | — | **$27K-$114K ARR** |

Assumptions: 18% trial conversion, 5% monthly churn, avg $19/station, mix of subscription + event packs.

---

## Phase 7: SEA Go-To-Market Strategy (from Gemini Deep Research)

### 7.1 Geographic rollout

| Phase | Markets | Rationale | Timeline |
|-------|---------|-----------|----------|
| **Phase 1** | Singapore, Malaysia | High digital literacy, high labor costs, English-speaking | Month 1-6 |
| **Phase 2** | Thailand, Philippines | Large deskless workforce, rising compliance needs, local connections | Month 6-12 |
| **Phase 3** | Indonesia, Vietnam | Massive workforce scale, compliance modernization wave | Month 12-18 |

### 7.2 SEA-specific tactics

| Tactic | Detail |
|--------|--------|
| **Localization** | Support local date formats and public holiday calendars for SG, MY, TH, ID, PH |
| **Low-friction onboarding** | First QR scan within 3 minutes of signup — the "aha moment" |
| **Payroll integration** | Partner with Talenox, HReasily, Swingvy — attendance is the "input" for their payroll "output" |
| **POS reseller channel** | Partner with shops selling POS systems to F&B/retail — same buyer persona |
| **PDPA/GDPR compliance** | Data hosted in AWS Singapore region via Neon — region-compliant |
| **Public dashboard as trust** | Employees trust the system when they can see their own logs instantly |
| **No credit card trial** | Essential for SEA where CC penetration is low — email-only signup |

### 7.3 SEA competitive edge

Our biggest competitor in SEA isn't Jibble or Clockify — it's **paper and punch cards**. The pitch: "Cheaper than an hour of lost productivity."

| Competitor Tier | Examples | Our Edge |
|-----------------|----------|----------|
| **Global giants** | Jibble, Clockify, Deputy | Overbuilt for local workflows; we're simpler |
| **Regional HRMS** | SalaryBox (India), Swingvy/BrioHR (SEA) | Strong suites but no multi-station scanning + offline |
| **Manual/legacy** | Paper, punch cards | Our biggest opportunity; pitch affordability + instant reports |

---

## Phase 8: Multi-Tenant Scale-Out Architecture

### 8.1 Database isolation strategy

Use **Row-Level Security (RLS)** with `tenant_id` on every table — NOT separate databases per client.

```sql
-- Enable RLS on scans table
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;

-- Policy: each tenant sees only their data
CREATE POLICY tenant_isolation ON scans
  USING (tenant_id = current_setting('app.tenant_id')::text);

-- Set tenant context per request
SET app.tenant_id = 'org_abc123';
```

**Why RLS over separate databases?**
- One schema to maintain across all clients
- Easier migrations and updates
- Neon's connection pooling works better with shared databases
- Can still shard later if needed (by region)

### 8.2 Edge-first architecture

```
[Station SQLite] ←→ [Neon PostgreSQL (RLS)] ←→ [Public Dashboard]
     (buffer)              (source of truth)         (read-only)
```

- **Local SQLite stays** — acts as edge buffer for offline resilience
- **Sync conflict resolution**: Last-Write-Wins with station_name + scanned_at as natural key
- **Idempotency keys** (already implemented) prevent duplicates on retry

### 8.3 Scale considerations

| Challenge | Solution |
|-----------|----------|
| **Sync storms** (500 stations at 9:01 AM) | Rate limiting per tenant + staggered sync windows |
| **Neon cold starts** | Keep-alive heartbeat for active tenants during peak hours |
| **Large Excel exports** | Move to background worker (BullMQ or Bun worker) |
| **Connection pool exhaustion** | Already configured (50 connections); add per-tenant connection limits |
| **Multi-region latency** | Phase 2: Neon read replicas in SG + US regions |

### 8.4 Tenant onboarding flow

```
Stripe checkout → webhook → create tenant row → generate API key → email to customer
                                                                         ↓
Customer enters API key in .env → station connects → heartbeat validates → full access
```

---

## Expanded Use Cases (Beyond Events)

TrackAttendance is NOT just for events. The offline-first, multi-station architecture serves any organization tracking people movement through physical spaces.

### Workforce & HR

| Use Case | Description | Key Feature |
|----------|-------------|-------------|
| **Factory shift logging** | Clock-in/out at production lines without WiFi | Offline-first + multi-station |
| **Construction site safety** | Badge everyone on-site for safety compliance | Audit trail + Excel export |
| **Warehouse operations** | Track staff across loading docks and floors | Cross-station duplicate detection |
| **Field service teams** | Mobile workforce check-in at job sites | Per-station pricing (not per-user) |
| **Healthcare shift compliance** | Nurse/doctor shift verification with audit trail | Multi-floor sync + timestamps |

### Education & Training

| Use Case | Description | Key Feature |
|----------|-------------|-------------|
| **University lectures** | Students scan in per class/room | Multi-room sync + BU breakdown |
| **Corporate training** | Track attendance across training sessions | Excel export for compliance |
| **Certification programs** | Proof of attendance for professional development | Tamper-proof scan records |
| **After-school programs** | Youth check-in/out for safety | Real-time parent dashboard |

### Membership & Access

| Use Case | Description | Key Feature |
|----------|-------------|-------------|
| **Coworking spaces** | Know who's in the building | Live mobile dashboard |
| **Gym / fitness studios** | Member check-in without expensive hardware | $19/station vs $199+ kiosks |
| **Libraries** | Patron visit tracking for funding reports | Auto-reports + Excel export |
| **Religious organizations** | Congregation attendance for leadership | Simple setup, free tier |
| **Associations / clubs** | Meeting attendance for quorum tracking | Per-event pricing option |

### Compliance & Government

| Use Case | Description | Key Feature |
|----------|-------------|-------------|
| **Government meetings** | Attendance verification for officials | Offline + audit trail |
| **Military formations** | Troop accountability in areas with no signal | Full offline capability |
| **Safety drills** | Fire drill / evacuation accounting | Instant headcount on mobile |
| **Visitor management** | Building access logging (cheaper than Envoy) | 6-18x cheaper per location |

---

*Plan created: 2026-03-14*
*Enhanced: 2026-03-14 (market research, pain points, pricing models, regional strategy)*
*Updated: 2026-03-14 (SEA GTM strategy, multi-tenant RLS, expanded use cases — from Gemini Deep Research)*
*Status: Ready for implementation*
