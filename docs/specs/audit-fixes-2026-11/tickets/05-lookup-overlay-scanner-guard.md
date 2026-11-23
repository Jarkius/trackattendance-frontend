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
- Changed files:
- Verification results:
- Known limitations:
