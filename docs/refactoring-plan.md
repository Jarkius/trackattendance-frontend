# Refactoring Plan

## Goals
- Improve separation of concerns between the desktop shell (PyQt), domain logic, and persistence so each layer can be tested and evolved independently.
- Reduce duplication around employee roster bootstrapping and export handling.
- Harden error handling and validation paths so operational failures present actionable guidance to operators.
- Prepare the codebase for automated testing (unit + integration) and future feature work such as offline queueing, alternative input devices, and background cloud synchronization for centralized reporting.

## Phase 1 – Establish Core Boundaries
1. **Extract application configuration module**
   - Introduce a small module (e.g., `config.py`) that centralizes derived paths such as `DATA_DIRECTORY`, `EXPORT_DIRECTORY`, and `UI_INDEX_HTML`, and exposes helpers for resolving PyInstaller contexts. This removes the need for `main.py` to compute paths itself and simplifies testing of path logic. 【F:main.py†L52-L73】
2. **Split `AttendanceService` responsibilities**
   - Create a domain-level service that purely coordinates database calls, workbook ingestion, and export logic, and move the station configuration dialog + QMessageBox interactions to a thin UI adapter class. This lets the service operate without Qt dependencies, making it suitable for headless tests and alternative interfaces. 【F:attendance.py†L34-L158】
3. **Wrap SQLite access with context-aware repository classes**
   - Replace the monolithic `DatabaseManager` with separate repositories (e.g., `StationRepository`, `EmployeeRepository`, `ScanRepository`) constructed from a shared connection factory. This clarifies intent and enables mocking or swapping persistence later. 【F:database.py†L27-L157】

## Phase 2 – Improve Data Workflows
1. **Normalize workbook ingestion**
   - Extract the workbook parsing logic into a dedicated `workbook_ingestion.py` module with explicit data validation, error types, and logging hooks. This allows CLI tools or background jobs to reuse ingestion without spinning up the GUI. 【F:attendance.py†L52-L107】
2. **Introduce typed DTOs for UI payloads**
   - Define dataclasses for request/response payloads exchanged with the web UI. Use serializer helpers to convert DTOs to dictionaries before sending them through QWebChannel, reducing ad-hoc dict construction and preventing accidental key drift. 【F:attendance.py†L120-L195】
3. **Centralize export writer**
   - Move spreadsheet export behavior into a reusable writer class that accepts scan iterables and column configuration. This enables future CSV/JSON exporters and allows tests to assert on workbook content without invoking Qt. 【F:attendance.py†L167-L195】

## Phase 3 – Desktop Shell Cleanup
1. **Refactor `initialize_app`**
   - Break `initialize_app` into composable helpers: one for window construction, one for channel wiring, and one for load handling. This reduces cognitive load and facilitates future embedding scenarios (e.g., kiosk mode vs. windowed mode). 【F:main.py†L85-L180】
2. **Isolate shutdown/export orchestration**
   - Move the close-event override and export trigger logic into a `WindowLifecycleController` class responsible for listening to signals and interacting with the service. This keeps `main.py` declarative and unit-testable. 【F:main.py†L214-L298】
3. **Add dependency injection seams**
   - Allow `main()` to receive factories for the service and API objects, enabling CLI hooks and test harnesses to supply fakes. This makes it feasible to write regression tests covering the PyQt wiring without touching production services. 【F:main.py†L187-L306】

## Phase 4 – Testing & Tooling
1. **Set up unit test scaffolding**
   - Configure `pytest` with fixtures that provide an in-memory SQLite database and temporary directories. Port the scripts under `tests/` into automated tests that validate scan registration, export formatting, and workbook ingestion. 【F:tests/simulate_scans.py†L1-L200】
2. **Add type checking and linting**
   - Adopt `mypy` (with `qtpy-stubs` or protocol interfaces for Qt objects) and `ruff` to enforce import hygiene, unused detection, and style consistency. This will surface latent bugs, such as assuming attributes exist on Qt wrappers, during CI instead of runtime. 【F:main.py†L85-L298】
3. **Document developer workflows**
   - Expand `README.md` with instructions for running the new tests and toolchain, including notes on PyQt environment prerequisites and how to supply sample data. Encourage contributors to use the new modules and DTOs.

## Phase 5 – Iterative Enhancements
1. **Front-end module reorganization**
   - Convert `web/script.js` into ES modules with separate files for API bridge, state management, and UI rendering. This will dovetail with DTO changes and simplify writing front-end unit tests. 【F:web/script.js†L1-L200】
2. **Offline-first sync and cloud reporting**
   - Design a synchronization service that queues unsent attendance events locally (e.g., SQLite table or durable queue) and pushes batches to a cloud API when an internet connection becomes available. Ensure retries and exponential backoff so kiosks remain resilient during flaky connectivity.
   - Provide a background worker hook that can be triggered on interval, on successful export, or during application shutdown to flush pending data. Surface status to operators (e.g., pending count, last sync time) through the UI.
   - Define cloud-side contract requirements (API endpoints, authentication, data retention) and include environment-based configuration so deployments can opt into cloud sync without affecting purely offline setups.
3. **Telemetry and logging pipeline**
   - Introduce structured logging (e.g., JSON logs) from the Python side and surface key events (scan success/failure, exports, sync attempts) for future monitoring or audit requirements.
4. **Accessibility & UX review**
   - Evaluate keyboard focus management, color contrast, and error messaging in the web UI after refactors to ensure the kiosk experience remains inclusive.

## Deliverables
- New modules (`config.py`, `repositories/`, `workbook_ingestion.py`, exporter classes) with unit tests.
- Updated `main.py` and `attendance.py` leveraging the extracted layers.
- CI workflow running lint, type-check, and test jobs.
- Documentation updates describing the architecture and operational playbooks.
