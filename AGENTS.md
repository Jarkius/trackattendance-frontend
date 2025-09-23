# Repository Guidelines

## Project Structure & Module Organization
- `main.py` hosts the PyQt6 wrapper that loads the web UI from `web/index.html`; keep desktop-facing logic here.
- Front-end assets live in `web/` (`css/`, `fonts/`, `images/`, `script.js`); mirror this layout for new modules and bundle-ready assets.
- `Backup/` contains legacy templates and experiments; use it only for archived references and avoid loading code from there at runtime.
- Use `.venv/` for the project-specific virtual environment; do not commit its contents.

## Build, Test, and Development Commands
- `python -m venv .venv` - create a fresh environment.
- `.venv\Scripts\activate` - activate the environment on Windows; adapt for other shells when documenting steps.
- `pip install PyQt6 PyQt6-WebEngine` - install the required desktop stack; pin versions in `requirements.txt` when one is introduced.
- `python main.py` - launch the PyQt experience and validate production paths.
- `python test.py` - run the Eel/Chromium fallback; use this to verify the browser-hosted flow.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indentation, PascalCase classes, snake_case functions, and descriptive module names (e.g., `qr_scanner.py`).
- Keep UI bindings in sync: JS identifiers in `web/script.js` should stay camelCase and match element IDs defined in `index.html`.
- Scope CSS by component in `web/css/`; use kebab-case class names and avoid inline styles except for quick diagnostics.
- Provide docstrings for public functions that surface into QWebChannel so the desktop-web contract stays clear.

## Testing Guidelines
- Today we rely on manual verification via `python main.py` (PyQt) and `python test.py` (Eel). Exercise both paths before opening a PR.
- When adding Python logic, seed a `tests/` package with `pytest`; name files `test_<feature>.py` and target >=80% coverage for new code.
- Capture UI diffs with screenshots saved under `Backup/QR2/` (or a newly dated folder) whenever layout shifts.
- Smoke-test on Windows and Chrome-based browsers to ensure animations and transparency settings behave consistently.

## Commit & Pull Request Guidelines
- Local checkout lacks visible history; adopt short, imperative commit summaries (e.g., `Add fade animation for load screen`) with optional detail lines.
- Reference Jira or GitHub issue IDs where applicable, and group related asset changes in the same commit.
- PRs should explain the change, outline validation steps, and attach screenshots or GIFs for any front-end impact.
- Note any configuration changes (env vars, file paths) explicitly so deployment scripts stay in sync.

## Security & Configuration Tips
- Keep secrets and API keys out of the repo; fetch them from environment variables read inside `main.py`.
- Review third-party fonts or images added under `web/fonts` and `web/images` for licensing before publishing builds.
