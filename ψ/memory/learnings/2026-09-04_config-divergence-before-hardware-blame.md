---
pattern: When a failure is concentrated on a subset of otherwise-identical nodes/stations/machines, check configuration divergence between the affected and unaffected subsets before reaching for a hardware or environmental explanation
date: 2026-09-04
source: rrr: Jarkius/trackattendance-frontend
concepts: [debugging, root-cause-analysis, fleet-deployment, config-drift]
---

## The pattern

A fleet of N identical nodes (kiosks, servers, workers) shows a failure signature
concentrated on a small subset (e.g. 2 of 10), not spread evenly across all of them.
The instinct is to blame something physical/local to those specific nodes — hardware,
network path, a flaky device — because "why would only some of them fail if the code
is the same?"

Check first whether those specific nodes have a **feature flag, env var, or config
value** that differs from the rest of the fleet, before investigating hardware. A
concentrated-but-not-universal failure pattern is actually *more* consistent with config
divergence than with independent hardware failures, which would more plausibly hit a
random subset rather than a specific matching pair/group.

## Why it matters

In the source incident: ~30 corrupted badge scans across a 10-station event were
concentrated on exactly 2 stations. The initial hypothesis was a barcode-scanner
hardware double-fire issue specific to those two physical scanner units. The actual
cause was that those two stations had a real-time sync feature flag enabled that the
other eight did not — the flag introduced a network wait in the scan path, and a
scanner double-fire during that wait (which *can* happen on any unit, just rarely
enough not to matter without the wait) is what produced the corruption. Checking
per-station config would have surfaced this in one query, versus the actual path of
reading raw logs before the pattern clicked.

## How to apply

When a fleet-wide failure is uneven:
1. Before physical/hardware theories, diff the actual runtime config (env vars, feature
   flags, persisted settings) between the affected and unaffected nodes.
2. If a config difference exists on exactly the affected subset, treat that as the
   leading hypothesis, not a footnote — it doesn't need to be the *direct* cause, it
   only needs to change the *timing or path* through otherwise-shared code enough to
   expose a rare pre-existing edge case (as it did here: the flag added a wait; the
   wait exposed a race that existed everywhere but rarely manifested without it).
3. Uneven-but-not-universal is itself a signal worth naming out loud early, rather than
   silently investigating hardware first and only checking config after that hypothesis
   fails.
