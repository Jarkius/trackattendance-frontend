#!/usr/bin/env python3
"""
Live Detection Demo
Shows camera feed with face/pose detection overlays.

Usage:
    python demo_detection.py [--duration 30] [--scale 0.5]

Press Q to quit early.
"""

import cv2
import time
import argparse
import os
import sys

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'


def main():
    parser = argparse.ArgumentParser(description='Live face/pose detection demo')
    parser.add_argument('--duration', type=int, default=60,
                        help='Demo duration in seconds (default: 60)')
    parser.add_argument('--scale', type=float, default=0.5,
                        help='Preview window scale (default: 0.5)')
    parser.add_argument('--camera', type=int, default=0,
                        help='Camera ID (default: 0)')
    parser.add_argument('--confidence', type=float, default=0.3,
                        help='Min detection confidence (default: 0.3)')
    args = parser.parse_args()

    # Check for MediaPipe
    try:
        import mediapipe as mp
    except ImportError:
        print("MediaPipe not installed. Run: pip install mediapipe")
        sys.exit(1)

    # Load models
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    face_model = os.path.join(models_dir, 'blaze_face_short_range.tflite')
    pose_model = os.path.join(models_dir, 'pose_landmarker_lite.task')

    if not os.path.exists(face_model) or not os.path.exists(pose_model):
        print(f"Model files missing in {models_dir}")
        print("Download from: https://developers.google.com/mediapipe/solutions/vision/face_detector")
        sys.exit(1)

    # Initialize face detector
    base_opts = mp.tasks.BaseOptions(model_asset_path=face_model)
    face_opts = mp.tasks.vision.FaceDetectorOptions(
        base_options=base_opts,
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        min_detection_confidence=args.confidence,
    )
    face_det = mp.tasks.vision.FaceDetector.create_from_options(face_opts)

    # Initialize pose detector
    base_opts2 = mp.tasks.BaseOptions(model_asset_path=pose_model)
    pose_opts = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=base_opts2,
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        min_pose_detection_confidence=args.confidence,
    )
    pose_det = mp.tasks.vision.PoseLandmarker.create_from_options(pose_opts)

    # Open camera
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Failed to open camera {args.camera}")
        if IS_MACOS:
            print("Grant camera permission: System Settings > Privacy & Security > Camera")
        elif IS_WINDOWS:
            print("Check: Settings > Privacy > Camera")
        sys.exit(1)

    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("=" * 50)
    print("Live Detection Demo")
    print("=" * 50)
    print(f"Camera: {cam_w}x{cam_h}")
    print(f"Duration: {args.duration}s")
    print(f"Confidence threshold: {args.confidence}")
    print()
    print("Press Q to quit")
    print("=" * 50)

    # Stats
    frame_count = 0
    face_detections = 0
    pose_detections = 0

    start = time.time()
    while time.time() - start < args.duration:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        detection_text = "No detection"
        face_found = False
        pose_found = False

        # Face detection - green box
        face_result = face_det.detect(mp_image)
        if face_result.detections:
            face_found = True
            face_detections += 1
            for det in face_result.detections:
                bbox = det.bounding_box
                x, y = int(bbox.origin_x), int(bbox.origin_y)
                bw, bh = int(bbox.width), int(bbox.height)
                conf = det.categories[0].score

                # Green bounding box
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 3)
                cv2.putText(frame, f"FACE {conf:.0%}", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            detection_text = f"Face detected ({len(face_result.detections)})"

        # Pose detection - magenta landmarks
        pose_result = pose_det.detect(mp_image)
        if pose_result.pose_landmarks:
            pose_found = True
            if not face_found:
                pose_detections += 1

            for landmarks in pose_result.pose_landmarks:
                # Draw visible landmarks
                for lm in landmarks:
                    if lm.visibility > 0.5:
                        cx, cy = int(lm.x * w), int(lm.y * h)
                        cv2.circle(frame, (cx, cy), 5, (255, 0, 255), -1)

                # Draw skeleton connections (simplified)
                connections = [
                    (11, 12),  # shoulders
                    (11, 13), (13, 15),  # left arm
                    (12, 14), (14, 16),  # right arm
                    (11, 23), (12, 24),  # torso
                    (23, 24),  # hips
                    (23, 25), (25, 27),  # left leg
                    (24, 26), (26, 28),  # right leg
                ]
                for i, j in connections:
                    if i < len(landmarks) and j < len(landmarks):
                        lm1, lm2 = landmarks[i], landmarks[j]
                        if lm1.visibility > 0.5 and lm2.visibility > 0.5:
                            pt1 = (int(lm1.x * w), int(lm1.y * h))
                            pt2 = (int(lm2.x * w), int(lm2.y * h))
                            cv2.line(frame, pt1, pt2, (255, 0, 255), 2)

            if not face_found:
                detection_text = f"Pose detected ({len(pose_result.pose_landmarks)})"

        # Status bar at top
        elapsed = time.time() - start
        remaining = args.duration - elapsed
        cv2.rectangle(frame, (0, 0), (w, 45), (0, 0, 0), -1)
        cv2.putText(frame, detection_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(frame, f"{remaining:.0f}s", (w - 60, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)

        # Resize for display
        display_w = int(w * args.scale)
        display_h = int(h * args.scale)
        display = cv2.resize(frame, (display_w, display_h))
        cv2.imshow("Detection Demo - Press Q to quit", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\nQuitting early...")
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    face_det.close()
    pose_det.close()

    # Summary
    duration = time.time() - start
    print()
    print("=" * 50)
    print("Demo Summary")
    print("=" * 50)
    print(f"Duration: {duration:.1f}s")
    print(f"Frames processed: {frame_count}")
    print(f"FPS: {frame_count / duration:.1f}")
    print(f"Face detections: {face_detections}")
    print(f"Pose-only detections: {pose_detections}")
    print("=" * 50)


if __name__ == '__main__':
    main()
