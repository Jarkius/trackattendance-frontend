# Project Verification and Conventions

Project-specific facts that the shared engineering skills read. Skills say "the project's CI test command"; this file defines it.

## Verification

- Activate `.venv` first (`.venv\Scripts\activate`), as `CLAUDE.md` explains.
- CI test command, from `.github/workflows/test.yml`:

```bash
python -m pytest tests/ \
  --ignore=tests/test_ui_bridge.py \
  --ignore=tests/test_validation_ui.py \
  --ignore=tests/test_camera_plugin.py \
  --ignore=tests/test_proximity_detector.py \
  --ignore=tests/stress_full_app.py \
  --ignore=tests/simulate_scans.py \
  --ignore=tests/simulate_multi_station.py \
  -v --tb=short
```

- Focused scripts are listed under Commands in `CLAUDE.md`.
- CI runs no lint or typecheck. Treat that as a known gap, not a requirement.
- Build and packaging check: `pyinstaller TrackAttendance.spec`.

## Conventions

- Config flags: add them to `config.py` with a `.env` override, defaulting off.
- Learnings and retrospectives: `ψ/memory/`.
- Glossary and ADRs: `GLOSSARY.md` at the repo root and `docs/adr/`, both created lazily.

## UI runtime

The UI is a PyQt6 `QWebEngineView` kiosk, not a browser route.
- Prototype by loading throwaway HTML into a separate `QWebEngineView` window from a disposable launcher script, so it keeps the real `web/` styling (Materialize CSS). Do not wire it to SQLite or the cloud API.
- Capture screenshots of the widget with `widget.grab()`. No browser-automation setup is documented.

## Review radar

Stack-specific patterns for `system-review` (Python, PyQt6, SQLite, vanilla JS in `web/`):
- Bare or overly broad `except` clauses that swallow sync or database errors.
- Raw SQL built with string formatting or concatenation instead of parameters.
- Unvalidated data crossing the QWebChannel bridge between `web/script.js` and Python.
- Untrusted input passed to `eval`, `exec`, `pickle`, or `yaml.load` without a safe loader.
