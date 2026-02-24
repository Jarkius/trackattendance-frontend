---
title: Presence State Machine > Cooldown for Proximity Detection: When detecting people
tags: [camera, proximity-detection, state-machine, ux, audio, qt]
created: 2026-02-24
source: rrr: trackattendance-frontend
---

# Presence State Machine > Cooldown for Proximity Detection: When detecting people

Presence State Machine > Cooldown for Proximity Detection: When detecting people with a camera to trigger one-time actions (greetings, alerts), use a presence state machine instead of a cooldown timer. Cooldown just spaces out repeated triggers; a state machine (empty → present → quiet → person leaves → empty) fires the callback exactly once per arrival. Key: track absence_threshold (seconds with no detection before reset). Layer with activity suppression (e.g. suppress during active badge scanning). Guard audio overlap — two QMediaPlayer instances WILL play simultaneously if not checked.

---
*Added via Oracle Learn*
