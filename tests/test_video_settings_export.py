"""Admin "Export Settings" round-trips every idle screensaver / hold screen / shared video
setting: set it through the admin bridge, export .env, load config from the exported
values, and get the same settings back."""
import importlib
import os
import re
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

KEYS = ("SCREENSAVER_ENABLED", "SCREENSAVER_CONTENT", "SCREENSAVER_IDLE_SECONDS",
        "HOLD_ENABLED", "HOLD_CONTENT", "HOLD_SCANS",
        "VIDEO_LOOP_PAUSE_SECONDS", "SCREENSAVER_MUTED", "SCREENSAVER_CAMERA")

# Every value differs from its config.py default, so a missed key cannot pass by accident
CHANGED = {
    "SCREENSAVER_ENABLED": True, "SCREENSAVER_CONTENT": "image", "SCREENSAVER_IDLE_SECONDS": 125,
    "HOLD_ENABLED": True, "HOLD_CONTENT": "video", "HOLD_SCANS": "block",
    "VIDEO_LOOP_PAUSE_SECONDS": 45, "SCREENSAVER_MUTED": True, "SCREENSAVER_CAMERA": "sound",
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    pytest.importorskip("PyQt6")
    os.environ.setdefault("CLOUD_API_KEY", "test-api-key")
    os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")
    import config
    import main
    from database import DatabaseManager

    saved = {k: getattr(config, k) for k in KEYS}
    db = DatabaseManager(tmp_path / "t.db")
    a = SimpleNamespace(_voice_player=None)
    a._save_setting = lambda k, v: db.set_meta(f"setting:{k}", v)
    monkeypatch.setattr(main, "EXEC_ROOT", tmp_path)
    yield a, main.Api, config, tmp_path
    for k, v in saved.items():
        setattr(config, k, v)
    db.close()


def set_through_admin(a, Api):
    v = CHANGED
    assert Api.admin_set_screensaver(a, v["SCREENSAVER_ENABLED"])["ok"]
    assert Api.admin_set_screensaver_content(a, v["SCREENSAVER_CONTENT"])["ok"]
    assert Api.admin_set_screensaver_idle(a, v["SCREENSAVER_IDLE_SECONDS"])["ok"]
    assert Api.admin_set_hold(a, v["HOLD_ENABLED"])["ok"]
    assert Api.admin_set_hold_content(a, v["HOLD_CONTENT"])["ok"]
    assert Api.admin_set_hold_scans(a, v["HOLD_SCANS"])["ok"]
    assert Api.admin_set_video_loop_pause(a, v["VIDEO_LOOP_PAUSE_SECONDS"])["ok"]
    assert Api.admin_set_screensaver_muted(a, v["SCREENSAVER_MUTED"])["ok"]
    assert Api.admin_set_screensaver_camera(a, v["SCREENSAVER_CAMERA"])["ok"]


def test_export_round_trips_all_video_settings(api, monkeypatch):
    a, Api, config, root = api
    (root / ".env").write_text("# hold screen\nHOLD_SCANS=accept\nHOLD_ENABLED=False\n",
                               encoding="utf-8")
    set_through_admin(a, Api)
    assert Api.admin_export_env(a)["ok"] is True

    text = (root / ".env").read_text(encoding="utf-8")
    assert "# hold screen\nHOLD_SCANS=block\nHOLD_ENABLED=True\n" in text   # edited in place
    exported = dict(re.findall(r"^([A-Z_]+)=(.*)$", text, re.M))
    for key in KEYS:
        assert list(re.findall(rf"^{key}=", text, re.M)) == [f"{key}="], f"{key} once"
        monkeypatch.setenv(key, exported[key])

    # Load config from the exported values only, as a fresh station copying this .env would
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False, raising=False)
    try:
        reloaded = importlib.reload(config)
        assert {k: getattr(reloaded, k) for k in KEYS} == CHANGED
    finally:
        monkeypatch.undo()
        importlib.reload(config)
