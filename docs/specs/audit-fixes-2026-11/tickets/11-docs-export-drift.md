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
- Changed files:
- Verification results:
- Known limitations:
