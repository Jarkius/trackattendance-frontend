# Detection Flicker and Cooldown Interaction

**Date**: 2026-02-26
**Project**: trackattendance-frontend
**Context**: Standing person re-greeted after detection briefly dropped and cooldown expired

## Pattern

In presence detection systems with three timing parameters:
- `absence_threshold`: how long no-detection before state resets to "empty"
- `cooldown`: minimum time between greetings
- `scan_busy_seconds`: suppress greetings after activity

The effective re-greet window is `cooldown + absence_threshold`, not just `cooldown`. A person standing still can be re-greeted if:
1. Detection flickers (person looks down, turns slightly)
2. Flicker lasts longer than `absence_threshold` (state resets to empty)
3. Person re-detected after `cooldown` has elapsed since last greeting

## Fix

Set cooldown significantly longer than the expected standing duration. For kiosk use: 60s cooldown + 3s absence = person must stand 63s with a detection gap before re-greeting.

## Also Learned

Use bounding box size / frame width as a free distance proxy with MediaPipe face detection. For pose detection without bounding boxes, use horizontal landmark spread instead.
