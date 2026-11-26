"""POC: compare person detectors on saved kiosk frames, onnxruntime CPU, 2 threads.

Candidates: YOLO26n-320 (AGPL, baseline), YOLOX-Tiny/Nano-416 (Apache-2.0, Megvii release ONNX),
D-FINE-N-640 (Apache-2.0, exported from the original repo weights).

The current detector is scored separately by current_detector.py (needs the project venv).

Usage: python compare.py <conf> <frame.png>...   prints persons per frame per model, then latency.
Writes <frame>_cmp.png with every model's boxes (one colour per model).
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parents[2] / ".scratchpad" / "yolo-poc"   # big, gitignored: venv, models, frames


def session(path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 2
    return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])


def nms(boxes, scores, conf):
    if not boxes:
        return []
    rects = [[x1, y1, x2 - x1, y2 - y1] for x1, y1, x2, y2 in boxes]
    idx = np.array(cv2.dnn.NMSBoxes(rects, scores, conf, 0.5)).flatten()
    return [(*boxes[i], scores[i]) for i in idx]


class Yolo26:
    name, size = "yolo26n-320 (AGPL)", 320

    def __init__(self):
        self.s = session(HERE / "models/yolo26n-320.onnx")

    def __call__(self, img, conf):
        h, w = img.shape[:2]
        r = min(self.size / h, self.size / w)
        nh, nw = round(h * r), round(w * r)
        top, left = (self.size - nh) // 2, (self.size - nw) // 2
        c = np.full((self.size, self.size, 3), 114, np.uint8)
        c[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh))
        blob = cv2.cvtColor(c, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255
        p = self.s.run(None, {"images": blob})[0][0].T            # export is (84, N): cx,cy,w,h + 80 classes
        score = p[:, 4]                                            # person class
        keep = score >= conf
        cx, cy, bw, bh = (p[keep, i] for i in range(4))
        b = np.stack([cx - bw / 2 - left, cy - bh / 2 - top, cx + bw / 2 - left, cy + bh / 2 - top], 1) / r
        return nms(b.tolist(), score[keep].tolist(), conf)


class Yolox:
    size = 416

    def __init__(self, variant):
        self.name = f"yolox-{variant}-416 (Apache)"
        self.s = session(HERE / f"dl/yolox/yolox_{variant}.onnx")
        grids, strides = [], []
        for st in (8, 16, 32):
            n = self.size // st
            xv, yv = np.meshgrid(np.arange(n), np.arange(n))
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            strides.append(np.full((n * n, 1), st))
        self.grid, self.stride = np.concatenate(grids), np.concatenate(strides)

    def __call__(self, img, conf):
        h, w = img.shape[:2]
        r = min(self.size / h, self.size / w)
        c = np.full((self.size, self.size, 3), 114, np.uint8)       # YOLOX: top-left pad, BGR, 0-255
        c[:round(h * r), :round(w * r)] = cv2.resize(img, (round(w * r), round(h * r)))
        out = self.s.run(None, {"images": c.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
        xy = (out[:, :2] + self.grid) * self.stride
        wh = np.exp(out[:, 2:4]) * self.stride
        score = out[:, 4] * out[:, 5]                                  # objectness * person
        keep = score >= conf
        b = np.concatenate([xy - wh / 2, xy + wh / 2], 1)[keep] / r
        return nms(b.tolist(), score[keep].tolist(), conf)


class DFine:
    name, size = "d-fine-n-640 (Apache)", 640

    def __init__(self):
        self.s = session(HERE / "models/dfine-n-640.onnx")

    def __call__(self, img, conf):
        h, w = img.shape[:2]
        blob = cv2.cvtColor(cv2.resize(img, (self.size, self.size)), cv2.COLOR_BGR2RGB)
        blob = blob.transpose(2, 0, 1)[None].astype(np.float32) / 255
        labels, boxes, scores = self.s.run(None, {"images": blob, "orig_target_sizes": np.array([[w, h]], np.int64)})
        keep = (scores[0] >= conf) & (labels[0] == 0)
        return [(*bx, float(sc)) for bx, sc in zip(boxes[0][keep].tolist(), scores[0][keep])]


COLOURS = [(0, 0, 255), (0, 200, 0), (255, 128, 0), (255, 0, 255)]


def main():
    conf, frames = float(sys.argv[1]), sys.argv[2:]
    models = [Yolo26(), Yolox("tiny"), Yolox("nano"), DFine()]
    print(f"conf {conf}")
    print(f"{'frame':28}" + "".join(f"{m.name:>26}" for m in models))
    for fp in frames:
        img = cv2.imread(fp)
        w = img.shape[1]
        shown, cells = img.copy(), []
        for m, col in zip(models, COLOURS):
            ps = m(img, conf)
            cells.append(f"{len(ps)}" + (f" [{max(p[4] for p in ps):.2f} {100 * (ps[0][2] - ps[0][0]) / w:.0f}%w]" if ps else ""))
            for x1, y1, x2, y2, s in ps:
                cv2.rectangle(shown, (int(x1), int(y1)), (int(x2), int(y2)), col, 2)
        for i, (m, col) in enumerate(zip(models, COLOURS)):
            cv2.putText(shown, m.name, (8, 20 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
        cv2.imwrite(str(Path(fp).with_name(Path(fp).stem + "_cmp.png")), shown)
        print(f"{Path(fp).name:28}" + "".join(f"{c:>26}" for c in cells))
    img = cv2.imread(frames[0])
    print(f"\n{'model':26} {'ms mean':>8} {'ms p95':>8}")
    for m in models:
        for _ in range(5):
            m(img, conf)
        t = []
        for _ in range(40):
            s = time.perf_counter(); m(img, conf); t.append((time.perf_counter() - s) * 1000)
        print(f"{m.name:26} {np.mean(t):8.1f} {np.percentile(t, 95):8.1f}")


if __name__ == "__main__":
    main()
