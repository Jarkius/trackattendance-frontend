# 08: Duplicate config validation and an accurate alert message (#107, #108)

## Objective
Duplicate handling can't be silently disabled by a config typo, and the alert states the real time window.

## Dependencies
- none. It touches `web/script.js` near :1348, so land it after 04 and 05 to avoid conflicts.

## Scope
- Relevant modules/files: `config.py` :281, `attendance.py` (the duplicate response near :528 and :604), `web/script.js` :1348
- Expected behavior:
  - `DUPLICATE_BADGE_ACTION` goes through `.strip().lower()` and is checked against `{warn, block, silent}`. Any other value falls back to `warn` with a logged warning.
  - The duplicate response carries `duplicateWindowSeconds`. JS formats it ("1 minute", "30 seconds", "5 minutes").

## Acceptance Criteria
- [ ] Given `DUPLICATE_BADGE_ACTION="block "`, then the action is `block`.
- [ ] Given `"blok"`, then the action is `warn` and a warning is logged.
- [ ] Given `DUPLICATE_BADGE_TIME_WINDOW_SECONDS=60`, then the alert reads "Scanned within 1 minute". The block-mode text is checked as well.

## Contracts and Constraints
- Follow the existing `_safe_int`-style helpers in `config.py`.

## Verification
```bash
python -m pytest tests/test_config.py tests/test_duplicate_detection.py -v
```

## Completion Report
- Changed files: `config.py` (new `_safe_choice` helper; `DUPLICATE_BADGE_ACTION` is stripped, lowercased and validated against warn/block/silent, falling back to `warn` with a logged warning), `attendance.py` (both duplicate responses carry `duplicateWindowSeconds`), `web/script.js` (`formatDuplicateWindow` and `duplicateWindowMessage`; the warn and block alerts both read "Scanned within <window>"), `tests/test_config.py`, `tests/test_duplicate_detection.py`.
- Verification results: `pytest tests/test_config.py tests/test_duplicate_detection.py` gives 49 passed. New tests cover "block " giving block, "blok" giving warn plus a warning, and the window field in the warn and block responses (the existing test already covers "BLOCK"). QWebEngineView harness with a stub `submit_scan` response: windows 60, 30, 300 and 90 give "1 minute", "30 seconds", "5 minutes" and "1 min 30 sec" in both warn and block alerts. Against the old script.js, 7 of the 8 cases fail. CI-equivalent script: see the final report.
- Known limitations: the Python block-mode `message` still says "N seconds". The UI replaces it whenever `duplicateWindowSeconds` is present. Not tried at the kiosk.
