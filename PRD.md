# Product Requirements: Track Attendance UI/UX Refresh

## 1. Goal

Deliver an operator-friendly scanning console that stays informative even when idle, handles unmatched scans gracefully, and communicates export status without blocking automation.

## 2. Scope

- Refresh the visual state of the recent history module (placeholder row, metadata line, timestamp alignment).
- Simplify branding and remove any personal/demo data from the shipped assets.
- Introduce a reusable export overlay with auto-hide behaviour.
- Ensure the stress-harness workflow can trigger exports without human interaction.

## 3. User Stories

### 3.1 Clean initial state
**As an operator** I want the recent history list to show a clear “Awaiting first scan” message so the UI looks intentional before the first attendee arrives.
- Placeholder should disappear as soon as the first scan is recorded.
- Placeholder must carry no personally identifiable information.

### 3.2 Consolidated history metadata
**As a supervisor** I need each history row to display legacy ID, SL L1, position, and timestamp on a compact line, so the most relevant attributes are visible without opening the export.
- When the scan is unmatched, show a clear follow-up note instead of those fields.

### 3.3 Export overlay behaviour
**As an operator** I want a consistent overlay when exports run (either manually or during shutdown) so I know whether the report succeeded.
- Overlay should display success/failure messaging, file path when available, and auto-dismiss after a short delay.
- Automation paths (stress harness) must be able to bypass the overlay and still capture an export.

### 3.4 Branding and packaging
**As a maintainer** I need a neutral application name and icon, plus a ready-to-run Windows bundle, so the tool can be distributed without manual tweaks.
- All references to legacy branding are removed.
- PyInstaller spec generates `dist/TrackAttendance/TrackAttendance.exe` with the custom icon.

## 4. Non-Goals

- Backend refactors beyond what is required for the UX updates.
- Replacing the existing SQLite or XLSX stack.
- Web-based deployment.

## 5. Acceptance Checklist

- [ ] Placeholder history row renders on first load and disappears after a scan.
- [ ] Metadata row shows `legacyId . SL L1 . Position` or the unmatched note, and timestamp aligns with the name.
- [ ] Export overlay appears for manual exports and during window close (when not suppressed), then auto-hides.
- [ ] Stress harness saves an export to `exports/` with no manual intervention.
- [ ] `TrackAttendance.spec` builds a working executable with the custom icon.
- [ ] README documents console setup, packaging, and privacy expectations.
