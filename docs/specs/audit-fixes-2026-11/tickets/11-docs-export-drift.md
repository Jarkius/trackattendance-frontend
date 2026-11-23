# 11: Export API documentation drift (#112)

## Objective
The docs describe the export endpoint the server actually implements, and the client warns on possible truncation.

## Dependencies
- none. **Needs explicit user approval:** it edits the existing `docs/API.md` and `CLAUDE.md` (project safety boundary).

## Scope
- Relevant modules/files: `docs/API.md` (Dashboard Export section), `CLAUDE.md` (Cloud API line), `dashboard.py` (after the export fetch, ~:310)
- Expected behavior:
  - Document the object-shaped `scans`, `total_records`, `export_timestamp` and the `limit` cap of 100000.
  - The client logs a warning when `total_records >= 100000`.

## Acceptance Criteria
- [ ] The `docs/API.md` export section matches the `server.ts` response.
- [ ] `CLAUDE.md` no longer says "paginated".
- [ ] A test shows the warning is logged at 100000 records.

## Verification
```bash
python -m pytest tests/test_dashboard.py -v
```

## Completion Report
- Changed files: `docs/API.md` (export section matches server.ts: object scans, total_records, export_timestamp, limit, no pagination); `CLAUDE.md` (Cloud API line no longer "paginated"; Privacy line covers walk-in typed text synced as badge_id); `dashboard.py` (EXPORT_SERVER_LIMIT; warns when export reaches 100000); `tests/test_dashboard.py` (warning at 100000, none at 99999)
- Verification results: `pytest tests/test_dashboard.py -q -p no:cacheprovider` -> 28 passed
- Known limitations: the warning is advisory only; exports above 100000 scans are still truncated server-side (no pagination exists).
