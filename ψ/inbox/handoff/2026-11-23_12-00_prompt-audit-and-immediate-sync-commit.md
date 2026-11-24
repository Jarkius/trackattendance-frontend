# Handoff: prompt audit + pending-work commit (2026-11-23)

## What happened this session
1. Ran `/claude-api prompt-audit` on the Claude Code config that loads in this project
   (project `CLAUDE.md`/`AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.claude/agents/impeccable-*.md`,
   `~/.claude/skills/impeccable/SKILL.md`). Target model: Claude Sonnet 5.5.
2. Applied the audit's three stale-fact fixes and merged them to `main` (commit `e05a467`):
   - 5 utility-script paths `scripts/*.py` -> `tests/*.py` (moved in `09fb0e5`)
   - `LOG_LEVEL` -> `LOGGING_LEVEL` (what `config.py:222` reads), plus `DUPLICATE_BADGE_ALERT_DURATION_MS`
   - `scripts/` description now says it holds only `sync-to-saas.sh`
3. Committed the previously pending work and pushed to `main` (`e05a467..4555895`), as three commits:
   - `feat`: optional immediate per-scan cloud upload (`IMMEDIATE_SYNC_ENABLED`, off by default; admin "Immediate Write" toggle;
     `AttendanceService.set_sync_service`, `SyncService.sync_single_scan`, `tests/test_immediate_sync.py`) + version label moved under Dashboard title
   - `build`: `build.bat` now installs to `C:\TrackAttendance` (`nodeploy` skips)
   - `docs`: `ψ/memory` learnings + 2026-09 retrospective; `.gitignore` for `.env.bak*`, `.omc/`, `.omx/`, `logs/cloudrun-*.json`

See `git log` / `git show` for details; nothing here duplicates the diffs.

## State
- Branch: `main`, in sync with `origin/main`.
- Left uncommitted on purpose: `.claude/settings.local.json` (local permissions rule only).
- Leftover branch `docs/fix-stale-script-paths` exists locally and on `origin` (already merged, safe to delete once the user agrees).
- `.env.bak*` files in the repo root are now ignored but still on disk and may hold secrets; user should move/delete them.

## Not verified / open
- I did NOT run the app, `tests/test_immediate_sync.py`, or any other tests this session; the immediate-sync feature was committed after reading the diffs only.
- Immediate-write relies on the idle batch sync to mark rows `synced` later (same idempotency key); worth an end-to-end check against the cloud API before an event.
- Audit flags with no edit made: `AGENTS.md` and `CLAUDE.md` have drifted (AGENTS has `audio.py`/`assets/`; CLAUDE has Cloud API, saas fork, duplicate-detection) — decide whether AGENTS.md becomes a pointer to CLAUDE.md.
  `.scratchpad/build-v2.1.10/` holds frozen copies of both files (gitignored; kept per scratch convention).
- The other 105 `~/.claude/skills/*` (symlinks into `C:\Workspace\AI\skill-hub`) and plugin skills were not audited line by line.

## Suggested skills for the next agent
- `run` — launch the kiosk app and confirm immediate-sync/toggle work in the real app.
- `diagnosing-bugs` — if the immediate-write path misbehaves (queue full, coordinator paused, duplicate uploads).
- `code-review` — review the `feat` commit (`attendance.py`, `sync.py`, `main.py`) before the next release.
- `claude-api` with `prompt-audit` — re-run the audit after further CLAUDE.md edits or a model change.

## Reminders from project CLAUDE.md
Use `.venv\Scripts\python.exe` (system Python lacks PyQt6). Bugfixes to shared code can be ported with `bash scripts/sync-to-saas.sh`.
