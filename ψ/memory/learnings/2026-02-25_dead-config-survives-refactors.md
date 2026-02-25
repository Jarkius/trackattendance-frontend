# Dead Config Variables Survive Refactors

**Date**: 2026-02-25
**Project**: trackattendance-frontend
**Context**: CAMERA_GREETING_COOLDOWN_SECONDS was documented, passed through init, stored on self, but never read after the state machine replaced the cooldown approach

## Pattern

When replacing a mechanism (e.g., time-based cooldown → state machine), audit all references to the old config variable. The variable may survive in:
1. `.env` / `.env.example` — users keep setting it
2. `config.py` — still parsed and validated
3. Constructor params — still passed through layers
4. `self.cooldown` — still stored, never read

## Why It Matters

- Users think they're tuning behavior but nothing changes
- Config documentation becomes misleading
- No test catches it because no test exercises the config→behavior path

## Resolution Options

- **Delete**: if the behavior is truly gone
- **Repurpose**: if the variable fills a new behavioral gap (preferred here — cooldown became min gap between greetings)
- **Deprecate with warning**: log a warning if set, pointing to the replacement
