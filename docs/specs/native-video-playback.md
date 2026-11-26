# Native video playback for the screensaver and hold screen

## Problem and Goal
Event operators receive the key-visual video as an MP4 (H.264/AAC). PyQt6's QtWebEngine
cannot decode H.264, so the page's `<video>` rejects it and the operator must convert it to
WebM first (`scripts/convert-to-webm.bat`). Qt Multimedia (`QMediaPlayer`, already used for
the voices) does decode it: a 1920x1080 H.264 MP4 played without errors on the kiosk.

Goal: an operator drops an MP4 (or WebM) into `media\` and it plays, with no conversion.
Also, on the hold screen a looping video with sound is tiring during an event; allow a
pause between loops.

## Scope
### In scope
- Play the full-screen display's video through Qt Multimedia in a native panel stacked
  over the `QWebEngineView`, inside the existing frameless full-screen window.
- `web/script.js` keeps every decision: when to show/hide, Esc, Ctrl+Shift+H, scans while
  held, mouse/jitter, camera Wake/Sound/Off, sound fades. It drives the panel through the
  bridge instead of a `<video>` element.
- Choose the video in Python: try `media\` candidates (newest first) then the built-in
  default with Qt's player; keep the first that loads with a video track.
- "Pause between loops" for the video on the idle screensaver and the hold screen
  (seconds, default 0 = continuous). During the pause the video rests silently on its
  first frame (not the image).
- Esc safety net in Python: Esc always takes the panel down, even if the page stops
  responding.

### Non-goals
- Image mode: stays an `<img>` in the page.
- Fill/crop or stretch scaling: keep "contain" (letterbox), as today.
- Removing `scripts/convert-to-webm.bat` (still useful for formats Qt cannot read).

## Domain and Contracts
**Panel** (`native_video.py`, `NativeVideoPanel`): a `QVideoWidget` child of the main window,
kept over the web view's geometry; `Qt.FocusPolicy.NoFocus`,
`WA_TransparentForMouseEvents`, aspect "keep" (contain), black background. Owns one
`QMediaPlayer` and creates its `QAudioOutput` on the current default output device at each
play, so a speaker switched after start-up is used.
- `play(path, volume, loop_pause_s)`, `stop()`, `set_volume(v)` (clamped 0..1).
- `loop_pause_s == 0`: loop forever. `> 0`: at end of media, seek to 0, pause (first frame
  shown, silent), resume after `loop_pause_s`.
- Signal `failed(str)` on a player error while playing.

**Choosing the video** (`NativeVideoPanel` probe, async): candidates from
`screensaver_media.resolve_screensaver_media()["video"]`; a candidate is usable when a
`QMediaPlayer` reaches `LoadedMedia`/`BufferedMedia` with `hasVideo()`; error, invalid
media or a 10 s timeout rejects it with a reason.

**Bridge (`Api`)**, page-facing:
- `get_screensaver_media() -> {video: {name, source}|null, video_rejected: [{name, source,
  why}], image: [candidates], folder}`. Returns `{pending: true}` until the video probe has
  finished; signal `screensaver_media_ready(dict)` delivers the same dict once ready.
- `screensaver_video_play(volume: float, loop_pause_s: int)`: plays the chosen video only. The page cannot
  name a file. No-op returning `{ok: false}` when no video is usable.
- `screensaver_video_stop()`, `screensaver_video_set_volume(float)`.
- Signal `screensaver_video_failed(str)`.
- `admin_set_video_loop_pause(int)`: 0..300 s, persisted as `setting:video_loop_pause_seconds`;
  `.env` `VIDEO_LOOP_PAUSE_SECONDS` (default 0) is the starting value, like the other
  screensaver settings.

## User Behavior and Acceptance Criteria
### Scenario: operator drops an MP4
Given `media\checkin-guide_v07.mp4` (H.264/AAC) is the newest video
When the idle screensaver or hold screen shows video
Then that MP4 plays full screen, letterboxed, with sound per the camera mode

### Scenario: input still reaches the page
Given the video is playing over the page
When Esc is pressed, a badge is scanned, Ctrl+Shift+H is pressed, or the screen is clicked
Then the page receives it exactly as with the old `<video>` (same close/scan/hold behavior)

### Scenario: unplayable file
Given the newest file in `media\` cannot be read by Qt
Then it is skipped, the next candidate plays, and Admin and the log say why

### Scenario: pause between loops
Given the idle screensaver or the hold screen shows video and "Pause between loops" is 30 s
When the video reaches its end
Then it rests on its first frame with no sound for 30 s, then plays again
And with 0 s it loops continuously as before

### Scenario: camera Sound mode
Given camera mode Sound and the video playing silently
When a person is detected
Then the volume fades in over about 2 s, and out after they leave

## UX Contract
Admin gains one shared "Pause between loops" slider under "Screensaver shows" (0–300 s,
step 5), greyed out when both the screensaver and the hold screen show the image. Admin media status line unchanged in form.
Spike evidence (real badge scanner, Esc, clicks reach the page with the panel on top, kiosk
full screen): see PR #121 discussion.

## Failure and Edge Cases
- Player error while playing: panel hides, `screensaver_video_failed` fires, page closes
  the overlay and re-arms (as today on `<video>` error).
- Page unresponsive: Python Esc filter stops the panel; it never consumes the key.
- Window resize / full-screen toggle: panel follows the web view geometry.
- Admin/dashboard opened: the page already closes the screensaver first; the panel stops.
- App shutdown: player stopped before the window closes.

## Security and Operations
- The page can only start the chosen video; no file path crosses the bridge.
- Log: chosen video and rejections at start-up; play/stop/failures with reason.
- Bundle: Qt Multimedia widgets are part of PyQt6 already; no new dependency.

## Decisions and Assumptions
- LOCKED: option B over auto-conversion (user, this PR). Contain scaling. Pause applies to
  both the idle screensaver and the hold screen; it rests on the video's first frame.
- ASSUMED: default pause 0 (off) so behavior is unchanged until an operator sets it.

## Slices (sequential, single owner)
1. **Panel + player** — `native_video.py`: geometry follow, focus/mouse transparency, play/
   stop/volume, loop and pause-between-loops, probe. Unit tests with a fake player.
2. **Wire the page to it** — `Api` slots/signals, video chosen in Python, `web/script.js`
   video path through the bridge, `<video>` removed, Admin status from the Python result,
   Esc safety net. In-engine input check and app run.
3. **Loop pause setting** — config/.env, `admin_set_video_loop_pause`, persisted setting,
   Admin slider, passed to `screensaver_video_play`. Docs.

## Verification
```bash
python -m pytest tests/ --ignore=tests/test_ui_bridge.py --ignore=tests/test_validation_ui.py \
  --ignore=tests/test_camera_plugin.py --ignore=tests/test_proximity_detector.py \
  --ignore=tests/stress_full_app.py --ignore=tests/simulate_scans.py \
  --ignore=tests/simulate_multi_station.py -v --tb=short
node --check web/script.js
python main.py   # manual: MP4 in media\, idle + hold video, Esc, scan, click, Sound mode, pause
```
