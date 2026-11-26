# 01: People backend, switched on from .env (tracer bullet)

## Objective
`CAMERA_DETECTOR=person` in `.env` makes the running app detect presence with YOLOX-Nano on
the full frame, apply Min Person (box height) and log sizes, with the existing state machine.
Faces mode is unchanged.

## Dependencies
- none

## Scope
- Relevant modules/files:
  - new `plugins/camera/person_detector.py` (`PersonDetector`: load, preprocess, decode, NMS,
    `detect(frame) -> [(x, y, w, h, score)]`)
  - `plugins/camera/proximity_detector.py` (mode `person`, Min Person filter, full-frame input,
    "too small" log, fallback to face)
  - `plugins/camera/proximity_manager.py` (pass the new args; startup log names the active mode)
  - `config.py` (`CAMERA_DETECTOR`, `CAMERA_MIN_PERSON_PCT`, `CAMERA_PERSON_CONFIDENCE`)
  - `main.py` (pass config to the manager)
  - `plugins/camera/models/yolox_nano.onnx` + `NOTICE-YOLOX.md`
  - `requirements.txt` (`onnxruntime`, pinned)
  - new `scripts/detector-poc/app_detector_check.py` (runs the app's `ProximityDetector` in
    People mode on saved frames and prints persons + height %)
  - new `tests/test_person_detector.py`
- Expected behavior: see the spec "Detector contract", "Failure and Edge Cases".

## Acceptance Criteria
- [ ] Given `CAMERA_DETECTOR=person`, When the camera starts, Then the log states the People
      backend is active (model, threads, min person %, confidence).
- [ ] Given a frame with a person box height >= Min Person, When `confirm_frames` such frames
      are processed, Then presence goes empty → present with method `person` and the log shows
      the box height %.
- [ ] Given only smaller persons, Then presence stays empty and a throttled
      "Person seen but too small: NN% of frame height (needs >= MM%)" line appears.
- [ ] Given the model missing or onnxruntime not importable, Then a WARNING names the reason
      and Faces mode runs.
- [ ] Given `CAMERA_DETECTOR=face` (default), Then behaviour and the existing tests are unchanged.
- [ ] `app_detector_check.py` on the POC frames gives the POC's YOLOX-Nano results
      (persons found / 0 on empty cabinet frames).

## Contracts and Constraints
- Decode exactly as `scripts/detector-poc/compare.py` `Yolox` (top-left letterbox 416, BGR
  0-255, grids/strides 8/16/32, objectness x class 0, NMS 0.5). Verify the ONNX output shape
  `(1, 3549, 85)` at load and fall back if it differs.
- onnxruntime `intra_op_num_threads=2`, CPU provider only. Import lazily inside
  `PersonDetector` so Faces stations never load it.
- Unit tests: decoding and thresholds with a stub session returning a crafted
  `(1, 3549, 85)` array; Min Person filter; fallback paths. One test runs the real model on a
  blank frame and expects 0 persons (skipped if onnxruntime missing). No camera photos in the repo.
- Write each test first and watch it fail (TDD).

## Verification
```bash
.venv\Scripts\python.exe -m pytest tests/test_person_detector.py -v
.venv\Scripts\python.exe tests/test_proximity_detector.py
.venv\Scripts\python.exe tests/test_camera_plugin.py
.venv\Scripts\python.exe scripts\detector-poc\app_detector_check.py .scratchpad\yolo-poc\frames
```
Manual: `.env` `CAMERA_DETECTOR=person`, run `main.py`, cabinet for 60 s (no presence), walk in (presence).

## Completion Report
- Changed files:
- Verification results:
- Known limitations:
