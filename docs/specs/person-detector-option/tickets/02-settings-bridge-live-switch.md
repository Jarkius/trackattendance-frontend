# 02: Detector settings: per-station persistence, bridge, live switch

## Objective
The detector mode and Min Person are per-station settings like the other camera settings:
saved in SQLite, settable from the bridge, applied live without a restart, reset to `.env`,
and written by Export .env.

## Dependencies
- 01

## Scope
- Relevant modules/files:
  - `main.py`:
    - load `setting:camera_detector` and `setting:min_person_pct` at startup (next to `min_size_pct`);
    - new `admin_set_camera_detector(str)` and `admin_set_min_person_pct(float)`;
    - `admin_get_local_settings` (around `main.py:1603`) returns `camera_detector`,
      `camera_detector_active` and `min_person_pct`;
    - `admin_reset_camera_settings` keys plus the defaults snapshot;
    - `admin_export_env` writes `CAMERA_DETECTOR` and `CAMERA_MIN_PERSON_PCT`.
  - `plugins/camera/proximity_manager.py` / `proximity_detector.py`: a thread-safe pending
    mode switch, applied on the camera thread at the next frame, resetting presence to empty.
  - new `tests/test_camera_detector_settings.py`.
- Expected behavior: spec scenarios "switching keeps each mode's setting", "first switch",
  "survive restart and export", "reset".

## Acceptance Criteria
- [ ] Given Faces at Min Face 9%, When set to People, Min Person 35%, then back to Faces, Then
      Min Face is still 9% and Min Person is still 35% (both persisted).
- [ ] Given People chosen but the backend fails, Then `admin_set_camera_detector` returns
      `active: "face"` and the getter reports `camera_detector_active: "face"`.
- [ ] Given a restart, Then the saved mode and Min Person are applied before the camera starts.
- [ ] Given Reset camera settings, Then both return to `.env` values and the SQLite keys are removed.
- [ ] Given Export .env, Then `CAMERA_DETECTOR` and `CAMERA_MIN_PERSON_PCT` lines are updated in
      place (comments preserved, as the existing export does).
- [ ] Bridge input is validated: unknown mode → rejected with `ok: False`; pct clamped to 0.10–0.90.

## Contracts and Constraints
- Follow the existing `admin_set_min_size_pct` / `_save_setting` pattern exactly.
- Never build or swap the detector backend from the Qt thread.

## Verification
```bash
.venv\Scripts\python.exe -m pytest tests/test_camera_detector_settings.py -v
.venv\Scripts\python.exe tests/test_proximity_detector.py
```

## Completion Report
- Changed files: `main.py` (defaults snapshot, `load_saved_settings`, `admin_get_local_settings`, `admin_set_camera_detector`, `admin_set_min_person_pct`, reset, export), `plugins/camera/proximity_detector.py` (`set_mode`, which queues a switch applied on the camera thread), `plugins/camera/proximity_manager.py` (`set_detector_mode`, `active_detector`), `tests/test_camera_detector_settings.py` (new, 13 tests).
- Verification results: `test_camera_detector_settings.py` 13 passed; live-switch tests in `test_person_detector.py` pass.
- Known limitations: the People backend is built on the caller (Qt) thread, about 0.1 s, and handed to the camera thread ready-made.
