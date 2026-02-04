"""
USB Barcode Scanner Module
Handles keyboard-emulating USB barcode scanners
"""

import threading
import queue
import time
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import sys

IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')
IS_MACOS = sys.platform == 'darwin'

# Platform-specific imports
EVDEV_AVAILABLE = False
MSVCRT_AVAILABLE = False

if IS_LINUX:
    try:
        import evdev
        from evdev import InputDevice, categorize, ecodes
        EVDEV_AVAILABLE = True
    except ImportError:
        print("Warning: evdev not available. USB scanner will use fallback mode.")

if IS_WINDOWS:
    try:
        import msvcrt
        MSVCRT_AVAILABLE = True
    except ImportError:
        pass


class ScannerMode(Enum):
    """USB scanner operating modes"""
    KEYBOARD_EMULATION = "keyboard"  # Standard HID keyboard emulation
    SERIAL = "serial"                  # Serial/COM port mode


@dataclass
class USBScannerConfig:
    """Configuration for USB scanner"""
    mode: ScannerMode = ScannerMode.KEYBOARD_EMULATION
    device_path: Optional[str] = None  # e.g., '/dev/input/event0' (Linux)
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    timeout: float = 0.5  # Timeout for complete barcode read
    
    # For keyboard emulation mode
    key_mapping: dict = None
    
    def __post_init__(self):
        if self.key_mapping is None:
            # Standard USB HID keycode to character mapping
            self.key_mapping = {
                # Numbers
                2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
                7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
                # Letters
                30: 'a', 48: 'b', 46: 'c', 32: 'd', 18: 'e',
                33: 'f', 34: 'g', 35: 'h', 23: 'i', 36: 'j',
                37: 'k', 38: 'l', 50: 'm', 49: 'n', 24: 'o',
                25: 'p', 16: 'q', 19: 'r', 31: 's', 20: 't',
                22: 'u', 47: 'v', 17: 'w', 45: 'x', 21: 'y',
                44: 'z',
                # Special
                57: ' ',  # Space
                12: '-',  # Minus
                13: '=',  # Equal
                26: '[',  # Left bracket
                27: ']',  # Right bracket
                39: ';',  # Semicolon
                40: "'",  # Quote
                51: ',',  # Comma
                52: '.',  # Period
                53: '/',  # Slash
                43: '\\', # Backslash
                41: '`',  # Backtick
            }


@dataclass
class USBScanResult:
    """Result from USB scanner"""
    data: str
    timestamp: float
    device_info: Optional[str] = None


class USBScanner:
    """
    USB Barcode Scanner handler
    
    Features:
    - Supports keyboard-emulating USB scanners (HID)
    - Linux evdev support for direct device access
    - Cross-platform fallback using stdin
    - Threaded operation for non-blocking scanning
    - Automatic device detection (Linux)
    """
    
    # Common USB scanner vendor/product IDs
    KNOWN_SCANNERS = [
        ('0c2e', '0200'),  # Honeywell
        ('05e0', '1200'),  # Symbol/Motorola
        ('1a86', '7523'),  # CH340 (common Chinese scanners)
    ]
    
    def __init__(self, config: Optional[USBScannerConfig] = None):
        self.config = config or USBScannerConfig()
        self.is_running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._result_callbacks: List[Callable[[USBScanResult], None]] = []
        self._scan_results_queue: queue.Queue = queue.Queue()
        self._device: Optional[InputDevice] = None
        self._buffer = ""
        self._last_key_time = 0
    
    def add_result_callback(self, callback: Callable[[USBScanResult], None]):
        """Add callback for scan results"""
        self._result_callbacks.append(callback)
    
    def remove_result_callback(self, callback: Callable[[USBScanResult], None]):
        """Remove callback for scan results"""
        if callback in self._result_callbacks:
            self._result_callbacks.remove(callback)
    
    def list_devices(self) -> List[dict]:
        """List available input devices (Linux only)"""
        if not EVDEV_AVAILABLE:
            return []
        
        devices = []
        for path in evdev.list_devices():
            try:
                device = InputDevice(path)
                devices.append({
                    'path': path,
                    'name': device.name,
                    'phys': device.phys,
                    'info': device.info
                })
            except Exception as e:
                pass
        
        return devices
    
    def find_scanner_device(self) -> Optional[str]:
        """Auto-detect USB scanner device"""
        if not EVDEV_AVAILABLE:
            return None
        
        devices = self.list_devices()
        
        # Look for common scanner names
        scanner_keywords = ['barcode', 'scanner', 'reader', 'hid', 'keyboard']
        
        for device in devices:
            name_lower = device['name'].lower()
            if any(keyword in name_lower for keyword in scanner_keywords):
                return device['path']
        
        # If no specific scanner found, look for keyboards
        for device in devices:
            if 'keyboard' in device['name'].lower():
                return device['path']
        
        return None
    
    def _initialize_device(self) -> bool:
        """Initialize the USB scanner device"""
        if not EVDEV_AVAILABLE:
            print("evdev not available, using stdin fallback")
            return True
        
        # Use specified device or auto-detect
        device_path = self.config.device_path or self.find_scanner_device()
        
        if device_path:
            try:
                self._device = InputDevice(device_path)
                print(f"USB scanner connected: {self._device.name} at {device_path}")
                return True
            except Exception as e:
                print(f"Failed to open device {device_path}: {e}")
        
        print("No USB scanner found. Using stdin fallback.")
        return True  # Still return True to use fallback
    
    def _process_key_event(self, event) -> Optional[str]:
        """Process a single key event from scanner"""
        if event.type != ecodes.EV_KEY:
            return None
        
        key_event = categorize(event)
        
        if key_event.keystate != key_event.key_down:
            return None
        
        keycode = key_event.scancode
        
        # Check for Enter/Return (end of barcode)
        if keycode in [28, 96]:  # KEY_ENTER, KEY_KPENTER
            if self._buffer:
                result = self._buffer
                self._buffer = ""
                return result
            return None
        
        # Map keycode to character
        char = self.config.key_mapping.get(keycode)
        if char:
            self._buffer += char
        
        return None
    
    def _read_from_device(self) -> Optional[str]:
        """Read from USB device (Linux evdev)"""
        if self._device is None:
            return None
        
        try:
            # Non-blocking read with timeout
            event = self._device.read_one()
            if event:
                result = self._process_key_event(event)
                if result:
                    return result
        except Exception as e:
            print(f"Device read error: {e}")
        
        return None
    
    def _read_from_stdin(self) -> Optional[str]:
        """Fallback: read from stdin (for testing). Platform-aware."""
        if IS_WINDOWS and MSVCRT_AVAILABLE:
            # Windows: use msvcrt for non-blocking keyboard input
            if msvcrt.kbhit():
                try:
                    char = msvcrt.getwch()
                    if char in ('\r', '\n'):
                        if self._buffer:
                            result = self._buffer
                            self._buffer = ""
                            return result
                    else:
                        self._buffer += char
                except Exception:
                    pass
        else:
            # macOS/Linux: use select for non-blocking stdin
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                try:
                    char = sys.stdin.read(1)
                    if char == '\n':
                        if self._buffer:
                            result = self._buffer
                            self._buffer = ""
                            return result
                    else:
                        self._buffer += char
                except Exception:
                    pass

        return None
    
    def _scan_loop(self):
        """Main scanning loop"""
        while self.is_running:
            result = None
            
            if EVDEV_AVAILABLE and self._device:
                result = self._read_from_device()
            else:
                result = self._read_from_stdin()
            
            if result:
                scan_result = USBScanResult(
                    data=result,
                    timestamp=time.time(),
                    device_info=self._device.name if self._device else "stdin"
                )
                
                # Add to queue
                self._scan_results_queue.put(scan_result)
                
                # Notify callbacks
                for callback in self._result_callbacks:
                    try:
                        callback(scan_result)
                    except Exception as e:
                        print(f"Callback error: {e}")
            
            time.sleep(0.001)  # Small delay to prevent CPU overload
    
    def start(self) -> bool:
        """Start the USB scanner"""
        if self.is_running:
            return True
        
        if not self._initialize_device():
            return False
        
        self.is_running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        print("USB scanner started")
        return True
    
    def stop(self):
        """Stop the USB scanner"""
        self.is_running = False
        
        if self._scan_thread:
            self._scan_thread.join(timeout=1)
        
        if self._device:
            self._device.close()
            self._device = None
        
        print("USB scanner stopped")
    
    def get_scan_result(self, timeout: float = 0.1) -> Optional[USBScanResult]:
        """Get a scan result from the queue"""
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
    
    def simulate_scan(self, data: str):
        """Simulate a scan (for testing)"""
        scan_result = USBScanResult(
            data=data,
            timestamp=time.time(),
            device_info="simulated"
        )
        self._scan_results_queue.put(scan_result)
        
        for callback in self._result_callbacks:
            try:
                callback(scan_result)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class KeyboardListener:
    """
    Alternative: Global keyboard listener for barcode scanner input
    Uses pynput for cross-platform keyboard monitoring
    """
    
    def __init__(self, timeout: float = 0.5):
        self.timeout = timeout
        self._buffer = ""
        self._last_key_time = 0
        self._is_listening = False
        self._result_callbacks: List[Callable[[USBScanResult], None]] = []
        
        try:
            from pynput import keyboard
            self.keyboard = keyboard
            self.PYNPUT_AVAILABLE = True
        except ImportError:
            self.PYNPUT_AVAILABLE = False
            print("Warning: pynput not available. Install with: pip install pynput")
    
    def add_result_callback(self, callback: Callable[[USBScanResult], None]):
        """Add callback for scan results"""
        self._result_callbacks.append(callback)
    
    def _on_key_press(self, key):
        """Handle key press"""
        current_time = time.time()
        
        # Reset buffer if timeout exceeded
        if current_time - self._last_key_time > self.timeout:
            self._buffer = ""
        
        self._last_key_time = current_time
        
        try:
            # Alphanumeric key
            char = key.char
            self._buffer += char
        except AttributeError:
            # Special key
            if key == self.keyboard.Key.enter or key == self.keyboard.Key.return_:
                if self._buffer:
                    result = USBScanResult(
                        data=self._buffer,
                        timestamp=current_time,
                        device_info="keyboard_listener"
                    )
                    
                    for callback in self._result_callbacks:
                        try:
                            callback(result)
                        except Exception as e:
                            print(f"Callback error: {e}")
                    
                    self._buffer = ""
            elif key == self.keyboard.Key.space:
                self._buffer += " "
    
    def start(self):
        """Start keyboard listener"""
        if not self.PYNPUT_AVAILABLE:
            print("pynput not available")
            return False
        
        self._is_listening = True
        self._listener = self.keyboard.Listener(on_press=self._on_key_press)
        self._listener.start()
        print("Keyboard listener started")
        return True
    
    def stop(self):
        """Stop keyboard listener"""
        self._is_listening = False
        if hasattr(self, '_listener'):
            self._listener.stop()
        print("Keyboard listener stopped")


def test_usb_scanner():
    """Test the USB scanner"""
    print("Testing USB Scanner...")
    print("Scan a barcode or type and press Enter")
    print("Press Ctrl+C to quit")
    
    def on_scan(result: USBScanResult):
        print(f"\n[SCAN DETECTED]")
        print(f"  Data: {result.data}")
        print(f"  Time: {result.timestamp}")
        print(f"  Device: {result.device_info}")
    
    # List available devices
    if EVDEV_AVAILABLE:
        print("\nAvailable input devices:")
        scanner = USBScanner()
        devices = scanner.list_devices()
        for device in devices:
            print(f"  {device['path']}: {device['name']}")
    
    # Start scanner
    config = USBScannerConfig()
    scanner = USBScanner(config)
    scanner.add_result_callback(on_scan)
    
    with scanner:
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping...")
    
    print("USB scanner test complete!")


if __name__ == '__main__':
    test_usb_scanner()
