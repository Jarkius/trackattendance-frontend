# Per-station "People" camera detector (YOLOX-Nano)

## Problem and Goal

On wide-angle stations (Poly Studio R30) the camera decides badly whether someone is there:

- The Haar upper-body fallback counts furniture as a person. An open shelf with a bag
  fired on 6 of 10 empty frames, enough for the 3-frame confirmation. That woke the
  screensaver and played the greeting.
- Faces are small on a wide lens, so real people are missed. Far back facing the camera
  scored 0 of 8; partial, turned-away and walking people were mostly missed too.

The POC (`ψ/memory/learnings/2026-11-26_person-detector-poc.md`, scripts in
`scripts/detector-poc/`) measured YOLOX-Nano on 39 person frames and 18 empty frames from this
station. It found the person in all but one frame and raised 0 false alarms. It takes about
29 ms per frame (onnxruntime, 2 threads) and is Apache-2.0.

**Goal:** an Admin choice per station, **Detect: Faces | People**. People mode uses YOLOX-Nano
on the full camera frame, with its own distance setting "Min Person", so a wide-lens station
running the video loop wakes and unmutes for real people only. Faces mode stays exactly as
today.

## Scope

### In scope

- A YOLOX-Nano person backend (onnxruntime CPU, 2 threads) inside `ProximityDetector`, chosen
  by `CAMERA_DETECTOR=face|person`.
- A "Min Person" threshold measured on **box height as a fraction of frame height**.
  Diagnostics log lines show the size of every person seen and why one did not count.
- Admin: a Detect chooser, the Min Face / Min Person slider swap, Strictness disabled in
  People mode, live switching with no restart, per-station persistence, reset, `.env` export.
- Fallback to Faces with a clear log line and Admin hint when the model or onnxruntime can't
  load.
- Packaging: the `onnxruntime` requirement, the model file and its Apache-2.0 notice in the
  exe. Docs.

### Non-goals

- Changing Faces mode, including its Haar upper-body fallback. Stations with the cabinet
  problem switch to People.
- GPU or OpenVINO. YOLO26 or other AGPL models. Multi-person counting, tracking or analytics.
- Porting to `trackattendance-saas`. It is allowed (Apache-2.0), but a separate
  `scripts/sync-to-saas.sh` step after this ships.
- Badge scanning by camera (unchanged: USB only).

## Domain and Contracts

### Settings

These follow the existing camera-setting pattern: `config.py` + `.env`, SQLite override
`setting:<key>`, `admin_set_*` slot, reset, export.

| Key (.env / SQLite) | Type, range | Default | Applies to |
|---|---|---|---|
| `CAMERA_DETECTOR` / `camera_detector` | `face` \| `person` | `face` | both |
| `CAMERA_MIN_PERSON_PCT` / `min_person_pct` | float 0.10–0.90 | `0.30` | People |
| `CAMERA_PERSON_CONFIDENCE` (.env only) | float 0.30–0.90 | `0.50` | People |
| `CAMERA_MIN_SIZE_PCT` / `min_size_pct` (existing, "Min Face") | 0.05–0.80 | `0.20` | Faces |
| `CAMERA_HAAR_MIN_NEIGHBORS` (existing, "Strictness") | 2–10 | `5` | Faces only |
| `CAMERA_CONFIRM_FRAMES`, `CAMERA_ABSENCE_THRESHOLD_SECONDS` (existing) | unchanged | 3, 5 | both |
| `CAMERA_DETECTION_SCALE` (existing) | unchanged | 0.5 | Faces only (People uses the full frame) |

Each mode keeps **its own** size value. Switching never overwrites the other mode's value.

### Suggested values (shown as the Admin hint, documented in CONFIGURATION.md)

POC measurements on a Poly R30 at 640×480:
- person about 4–5 m away, facing the camera: box height **41%**;
- people further back across the room: **14%**;
- close, at the kiosk: **100%**.

| Station | Detect | Size setting | Why |
|---|---|---|---|
| Normal webcam, greeting only | Faces | Min Face 20% (default) | Unchanged behaviour |
| **Poly wide lens, video loop (wake / sound)** | **People** | **Min Person 30%** (default) | Counts someone about 4–5 m away (41%) and ignores people across the room (14%) |
| Busy hall, people walking close behind | People | Min Person 40–50% | Only people nearly at the kiosk |
| Small room, wake from further away | People | Min Person 20–25% | Earlier wake, but passers-by can wake it |
| Wide lens but must stay on Faces | Faces | Min Face 9–10% | Faces are small on a wide lens. Expect furniture false alarms from the upper-body fallback |

Confirm frames 3 and absence 5 s stay as they are in both modes.

### Detector contract

- `ProximityDetector(..., detector="face"|"person", min_person_pct=0.30, person_confidence=0.5)`.
  The state machine (confirm, absence, cooldown, callbacks) is shared and unchanged.
- In People mode a frame "has a person" when any detection with class 0 has
  `score >= person_confidence` and `box_height / frame_height >= min_person_pct`.
  `detection_method` is `"person"`. `last_faces` holds the counted person boxes for the overlay.
- A new `PersonDetector` (`plugins/camera/person_detector.py`) does the YOLOX-Nano
  preprocessing and decoding. That means a top-left letterbox to 416, BGR 0–255, grid/stride
  decode, objectness × class score, then NMS 0.5; see `scripts/detector-poc/compare.py`
  `Yolox`. Its interface is `detect(frame) -> list[(x, y, w, h, score)]` in frame pixels.
- Model: `plugins/camera/models/yolox_nano.onnx` (3.6 MB, Megvii release 0.1.1rc0), with
  `plugins/camera/models/NOTICE-YOLOX.md` (Apache-2.0 text or link, source URL, SHA-256).
- Bridge, following existing camera slots:
  - `admin_set_camera_detector(str) -> {"ok", "value", "active"}`. `active` is the mode
    really running, which can be `face` after a fallback.
  - `admin_set_min_person_pct(float) -> {"ok", "value"}`.
  - `admin_get_local_settings` adds `camera_detector`, `camera_detector_active` and
    `min_person_pct`.

## User Behavior and Acceptance Criteria

### Scenario: furniture does not wake a People station
Given Detect = People, Min Person 30%, the camera on the cabinet and nobody in view
When the camera runs for 60 s
Then the log has no `State: empty → present`, and the screensaver stays up and muted.

### Scenario: a person approaching wakes it
Given Detect = People and the screensaver video looping with camera mode `wake` (or `sound`)
When a person walks to about 4 m from the camera, facing it
Then within about 1 s the log shows `State: empty → present (person, ...)` with the box height %,
and the screensaver closes (`wake`) or its sound fades in (`sound`).

### Scenario: people across the room are ignored
Given Detect = People, Min Person 30%
When only people well behind the kiosk are in view (box height below 30%)
Then presence stays `empty`, and a throttled log line reports
`Person seen but too small: NN% of frame height (needs >= 30%)`.

### Scenario: switching keeps each mode's setting
Given Faces mode with Min Face 9%
When the admin switches to People, sets Min Person 35%, then switches back to Faces
Then Min Face still shows 9%; switching to People again shows 35%.
The switch takes effect without a restart, and presence resets to `empty`.

### Scenario: first switch to People shows the default
Given a station that never used People mode
When the admin picks People
Then Min Person shows the `.env` value (default 30%), and the hint names the suggested values.

### Scenario: settings survive restart and export
Given People mode with Min Person 35%
When the app restarts, or the admin clicks Export .env
Then the station starts in People mode at 35%, and `.env` gets
`CAMERA_DETECTOR=person` and `CAMERA_MIN_PERSON_PCT=0.35`.

### Scenario: reset camera settings
When the admin clicks Reset camera settings
Then Detect and Min Person return to their `.env` values, like the other camera settings.

### Scenario: Faces mode is unchanged
Given Detect = Faces
Then detection, logging and settings behave as before this change, and the existing camera
tests pass unchanged.

## UX Contract

- Admin → Camera gets a **Detect** chooser (Faces | People) above the size slider, using the
  same `adm-opt` buttons as the screensaver choosers, with `data-hint` text. The hints are
  "Faces: needs a visible face, best for normal webcams" and "People: whole body, for
  wide-angle cameras; ignores furniture".
- The size slider's label and value follow the active mode: "Min Face" (5–40%) or
  "Min Person" (10–90%), each showing its own stored value.
- Strictness is disabled (`.adm-slider:disabled`, already styled) in People mode.
- If People was chosen but `active` is `face`, show an inline hint: "People detection
  unavailable on this PC (see log) – using Faces".

## Failure and Edge Cases

- onnxruntime import fails, the model file is missing, or the session fails to create:
  log a WARNING with the reason, run Faces, and report `active = "face"`. Never crash the
  camera thread.
- An inference exception on one frame: log it at most once a minute and treat the frame as
  "no person". Three such failures in a row switch to Faces with a WARNING.
- Live switch while the camera thread runs: the backend swap happens on the camera thread at
  the next frame (a pending-mode flag), not from the Qt thread. No frame is processed by a
  half-built detector.
- Out-of-range values from `.env`, SQLite or the bridge are clamped, as the existing
  `_safe_float` and `admin_set_*` do. An unknown `CAMERA_DETECTOR` falls back to `face` with
  a log line.

## Security and Operations

- Privacy: frames are never saved or sent; only box sizes and scores are logged.
  Unchanged from today.
- Performance budget: People inference ≤ 50 ms mean on the kiosk CPU, with onnxruntime
  `intra_op_num_threads=2`. The existing `skip_frames=2` keeps it at about 5 inferences per
  second. Log the mean inference time once a minute at DEBUG.
- Packaging adds about 54 MB (measured: 696 → 750 MB). The onnxruntime binaries are 44 MB and the model is 3.6 MB.
- Licence: YOLOX code and weights are Apache-2.0 and need the NOTICE file. onnxruntime is MIT.
  No AGPL components.
- Rollout: the default stays `face`, so existing stations are unaffected. Enable People per
  station from Admin, then Export .env.

## Decisions and Assumptions

- LOCKED (user, 2026-11-26): drop the upper-body size tweak. Add People detection as a
  per-station option. Use an Apache-licensed model.
- LOCKED (POC evidence): YOLOX-Nano with onnxruntime. OpenCV DNN gives the same detections
  but took 41–69 ms on 8 threads and 149 ms on 2, so it is too costly. YOLOX-Tiny and
  D-FINE-N found people no better and were 2–6× slower.
- ASSUMED: Min Person default 30%, measured on box height. Based on one room and one camera.
  The size log lines let each station tune it.
- ASSUMED: People mode ignores `CAMERA_DETECTION_SCALE` and uses the full frame. YOLOX
  resizes to 416 anyway, and halving the frame loses far-away people.
- DEFERRED: a saas port, a person-count display, and an upper-body fix for Faces mode.
- LOCKED (found during implementation, 2026-11-26): **onnxruntime must load before PyQt6.**
  PyQt6 ships MSVC runtime 14.26; onnxruntime 1.32 loaded after it crashes the process
  (access violation, no Python traceback). Handled at four points:
  1. `main.py` imports onnxruntime before PyQt6 on camera stations.
  2. `tests/conftest.py` does the same for pytest.
  3. `PersonDetector` refuses to load onnxruntime after Qt (Faces fallback, not a crash).
  4. The exe: onnxruntime is shipped as plain files, because PyInstaller's dependency scan
     crashed the same way. The current `msvcp140*.dll` is bundled, and
     `build_hooks/rthook_msvc_runtime_first.py` loads it before PyInstaller's PyQt6 hook
     imports QtCore.
- Deviation: the exe grew by about 54 MB (696 → 750 MB), not about 25 MB. onnxruntime's two
  binaries are 44 MB.
- Deviation (UI): Min Face and Min Person are two slider rows, and the one for the active
  mode is shown. That is simpler than one slider changing range and default mark, and looks
  the same to the user.

## Verification

```bash
# unit tests (new + existing camera tests; camera tests are run individually, as CI ignores them)
.venv\Scripts\python.exe -m pytest tests/test_person_detector.py tests/test_camera_detector_settings.py -v
.venv\Scripts\python.exe tests/test_proximity_detector.py
.venv\Scripts\python.exe tests/test_camera_plugin.py
# CI suite (see .claude/rules/project-verification.md)
.venv\Scripts\python.exe -m pytest tests/ --ignore=tests/test_ui_bridge.py --ignore=tests/test_validation_ui.py --ignore=tests/test_camera_plugin.py --ignore=tests/test_proximity_detector.py --ignore=tests/stress_full_app.py --ignore=tests/simulate_scans.py --ignore=tests/simulate_multi_station.py -v --tb=short
# same detections as the POC on the saved frames (local only; frames are gitignored)
.venv\Scripts\python.exe scripts\detector-poc\app_detector_check.py .scratchpad\yolo-poc\frames
# packaging
pyinstaller TrackAttendance.spec
```

Manual, on the Poly station:
- cabinet only for 60 s: no presence;
- walk in to about 4 m: wake or sound within about 1 s;
- people across the room: no wake, "too small" log lines;
- switch modes in Admin: values kept; restart: mode kept;
- rename the model file: Faces fallback and the Admin hint.
