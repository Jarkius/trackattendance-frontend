# Suggested GitHub Issues

## 1. Extract configuration and service boundaries
- **Type:** refactor
- **Summary:** Create a `config.py` module for runtime paths and split `AttendanceService` into UI-free core plus Qt adapter.
- **Details:**
  - Move PyInstaller path detection and directory creation out of `main.py` into reusable helpers. 【F:main.py†L52-L110】
  - Introduce a pure-python service that handles employee bootstrapping and exports without `QInputDialog`/`QMessageBox` so headless tests can exercise business logic. 【F:attendance.py†L68-L158】
  - Update `main.py` to rely on the new abstractions and add constructor injection seams.

## 2. Modularize database access layer
- **Type:** refactor
- **Summary:** Break `DatabaseManager` into focused repository classes with shared connection lifecycle management.
- **Details:**
  - Extract station, employee, and scan operations into separate classes or functions to clarify intent and ease mocking. 【F:database.py†L39-L157】
  - Provide transaction helpers and connection context managers to avoid leaking open cursors.
  - Document schema migrations for future changes.

## 3. Isolate workbook ingestion and validation
- **Type:** enhancement
- **Summary:** Create dedicated module for parsing `employee.xlsx`, surfacing validation errors, and updating the DB.
- **Details:**
  - Encapsulate header validation and row cleaning currently in `_bootstrap_employee_directory`. 【F:attendance.py†L52-L107】
  - Emit structured errors/logging so operators know which rows failed.
  - Provide CLI/tests for ingestion without the GUI.

## 4. Rework export pipeline and shutdown flow
- **Type:** refactor
- **Summary:** Extract export logic and window close-event handling into maintainable components.
- **Details:**
  - Create an export writer class that can output XLSX/CSV and is reusable outside the GUI. 【F:attendance.py†L167-L195】
  - Move close-event override in `main.py` into a lifecycle controller that coordinates exports and UI overlays. 【F:main.py†L214-L298】
  - Add unit tests covering shutdown scenarios (successful export, failure, retry).

## 5. Establish automated quality gates
- **Type:** chore
- **Summary:** Introduce linting, typing, and testing workflows to prevent regressions.
- **Details:**
  - Configure `pytest` to replace ad-hoc scripts under `tests/`. 【F:tests/simulate_scans.py†L1-L200】
  - Add `mypy` and `ruff` to enforce style and typing. 【F:main.py†L85-L298】
  - Document commands in `README.md` and wire them into CI (GitHub Actions).

## 6. Enable offline-first cloud synchronization
- **Type:** enhancement
- **Summary:** Build a background synchronization pipeline so kiosks can upload attendance data to a cloud service whenever connectivity is restored, enabling centralized reporting.
- **Details:**
  - Introduce a local queue for unsent scans (e.g., additional SQLite table) and expose service methods to mark entries as synced.
  - Implement a sync worker that triggers on interval and during application shutdown to push pending data to configurable cloud endpoints with retry/backoff logic.
  - Define authentication and payload schemas for the remote API, plus monitoring hooks to track last sync time and outstanding records in the UI.
