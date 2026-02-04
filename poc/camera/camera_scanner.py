"""
Camera-based Barcode/QR Code Scanner Module
Uses OpenCV and pyzbar for real-time barcode detection from laptop camera
"""

import cv2
import numpy as np
from pyzbar.pyzbar import decode
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
import time
import queue
import sys

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'

# Check if OpenCV GUI (highgui) is available — not present in opencv-python-headless
try:
    cv2.namedWindow("__test__", cv2.WINDOW_NORMAL)
    cv2.destroyWindow("__test__")
    HIGHGUI_AVAILABLE = True
except cv2.error:
    HIGHGUI_AVAILABLE = False


class DetectionMode(Enum):
    """Barcode detection modes"""
    CONTINUOUS = "continuous"  # Always scanning
    TRIGGERED = "triggered"    # Only scan when triggered (e.g., proximity)
    MANUAL = "manual"          # Manual trigger only


@dataclass
class CameraConfig:
    """Configuration for camera scanner"""
    camera_id: int = 0  # Default camera (0 = built-in, 1+ = external)
    resolution: Tuple[int, int] = (1280, 720)
    fps: int = 30
    detection_mode: DetectionMode = DetectionMode.CONTINUOUS
    scan_cooldown: float = 2.0  # Seconds between scans
    enable_preview: bool = True
    preview_scale: float = 0.5
    barcode_types: List[str] = None  # None = all types
    
    def __post_init__(self):
        if self.barcode_types is None:
            self.barcode_types = ['QRCODE', 'CODE128', 'CODE39', 'EAN13', 'UPCA']


@dataclass
class ScanResult:
    """Result of a barcode scan"""
    data: str
    barcode_type: str
    timestamp: float
    confidence: float = 1.0
    bounding_box: Optional[Tuple[int, int, int, int]] = None


class CameraScanner:
    """
    Camera-based barcode/QR code scanner
    
    Features:
    - Real-time barcode detection from webcam
    - Support for multiple barcode formats (QR, Code128, Code39, etc.)
    - Visual feedback with bounding boxes
    - Configurable detection modes
    - Threaded operation for non-blocking scanning
    """
    
    def __init__(self, config: Optional[CameraConfig] = None):
        self.config = config or CameraConfig()
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._result_callbacks: List[Callable[[ScanResult], None]] = []
        self._frame_callbacks: List[Callable[[np.ndarray], None]] = []
        self._last_scan_time = 0
        self._last_detected_code: Optional[str] = None
        self._scan_results_queue: queue.Queue = queue.Queue()
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
    
    def add_result_callback(self, callback: Callable[[ScanResult], None]):
        """Add callback for scan results"""
        self._result_callbacks.append(callback)
    
    def remove_result_callback(self, callback: Callable[[ScanResult], None]):
        """Remove callback for scan results"""
        if callback in self._result_callbacks:
            self._result_callbacks.remove(callback)
    
    def add_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """Add callback for frame updates (for preview)"""
        self._frame_callbacks.append(callback)
    
    def _initialize_camera(self) -> bool:
        """Initialize camera capture"""
        self.cap = cv2.VideoCapture(self.config.camera_id)
        
        if not self.cap.isOpened():
            print(f"Failed to open camera {self.config.camera_id}")
            return False
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        
        # Read a test frame
        ret, frame = self.cap.read()
        if not ret:
            print("Failed to read from camera")
            self.cap.release()
            return False
        
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camera initialized: {actual_width}x{actual_height}")
        
        return True
    
    def _process_frame(self, frame: np.ndarray) -> List[ScanResult]:
        """Process a frame to detect barcodes"""
        results = []
        
        # Convert to grayscale for better detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Decode barcodes
        barcodes = decode(gray)
        
        for barcode in barcodes:
            # Get barcode data
            data = barcode.data.decode('utf-8')
            barcode_type = barcode.type
            
            # Filter by barcode type if specified
            if self.config.barcode_types and barcode_type not in self.config.barcode_types:
                continue
            
            # Get bounding box
            points = barcode.polygon
            if points:
                x_coords = [p.x for p in points]
                y_coords = [p.y for p in points]
                bbox = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
            else:
                bbox = None
            
            # Create result
            result = ScanResult(
                data=data,
                barcode_type=barcode_type,
                timestamp=time.time(),
                confidence=1.0,  # pyzbar doesn't provide confidence
                bounding_box=bbox
            )
            results.append(result)
            
            # Draw bounding box on frame (for preview)
            if self.config.enable_preview and bbox:
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), 
                             (0, 255, 0), 2)
                cv2.putText(frame, f"{data[:20]}...", (bbox[0], bbox[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return results
    
    def _scan_loop(self):
        """Main scanning loop (runs in separate thread)"""
        while self.is_running:
            if self.cap is None:
                time.sleep(0.1)
                continue
            
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            # Store current frame
            with self._frame_lock:
                self._current_frame = frame.copy()
            
            # Process frame for barcodes
            results = self._process_frame(frame)
            
            # Check cooldown and process results
            current_time = time.time()
            for result in results:
                # Cooldown check
                if current_time - self._last_scan_time < self.config.scan_cooldown:
                    continue
                
                # Duplicate check (same code within cooldown)
                if result.data == self._last_detected_code:
                    continue
                
                # Valid scan
                self._last_scan_time = current_time
                self._last_detected_code = result.data
                
                # Add to queue
                self._scan_results_queue.put(result)
                
                # Notify callbacks
                for callback in self._result_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        print(f"Callback error: {e}")
            
            # Notify frame callbacks
            for callback in self._frame_callbacks:
                try:
                    callback(frame)
                except Exception as e:
                    print(f"Frame callback error: {e}")
            
            # Small delay to prevent CPU overload
            time.sleep(0.01)
    
    def start(self) -> bool:
        """Start the camera scanner"""
        if self.is_running:
            return True
        
        if not self._initialize_camera():
            return False
        
        self.is_running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        print("Camera scanner started")
        return True
    
    def stop(self):
        """Stop the camera scanner"""
        self.is_running = False
        
        if self._scan_thread:
            self._scan_thread.join(timeout=1)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        print("Camera scanner stopped")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame"""
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    def get_scan_result(self, timeout: float = 0.1) -> Optional[ScanResult]:
        """Get a scan result from the queue (non-blocking)"""
        try:
            return self._scan_results_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def clear_results(self):
        """Clear pending scan results"""
        while not self._scan_results_queue.empty():
            try:
                self._scan_results_queue.get_nowait()
            except queue.Empty:
                break
    
    def reset_cooldown(self):
        """Reset scan cooldown (useful after proximity trigger)"""
        self._last_scan_time = 0
        self._last_detected_code = None
    
    def show_preview(self, window_name: str = "Camera Scanner"):
        """Show live preview window (blocking). Requires opencv-python (not headless)."""
        if not HIGHGUI_AVAILABLE:
            print("Preview not available (opencv-python-headless installed).")
            print("Camera scanning still works — preview is optional.")
            return

        if not self.is_running:
            print("Scanner not running. Call start() first.")
            return

        print("Press 'q' to quit preview")

        while self.is_running:
            frame = self.get_frame()
            if frame is not None:
                # Resize for preview
                if self.config.preview_scale != 1.0:
                    h, w = frame.shape[:2]
                    new_w = int(w * self.config.preview_scale)
                    new_h = int(h * self.config.preview_scale)
                    frame = cv2.resize(frame, (new_w, new_h))

                cv2.imshow(window_name, frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()
    
    def capture_single_scan(self, timeout: float = 30.0) -> Optional[ScanResult]:
        """Capture a single scan result (blocking with timeout)"""
        if not self.is_running:
            if not self.start():
                return None
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.get_scan_result(timeout=0.1)
            if result:
                return result
        
        return None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class ProximityDetector:
    """
    Simple proximity detection using camera motion detection
    Can be used to trigger greeting when someone approaches
    """
    
    def __init__(self, sensitivity: int = 5000, cooldown: float = 5.0):
        self.sensitivity = sensitivity
        self.cooldown = cooldown
        self._last_detection_time = 0
        self._background_frame: Optional[np.ndarray] = None
        self._detection_callbacks: List[Callable[[], None]] = []
    
    def add_detection_callback(self, callback: Callable[[], None]):
        """Add callback for proximity detection"""
        self._detection_callbacks.append(callback)
    
    def process_frame(self, frame: np.ndarray) -> bool:
        """Process frame for motion detection"""
        current_time = time.time()
        
        # Cooldown check
        if current_time - self._last_detection_time < self.cooldown:
            return False
        
        # Convert to grayscale and blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Initialize background
        if self._background_frame is None:
            self._background_frame = gray
            return False
        
        # Calculate difference
        frame_delta = cv2.absdiff(self._background_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Dilate threshold
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, 
                                        cv2.CHAIN_APPROX_SIMPLE)
        
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > self.sensitivity:
                motion_detected = True
                break
        
        # Update background
        self._background_frame = gray
        
        if motion_detected:
            self._last_detection_time = current_time
            
            # Notify callbacks
            for callback in self._detection_callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"Detection callback error: {e}")
        
        return motion_detected
    
    def reset(self):
        """Reset detector"""
        self._background_frame = None
        self._last_detection_time = 0


def test_camera_scanner():
    """Test the camera scanner"""
    print("Testing Camera Scanner...")
    print("Show a barcode/QR code to the camera")

    def on_scan(result: ScanResult):
        print(f"\n[SCAN DETECTED]")
        print(f"  Data: {result.data}")
        print(f"  Type: {result.barcode_type}")
        print(f"  Time: {result.timestamp}")

    config = CameraConfig(
        camera_id=0,
        resolution=(1280, 720),
        enable_preview=HIGHGUI_AVAILABLE,
        scan_cooldown=2.0
    )

    scanner = CameraScanner(config)
    scanner.add_result_callback(on_scan)

    with scanner:
        if HIGHGUI_AVAILABLE:
            print("Press 'q' in the preview window to quit")
            scanner.show_preview()
        else:
            print("Running headless (no preview). Press Ctrl+C to quit.")
            try:
                while scanner.is_running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass

    print("Camera scanner test complete!")


if __name__ == '__main__':
    test_camera_scanner()
