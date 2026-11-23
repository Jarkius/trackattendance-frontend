# 03: Immediate Write uses the batch event builder (#102)

## Objective
An event uploaded by Immediate Write is identical to the one the batch path would send for the same scan.

## Dependencies
- none. It edits `sync.py`, which is also touched by 01 and 02, so land it after 01 on the integration branch to avoid conflicts.

## Scope
- Relevant modules/files: `sync.py` (`sync_single_scan`, `_build_batch_events`)
- Expected behavior: `sync_single_scan` sends `{"events": _build_batch_events([scan], station_name)}`.

## Acceptance Criteria
- [ ] Given one `ScanRecord` (both a matched and a lookup scan), when the immediate and batch payloads are captured with mocked `requests.post`, then the event dicts are equal, including `meta` and the normalised `scanned_at`.
- [ ] The PR description states the operator remedy for cloud rows already stored without `meta`: clear the cloud data before the next event, or re-export locally.

## Contracts and Constraints
- `sync_single_scan` stays network-only. It must not touch `self.db` (see #66).
- The idempotency key is unchanged.

## Verification
```bash
python -m pytest tests/test_immediate_sync.py -v
```

## Completion Report
- Changed files: `sync.py` (`sync_single_scan` now sends `{"events": self._build_batch_events([scan], station_name)}` with the same Content-Type header as the batch path; short timeout and fire-and-forget semantics kept; not routed through `_post_events`, because this is best-effort with a 3 s timeout and batch sync is the safety net), `tests/test_immediate_sync.py` (`TestImmediateEventMatchesBatchEvent`: matched scan, lookup scan with `badge_id != legacy_id`, and a network-only check).
- Verification results: tests/test_immediate_sync.py + tests/test_sync_error_classification.py pass; local ci.sh passes.
- Known limitations: operator remedy for cloud rows already stored without `meta`. The server keeps the first copy of an idempotency key (`ON CONFLICT DO NOTHING`), so rows uploaded by Immediate Write before this fix keep `matched=false` and no `legacy_id` in the cloud. Remedy: use the admin "clear cloud data" before the next event (local data re-syncs with full meta), or accept that the cloud export shows those rows as unmatched. The new API stats (ticket 12) count rows with `business_unit` set as registered even without meta, so the dashboard attendance rate is already correct for those rows.
