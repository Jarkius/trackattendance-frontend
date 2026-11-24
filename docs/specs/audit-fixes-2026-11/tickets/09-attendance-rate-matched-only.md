# 09: Kiosk dashboard and export use the three attendance buckets (#109)

## Objective
The kiosk dashboard and the Excel export report the three buckets defined in the destination spec:
- registered attended, the only input to the attendance rate
- walk-ins, typed names of people missing from the roster
- unknown badge scans, which need review

The rate never exceeds 100%, and the Summary, By Business Unit and Deduplicated sheets agree.

## Dependencies
- 07 (case rule and the joins used by the local fallback)
- 12 defines the API fields. This ticket must work against both the old and the new API.

## Scope
- Relevant modules/files: `dashboard.py` (:149, :184-188, the local fallback :207-233, the export sheets :380-470), `database.py` (local bucket queries), `web/script.js` and `web/index.html` (where the dashboard counts are rendered)
- Expected behavior:
  - **Cloud path:** use `matched_unique`, `walkin_unique` and `unknown_badge_unique` when present. Otherwise fall back to the sum of `business_units[].unique` excluding `Unmatched` for matched, with walk-in and unknown counts unavailable (`None`).
  - **Local fallback:** compute all three buckets from SQLite with the same rules.
  - **Export:** the Summary sheet shows all three buckets. Walk-ins are listed as their own section or rows, never in "Not Yet Scanned". The By Business Unit and Deduplicated sheets count by the normalised `legacy_id`.

## Acceptance Criteria
- [ ] Given 10 registered, 10 matched employees attended, 2 walk-in names and 1 garbled badge, then `scanned=10`, `attendance_rate=100.0`, `walkins=2` and `unknown_badges=1`, both from the cloud fields and from the local fallback.
- [ ] Given an old API response without the new fields, then `scanned` comes from the BU sum and nothing crashes.
- [ ] Given the same employee scanned via a badge and via lookup, then all three sheets count them once.
- [ ] Given walk-ins `"Somchai"` and `"somchai "`, then they count as 1.
- [ ] The dashboard UI shows walk-ins and unknown badge scans as separate figures.

## Contracts and Constraints
- The bucket definitions are LOCKED in the destination spec. Walk-in names do sync to the cloud (LOCKED).

## Verification
```bash
python -m pytest tests/test_dashboard.py tests/test_bu_export.py tests/test_excel_export.py -v
```

## Completion Report
- Changed files: `dashboard.py` (cloud path uses `matched_unique`/`walkin_unique`/`unknown_badge_unique`, old-server BU-sum fallback, local fallback when cloud stats are unavailable, rate capped at 100 with a warning, new keys `walkins`/`unknown_badges`/`total_present`; export Summary shows the buckets, new "Walk-ins" sheet, BU/Dedup/Not Yet Scanned count by normalised legacy_id; helpers `classify_export_scan`, `bucket_export_scans`, `compute_bu_breakdown`), `database.py` (`normalize_walkin_name`, `get_attendance_buckets`), `web/index.html` and `web/script.js` (Walk-ins and Unknown badges figures, hidden when null), `tests/test_dashboard.py`, `tests/test_bu_export.py` (now tests the real `compute_bu_breakdown` instead of a copy).
- Verification results: the three target test files pass (63 passed). New tests fail on the base code (9 failed in test_dashboard.py; test_bu_export.py fails to import). Local CI: 501 passed, 1 skipped.
- Known limitations: the local walk-in and unknown counts treat a scan as unmatched when no roster row matches `COALESCE(legacy_id, badge_id)` (the same join as the BU query), which is slightly broader than "legacy_id IS NULL". The export Summary derives its buckets from the export rows, so it can differ from the live dashboard if the cloud roster summary is stale. The UI change was not exercised in a running window.
