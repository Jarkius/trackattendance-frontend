---
title: WebKit range input slider styling: gradient must go on `-webkit-slider-runnable-
tags: [css, webkit, pyqt6, qwebengine, slider, materialize]
created: 2026-03-06
source: rrr: trackattendance-frontend
---

# WebKit range input slider styling: gradient must go on `-webkit-slider-runnable-

WebKit range input slider styling: gradient must go on `-webkit-slider-runnable-track` pseudo-element, NOT the element background. The track renders on top of the element bg, creating a "border" effect. Set element background to transparent, put linear-gradient on the track. Use !important to override Materialize/framework defaults. Update --fill CSS variable via JS on input event.

---
*Added via Oracle Learn*
