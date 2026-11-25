# Handoff: TrackAttendance kiosk, camera false detections, YOLO26 person-detection POC

Repo: `C:\workspace\trackattendance-frontend`, branch `feat/kiosk-video-hold-screen`, open PR
https://github.com/Jarkius/trackattendance-frontend/pull/121 (description is up to date and
lists the open items). Read `CLAUDE.md` and `.claude/rules/*.md` first; always use
`.venv\Scripts\python.exe`.

## Already done (do not redo): see commits and docs
- `e3629ae` camera picker fix, screensaver camera modes, diagnostics logging
- `d5e96bb` per-event `media\` folder (newest file first), neutral defaults in `assets/media`
- `7917459` native Qt video playback (MP4), pause between loops: spec
  `docs/specs/native-video-playback.md`
- User-facing config: `docs/CONFIGURATION.md` (Hold Screen & Idle Screensaver section)

## Current focus: the camera counts furniture as a person
Symptom: the Poly Studio R30 camera (Camera 1, wide angle) was pointed at a cabinet and the
log showed `State: empty → present (upperbody, ...)`. Context: Admin "Min Face" (setting
`min_size_pct`) was lowered from 20% to 9% so real faces at the wide-angle lens count; the
Haar upper-body fallback in `plugins/camera/proximity_detector.py` uses the same minimum,
so it now accepts small, furniture-sized boxes.

### Uncommitted change, awaiting evidence (user asked: look at the camera image before code)
- `plugins/camera/proximity_detector.py`: upper-body minimum = 2x face minimum; the
  presence log now includes box px and % of frame width.
- `tests/test_upperbody_size.py`: 4 tests, all passing.
- Not yet verified against a real frame. Keep it uncommitted until the evidence (step 1
  below) supports it; revert if the frame shows a different cause.

### The user wants a POC first: YOLO26n / YOLO26s exported to ONNX or OpenVINO
- **License flag already raised to the user:** Ultralytics YOLO and its weights are AGPL-3.0.
  Fine for a POC. Shipping it, especially in the commercial `trackattendance-saas` fork, needs
  AGPL compliance or an Ultralytics Enterprise license. That is a business decision, still open.
- An isolated POC env is installed (it does not touch the project `.venv`):
  `C:\Users\mymeeting\AppData\Local\Temp\claude\6e6ecdf8fcace09d\ef9ad7ad-3c13-4656-a12f-a56855d70429\scratchpad\yolo-poc\.venv-export`
  (ultralytics 8.4.218, torch 2.15 CPU, onnxruntime 1.32, openvino 2026.4).
  Note: that scratchpad belongs to the previous session; copy the scripts out if it is gone.
- Scripts there (written, **not yet run**):
  - `export_models.py`: downloads `yolo26n`/`yolo26s` and exports ONNX + OpenVINO at 640 and
    320 into `models/`.
  - `yolo_person.py`: kiosk-like runtime (onnxruntime/openvino + OpenCV only, 2 threads):
    `bench <frame.png>` (latency per model), `detect <frame.png> <out.png> [conf]` (person
    boxes per model, tiled image). Its decoder assumes YOLO26's end-to-end output (1,N,6) and
    falls back to the classic (1,84,N) layout with NMS; confirm against the real export.
  - `..\camera_evidence.py <cam_index> <min_size_pct> <out.png>`: grabs a frame from the
    camera and runs the app's *current* YuNet + upper-body detectors, drawing boxes and showing
    old vs new upper-body rule. Run with `.venv\Scripts\python.exe` from the repo.

### Next steps
1. **The kiosk app is now closed** (the user closed it), so the camera is free. With the
   Poly still pointed at the cabinet: run `camera_evidence.py 1 0.09 <out.png>`, **look at the
   image**, and report what produced the "person" (expected: a cyan upper-body box on the
   cabinet). Save frames: cabinet (no person), user in view, user side-on or at the edge.
   Frames show the user's room: keep them in the scratchpad and don't publish them.
2. Run `export_models.py` (needs internet for the weights), then `yolo_person.py bench` on a
   saved frame. Compare with the current detector's per-frame cost. The kiosk's camera loop
   processes about 5 fps (`skip_frames=2` at about 15 fps).
3. Run `yolo_person.py detect` on each saved frame at conf 0.5 and 0.35: false persons on the
   cabinet, misses on the user, box sizes.
4. Report a table to the user: model × runtime × input size → ms mean/p95, false/missed
   persons, added bundle size (onnxruntime about 15 MB vs openvino larger; model file size),
   plus a recommendation and the AGPL decision. Do not integrate into the app until the user
   decides.
5. Then decide the uncommitted upper-body change: commit (if the evidence supports it and YOLO
   is not adopted), or drop it (if YOLO replaces the Haar fallback).

## Still open on PR #121 (no action needed now)
- Pause between loops not yet seen on screen. It's unit-tested; every live run so far closed
  before the video ended. The easiest check is the hold screen with Video: it ignores mouse
  and camera, only Esc closes it.
- Rebuild/test the packaged exe (`build.bat` / `pyinstaller TrackAttendance.spec`); the
  deployed `C:\TrackAttendance` still runs an older build.
- `tests/test_barrier_reset_integration.py` was flaky once while the app ran; it passed 3/3
  on rerun.
- Port shared fixes to the saas fork with `scripts/sync-to-saas.sh` (see `CLAUDE.md`).
- The site's network to Cloud Run drops packets (dashboard waits of 7–90 s, measured outside
  the app); the user was told it's a network issue. A 3 s connect timeout was offered, not done.

## Working agreements learned in this session
- Check real evidence (camera frame, log) before changing detection code.
- Commit or push only when asked; keep unverified changes out of commits.
- The user tests by running `.venv\Scripts\python.exe main.py` in Herdr tab 2 (pane `w7:p3`);
  the log is `logs\trackattendance.log`. A Monitor on that log works well during live tests.
- The CI pytest command crashes in a single run locally (pre-existing); run test files one
  by one (see the loop used in this session: each `tests/test_*.py` minus the CI ignore list).

## Suggested skills
- `superpowers:systematic-debugging` for the false-detection root cause (evidence first).
- `superpowers:test-driven-development` if detection code changes after the POC.
- `superpowers:verification-before-completion` before reporting POC numbers or "fixed".
- `engineering-orchestrator` before starting any integration work after the POC.
- `herdr` to read the user's test pane (only if the user mentions Herdr).
