#!/usr/bin/env python3
"""
Camera permission grant and hardware test.

macOS: Triggers the camera permission dialog. Run from Terminal.app manually.
Windows: Just tests camera access (no permission dialog needed).

Usage:
    macOS:   python grant_camera.py
    Windows: python grant_camera.py
"""
import sys
import os
import time

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'


def main():
    print("=" * 50)
    print("Camera Hardware Test")
    print("=" * 50)
    print()

    if IS_MACOS:
        print("macOS detected — this will trigger camera permission dialog.")
        print("If you see a popup, click 'Allow'.")
        print()
        # Must NOT set OPENCV_AVFOUNDATION_SKIP_AUTH so the dialog appears
        os.environ.pop('OPENCV_AVFOUNDATION_SKIP_AUTH', None)
    elif IS_WINDOWS:
        print("Windows detected — camera access does not require special permissions.")
        print()

    import cv2

    print("Opening camera...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print()
        print("Camera did NOT open.")
        print()
        if IS_MACOS:
            print("Possible reasons:")
            print("  1. You denied the permission popup — go to:")
            print("     System Settings > Privacy & Security > Camera")
            print("     and toggle ON for Terminal")
            print("  2. No popup appeared — you may be running this from")
            print("     a non-GUI context. Open Terminal.app and try again.")
        elif IS_WINDOWS:
            print("Possible reasons:")
            print("  1. Camera is in use by another application")
            print("  2. Camera drivers not installed")
            print("  3. Camera access blocked in Windows Privacy Settings:")
            print("     Settings > Privacy > Camera")
        print("  - No camera hardware detected.")
        cap.release()
        return False

    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        print(f"Camera working! Resolution: {w}x{h}")
        print()

        # Quick barcode test
        from pyzbar.pyzbar import decode
        results = decode(frame)
        if results:
            print(f"Barcode detected in live frame: {results[0].data.decode()}")
        else:
            print("No barcode in current frame (that's fine, just testing camera)")

        # Show preview if GUI available
        try:
            print()
            print("Showing 3-second preview... (press 'q' to close early)")
            start = time.time()
            while time.time() - start < 3:
                ret, frame = cap.read()
                if ret:
                    cv2.imshow("Camera Test - Press Q to close", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            cv2.destroyAllWindows()
        except cv2.error:
            print("(Preview not available — opencv-python-headless installed)")
            print("Camera capture works fine, just no GUI preview.")
    else:
        print("Camera opened but failed to read frame.")

    cap.release()
    print()
    print("Camera test complete!")
    print("You can now run the full test suite:")
    print("  python test_poc.py")
    return True


if __name__ == '__main__':
    main()
