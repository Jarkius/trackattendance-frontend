# 07: One badge/Legacy ID normalisation rule (#106)

## Objective
The same badge resolves to the same employee everywhere: at import, at lookup, in duplicate checks and in reporting joins.

## Dependencies
- 06 (same import function)

## Scope
- Relevant modules/files:
  - `attendance.py` (import :195, lookup :505)
  - `database.py` (`load_employee_cache` :213, the joins in `get_scans_by_bu` :579 and `count_unmatched_scanned_badges` :593, the duplicate checks :404/:433)
- Expected behavior:
  - Add a `normalize_badge_id()` helper (see the destination spec).
  - The employee cache is keyed by the normalised ID.
  - Lookup normalises the scan value. The stored `scans.badge_id` keeps the raw scan.
  - The reporting joins use the same case rule as duplicate detection.
  - Numeric Legacy ID cells: zero-pad when the cell's number format is all zeros. Otherwise add a roster warning with the count (ASSUMED in the destination spec).

## Acceptance Criteria
- [ ] Given a roster `12345A`, when `12345a` is scanned, then it is matched and the employee-level duplicate check runs.
- [ ] Given a numeric cell `123` with number format `00000`, then the cache key is `00123`, and a `00123` scan matches.
- [ ] Given a numeric cell `123` with the General format, then the roster warning names the numeric-ID count.
- [ ] Given roster IDs `abc1` and `ABC1`, then the import reports a duplicate.
- [ ] Given a lookup scan stored with a different `badge_id`, then `get_scans_by_bu` counts it under its `legacy_id` (case-insensitive).

## Contracts and Constraints
- No schema change. If an index is needed for the joins, add it with the existing `CREATE INDEX IF NOT EXISTS` pattern.
- The idempotency key still uses the raw `badge_id`.

## Verification
```bash
python -m pytest tests/test_duplicate_detection.py tests/test_bu_export.py tests/test_search_employee_prefix_priority.py tests/test_encoding_thai.py -v
```

## Completion Report
- Changed files:
- Verification results:
- Known limitations:
