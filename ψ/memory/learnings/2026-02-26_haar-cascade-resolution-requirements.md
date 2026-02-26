# Haar Cascade Needs Higher Resolution Than Neural Network Detectors

**Date**: 2026-02-26
**Project**: trackattendance-frontend
**Context**: Haar cascade face detection failed at 192x108 but works at 640x480

## Pattern

OpenCV Haar cascade classifiers need significantly more pixels than neural network-based detectors (MediaPipe, YOLO). A face must be at least ~40-50 pixels wide for reliable Haar detection. At 192x108 resolution, a face at kiosk distance is only ~15-30px — below the detection threshold.

Neural network detectors (MediaPipe) can handle low-res inputs because they learn abstract features. Haar cascades match literal pixel patterns (edges, rectangles) and need enough resolution to form those patterns.

## Resolution Guide for Haar Cascade

| Resolution | Face at ~0.5m | Reliability |
|-----------|--------------|-------------|
| 192x108 | ~15-30px | Poor — below threshold |
| 320x240 | ~50-80px | Minimum viable |
| 640x480 | ~100-160px | Recommended |
| 1280x720 | ~200-320px | Diminishing returns, high CPU |

## Tuning Interactions

When adjusting `minNeighbors` (sensitivity):
- Lower = more sensitive but more false positives
- Compensate with higher `confirm_frames` (temporal filtering)
- `minNeighbors=3` + `confirm_frames=3` is a good balance

## General Rule

When a feature has multiple detection backends (MediaPipe → Haar → motion), set resolution to satisfy the **weakest** backend's requirements, not the strongest.
