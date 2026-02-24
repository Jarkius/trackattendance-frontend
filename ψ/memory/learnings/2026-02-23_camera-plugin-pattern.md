# Camera Plugin Pattern for PyQt6 Kiosk App

**Date**: 2026-02-23
**Context**: Designing integration of camera POC into trackattendance-frontend
**Source**: Architecture planning session

## Pattern: Optional Plugin with 3-Layer Graceful Degradation

When adding an optional hardware-dependent feature (camera, sensors, etc.) to a kiosk app:

### Layer 1: Config Toggle
```python
ENABLE_CAMERA_DETECTION = os.getenv("ENABLE_CAMERA_DETECTION", "False")
```
Default OFF. Zero overhead when disabled.

### Layer 2: Folder + Import Check
```python
if config.ENABLE_CAMERA_DETECTION:
    plugin_dir = Path(__file__).parent / "plugins" / "camera"
    if plugin_dir.is_dir():
        try:
            from plugins.camera.camera_manager import CameraPluginManager
        except ImportError as exc:
            LOGGER.warning("Camera deps not installed: %s", exc)
```
Late import inside start(), never at module level.

### Layer 3: Runtime Hardware Check
```python
def start(self) -> bool:
    ok = self._scanner.start()  # Returns False if camera won't open
    if not ok:
        LOGGER.warning("Camera hardware unavailable")
        return False
```

## Key Insight: Helper, Not Blocker

Camera detection supplements USB badge scanning — it must NEVER prevent the primary input method from working. Every failure mode logs a warning and lets the app continue normally.

## Integration Pattern

Route camera scan results through the SAME code path as USB scans (`Api.submit_scan`). This gives free UI feedback (animations, duplicate detection, voice, counters) with zero additional wiring.

## Tags
- plugin-architecture
- graceful-degradation
- pyqt6
- camera
- optional-dependency
