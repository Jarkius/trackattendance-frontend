---
query: "camera poc"
target: "trackattendance-frontend"
mode: deep
timestamp: 2026-02-23 17:21
---

# Trace: camera poc

**Target**: trackattendance-frontend
**Mode**: deep (5 parallel agents)
**Time**: 2026-02-23 17:21

## Oracle Results
None — first trace for this topic.

## Git History

### Key Commits (chronological)
1. **d0a596e** — `feat: cross-platform camera POC with Windows 11 compatibility` (2026-02-04)
   - Initial POC: USB scanner, camera scanner, voice feedback, proximity detection
   - Platform auto-detection (Windows/macOS/Linux)
   - 35/35 tests pass on macOS

2. **ff5e92c** — `feat: upgrade proximity detection to MediaPipe face+pose recognition` (2026-02-04)
   - Replaced motion detection with MediaPipe face + pose models
   - Added blaze_face_short_range.tflite and pose_landmarker_lite.task
   - Fallback to motion detection if MediaPipe unavailable
   - 38/38 tests pass on macOS

3. **5737b11** — `feat: add live detection demo script` (2026-02-20)
   - Visual demo with green face bounding boxes, magenta pose skeleton
   - CLI args: --duration, --scale, --confidence, --camera-id

### Branch
- `Jarkius/check-camera-poc` (current, no PR yet)

## Files Found

All in `poc/camera/`:

| File | Purpose | Lines |
|------|---------|-------|
| camera_scanner.py | Camera scanning + ProximityDetector (MediaPipe) | 548 |
| main_system.py | AttendanceSystem integration + CLI | 621 |
| test_poc.py | 34-test comprehensive suite | 645 |
| demo_detection.py | Live face/pose visualization demo | 206 |
| voice_feedback.py | Audio + TTS feedback system | 150+ |
| grant_camera.py | Cross-platform camera permissions | 104 |
| launcher.py | CLI entry point with modes | 110+ |
| web_dashboard.py | Flask REST API dashboard | - |
| database.py | SQLite schema (employees, events, attendance) | - |
| usb_scanner.py | USB HID barcode scanner | - |
| README.md | Full documentation | 378 |
| models/ | blaze_face_short_range.tflite, pose_landmarker_lite.task | - |

## GitHub Issues/PRs
- No dedicated issues or PRs for camera POC
- Related: PR #38 (merged) touched detection/dashboard features

## Cross-Repo Matches
- All camera POC work is self-contained in `poc/camera/` within this repo

## Oracle Memory
- No prior traces, learnings, or retrospectives about camera POC

## Summary

Camera POC is a fully functional prototype in `poc/camera/` on branch `Jarkius/check-camera-poc`. It combines:
- **Camera barcode/QR scanning** via OpenCV + pyzbar
- **Proximity detection** via MediaPipe face+pose (with motion fallback)
- **Voice feedback** via pygame + TTS
- **USB scanner** support
- **Web dashboard** via Flask

The POC is cross-platform (Windows 11, macOS, Linux) with 34+ passing tests on macOS. No PR has been created yet for this branch. No Oracle memory exists for this work — this is the first trace.
