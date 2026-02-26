---
title: Motion detection (frame differencing) detects change, not presence. A standing p
tags: [computer-vision, motion-detection, face-detection, Haar-cascade, fallback-testing, proximity]
created: 2026-02-26
source: rrr: trackattendance-frontend
---

# Motion detection (frame differencing) detects change, not presence. A standing p

Motion detection (frame differencing) detects change, not presence. A standing person becomes the background after the reference frame updates. For proximity/presence detection, use face detection instead. OpenCV Haar cascades ship with cv2, detect faces regardless of movement, and provide built-in distance filtering via minSize. When adding features dependent on a specific backend (e.g., size filtering on MediaPipe), verify the feature works on ALL fallback paths — test the fallback, not just the happy path.

---
*Added via Oracle Learn*
