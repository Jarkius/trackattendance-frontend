"""POC step 1: download YOLO26 n/s and export to ONNX and OpenVINO at 640 and 320 input."""
import shutil
from pathlib import Path

from ultralytics import YOLO

out = Path(__file__).resolve().parents[2] / ".scratchpad" / "yolo-poc" / "models"
out.mkdir(parents=True, exist_ok=True)
for name in ("yolo26n", "yolo26s"):
    for size in (640, 320):
        model = YOLO(f"{name}.pt")
        for fmt in ("onnx", "openvino"):
            path = Path(model.export(format=fmt, imgsz=size, half=False, dynamic=False, simplify=True))
            dest = out / f"{name}-{size}{'.onnx' if fmt == 'onnx' else '_openvino'}"
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            shutil.move(str(path), dest)
            print("exported", dest)
