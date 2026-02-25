---
title: When replacing a mechanism (e.g., time-based cooldown → state machine), audit al
tags: [config, refactoring, dead-code, state-machine, testing]
created: 2026-02-25
source: rrr: trackattendance-frontend
---

# When replacing a mechanism (e.g., time-based cooldown → state machine), audit al

When replacing a mechanism (e.g., time-based cooldown → state machine), audit all references to the old config variable. Dead config survives in .env, config.py, constructor params, and instance attributes — users think they're tuning behavior but nothing changes. Either delete, repurpose, or deprecate with a warning. No test catches it unless you test config→behavior wiring end-to-end.

---
*Added via Oracle Learn*
