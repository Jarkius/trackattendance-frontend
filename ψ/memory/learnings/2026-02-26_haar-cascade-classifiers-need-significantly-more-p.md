---
title: Haar cascade classifiers need significantly more pixels than neural network dete
tags: [OpenCV, Haar-cascade, resolution, detection, tuning, false-positives]
created: 2026-02-26
source: rrr: trackattendance-frontend
---

# Haar cascade classifiers need significantly more pixels than neural network dete

Haar cascade classifiers need significantly more pixels than neural network detectors (MediaPipe). At 192x108, faces are only ~15-30px wide — below Haar's detection threshold. Recommended: 640x480 for reliable Haar detection. When adjusting minNeighbors for sensitivity, compensate with confirm_frames for false positive filtering. When a feature has multiple detection backends, set resolution to satisfy the weakest backend's requirements.

---
*Added via Oracle Learn*
