---
title: When a UI indicator represents the output of a multi-layer decision system (dete
tags: [UI, state-management, indicators, effective-state, suppression]
created: 2026-02-25
source: rrr: trackattendance-frontend
---

# When a UI indicator represents the output of a multi-layer decision system (dete

When a UI indicator represents the output of a multi-layer decision system (detection + suppression + cooldown), the indicator must show the effective state — what would actually happen — not the raw state from one layer. If system A decides "yes" but system B vetoes it, the user-facing indicator should show "no." Apply all suppression conditions before updating the UI.

---
*Added via Oracle Learn*
