---
title: In presence detection with absence_threshold + cooldown timing, the effective re
tags: [proximity-detection, timing, cooldown, state-machine, MediaPipe, distance-filtering]
created: 2026-02-26
source: rrr: trackattendance-frontend
---

# In presence detection with absence_threshold + cooldown timing, the effective re

In presence detection with absence_threshold + cooldown timing, the effective re-greet window is cooldown + absence_threshold, not just cooldown. Detection flicker (person looks down, turns) can reset state to "empty" if it lasts longer than absence_threshold. If cooldown has also elapsed, the same standing person gets re-greeted. Fix: set cooldown significantly longer than expected standing duration. Also: bounding box width / frame width is a free distance proxy with MediaPipe face detection; for pose, use horizontal landmark spread.

---
*Added via Oracle Learn*
