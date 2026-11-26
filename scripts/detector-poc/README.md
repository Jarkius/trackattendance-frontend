# Person-detector POC (camera presence)

Throwaway-but-reusable scripts that compare person detectors on real kiosk camera frames.
Written to decide what replaces the Haar upper-body fallback in
`plugins/camera/proximity_detector.py`, which counts shelves and cabinets as people.
Results and lessons: `ψ/memory/learnings/2026-11-26_person-detector-poc.md`.

Data (venv, models, downloads, camera frames) lives in the gitignored
`.scratchpad/yolo-poc/`. Camera frames show the room and people: never commit them.

## Set up (once, about 1.5 GB)

```bat
uv venv .scratchpad\yolo-poc\.venv-export
uv pip install --python .scratchpad\yolo-poc\.venv-export\Scripts\python.exe ultralytics onnx onnxruntime openvino onnxslim pyyaml tensorboard faster-coco-eval calflops loguru transformers scipy

:: YOLO26n (AGPL-3.0, baseline only): downloads weights, exports ONNX/OpenVINO at 640 and 320
.scratchpad\yolo-poc\.venv-export\Scripts\python.exe scripts\detector-poc\export_yolo26.py

:: YOLOX (Apache-2.0): Megvii's released ONNX files, 416x416
mkdir .scratchpad\yolo-poc\dl\yolox
curl -L -o .scratchpad\yolo-poc\dl\yolox\yolox_nano.onnx https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx
curl -L -o .scratchpad\yolo-poc\dl\yolox\yolox_tiny.onnx https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx

:: D-FINE-N (Apache-2.0): original repo + weights, exported to ONNX at 640
git clone --depth 1 https://github.com/Peterande/D-FINE.git .scratchpad\yolo-poc\dl\dfine-repo
curl -L -o .scratchpad\yolo-poc\dl\dfine_n_coco.pth https://github.com/Peterande/storage/releases/download/dfinev1.0/dfine_n_coco.pth
.scratchpad\yolo-poc\.venv-export\Scripts\python.exe scripts\detector-poc\export_dfine.py
```

## Capture frames (close the kiosk app first: it holds the camera)

| Script | What it does |
|---|---|
| `capture_empty.py <out_dir> <n> [cam]` | 20 s to leave the view, then n frames 3 s apart |
| `guided.py [cam]` | Beep-guided person poses: 1 close, 2 far, 3 side-on, 4 edge, 5 walk past |
| `camera_evidence.py <cam> <min_pct> <out.png>` | One frame with the app's current face/upper-body boxes drawn |

## Score

```bat
:: current app detector (needs the PROJECT venv: it imports plugins/)
.venv\Scripts\python.exe scripts\detector-poc\current_detector.py .scratchpad\yolo-poc\frames\person\*.png
:: candidate models: persons per frame, writes <frame>_cmp.png, then latency (40 runs)
.scratchpad\yolo-poc\.venv-export\Scripts\python.exe scripts\detector-poc\compare.py 0.5 <frames...>
:: contact sheet to set the ground truth by eye BEFORE reading the scores
.scratchpad\yolo-poc\.venv-export\Scripts\python.exe scripts\detector-poc\sheet.py ".scratchpad\yolo-poc\frames\person\*.png" sheet.png
```

Gotchas: check each export's real output shape (the YOLO26 ONNX export is `(1, 84, N)` and
needs NMS, not the end-to-end `(1, N, 6)`); time a model 3 times, since one run can be off by 2x;
the export venv's OpenCV has no Haar cascades, so score the current detector with the project venv.
