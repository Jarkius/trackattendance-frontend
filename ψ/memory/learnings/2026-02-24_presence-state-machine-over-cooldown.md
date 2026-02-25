# Presence State Machine > Cooldown for Proximity Detection

**Date**: 2026-02-24
**Context**: Camera proximity greeting plugin for kiosk attendance app
**Project**: trackattendance-frontend

## Pattern

When detecting people with a camera to trigger one-time actions (greetings, alerts), use a **presence state machine** instead of a cooldown timer.

### Cooldown approach (flawed):
- Detect face → fire callback → wait N seconds → detect again → fire again
- Person standing still gets greeted repeatedly
- Increasing cooldown just spaces out the annoyance

### State machine approach (correct):
```
empty   + person seen  → present (fire callback ONCE)
present + person seen  → present (stay quiet)
present + no person for N seconds → empty (reset)
empty   + person arrives → greet again
```

### Key parameters:
- `absence_threshold`: seconds with no detection before resetting to "empty" (3s default — tune based on camera reliability)
- Layer with **activity suppression**: if the system is busy (e.g. badge scans happening), suppress callbacks regardless of state

### Additional guard: audio overlap
When multiple audio sources exist (scan confirmation + greeting), check if one is playing before firing the other. Two `QMediaPlayer` instances WILL play simultaneously if not guarded.

## Tags
`camera`, `proximity-detection`, `state-machine`, `ux`, `audio`
