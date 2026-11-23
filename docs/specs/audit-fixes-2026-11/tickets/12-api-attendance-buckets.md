# 12: API: attendance buckets in the stats endpoints and the public dashboard (#109)

## Objective
`trackattendance-api` reports registered attended, walk-ins and unknown badge scans separately, and the public mobile dashboard's headline rate uses only registered attended.

## Dependencies
- none. The repo is `C:\workspace\trackattendance-api` (separate git repo). Use branch `feature/attendance-buckets`.

## Scope
- Relevant modules/files: `server.ts` (`GET /v1/dashboard/stats` ~:506, `GET /v1/dashboard/public/stats` ~:575), `public/index.html` (hero rate ~:906-911, and any other use of `unique_badges` as "attended", ~:1022), `README.md` (endpoint field list, if it documents fields)
- Expected behavior:
  - Add `matched_unique`, `walkin_unique` and `unknown_badge_unique` to both endpoints, using the SQL rules in the destination spec's "Attendance buckets" table.
  - Keep `unique_badges` and every existing field unchanged (additive change only).
  - Public dashboard: hero rate = `matched_unique / total_registered`, capped at 100%, falling back to `unique_badges` if the field is absent. Show walk-ins next to the hero stats ("+N walk-in"). Don't redesign the page.

## Acceptance Criteria
- [ ] Both endpoints return the three new integer fields, and the existing fields are unchanged.
- [ ] Walk-in normalisation in SQL is `lower(regexp_replace(btrim(badge_id), '\s+', ' ', 'g'))`.
- [ ] The registered-attended key is `COALESCE(NULLIF(meta->>'legacy_id',''), badge_id)` over `business_unit IS NOT NULL`.
- [ ] Given seeded rows (10 matched, 2 manual unmatched with case and space variants of one name plus one other name, 1 badge unmatched), then the SQL gives matched=10, walk-ins=2 and unknown=1. Verify by running the query text against a throwaway Postgres if one is available, and otherwise by careful reasoning plus a unit-level extraction of the SQL strings. State which in the report.
- [ ] `npx tsc --noEmit` passes. That is the repo's CI.

## Contracts and Constraints
- No schema migration. Existing columns: `business_unit`, `scan_source`, `meta`.
- Don't commit `.claude/settings.local.json`. Don't push. Don't deploy.

## Verification
```bash
cd C:/workspace/trackattendance-api && npx tsc --noEmit
```

## Completion Report
- Changed files:
- Verification results:
- Known limitations:
