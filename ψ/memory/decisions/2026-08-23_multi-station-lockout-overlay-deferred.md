# Decision: Multi-Station Lockout Overlay (Clear-in-Progress + Scheduled-Opening) — Deferred

**Date**: 2026-08-23
**Decision**: Skip for now. Not building either sub-feature at this time.
**Status**: Deferred, not rejected — revisit if the triggering conditions below actually occur.

## Where this came from

While closing out the sync-coordinator bugfix PR (#64), the user manually
tested "clear this workstation" and "clear all workstations" live and asked
whether other running stations should show a full-screen "please wait"
overlay while a remote clear (or a scheduled event start) is in progress,
instead of the current silent background clear + toast alert. This surfaced
two related but separable feature ideas:

- **(A) Clear-in-progress lockout**: when one station triggers an admin
  clear, every other running station should visibly block scanning while it
  detects and applies that clear.
- **(B) Scheduled-opening lockout**: a station shows a "not open yet"
  overlay until a configured event start time, then auto-transitions to the
  normal scan screen.

A branch (`feat/multi-station-clear-and-lockdown-overlay`) was created off
`main` in anticipation, but received zero commits — closed unused as part of
this decision.

## What was evaluated

Full evaluation detail — architecture, four dimensions considered (escape
hatch/recovery, trigger authority, propagation timing, offline behavior),
and a cost/value table — was written to
`.omc/plans/multi-station-lockout-overlay-evaluation.md` (tool-local state,
not committed to git). Key points carried forward here since that file may
not persist:

- The existing remote-clear detection (`_handle_clear_epoch_and_heartbeat_slot`
  in `main.py`) already works correctly and cannot hang/deadlock — it's a
  fully synchronous sequence on the main thread with no cross-machine
  waiting. Any lockout overlay would be UI polish on top of already-correct
  underlying behavior, not a fix for a real correctness bug.
- **Non-negotiable requirement identified, if (A) is ever built**: any
  lockout must let the person standing at a locked station self-recover via
  the local PIN-gated admin panel, without depending on another machine
  being online or reachable. A blocking modal with no local escape hatch
  would let one station's clear action strand every other station with no
  recourse — flagged explicitly by the user mid-discussion as their primary
  concern, and confirmed as a real design trap (not a deadlock in the
  technical sense, but the same "stuck forever" shape as issue #65).
- Push-based clear notification (websocket/SSE instead of the current ~10s
  poll) was evaluated and explicitly rejected as not worth new backend
  infrastructure — a shorter poll interval closes most of the staleness gap
  for near-zero cost.
- A "main machine" / designated-controller-station concept was raised and
  explicitly rejected earlier in the same conversation — the existing
  PIN-gated admin access already solves the actual access-control need;
  adding station hierarchy would be complexity without a corresponding
  requirement.

## Why deferred rather than built

The user was not sure whether either sub-feature reflects a real recurring
need — the idea surfaced from *testing* the clear buttons during PR #64's
manual verification pass, not from a documented incident or a scheduled
event requirement. Rather than build speculative UX polish on top of
already-correct behavior, the call was made to defer and write this down so
the reasoning isn't lost.

## When to revisit

Reopen this if either becomes true:
- Multi-station clears become frequent enough in practice that the current
  silent-background-clear + toast has caused a real, observed problem (a
  lost scan, a confused user, a support ticket) — not just discomfort from
  testing it directly.
- A real recurring scheduled/timed event exists where stations need to stay
  locked until a specific start time.

If revisiting, start from the evaluation doc's cost/value ranking: (B)
scheduled-opening is lower-risk and higher-value-per-effort than (A)
clear-in-progress, and both should honor the local-self-recovery requirement
above from the start rather than retrofitting it.

See also [[project-sync-coordinator-bugfixes]] (Claude Code session memory)
for the #65 barrier-reset pattern this decision explicitly avoids repeating
in a new form.
