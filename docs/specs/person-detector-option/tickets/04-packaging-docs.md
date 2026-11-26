# 04: Packaging and docs

## Objective
The packaged exe runs People mode (onnxruntime + model + notice bundled), and the docs explain
when to use each mode and the suggested values.

## Dependencies
- 01 (can run in parallel with 02/03; docs mention the Admin controls from 03)

## Scope
- Relevant modules/files:
  - `TrackAttendance.spec` (onnxruntime DLLs via `collect_dynamic_libs('onnxruntime')` or
    equivalent; `plugins/camera/models` already bundled)
  - `build.bat` if it lists dependencies
  - `docs/CONFIGURATION.md` (Camera Detection table: new keys; "Detect: Faces vs People"
    with the suggested-values table from the spec; the detection-chain line)
  - `.env.example`, `README.md` (camera section), `CLAUDE.md` env-variable list
- Expected behavior: spec "Security and Operations", "Suggested values".

## Acceptance Criteria
- [ ] `pyinstaller TrackAttendance.spec` builds; the exe started with `CAMERA_DETECTOR=person`
      logs the People backend active (not the fallback).
- [ ] The exe size grows by about 25 MB or less; note the measured number in the report.
- [ ] CONFIGURATION.md documents `CAMERA_DETECTOR`, `CAMERA_MIN_PERSON_PCT`,
      `CAMERA_PERSON_CONFIDENCE`, the suggested values, and that People ignores
      `CAMERA_DETECTION_SCALE` and Strictness.
- [ ] `NOTICE-YOLOX.md` ships next to the model in the exe.

## Contracts and Constraints
- Do not overwrite existing docs wholesale; edit the relevant sections only.

## Verification
```bash
pyinstaller TrackAttendance.spec
```
Manual: run the built exe on the Poly station in People mode; check the log.

## Completion Report
- Changed files: `TrackAttendance.spec` (onnxruntime shipped as files and excluded from analysis, `msvcp140*.dll` bundled, run-time hook), `build_hooks/rthook_msvc_runtime_first.py` (new), `docs/CONFIGURATION.md`, `.env.example`, `README.md`, `CLAUDE.md`.
- Verification results: `pyinstaller TrackAttendance.spec` builds. The exe started with `CAMERA_DETECTOR=person` logs "People detection active" and detects on the Poly. Without the hook it crashed (exit 139).
- Known limitations: the exe grew by about 54 MB (696 → 750 MB), not about 25 MB. Tested on this PC only; the hook makes camera stations use the bundled 14.51 runtime.
