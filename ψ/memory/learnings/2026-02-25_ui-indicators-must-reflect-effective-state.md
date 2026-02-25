# UI Indicators Must Reflect Effective State

**Date**: 2026-02-25
**Project**: trackattendance-frontend
**Context**: Camera icon showed "person detected" (red) during scan-busy window when greetings were actually suppressed

## Pattern

When a UI indicator represents the output of a multi-layer decision system (detection + suppression + cooldown), the indicator must show the **effective** state — what would actually happen — not the raw state from one layer.

## Example

- Raw detection state: "present" (person in frame)
- Scan-busy suppression: active (last scan 5s ago, busy window is 40s)
- Effective state: "empty" (greeting won't fire, so icon should show green/ready)

## Fix

Apply all suppression conditions before updating the UI:
```python
raw_state = detector.presence_state
effective_state = "empty" if time.time() < busy_until else raw_state
overlay.notify_state(effective_state)
```

## General Rule

If system A decides "yes" but system B vetoes it, the user-facing indicator should show "no." The indicator should reflect the final decision, not an intermediate signal.
