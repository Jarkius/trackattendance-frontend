"""Whole-body person detection with YOLOX-Nano (Apache-2.0) on onnxruntime CPU.

Used by ProximityDetector in "People" mode (CAMERA_DETECTOR=person), for wide-angle cameras
where faces are small and the Haar upper-body fallback mistakes furniture for people.
Spec: docs/specs/person-detector-option.md. Model notice: models/NOTICE-YOLOX.md.

The released ONNX takes a 416x416 BGR image, 0-255, padded with 114 at the bottom/right
(top-left letterbox), and returns raw rows (1, 3549, 85): x/y offsets in grid cells,
log(w/h / stride), objectness and 80 class scores (both already sigmoid).
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

import cv2
import numpy as np

INPUT_SIZE = 416
STRIDES = (8, 16, 32)
GRID_ROWS = sum((INPUT_SIZE // s) ** 2 for s in STRIDES)  # 3549
PERSON_CLASS = 0
NMS_IOU = 0.5
THREADS = 2  # leave the kiosk's other cores to the UI, sync and video

if getattr(sys, "frozen", False):
    _MODELS_DIR = os.path.join(getattr(sys, "_MEIPASS", ""), "plugins", "camera", "models")
else:
    _MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(_MODELS_DIR, "yolox_nano.onnx")

Box = Tuple[float, float, float, float, float]  # x, y, w, h, score in frame pixels


class PersonDetectorUnavailable(RuntimeError):
    """The People backend cannot run here; the message says why (shown in the log)."""


def _grid() -> Tuple[np.ndarray, np.ndarray]:
    cells, strides = [], []
    for s in STRIDES:
        n = INPUT_SIZE // s
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        cells.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), s))
    return np.concatenate(cells).astype(np.float32), np.concatenate(strides).astype(np.float32)


class PersonDetector:
    """detect(frame) -> person boxes (x, y, w, h, score) with score >= confidence."""

    def __init__(self, model_path: str = MODEL_PATH, confidence: float = 0.5,
                 session=None):
        self.confidence = confidence
        if session is None:
            session = self._open(model_path)
        shape = list(session.get_outputs()[0].shape)
        if shape[-2:] != [GRID_ROWS, 85]:
            raise PersonDetectorUnavailable(
                f"unexpected model output {shape}, expected [1, {GRID_ROWS}, 85] (YOLOX 416)")
        self._session = session
        self._input = session.get_inputs()[0].name
        self._cells, self._strides = _grid()

    @staticmethod
    def _open(model_path: str):
        if not os.path.exists(model_path):
            raise PersonDetectorUnavailable(f"model file not found: {model_path}")
        # PyQt6 ships an old MSVC runtime (14.26); onnxruntime loaded after it crashes the
        # whole process (access violation). main.py loads onnxruntime before PyQt6; if that
        # did not happen, refuse here so the kiosk falls back to faces instead of crashing.
        if (sys.platform == "win32" and "onnxruntime" not in sys.modules
                and "PyQt6.QtCore" in sys.modules):
            raise PersonDetectorUnavailable(
                "onnxruntime must be imported before PyQt6 (see main.py); not loading it now")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise PersonDetectorUnavailable(f"onnxruntime not installed ({exc})") from exc
        try:
            options = ort.SessionOptions()
            options.intra_op_num_threads = THREADS
            return ort.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])
        except Exception as exc:  # corrupt file, unsupported CPU, ...
            raise PersonDetectorUnavailable(f"cannot load {model_path}: {exc}") from exc

    def detect(self, frame: np.ndarray) -> List[Box]:
        h, w = frame.shape[:2]
        scale = min(INPUT_SIZE / h, INPUT_SIZE / w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, np.uint8)
        canvas[:nh, :nw] = cv2.resize(frame, (nw, nh))
        blob = canvas.transpose(2, 0, 1)[None].astype(np.float32)

        rows = self._session.run(None, {self._input: blob})[0][0]
        scores = rows[:, 4] * rows[:, 5 + PERSON_CLASS]
        keep = scores >= self.confidence
        if not keep.any():
            return []
        centre = (rows[keep, :2] + self._cells[keep]) * self._strides[keep]
        size = np.exp(rows[keep, 2:4]) * self._strides[keep]
        rects = np.concatenate([centre - size / 2, size], 1) / scale
        kept = scores[keep]
        idx = np.array(cv2.dnn.NMSBoxes(rects.tolist(), kept.tolist(),
                                        self.confidence, NMS_IOU)).flatten()
        return [(float(rects[i][0]), float(rects[i][1]), float(rects[i][2]),
                 float(rects[i][3]), float(kept[i])) for i in idx]
