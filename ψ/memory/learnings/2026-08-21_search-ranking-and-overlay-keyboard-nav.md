# Lesson Learned: Search Ranking Tiers and Overlay Event-Handler Coverage

**Date**: 2026-08-21
**Context**: Sync-coordinator bugfix session (#65–#69), followed by two live UX bugs the user found while testing: `search_employee()` ranking and the employee-lookup overlay's keyboard/scroll behavior.

## Pattern: "Prefix match" is not one tier — first-word-prefix and later-word-prefix can conflict

`AttendanceService.search_employee()` originally treated "query is a substring of the name, anywhere" as a single tier, capped at 10 results in employee-cache iteration order. For a short query like `"c"`, this let a name that merely *contains* the letter (e.g. "Marcus") fill all 10 slots before a name that actually *starts with* it (e.g. "Carlos") was ever considered. The first fix split this into "prefix match" vs "contains anywhere" — but that wasn't the full picture either: within "prefix match," a query like `"j"` still let a surname-prefix hit ("Parichart **J**iravachara") outrank a first-name-prefix hit ("**J**ihun Jung"), because both landed in the same bucket with no further ordering. **Rule**: when ranking name/text search results by prefix relevance, distinguish which *word* of a multi-word field the query prefixes — first word first, other words after — don't treat "starts with" as a single flat tier. Test against realistic multi-field data (first name + surname, not just a two-item synthetic pair) to catch this the first time.

## Discovery: Multiple Python interpreters on one machine is a standing, recurring risk here

This machine has at least three separate Python installs capable of running this PyQt6 app: the sandbox default (`C:\Python314\python.exe`, no PyQt6), a standalone Python 3.12 with PyQt6 (used for test verification in an earlier session), and the project's own `.venv` (Python 3.12, PyQt6, the actually-intended one per `CLAUDE.md` setup instructions). A user running `python .\main.py` hit `ModuleNotFoundError: No module named 'PyQt6'` simply because PATH resolved to the wrong one. **Rule**: when a `ModuleNotFoundError` looks like it "shouldn't happen" for a dependency you've already verified elsewhere, check *which* Python actually ran (`.venv/Scripts/python.exe` vs bare `python` vs another absolute path) before assuming the dependency itself is missing.

## Pattern: check for already-running instances before relaunching a GUI app

Running the app twice from two different interpreters against the same SQLite database happened twice in this session — once caught by checking `tasklist`, once needing `Get-CimInstance Win32_Process` to see the actual command line (`tasklist` alone doesn't show it, so two `python.exe` entries look identical until you check what each one is actually running). **Rule**: before relaunching a GUI app that owns a shared local database file, check for already-running instances with a command that shows the full command line, not just the process name.

## Pattern: a new modal/overlay must be added to every existing global event-handler branch, not just its own open/close functions

`web/script.js` has a global `document.keydown` handler with explicit branches for the admin overlay and dashboard overlay's `Escape` behavior, and a global `document.click` handler with explicit branches for which overlays should keep focus. The employee-lookup overlay was added later and had its own `hideLookupOverlay()`/`showLookupOverlay()` functions, but was never added to either global handler — so `Escape` fell through to closing the entire app window while the lookup overlay was open, and clicking inside it could steal focus back to the scan input. **Rule**: when adding a new modal/overlay to a codebase that already has global keyboard/click handlers special-casing existing overlays, grep for those handlers and add the new overlay to every branch — don't assume its own open/close functions are sufficient.
