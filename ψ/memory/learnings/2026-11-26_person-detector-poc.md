---
pattern: Before changing a camera detector, look at the real frame that fooled it, then score candidate models against frames you labelled by eye, with the licence of the exact weights you would ship in the table
date: 2026-11-26
source: session: Jarkius/trackattendance-frontend, PR #121 follow-up
concepts: [camera, proximity-detection, object-detection, onnx, licensing, evidence-first]
---

## Problem

Poly Studio R30 (wide-angle) station, Admin "Min Face" lowered to 9% so faces at the wide
lens count. The camera pointed at a cabinet and the log showed
`State: empty -> present (upperbody, 3 consecutive frames)` and played the greeting.

## What the evidence showed

- The false person was the **Haar upper-body fallback** drawing a box on the open shelf with
  a bag (box about 25% of frame width). In 10 empty, lit frames it fired on 6, including 3 in
  a row, which is enough for the app's 3-frame confirmation.
- The first proposed fix ("upper-body minimum = 2x the face minimum" = 18%) would **not** have
  helped: the box was 25%. It was dropped. Looking at the frame before coding saved a wrong fix.

## Results (onnxruntime CPU, 2 threads, conf 0.5, incl. pre/post-processing)

31 frames: 13 with a person (close, partial at edges, side-on, walking), 18 without.

| Detector | Licence (weights used) | Person found | False alarm | ms (3-run mean) | File |
|---|---|---|---|---|---|
| Current: YuNet face >= 9%, else Haar upper body | - | 7 by face (+2 body boxes, likely the cabinet) | **7 / 18** | ~18 | - |
| YOLO26n-320 | AGPL-3.0 | 12 / 13 | 0 | ~12 | 9.4 MB |
| **YOLOX-Nano-416** | **Apache-2.0** (Megvii release) | **12 / 13** | **0** | **~29** | **3.6 MB** |
| YOLOX-Tiny-416 | Apache-2.0 | 11 / 13 | 0 | 46-58 (p95 ~95) | 20 MB |
| D-FINE-N-640 | Apache-2.0 (original repo) | 13 / 13, also tiny far people | 0 | ~186 | 15 MB |

The one hard frame (someone bending away, back to camera) was missed by every model except D-FINE (0.67).
At conf 0.35 D-FINE also boxed a real shoulder 5% wide at the frame edge: a min-size rule handles it.
Far back (follow-up, 8 frames, open office, person about 4-5 m away facing the camera, box
about 11% of width / 40% of height): current detector 0/8 (face too small for 9%);
YOLO26n 8/8 (0.75-0.79), YOLOX-Nano 8/8 (0.85-0.86), YOLOX-Tiny 8/8, D-FINE-N 8/8 (0.93).
All also boxed real people further back (seated, walking): no false objects.
Consequence for the app: presence needs a minimum person size, measured on box **height**
(it tracks distance; width changes with pose and crossed arms), or far passers-by will wake it.
Not yet covered: event lighting, a crowd in front of the kiosk.

Recommendation: **YOLOX-Nano** for a per-station "people" detector (Apache-2.0, same hit rate
as YOLO26n, far under the 200 ms per-frame budget at 5 fps). D-FINE-N is the most sensitive
but ~186 ms is too close to the budget on this CPU.

## Lessons

1. **Look at the frame first.** The log said "upperbody"; only the image showed it was a shelf,
   and that the size-threshold fix could not work.
2. **Label ground truth by eye before reading scores** (`sheet.py` contact sheet). The guided
   capture did not go as planned (camera moved, "far" pose out of view); scoring against the
   plan instead of the pictures would have produced wrong miss counts.
3. **Licence belongs to the weights you download, not the architecture.** RT-DETR is
   Apache-2.0 from Baidu but AGPL when pulled through the `ultralytics` package. YOLO26 is AGPL.
4. **Check the real export's output shape.** The YOLO26 ONNX export was the classic
   `(1, 84, N)` layout needing NMS, not the end-to-end `(1, N, 6)`; the wrong decoder silently
   reported "0 persons" on frames with a person in them.
5. **Time each model at least 3 times.** One run reported YOLO26n at 26 ms, repeats gave 12 ms.
6. **Keep POC data in the repo's gitignored `.scratchpad/`, scripts in `scripts/detector-poc/`.**
   Temp folders get wiped; camera frames show people and must never be committed.

## Reuse

`scripts/detector-poc/README.md`: setup, capture (`capture_empty.py`, `guided.py`), scoring
(`current_detector.py`, `compare.py`, `sheet.py`).
