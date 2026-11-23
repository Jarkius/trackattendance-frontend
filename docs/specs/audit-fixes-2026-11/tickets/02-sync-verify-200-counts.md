# 02: Verify 200 response counts before marking synced (#110)

## Objective
Scans are marked synced only when the 200 response is a recognised batch result that accounts for every event.

## Dependencies
- 01 (same function, `sync_scan_batch_network_only`)

## Scope
- Relevant modules/files: `sync.py` (the 200 branch of `sync_scan_batch_network_only`, and of the legacy path if it is still reachable)
- Expected behavior: `saved` and `duplicates` must both be ints and must sum to `len(events)`. Otherwise every id goes to `pending_ids`, with a logged error.

## Acceptance Criteria
- [ ] Given a 200 with `{}`, then all ids are pending and none are synced.
- [ ] Given a 200 with `{"saved": 98, "duplicates": 1}` for 100 events, then all are pending and the mismatch is logged.
- [ ] Given a 200 with `{"saved": 98, "duplicates": 2}`, then all 100 are synced.

## Contracts and Constraints
- The result dict shape is LOCKED. No server change.

## Verification
```bash
python -m pytest tests/test_sync_network_only_batch.py tests/test_api_contracts.py -v
```

## Completion Report
- Changed files: implemented in ticket 01 (`_post_events` coverage check in `sync.py`: `saved + duplicates` must equal the batch size, otherwise the ids stay pending).
- Verification results: `tests/test_sync_error_classification.py::TestTransientClassification::test_200_with_empty_object_body_leaves_everything_pending`, `::test_200_whose_counts_do_not_cover_batch_is_pending`, `::test_duplicates_count_toward_coverage`, `::test_200_with_json_that_is_not_an_object_is_pending`.
- Known limitations: none.
