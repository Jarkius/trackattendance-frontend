# Handoff: Camera Proximity Plugin — Production Ready

**Date**: 2026-02-24 19:58
**Branch**: Jarkius/check-camera-poc
**Context**: 95%

## What We Did

- Drafted README v1.5.0 with full camera plugin documentation (features, config, troubleshooting)
- Implemented scan-busy suppression — greetings stay quiet during active badge scanning queues
- Built presence-aware state machine — greet once per person arrival, not on repeat (empty → present → quiet)
- Added hysteresis (`CAMERA_CONFIRM_FRAMES=3`) — prevents false-positive greetings from shadows/flickers
- Raised MediaPipe confidence threshold 0.3 → 0.5
- Added `CAMERA_SHOW_OVERLAY` toggle — preview (debug) vs icon (production)
- Built 32x32 QPainter camera status icon with green active dot
- Made GreetingPlayer thread-safe — QObject + QMetaObject.invokeMethod pattern
- Replaced cross-thread Qt state read with time-based flag for voice overlap prevention
- Validated plugin modularity — app works fine without plugins/camera/ folder
- Validated performance — camera runs in separate daemon thread, zero blocking
- Added 7 new .env config variables, all documented in .env.example and README
- Created IT Service Desk SOP (saved to Desktop, not in repo)

## Pending

- [ ] Test camera plugin on actual kiosk hardware at event venue
- [ ] Tune `CAMERA_CONFIRM_FRAMES` and `CAMERA_ABSENCE_THRESHOLD_SECONDS` based on real conditions
- [ ] PR review and merge `Jarkius/check-camera-poc` → main
- [ ] Add unit tests for ProximityDetector state machine (process_frame with synthetic frames)
- [ ] Add `is_playing()` public method to VoicePlayer for proper overlap prevention (replace 3s magic number)
- [ ] Consider replacing QPainter camera icon with SVG asset
- [ ] Send IT Service Desk SOP email to junior IT staff

## Next Session

- [ ] Run app on kiosk hardware with `ENABLE_CAMERA_DETECTION=True`, observe behavior in real queue
- [ ] Create PR for `Jarkius/check-camera-poc` → main (consider squash merge to clean 20+ commits)
- [ ] Write unit tests for `ProximityDetector.process_frame()` — test state transitions with mock frames
- [ ] If hardware test reveals issues, iterate on detection parameters

## Key Files

- `plugins/camera/proximity_detector.py` — State machine + hysteresis logic
- `plugins/camera/proximity_manager.py` — Orchestration, scan suppression, thread-safe callbacks
- `plugins/camera/greeting_player.py` — Thread-safe QObject audio player
- `plugins/camera/camera_overlay.py` — Preview/icon dual-mode overlay
- `config.py` — All camera config variables (lines 282-310)
- `main.py` — Plugin wiring (lines 820-845, 430-436)
- `README.md` — v1.5.0 docs
- `C:\Users\jsanitareephon\Desktop\IT_Service_Desk_Rules.md` — IT policy (not in repo)
