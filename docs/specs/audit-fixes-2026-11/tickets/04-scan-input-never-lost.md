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
- Changed files:
- Verification results:
- Known limitations:
