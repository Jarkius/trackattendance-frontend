"""People mode of the camera plugin: YOLOX-Nano decoding (PersonDetector) and the
ProximityDetector state machine fed by it (Min Person on box height, fallback to faces).

Spec: docs/specs/person-detector-option.md. Uses stub onnxruntime sessions with crafted
outputs, plus one run of the real model on a blank frame. No camera photos.
"""
import logging
import os
import sys
import types

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")
if not hasattr(cv2, "resize"):  # another test file may have replaced cv2 with a mock
    pytest.skip("real OpenCV not available", allow_module_level=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plugins.camera.person_detector import (  # noqa: E402
    PersonDetector, PersonDetectorUnavailable, MODEL_PATH, GRID_ROWS)
from plugins.camera.proximity_detector import ProximityDetector  # noqa: E402

STRIDE8_CELLS = 52  # 416 / 8


class StubSession:
    """Stands in for onnxruntime.InferenceSession: returns a fixed raw YOLOX output."""

    def __init__(self, output, shape=(1, GRID_ROWS, 85)):
        self.output, self.shape, self.calls = output, list(shape), []

    def get_inputs(self):
        return [types.SimpleNamespace(name="images", shape=[1, 3, 416, 416])]

    def get_outputs(self):
        return [types.SimpleNamespace(name="output", shape=self.shape)]

    def run(self, _names, feed):
        self.calls.append(feed["images"].shape)
        return [self.output]


def raw_output(cells=(), shape=(1, GRID_ROWS, 85)):
    """cells: (cx, cy, size_px, objectness, person_score, other_class_score) on the stride-8 grid."""
    out = np.zeros(shape, np.float32)
    for cx, cy, size, obj, person, other in cells:
        row = out[0, cy * STRIDE8_CELLS + cx]
        row[0:2] = 0.5                      # offset inside the cell -> centre at (cx+0.5)*8
        row[2:4] = np.log(size / 8.0)       # wh are log(size / stride)
        row[4], row[5], row[6] = obj, person, other
    return out


def detector_with(output, confidence=0.5):
    return PersonDetector(confidence=confidence, session=StubSession(output))


# --- PersonDetector: decoding -------------------------------------------------

def test_decodes_a_person_box_in_frame_pixels():
    det = detector_with(raw_output([(10, 20, 80, 1.0, 0.9, 0.0)]))
    boxes = det.detect(np.zeros((416, 416, 3), np.uint8))
    assert len(boxes) == 1
    x, y, w, h, score = boxes[0]
    assert (round(x), round(y), round(w), round(h)) == (44, 124, 80, 80)
    assert score == pytest.approx(0.9)


def test_scales_boxes_back_through_the_top_left_letterbox():
    # 640x480 -> scale 0.65 into 416x416, padded at the bottom only (YOLOX pads top-left)
    det = detector_with(raw_output([(10, 20, 80, 1.0, 0.9, 0.0)]))
    x, y, w, h, _ = det.detect(np.zeros((480, 640, 3), np.uint8))[0]
    assert (x, y, w, h) == pytest.approx((44 / 0.65, 124 / 0.65, 80 / 0.65, 80 / 0.65), abs=0.01)


def test_feeds_a_416_letterboxed_bgr_blob():
    session = StubSession(raw_output())
    PersonDetector(session=session).detect(np.zeros((480, 640, 3), np.uint8))
    assert session.calls == [(1, 3, 416, 416)]


def test_ignores_low_scores_and_other_classes():
    det = detector_with(raw_output([
        (5, 5, 40, 1.0, 0.4, 0.0),    # person but below 0.5
        (30, 30, 40, 1.0, 0.1, 0.99),  # confidently another class
        (40, 10, 40, 0.5, 0.9, 0.0),   # objectness x person = 0.45
    ]))
    assert det.detect(np.zeros((416, 416, 3), np.uint8)) == []


def test_merges_overlapping_boxes_of_one_person():
    det = detector_with(raw_output([(10, 20, 80, 1.0, 0.9, 0.0), (11, 20, 80, 1.0, 0.8, 0.0)]))
    assert len(det.detect(np.zeros((416, 416, 3), np.uint8))) == 1


def test_rejects_a_model_with_an_unexpected_output_layout():
    with pytest.raises(PersonDetectorUnavailable, match="output"):
        PersonDetector(session=StubSession(raw_output(), shape=(1, 84, 2100)))


def test_missing_model_file_is_reported_as_unavailable(tmp_path):
    with pytest.raises(PersonDetectorUnavailable, match="not found"):
        PersonDetector(model_path=str(tmp_path / "missing.onnx"))


def test_real_model_finds_nobody_in_a_blank_frame():
    pytest.importorskip("onnxruntime")
    det = PersonDetector()
    assert os.path.exists(MODEL_PATH)
    assert det.detect(np.full((480, 640, 3), 128, np.uint8)) == []


# --- ProximityDetector in People mode -----------------------------------------

class FakePerson:
    """PersonDetector stand-in: returns preset boxes, records frame sizes it was given."""

    def __init__(self, boxes=(), error=None):
        self.boxes, self.error, self.frames = list(boxes), error, []

    def detect(self, frame):
        self.frames.append(frame.shape[:2])
        if self.error:
            raise self.error
        return list(self.boxes)


def people_detector(fake, **kw):
    kw.setdefault("confirm_frames", 3)
    return ProximityDetector(detector="person", skip_frames=0, cooldown=0,
                             person_factory=lambda: fake, **kw)


FRAME = np.zeros((480, 640, 3), np.uint8)


def run(det, n):
    for _ in range(n):
        det.process_frame(FRAME)


def test_tall_enough_person_becomes_present(caplog):
    fake = FakePerson([(100, 50, 120, 200, 0.86)])  # 200 / 480 = 42% of frame height
    det = people_detector(fake, min_person_pct=0.30)
    assert det.active_detector == "person"
    with caplog.at_level(logging.INFO):
        run(det, 3)
    assert det.presence_state == "present"
    assert det.detection_method == "person"
    assert det.last_faces == [[100, 50, 120, 200]]
    assert "42% of frame height" in caplog.text


def test_person_smaller_than_min_person_does_not_count(caplog):
    fake = FakePerson([(300, 100, 30, 67, 0.9)])  # 67 / 480 = 14%
    det = people_detector(fake, min_person_pct=0.30)
    with caplog.at_level(logging.INFO):
        run(det, 5)
    assert det.presence_state == "empty"
    assert "Person seen but too small: 14% of frame height (needs >= 30%" in caplog.text


def test_people_mode_uses_the_full_frame_not_the_downscaled_one():
    fake = FakePerson()
    det = people_detector(fake, detection_scale=0.5)
    run(det, 1)
    assert fake.frames == [(480, 640)]


def test_unavailable_person_backend_falls_back_to_faces(caplog):
    def broken():
        raise PersonDetectorUnavailable("onnxruntime not installed")
    with caplog.at_level(logging.WARNING):
        det = ProximityDetector(detector="person", person_factory=broken)
    assert det.active_detector == "face"
    assert "onnxruntime not installed" in caplog.text


def test_repeated_inference_errors_fall_back_to_faces(caplog):
    det = people_detector(FakePerson(error=RuntimeError("bad frame")))
    with caplog.at_level(logging.WARNING):
        run(det, 3)
    assert det.active_detector == "face"
    assert det.presence_state == "empty"
    assert "falling back to faces" in caplog.text.lower()


def test_unknown_mode_runs_faces():
    assert ProximityDetector(detector="robot").active_detector == "face"


def test_faces_is_the_default_and_never_builds_the_person_backend():
    def must_not_run():
        raise AssertionError("person backend built in face mode")
    assert ProximityDetector(person_factory=must_not_run).active_detector == "face"


# --- live switching (ticket 02): queued from the UI thread, applied on the camera thread ---

def test_switch_to_people_takes_effect_at_the_next_frame_and_resets_presence():
    det = ProximityDetector(skip_frames=0, cooldown=0, confirm_frames=1)
    det._presence_state = "present"
    fake = FakePerson([(100, 50, 120, 200, 0.9)])
    det.set_mode("person", fake)
    assert det.active_detector == "person"   # reported straight away (pending)
    assert fake.frames == []                  # nothing ran on the caller's thread
    det.process_frame(FRAME)
    assert fake.frames == [(480, 640)]
    assert det.detection_method == "person"


def test_switch_back_to_faces_stops_using_the_person_backend():
    fake = FakePerson()
    det = people_detector(fake)
    det.set_mode("face")
    run(det, 2)
    assert det.active_detector == "face"
    assert fake.frames == []


def test_switch_resets_presence_to_empty():
    det = people_detector(FakePerson([(100, 50, 120, 200, 0.9)]), confirm_frames=1)
    run(det, 1)
    assert det.presence_state == "present"
    det.set_mode("face")
    run(det, 1)
    assert det.presence_state == "empty"


# --- manager: builds the backend off the camera thread, reports what really runs ---

from plugins.camera import person_detector as person_module  # noqa: E402
from plugins.camera.proximity_manager import ProximityGreetingManager  # noqa: E402


def test_manager_switch_to_people_hands_a_ready_backend_to_the_detector(monkeypatch):
    fake = FakePerson()
    monkeypatch.setattr(person_module, "PersonDetector", lambda confidence: fake)
    mgr = ProximityGreetingManager()
    mgr._detector = ProximityDetector(skip_frames=0)
    assert mgr.set_detector_mode("person") == "person"
    assert mgr.active_detector == "person"
    mgr._detector.process_frame(FRAME)
    assert fake.frames == [(480, 640)]


def test_manager_reports_faces_when_people_cannot_load(monkeypatch, caplog):
    def broken(confidence):
        raise PersonDetectorUnavailable("model file not found: x")
    monkeypatch.setattr(person_module, "PersonDetector", broken)
    mgr = ProximityGreetingManager()
    mgr._detector = ProximityDetector(skip_frames=0)
    with caplog.at_level(logging.WARNING):
        assert mgr.set_detector_mode("person") == "face"
    assert mgr.active_detector == "face"
    assert mgr._detector_mode == "person"          # the choice is kept for next start
    assert "model file not found" in caplog.text


def test_manager_without_a_running_camera_remembers_the_mode(monkeypatch):
    monkeypatch.setattr(person_module, "PersonDetector", lambda confidence: FakePerson())
    mgr = ProximityGreetingManager()
    assert mgr.set_detector_mode("person") == "person"
    assert mgr._detector_mode == "person"


# --- Windows DLL clash: onnxruntime must load before PyQt6 -------------------------

def test_refuses_onnxruntime_after_qt_on_windows_instead_of_crashing(monkeypatch, tmp_path):
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delitem(sys.modules, "onnxruntime", raising=False)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", types.ModuleType("PyQt6.QtCore"))
    with pytest.raises(PersonDetectorUnavailable, match="before PyQt6"):
        PersonDetector(model_path=str(model))
