# 03: Admin UI: Detect chooser, Min Face / Min Person slider, hints

## Objective
An admin can pick Faces or People in Admin → Camera, tune the matching size slider, see the
suggested values, and see when People fell back to Faces.

## Dependencies
- 02

## Scope
- Relevant modules/files:
  - `web/index.html` (Camera section: Detect `adm-opt` buttons with `data-hint`; slider label/value ids)
  - `web/script.js` (load from the settings getter; call `admin_set_camera_detector` /
    `admin_set_min_person_pct`; swap slider label, range (Faces 5–40, People 10–90) and value;
    disable Strictness in People; fallback hint)
  - `web/css/style.css` only if needed (`.adm-opt:disabled`, `.adm-slider:disabled` exist)
- Expected behavior: spec "UX Contract" and the suggested-values table (hint text).

## Acceptance Criteria
- [ ] Given Faces, Then the slider reads "Min Face" with its stored value and Strictness is enabled.
- [ ] When People is picked, Then the slider reads "Min Person" with its own stored value
      (default 30%), Strictness is disabled, and the hint shows the suggested values.
- [ ] Given People chosen and `camera_detector_active == "face"`, Then the hint
      "People detection unavailable on this PC (see log) – using Faces" shows.
- [ ] Reopening Admin shows the persisted mode and values.

## Contracts and Constraints
- Reuse existing chooser/slider helpers (`bindChooser`, `syncSlider`) and the hint pattern
  (`showCameraModeHint`); register listeners after `bindChooser` (known ordering pitfall).
- Check it visually with a disposable `QWebEngineView` launcher and `widget.grab()`
  (`.claude/rules/project-verification.md` "UI runtime").

## Verification
```bash
.venv\Scripts\python.exe -m pytest tests/test_camera_detector_settings.py -v
```
Manual: Admin → Camera on the Poly station; switch modes, move sliders, restart, reopen.

## Completion Report
- Changed files: `web/index.html` (Detect chooser, Min Person row), `web/script.js` (`applyDetectorUi`, chooser and slider bindings, load and reset refresh).
- Verification results: a throwaway QWebEngineView check. Faces shows Min Face, Strictness enabled and the Faces hint. People shows Min Person (30%), Strictness disabled and the People hint. Screenshot reviewed. The script.js syntax check passes.
- Known limitations: two rows, one shown per mode, instead of one swapping slider (same look). The "unavailable" hint and persistence across reopen are still to be checked in the live app.
