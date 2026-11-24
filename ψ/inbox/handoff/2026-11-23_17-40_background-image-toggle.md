# Handoff: background image admin toggle

Date: 2026-11-23 17:40

## Done (commit d2061bc, pushed to main)
- Admin panel > Display > **Background Image** toggle (`admin-party-bg-toggle`). Applies live to `body.party-bg`, persisted in SQLite meta `setting:show_party_background` (overrides `.env` `SHOW_PARTY_BACKGROUND`). Pattern copied from Immediate Write toggle.
- Files: `main.py` (`admin_set_party_background` slot, settings payload key `show_party_background`, load on startup), `web/index.html`, `web/script.js`, `web/css/style.css:25`.
- User renamed `web/images/party-bg.jpg` -> `background.jpg`; CSS updated to match and rename committed.

## Not verified
- User confirmed (2026-11-24) the toggle works at runtime.
- .exe not rebuilt (`build.bat`), so the installed copy lacks this.

## Open items
- `background.jpg` is really a PNG (1536x1024, ~3 MB) with a `.jpg` extension. Works via content sniffing; consider renaming to `.png` and updating the CSS.
- 3:2 image + `cover` crops top/bottom on 16:9 kiosks; a 1920x1080 image would fit better.
- `web/images/footer-city.png` shows as deleted in the working tree. Not done by this session and not committed; confirm with the user whether that is intended.
- Other uncommitted work (attendance.py, dashboard.py, database.py, docs, tests, `.claude/`, `voices/`, other handoffs) is unrelated to this task; left untouched.

## Suggested skills
- `run`: launch the app and confirm the toggle works.
- `pyinstaller-windows-deployment`: rebuild and deploy the .exe.
