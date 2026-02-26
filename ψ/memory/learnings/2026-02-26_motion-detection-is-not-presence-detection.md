# Motion Detection Is Not Presence Detection

**Date**: 2026-02-26
**Project**: trackattendance-frontend
**Context**: Camera greeting plugin used motion fallback that couldn't detect standing people

## Pattern

Motion detection (frame differencing) detects **change**, not **presence**. A person standing still becomes the background after the reference frame updates. This makes it fundamentally wrong for proximity/presence detection where you need to know "is someone here?" not "did something move?"

## Symptoms

- Person walks up → detected (motion) → greeted
- Person stands still → no motion → state resets to "empty" after absence_threshold
- Person shifts weight → motion detected → re-greeted (if cooldown expired)

## Solution

Use face detection for presence. OpenCV Haar cascades:
- Ship with cv2 (zero extra dependencies)
- Detect faces regardless of movement
- `minSize` parameter provides built-in distance filtering
- Reliable as fallback when MediaPipe isn't available

## Detection Chain (best to worst)

1. MediaPipe face + pose (most accurate, needs mediapipe package)
2. OpenCV Haar cascade (reliable, ships with cv2, frontal faces only)
3. Motion detection (last resort, only useful for general activity sensing)

## Meta-Lesson

When adding features that depend on a specific backend (e.g., size filtering on MediaPipe bounding boxes), verify the feature works on ALL fallback paths. Test the fallback, not just the happy path.
