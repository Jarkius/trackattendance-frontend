# Employee Attendance System - Beta Prototype

A comprehensive attendance tracking system that integrates USB barcode scanners, laptop camera-based QR/barcode scanning, proximity detection, and voice feedback for company events.

## Features

### Core Features
- **USB Barcode Scanner Support** - Works with standard HID keyboard-emulating scanners
- **Camera-based Scanning** - Use your HP EliteBook 840 G11 camera to scan badges
- **Proximity Detection** - Detects when someone approaches and provides voice guidance
- **Voice Feedback** - Pre-recorded audio messages for all scenarios
- **SQLite Database** - Persistent storage for employees, events, and attendance
- **Web Dashboard** - Real-time monitoring and management interface

### Scanning Methods
1. **USB Scanner** - Plug in any USB barcode scanner (works as keyboard input)
2. **Camera Scanner** - Show badge to laptop camera
3. **Both Combined** - Seamlessly use either method

### Voice Messages
- Welcome greeting
- Scan prompt
- Badge matched confirmation
- Check-in/check-out success
- Error messages
- Proximity greeting ("Hello! Please scan your badge...")

## Project Structure

```
attendance_system/
├── database.py          # SQLite database operations
├── voice_feedback.py    # Voice/audio feedback system
├── camera_scanner.py    # Camera-based barcode scanning
├── usb_scanner.py       # USB barcode scanner handler
├── main_system.py       # Main integration and CLI
├── web_dashboard.py     # Flask web interface
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── attendance.db       # SQLite database (created on first run)
└── audio/              # Voice message files (created on first run)
```

## Installation

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. For Linux (USB Scanner Support)

```bash
# Install evdev for direct USB device access
pip install evdev

# You may need to add your user to the input group
sudo usermod -a -G input $USER
```

### 3. For Camera Support

```bash
# On Linux, you may need v4l2
sudo apt-get install libv4l-dev

# For pyzbar dependencies
sudo apt-get install libzbar0
```

## Usage

### Quick Start - Demo Mode

```bash
python main_system.py --demo
```

This runs a demonstration with simulated scans.

### Interactive CLI Mode

```bash
python main_system.py
```

Provides a menu-driven interface to:
- Start/stop the system
- View statistics
- Manage employees and events
- Simulate scans

### Web Dashboard

```bash
python web_dashboard.py
```

Then open your browser to `http://localhost:5000`

The dashboard provides:
- Real-time system status
- Attendance statistics
- Employee management
- Event management
- Scan simulation

### Generate Sample Audio Files

```bash
python main_system.py --init-audio
```

This creates TTS audio files for all voice messages.

## Configuration

### System Configuration

Edit `SystemConfig` in `main_system.py`:

```python
config = SystemConfig(
    enable_usb_scanner=True,        # Enable USB scanner
    enable_camera_scanner=True,     # Enable camera scanning
    enable_proximity_detection=True, # Enable motion-based greeting
    enable_voice=True,              # Enable voice feedback
    camera_id=0,                    # Camera device ID (0 = built-in)
    camera_resolution=(1280, 720),  # Camera resolution
)
```

### Camera-Only Mode (Your Use Case)

If you want to use **only the camera** (no USB scanner):

```python
config = SystemConfig(
    enable_usb_scanner=False,
    enable_camera_scanner=True,
    enable_proximity_detection=True,  # Greet people when they approach
    enable_voice=True,
)
```

### USB-Only Mode

```python
config = SystemConfig(
    enable_usb_scanner=True,
    enable_camera_scanner=False,
    enable_proximity_detection=False,
    enable_voice=True,
)
```

## How It Works

### 1. Proximity Detection (Camera Mode)

When someone approaches the laptop:
1. Camera detects motion
2. System plays greeting: *"Hello! Please scan your badge to check in."*
3. Person shows badge to camera
4. Camera scans the barcode/QR code
5. Voice confirms: *"Check-in successful. Welcome!"*

### 2. USB Scanner Mode

1. Person scans badge with USB scanner
2. System immediately processes the scan
3. Voice confirms check-in/check-out

### 3. Check-out

If an employee scans again after checking in:
- System records check-out time
- Voice says: *"Check-out successful. Goodbye!"*

## Database Schema

### Employees Table
- `id` - Internal ID
- `badge_id` - Scannable badge ID (e.g., "EMP001")
- `name` - Employee name
- `department` - Department
- `email` - Email address

### Events Table
- `id` - Event ID
- `name` - Event name
- `description` - Event description
- `start_time` - Event start
- `end_time` - Event end
- `location` - Event location

### Attendance Table
- `id` - Record ID
- `employee_id` - Reference to employee
- `event_id` - Reference to event
- `check_in_time` - Check-in timestamp
- `check_out_time` - Check-out timestamp
- `check_in_method` - 'usb_scanner', 'camera', or 'manual'

## API Endpoints

The web dashboard provides REST API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/start` | POST | Start system |
| `/api/stop` | POST | Stop system |
| `/api/stats` | GET | System statistics |
| `/api/employees` | GET | List employees |
| `/api/employees` | POST | Add employee |
| `/api/events` | GET | List events |
| `/api/events` | POST | Create event |
| `/api/attendance/<id>` | GET | Event attendance |
| `/api/simulate-scan` | POST | Simulate scan |

## Testing

### Simulate Scans

```python
from main_system import AttendanceSystem, SystemConfig

system = AttendanceSystem()
with system:
    # Simulate badge scans
    system.simulate_scan("EMP001")
    system.simulate_scan("EMP002")
```

### Test Camera Only

```bash
python camera_scanner.py
```

Shows a preview window. Show barcodes to the camera.

### Test USB Scanner

```bash
python usb_scanner.py
```

Lists available devices. Scan with your USB scanner.

## Integration Guide

### Integrate into Your Existing Project

```python
from attendance_system.main_system import AttendanceSystem, SystemConfig

# Create system with your configuration
config = SystemConfig(
    enable_usb_scanner=True,
    enable_camera_scanner=True,
    enable_voice=True,
)

system = AttendanceSystem(config)

# Start the system
system.start()

# The system runs in background threads
# It will automatically:
# - Process USB scanner input
# - Process camera scans
# - Play voice feedback
# - Record to database

# Get statistics
stats = system.get_stats()
print(f"Check-ins today: {stats['successful_checkins']}")

# Get attendance records
records = system.get_today_attendance()

# Stop when done
system.stop()
```

### Custom Callbacks

```python
def on_attendance(record):
    print(f"New attendance: {record}")
    # Send to your external system

# Add callback (extend the system class)
```

## Troubleshooting

### Camera Not Working

```bash
# List available cameras
python -c "import cv2; print([cv2.VideoCapture(i).isOpened() for i in range(3)])"

# Test camera
python camera_scanner.py
```

### USB Scanner Not Detected

```bash
# List input devices (Linux)
python -c "from evdev import list_devices; print(list_devices())"

# Test scanner
python usb_scanner.py
```

### No Audio

```bash
# Test pygame audio
python -c "import pygame; pygame.mixer.init(); print('Audio OK')"

# Generate audio files
python main_system.py --init-audio
```

## Hardware Requirements

### Minimum
- Python 3.8+
- Webcam (for camera mode)
- USB port (for scanner mode)
- Speakers (for voice feedback)

### Recommended (Your HP EliteBook 840 G11)
- ✅ Built-in webcam (sufficient for badge scanning)
- ✅ USB ports for scanner
- ✅ Built-in speakers for voice
- ✅ Sufficient processing power for real-time video

## Future Enhancements

Potential improvements for production:

1. **Face Recognition** - Identify employees without badges
2. **Mobile App** - Check-in via smartphone
3. **Cloud Sync** - Sync with cloud database
4. **Analytics Dashboard** - Advanced reporting
5. **Multi-camera Support** - Multiple entry points
6. **RFID Integration** - Support RFID cards
7. **Slack/Teams Integration** - Notifications

## License

MIT License - Free for commercial use

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the code comments
3. Test individual components
