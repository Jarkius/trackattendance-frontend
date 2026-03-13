# Eliminate Coordination Problems by Centralizing the Actor

**Date**: 2026-03-13
**Context**: TrackAttendance 6-station registration event — all stations greeting simultaneously when groups arrive
**Confidence**: High

## Key Learning

When multiple independent agents (6 kiosk laptops) need to coordinate behavior (greeting visitors), the instinct is to add coordination protocols — random delays, cloud-based state sharing, leader election. But these approaches add complexity and still produce suboptimal results (staggered chaos is still chaos).

The better approach is to ask: "Does every agent need to perform this action?" If one agent can serve all, centralize that function and disable it on the others. A single 120-degree camera unit greeting all visitors is simpler, more effective, and more resilient than any inter-station coordination protocol.

This pattern applies broadly: instead of coordinating N workers to avoid conflicts, consider whether a single dedicated worker eliminates the coordination problem entirely. The existing admin panel camera toggle already supports this — no new code needed, just a deployment decision.

## The Pattern

```
Problem: N agents doing X simultaneously causes chaos
Bad: Add coordination protocol between N agents (complex, fragile)
Good: Centralize X on 1 dedicated agent, disable X on N-1 agents

Example:
- Bad: 6 stations with random greeting delays + cloud state sync
- Good: 1 central camera station greets, 6 scan stations disable camera
```

## Why This Matters

- Reduces system complexity (no coordination protocol to maintain)
- Eliminates race conditions and timing issues entirely
- Leverages existing toggle infrastructure (admin panel camera on/off)
- Resilient: if central unit fails, any station can re-enable camera as fallback
- Production operators understand "one speaker" better than "distributed coordination with random jitter"

## Tags

`architecture`, `coordination`, `simplification`, `production-insight`, `camera`, `greeting`, `kiosk`
