# 04: Scanner keystrokes are never lost to overlay or focus state (#104)

## Objective
Every scanner burst on the scan screen is captured in full, whether or not the duplicate alert is showing and wherever focus is.

## Dependencies
- none

## Scope
- Relevant modules/files: `web/script.js` (`__handleDuplicateBadge` near :729, `returnFocusToInput` :636, the global keydown handler :3125-3145, the barcode keyup submit :1817)
- Expected behavior:
  - The duplicate alert no longer sets `barcodeInput.disabled`. A new scan dismisses the alert.
  - A printable key that arrives while focus is outside the admin, dashboard and lookup inputs is appended to the barcode input synchronously, and focus moves there with no delay.

## Acceptance Criteria
- [ ] Given the warn-mode duplicate alert is visible, when a second badge is typed at scanner speed (10 ms per character) plus Enter, then it is submitted in full and the alert closes.
- [ ] Given focus is on `<body>`, when a badge is typed at scanner speed plus Enter, then the full ID is submitted.
- [ ] Given the dashboard or admin overlay is open, then scanner input behaves exactly as before. That ticket does not change it.
- [ ] Block mode still rejects the duplicate itself. Only the *next* scan is unblocked.

## Contracts and Constraints
- Keep the clear-before-bridge-call behavior (`script.js:1366`), which prevents concatenation.
- Don't touch the lookup overlay. That is ticket 05.
- The `web/` code is shared with `trackattendance-saas`, so keep the changes portable.

## Verification
- Disposable harness: load `web/index.html` in a separate `QWebEngineView` with a stub bridge, simulate key bursts via `runJavaScript` or `QTest.keyClicks`, and record the submitted values. Keep the harness in the scratchpad, not in the repo.
- Manual check with a real scanner at the kiosk.
```bash
python -m pytest tests/test_duplicate_detection.py -v
```

## Completion Report
- Changed files: `web/script.js` only. The duplicate alert no longer sets `barcodeInput.disabled` (removed from show, auto-dismiss and `dismissDuplicateOverlay`). New `captureStrayScanKey(event)` dismisses an open alert on any printable key, and when focus is outside the input it appends the key synchronously, `preventDefault`s and focuses the input at once. The global keydown handler uses it. When the lookup or admin overlay is open it keeps the old `returnFocusToInput()` path. `returnFocusToInput` keeps its 80 ms delay for the non-key callers (post-scan, window focus, overlay close). The clear-before-bridge-call in `submitScan` is untouched. Python is unchanged.
- Verification results: disposable QWebEngineView + real QWebChannel harness (outside repo), keys sent with QTest at 10 ms/char. (a) alert visible, input focused, "123456"+Enter: submitted in full and the overlay hides. (a2) block-style alert, focus on body, "246810"+Enter: submitted in full and the overlay hides. (b) focus on body, "987654"+Enter: submitted in full. (c) baseline focused scan "555555": submitted. The same harness against the old script.js fails 5 of the checks. CI-equivalent script: 431 passed, 1 skipped.
- Known limitations: not tried with a real scanner at the kiosk. Dashboard/admin scanner behavior was not exercised in the harness. Keys typed with ctrl/alt/meta are not captured. Ticket 05 can reuse `captureStrayScanKey` for the lookup overlay.
