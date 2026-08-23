# Lesson Learned: Council-Reviewed Threading Overhaul + Verification Ceiling

**Date**: 2026-08-17
**Context**: TrackAttendance Slice A/B performance refactor (SQLite fixes + sync coordinator threading overhaul), council-planned then implemented across five sequential passes.

## Pattern: Verify tool output before building on a claimed summary

A message mid-session claimed to summarize an independent reviewer's (Codex) assessment, formatted persuasively with specific technical recommendations. The actual background tool call had failed silently (exit code 1, empty output file). Checking the real output artifact — not the plausible-sounding claim — caught this before any of it was incorporated into the plan. **Rule**: when a claim purports to summarize a tool/subagent's output, check the tool's actual output (file, exit code, return value) before treating the claim as evidence. A well-formatted summary is not verification.

## Discovery: Repetition doesn't make a claim true

"SHA-256-based idempotency keys" was stated as a requirement across multiple turns of the same conversation — by the user's instructions text and repeated by me in synthesis — before an independent code review (Codex, reading `sync.py` directly) caught that the actual implementation uses a deterministic string format (`{station}-{badge_id}-{local_id}`), with SHA-256 used elsewhere (roster-summary hashing) entirely unrelated to scan idempotency. Nobody had actually checked the code; the claim just survived because it went unchallenged. **Rule**: a claim's survival across conversation turns is not evidence of its correctness — trace it back to the actual code/data it describes at least once before treating it as settled.

## Pattern: snapshot-on-main / work-on-worker / apply-on-main for Qt+SQLite+threading

For any Qt desktop app with a single-threaded SQLite connection where you need to move blocking network I/O off the UI thread: (1) snapshot the data you need from SQLite on the main thread, (2) submit a closure containing ONLY network I/O to a worker thread, (3) marshal the result back via `QMetaObject.invokeMethod(obj, "slot", Qt.ConnectionType.QueuedConnection)`, (4) apply any SQLite mutations in that marshaled slot, back on the main thread. This shape was reused identically for both automatic and manual sync in this session and avoids ever needing `check_same_thread=False` or a second SQLite connection.

## Discovery: A generation-counter barrier prevents stale-async-result corruption without blocking

When a synchronous invalidating operation (here: clearing all local scan data) can race with in-flight or queued async work (background sync jobs), a lightweight fix is: bump a generation counter and drop the queue when the invalidating operation starts; check the generation at result-delivery time and skip the callback if it's stale. This lets an in-flight job finish naturally (no forced cancellation) while guaranteeing its result never mutates state after the invalidation — without the calling thread having to block waiting for that in-flight job.

## Discovery: Fixing one instance of a risky pattern doesn't mean you've fixed all instances

The codebase had three structurally identical "clear all local scan data" call sites (one automatic remote-clear-detection path, two admin-triggered paths). The barrier fix was initially scoped to only the first one mentioned in the plan. Deliberately grepping for the underlying operation (`clear_all_scans()`) after finishing the first fix surfaced the other two, which had the identical race and needed the identical fix. **Rule**: after fixing a risky pattern at one call site, grep for the underlying dangerous operation across the whole codebase — don't assume the plan's stated scope was exhaustive.

## Discovery: "All tests pass" can quietly become a false finish line when the test environment can't exercise the riskiest paths

Across five implementation passes, PyQt6 (required to even import `main.py`/`attendance.py`) was unavailable in the working sandbox. Every new test touching those files was written with a `PYQT6_AVAILABLE` skip guard and reported honestly as "skipped" rather than "passed" — but the aggregate framing of "N tests, 0 failures" across passes still implicitly functioned as a success signal until the user asked to actually run the app, at which point it became clear that the parts of the design most worth verifying (real Qt signal delivery across threads, real cross-thread SQLite access under load) had never been exercised at all. **Rule**: when a structural test-environment gap (missing dependency, no GUI, no live network) prevents testing the highest-risk part of a change, name that gap as a standing unresolved risk in every status report — not just as a footnote — until it's actually closed.
