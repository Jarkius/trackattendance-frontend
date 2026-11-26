"""Camera detector settings (People mode): .env parsing, per-station persistence, bridge.

Spec: docs/specs/person-detector-option.md.
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def load_config(monkeypatch):
    """Re-import config with the given env vars (and no .env file influence for these keys)."""
    import config

    def _load(**env):
        for key in ("CAMERA_DETECTOR", "CAMERA_MIN_PERSON_PCT", "CAMERA_PERSON_CONFIDENCE"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False, raising=False)
        return importlib.reload(config)

    yield _load
    importlib.reload(config)


def test_people_settings_default_to_faces_30pct_and_half_confidence(load_config):
    cfg = load_config()
    assert cfg.CAMERA_DETECTOR == "face"
    assert cfg.CAMERA_MIN_PERSON_PCT == 0.30
    assert cfg.CAMERA_PERSON_CONFIDENCE == 0.50


def test_people_mode_is_read_from_env(load_config):
    cfg = load_config(CAMERA_DETECTOR=" Person ", CAMERA_MIN_PERSON_PCT="0.4",
                      CAMERA_PERSON_CONFIDENCE="0.6")
    assert (cfg.CAMERA_DETECTOR, cfg.CAMERA_MIN_PERSON_PCT, cfg.CAMERA_PERSON_CONFIDENCE) == \
        ("person", 0.4, 0.6)


def test_unknown_detector_falls_back_to_faces(load_config):
    assert load_config(CAMERA_DETECTOR="robot").CAMERA_DETECTOR == "face"


def test_people_values_are_clamped(load_config):
    cfg = load_config(CAMERA_MIN_PERSON_PCT="2", CAMERA_PERSON_CONFIDENCE="0.05")
    assert cfg.CAMERA_MIN_PERSON_PCT == 0.90
    assert cfg.CAMERA_PERSON_CONFIDENCE == 0.30


# --- per-station persistence and bridge (ticket 02) ----------------------------

class FakeDetector:
    def __init__(self):
        self.min_person_pct, self.min_size_pct, self.modes = 0.30, 0.20, []


class FakeManager:
    """Stands in for ProximityGreetingManager: records mode switches, can fail People."""

    def __init__(self, people_works=True):
        self.people_works = people_works
        self._detector = FakeDetector()
        self._detector_mode, self._min_person_pct, self._min_size_pct = "face", 0.30, 0.20
        self.active = "face"
        # read by admin_get_local_settings
        self._running, self._show_overlay, self._cooldown = True, False, 60.0
        self._absence_threshold, self._confirm_frames, self._haar_min_neighbors = 5.0, 3, 5

    def set_overlay_mode(self, _on):
        pass

    def set_detector_mode(self, mode):
        self._detector_mode = mode
        self.active = mode if (mode == "face" or self.people_works) else "face"
        return self.active

    @property
    def active_detector(self):
        return self.active


@pytest.fixture
def api(tmp_path, monkeypatch):
    pytest.importorskip("PyQt6")
    os.environ.setdefault("CLOUD_API_KEY", "test-api-key")
    os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")
    import config
    import main
    from database import DatabaseManager
    from types import SimpleNamespace

    saved = {k: getattr(config, k) for k in (
        "CAMERA_DETECTOR", "CAMERA_MIN_PERSON_PCT", "CAMERA_MIN_SIZE_PCT")}
    db = DatabaseManager(tmp_path / "t.db")
    db.set_station_name("T")
    a = SimpleNamespace(_service=SimpleNamespace(_db=db), _proximity_manager=FakeManager(),
                        _voice_player=None)
    a._save_setting = lambda k, v: db.set_meta(f"setting:{k}", v)
    a._config_defaults = {"camera_detector": "face", "min_person_pct": 0.30,
                          "camera_device_id": 0, "greeting_cooldown": 60.0, "min_size_pct": 0.20,
                          "absence_threshold": 5.0, "confirm_frames": 3, "haar_min_neighbors": 5}
    a.db = db
    yield a, main.Api, config
    for k, v in saved.items():
        setattr(config, k, v)
    db.close()


def restart(api_tuple):
    a, Api, config = api_tuple
    config.CAMERA_DETECTOR, config.CAMERA_MIN_PERSON_PCT, config.CAMERA_MIN_SIZE_PCT = "face", 0.30, 0.20
    Api.load_saved_settings(a)


def test_mode_and_min_person_survive_restart(api):
    a, Api, config = api
    assert Api.admin_set_camera_detector(a, "person") == {"ok": True, "value": "person", "active": "person"}
    assert Api.admin_set_min_person_pct(a, 0.35)["value"] == 0.35
    restart(api)
    assert (config.CAMERA_DETECTOR, config.CAMERA_MIN_PERSON_PCT) == ("person", 0.35)


def test_switching_modes_keeps_each_size_setting(api):
    a, Api, config = api
    Api.admin_set_min_size_pct(a, 0.09)
    Api.admin_set_camera_detector(a, "person")
    Api.admin_set_min_person_pct(a, 0.35)
    Api.admin_set_camera_detector(a, "face")
    restart(api)
    assert (config.CAMERA_DETECTOR, config.CAMERA_MIN_SIZE_PCT, config.CAMERA_MIN_PERSON_PCT) == \
        ("face", 0.09, 0.35)


def test_min_person_updates_the_running_detector_and_is_clamped(api):
    a, Api, _ = api
    assert Api.admin_set_min_person_pct(a, 0.02)["value"] == 0.10
    assert Api.admin_set_min_person_pct(a, 5)["value"] == 0.90
    assert a._proximity_manager._detector.min_person_pct == 0.90
    assert a._proximity_manager._min_person_pct == 0.90


def test_unknown_mode_is_rejected(api):
    a, Api, config = api
    assert Api.admin_set_camera_detector(a, "robot")["ok"] is False
    assert config.CAMERA_DETECTOR == "face"


def test_people_that_cannot_run_reports_faces_active(api):
    a, Api, _ = api
    a._proximity_manager.people_works = False
    result = Api.admin_set_camera_detector(a, "person")
    assert result == {"ok": True, "value": "person", "active": "face"}
    settings = Api.admin_get_local_settings(a)
    assert settings["camera_detector"] == "person"
    assert settings["camera_detector_active"] == "face"


def test_settings_getter_reports_people_values(api):
    a, Api, _ = api
    Api.admin_set_camera_detector(a, "person")
    Api.admin_set_min_person_pct(a, 0.4)
    s = Api.admin_get_local_settings(a)
    assert (s["camera_detector"], s["camera_detector_active"], s["min_person_pct"]) == ("person", "person", 0.4)


def test_corrupt_saved_values_are_ignored(api):
    a, _, config = api
    a.db.set_meta("setting:camera_detector", "robot")
    a.db.set_meta("setting:min_person_pct", "banana")
    restart(api)
    assert (config.CAMERA_DETECTOR, config.CAMERA_MIN_PERSON_PCT) == ("face", 0.30)


def test_reset_camera_settings_restores_env_values(api):
    a, Api, config = api
    Api.admin_set_camera_detector(a, "person")
    Api.admin_set_min_person_pct(a, 0.5)
    Api.admin_reset_camera_settings(a)
    assert (config.CAMERA_DETECTOR, config.CAMERA_MIN_PERSON_PCT) == ("face", 0.30)
    assert a._proximity_manager._detector_mode == "face"
    assert a.db.get_meta("setting:camera_detector") is None
    assert a.db.get_meta("setting:min_person_pct") is None


def test_export_env_writes_people_settings(api, tmp_path, monkeypatch):
    a, Api, config = api
    import main
    monkeypatch.setattr(main, "EXEC_ROOT", tmp_path)
    (tmp_path / ".env").write_text("# camera\nCAMERA_DETECTOR=face\n", encoding="utf-8")
    Api.admin_set_camera_detector(a, "person")
    Api.admin_set_min_person_pct(a, 0.35)
    assert Api.admin_export_env(a)["ok"] is True
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "# camera\nCAMERA_DETECTOR=person\n" in text
    assert "CAMERA_MIN_PERSON_PCT=0.35" in text
