# 05: The lookup overlay ignores scanner bursts (#103)

## Objective
Scanning a badge while the lookup overlay is open processes that badge as a fresh scan. It never records a lookup result.

## Dependencies
- 04 (it reuses that ticket's stray-key capture path in `script.js`)

## Scope
- Relevant modules/files: `web/script.js` (`showLookupOverlay` :1214, the lookup keydown handler :1273, the global keydown handler :3125)
- Expected behavior:
  - A printable key while the overlay is open closes the overlay and starts a new scan in the barcode input.
  - The Enter that ends that burst submits the scan and does not click a result button.

## Acceptance Criteria
- [ ] Given the overlay shows results with the first one focused, when "123456" plus Enter is typed at scanner speed, then `submit_scan("123456")` is called and `submit_manual_scan` is not.
- [ ] Given the overlay is open, when the user presses ArrowDown then Enter with no preceding characters, then the highlighted result is recorded (no regression).
- [ ] Mouse clicks on "Record Scan" still work.

## Contracts and Constraints
- No new bridge methods are needed.
- Non-goal: lookup ranking or search behavior.

## Verification
- Disposable `QWebEngineView` harness (as in ticket 04) with a stub bridge that records calls.
- Manual check at the kiosk.

## Completion Report
- Changed files: `web/script.js` only. The global keydown handler now treats a printable key (not Space, no ctrl/alt/meta) with focus inside the open lookup overlay as a new scan: it hides the overlay and calls `captureStrayScanKey(event)`, so focus and the first character move to the barcode input. The burst's Enter then submits through the normal `submit_scan` path and never reaches the focused "Record Scan" button. Arrow keys, Enter, Tab and Space keep their lookup behavior.
- Verification results: disposable QWebEngineView + real QWebChannel harness, stub `search_employee` returning 2 results, keys at 10 ms/char. Before (0667df4): the burst case failed, with `submit_manual_scan("smith","L1")` called instead of `submit_scan`. After: (1) "123456"+Enter gives only `submit_scan("123456")` and the overlay hides. (2) ArrowDown+Enter gives `submit_manual_scan("smith","L2")`. (2b) Enter alone gives L1. (3) Clicking Record Scan gives `submit_manual_scan("smith","L1")`. CI-equivalent script: 433 passed, 1 skipped.
- Known limitations: the harness needed `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu` to run reliably. Not tried with a real scanner at the kiosk. A scan whose first character is a space is not captured by this path.
