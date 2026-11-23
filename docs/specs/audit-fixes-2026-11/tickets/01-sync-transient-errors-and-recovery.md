# 01: Sync transient errors, batch bisection, failed-scan recovery (#101)

## Objective
No scan is permanently parked as `failed` unless the server rejected that specific event. Scans already sitting in `failed` recover automatically.

## Dependencies
- none

## Scope
- Relevant modules/files: `sync.py` (`sync_scan_batch_network_only`, plus the legacy `_sync_one_batch` if still reachable), `database.py` (a new `requeue_failed_scans()`), and the `main.py` startup path.
- Expected behavior:
  - Classify errors as either transient (→ `pending_ids`) or event-rejected (→ `failed_ids`, only after bisection).
  - Bisect 400/422 batches down to single events, inside the same network-only job.
  - At startup, call `requeue_failed_scans()` once, on the main thread.

## Acceptance Criteria
- [ ] Given a mocked 400 when the batch contains event X and 200 otherwise, when a 10-event batch syncs, then 9 ids are in `synced_ids` and only X's id is in `failed_ids`.
- [ ] Given a `ChunkedEncodingError`, a 403, a 404, a 408, a 413, or a 200 with a non-JSON body, then every id is in `pending_ids` and `failed_ids` is empty.
- [ ] Given a split during bisection hits a transient error, then the unresolved ids are `pending`, not `failed`.
- [ ] Given a DB with `failed` rows, when the app starts (`requeue_failed_scans()`), then they are `pending` and the count is logged.
- [ ] The existing coordinator/barrier tests still pass.

## Contracts and Constraints
- The result dict shape is LOCKED (see the destination spec). No SQLite access inside the network-only function.
- Remove the now-dead `_is_retryable_error`, or use it. Don't leave both.
- Non-goal: the `ok` field semantics (#68).

## Verification
```bash
python -m pytest tests/test_sync_network_only_batch.py tests/test_sync_retry.py tests/test_barrier_reset_integration.py tests/test_sync_coordinator.py -v
python -m pytest tests/ <CI ignores from project-verification.md> -v --tb=short
```

## Completion Report
- Changed files: `sync.py` (classification and bisection moved into `sync_scan_batch_network_only` plus a new `_post_events` helper; `_is_retryable_error` is now used), `database.py` (`requeue_failed_scans()`), `main.py` (one startup call, logs the count), `tests/test_sync_error_classification.py` (new), `tests/test_sync_network_only_batch.py` (two assertions that encoded the old bug now expect `pending_ids`).
- Verification results: the five ticket test files pass (71 passed, 4 subtests). The local CI script passes (446 passed, 1 skipped; the two Windows-only standalone tests exit 0).
- Known limitations: the legacy `_sync_one_batch` path is unreachable from app code and was left unchanged. It still marks 4xx and generic `RequestException` batches as failed. Bisection is capped at 64 extra requests per batch; the remainder stays pending. Requeue runs once per startup, so a truly bad event is retried and re-failed once per launch. A 200 whose `saved + duplicates` does not equal the batch size is now pending.
