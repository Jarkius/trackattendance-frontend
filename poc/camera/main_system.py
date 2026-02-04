"""
Main Attendance System - Integration Module
Combines USB scanner, camera scanner, voice feedback, and database
"""

import os
import sys
import time
import threading
import queue
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

# Import our modules
from database import AttendanceDatabase, db, Employee, Event
from voice_feedback import VoiceFeedback, VoiceConfig, VoiceMessage, get_voice_feedback
from camera_scanner import CameraScanner, CameraConfig, ScanResult, ProximityDetector
from usb_scanner import USBScanner, USBScannerConfig, USBScanResult


@dataclass
class SystemConfig:
    """Main system configuration"""
    # Scanner settings
    enable_usb_scanner: bool = True
    enable_camera_scanner: bool = True
    enable_proximity_detection: bool = True
    
    # Voice settings
    enable_voice: bool = True
    voice_language: str = 'en'
    
    # Event settings
    auto_select_active_event: bool = True
    default_event_id: Optional[int] = None
    
    # Check-in mode
    allow_check_out: bool = True  # Allow check-out after check-in
    
    # Camera settings
    camera_id: int = 0
    camera_resolution: tuple = (1280, 720)


class AttendanceSystem:
    """
    Main Attendance System
    
    Integrates:
    - USB barcode scanner
    - Camera-based QR/barcode scanning
    - Proximity detection for greeting
    - Voice feedback
    - SQLite database
    
    Usage:
        system = AttendanceSystem()
        system.start()
        # System runs in background
        system.stop()
    """
    
    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig()
        self.db = db
        self.is_running = False
        
        # Components
        self.usb_scanner: Optional[USBScanner] = None
        self.camera_scanner: Optional[CameraScanner] = None
        self.proximity_detector: Optional[ProximityDetector] = None
        self.voice: Optional[VoiceFeedback] = None
        
        # State
        self.current_event: Optional[Event] = None
        self._processing_queue: queue.Queue = queue.Queue()
        self._processing_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            'total_scans': 0,
            'successful_checkins': 0,
            'failed_scans': 0,
            'last_scan_time': None,
            'last_scan_data': None
        }
        
        # Callbacks
        self._scan_callbacks: List = []
        self._attendance_callbacks: List = []
    
    def _init_voice(self):
        """Initialize voice feedback"""
        if not self.config.enable_voice:
            return
        
        voice_config = VoiceConfig(
            language=self.config.voice_language,
            greeting_cooldown=10
        )
        self.voice = VoiceFeedback(voice_config)
        print("Voice feedback initialized")
    
    def _init_usb_scanner(self):
        """Initialize USB scanner"""
        if not self.config.enable_usb_scanner:
            return
        
        usb_config = USBScannerConfig()
        self.usb_scanner = USBScanner(usb_config)
        self.usb_scanner.add_result_callback(self._on_usb_scan)
        print("USB scanner initialized")
    
    def _init_camera_scanner(self):
        """Initialize camera scanner"""
        if not self.config.enable_camera_scanner:
            return
        
        camera_config = CameraConfig(
            camera_id=self.config.camera_id,
            resolution=self.config.camera_resolution,
            enable_preview=False,  # No GUI in background mode
            scan_cooldown=2.0
        )
        self.camera_scanner = CameraScanner(camera_config)
        self.camera_scanner.add_result_callback(self._on_camera_scan)
        
        # Add frame callback for proximity detection
        if self.config.enable_proximity_detection:
            self.proximity_detector = ProximityDetector(
                sensitivity=5000,
                cooldown=10.0
            )
            self.proximity_detector.add_detection_callback(self._on_proximity_detected)
            self.camera_scanner.add_frame_callback(self._on_frame_for_proximity)
        
        print("Camera scanner initialized")
    
    def _on_proximity_detected(self):
        """Handle proximity detection"""
        print("[PROXIMITY] Person detected near camera")
        if self.voice:
            self.voice.proximity_greeting()
    
    def _on_frame_for_proximity(self, frame):
        """Process frame for proximity detection"""
        if self.proximity_detector:
            self.proximity_detector.process_frame(frame)
    
    def _on_usb_scan(self, result: USBScanResult):
        """Handle USB scanner result"""
        print(f"[USB SCAN] {result.data}")
        self._processing_queue.put({
            'source': 'usb',
            'data': result.data,
            'timestamp': result.timestamp
        })
    
    def _on_camera_scan(self, result: ScanResult):
        """Handle camera scanner result"""
        print(f"[CAMERA SCAN] {result.data}")
        self._processing_queue.put({
            'source': 'camera',
            'data': result.data,
            'timestamp': result.timestamp
        })
    
    def _process_scan(self, scan_data: Dict[str, Any]):
        """Process a scan and record attendance"""
        badge_id = scan_data['data'].strip()
        source = scan_data['source']
        
        self.stats['total_scans'] += 1
        self.stats['last_scan_time'] = scan_data['timestamp']
        self.stats['last_scan_data'] = badge_id
        
        # Find employee
        employee = self.db.get_employee_by_badge(badge_id)
        
        if not employee:
            print(f"  [FAIL] Badge not found: {badge_id}")
            self.stats['failed_scans'] += 1
            if self.voice:
                self.voice.speak(VoiceMessage.BADGE_NOT_FOUND)
            return
        
        print(f"  [FOUND] Employee: {employee.name} ({employee.department})")
        
        # Get current event
        event = self._get_current_event()
        if not event:
            print("  [FAIL] No active event")
            if self.voice:
                self.voice.speak(VoiceMessage.ERROR)
            return
        
        # Check existing attendance
        existing = self.db.get_today_attendance_for_employee(employee.id, event.id)
        
        if existing:
            if existing.check_out_time is None and self.config.allow_check_out:
                # Check out
                self.db.record_check_out(existing.id, source)
                print(f"  [CHECK-OUT] {employee.name}")
                if self.voice:
                    self.voice.announce_check_out(employee.name, success=True)
            else:
                # Already checked in and out
                print(f"  [INFO] Already checked in/out today")
                if self.voice:
                    self.voice.speak(VoiceMessage.ALREADY_CHECKED_IN)
        else:
            # New check-in
            self.db.record_check_in(employee.id, event.id, source)
            self.stats['successful_checkins'] += 1
            print(f"  [CHECK-IN] {employee.name}")
            if self.voice:
                self.voice.announce_check_in(employee.name, success=True)
    
    def _get_current_event(self) -> Optional[Event]:
        """Get the current/active event"""
        if self.current_event:
            return self.current_event
        
        if self.config.auto_select_active_event:
            active = self.db.get_active_events()
            if active:
                return active[0]
        
        if self.config.default_event_id:
            return self.db.get_event_by_id(self.config.default_event_id)
        
        return None
    
    def _processing_loop(self):
        """Background processing loop"""
        while self.is_running:
            try:
                scan_data = self._processing_queue.get(timeout=0.5)
                self._process_scan(scan_data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Processing error: {e}")
    
    def set_event(self, event_id: int):
        """Set the current event"""
        event = self.db.get_event_by_id(event_id)
        if event:
            self.current_event = event
            print(f"Event set: {event.name}")
        else:
            print(f"Event not found: {event_id}")
    
    def start(self) -> bool:
        """Start the attendance system"""
        if self.is_running:
            return True
        
        print("=" * 50)
        print("Starting Attendance System")
        print("=" * 50)
        
        # Initialize components
        self._init_voice()
        self._init_usb_scanner()
        self._init_camera_scanner()
        
        # Start scanners
        if self.usb_scanner:
            self.usb_scanner.start()
        
        if self.camera_scanner:
            self.camera_scanner.start()
        
        # Start processing thread
        self.is_running = True
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._processing_thread.start()
        
        # Play welcome message
        if self.voice:
            self.voice.speak(VoiceMessage.WELCOME)
            time.sleep(1)
            self.voice.speak(VoiceMessage.SCAN_PROMPT)
        
        print("=" * 50)
        print("System ready! Waiting for scans...")
        print("=" * 50)
        
        return True
    
    def stop(self):
        """Stop the attendance system"""
        print("\nStopping Attendance System...")
        
        self.is_running = False
        
        if self._processing_thread:
            self._processing_thread.join(timeout=1)
        
        if self.usb_scanner:
            self.usb_scanner.stop()
        
        if self.camera_scanner:
            self.camera_scanner.stop()
        
        if self.voice:
            self.voice.stop()
        
        print("System stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return self.stats.copy()
    
    def get_today_attendance(self) -> List[Dict]:
        """Get today's attendance records"""
        event = self._get_current_event()
        if event:
            return self.db.get_event_attendance(event.id)
        return []
    
    def simulate_scan(self, badge_id: str):
        """Simulate a badge scan (for testing)"""
        if self.usb_scanner:
            self.usb_scanner.simulate_scan(badge_id)
        else:
            self._processing_queue.put({
                'source': 'simulation',
                'data': badge_id,
                'timestamp': time.time()
            })
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class AttendanceSystemCLI:
    """Command-line interface for the attendance system"""
    
    def __init__(self):
        self.system: Optional[AttendanceSystem] = None
    
    def print_menu(self):
        """Print main menu"""
        print("\n" + "=" * 50)
        print("Attendance System - Command Menu")
        print("=" * 50)
        print("1. Start system (USB + Camera)")
        print("2. Start system (USB only)")
        print("3. Start system (Camera only)")
        print("4. Stop system")
        print("5. View statistics")
        print("6. View today's attendance")
        print("7. Simulate scan")
        print("8. Manage employees")
        print("9. Manage events")
        print("0. Exit")
        print("=" * 50)
    
    def start_system(self, mode: str = "full"):
        """Start the system with specified mode"""
        if self.system and self.system.is_running:
            print("System already running!")
            return
        
        config = SystemConfig()
        
        if mode == "usb":
            config.enable_camera_scanner = False
            config.enable_proximity_detection = False
        elif mode == "camera":
            config.enable_usb_scanner = False
        
        self.system = AttendanceSystem(config)
        self.system.start()
    
    def stop_system(self):
        """Stop the system"""
        if self.system:
            self.system.stop()
            self.system = None
        else:
            print("System not running")
    
    def view_stats(self):
        """View system statistics"""
        if not self.system:
            print("System not running")
            return
        
        stats = self.system.get_stats()
        print("\n--- System Statistics ---")
        print(f"Total scans: {stats['total_scans']}")
        print(f"Successful check-ins: {stats['successful_checkins']}")
        print(f"Failed scans: {stats['failed_scans']}")
        print(f"Last scan: {stats['last_scan_data']} at {stats['last_scan_time']}")
    
    def view_attendance(self):
        """View today's attendance"""
        if not self.system:
            print("System not running")
            return
        
        records = self.system.get_today_attendance()
        print(f"\n--- Today's Attendance ({len(records)} records) ---")
        for record in records[:20]:  # Show last 20
            status = "OUT" if record['check_out_time'] else "IN"
            print(f"  [{status}] {record['employee_name']} ({record['department']}) - {record['check_in_time']}")
    
    def simulate_scan(self):
        """Simulate a badge scan"""
        if not self.system:
            print("System not running")
            return
        
        badge_id = input("Enter badge ID to simulate: ").strip()
        if badge_id:
            self.system.simulate_scan(badge_id)
    
    def manage_employees(self):
        """Employee management submenu"""
        while True:
            print("\n--- Employee Management ---")
            print("1. List employees")
            print("2. Add employee")
            print("3. Back")
            
            choice = input("Select: ").strip()
            
            if choice == "1":
                employees = db.get_all_employees()
                print(f"\n--- Employees ({len(employees)}) ---")
                for emp in employees:
                    print(f"  {emp.badge_id}: {emp.name} ({emp.department})")
            
            elif choice == "2":
                badge_id = input("Badge ID: ").strip()
                name = input("Name: ").strip()
                dept = input("Department: ").strip()
                email = input("Email (optional): ").strip() or None
                
                if badge_id and name:
                    emp = db.add_employee(badge_id, name, dept, email)
                    print(f"Added: {emp.name}")
                else:
                    print("Badge ID and Name are required")
            
            elif choice == "3":
                break
    
    def manage_events(self):
        """Event management submenu"""
        while True:
            print("\n--- Event Management ---")
            print("1. List events")
            print("2. Create event")
            print("3. Set active event")
            print("4. Back")
            
            choice = input("Select: ").strip()
            
            if choice == "1":
                events = db.get_all_events()
                print(f"\n--- Events ({len(events)}) ---")
                for evt in events:
                    print(f"  [{evt.id}] {evt.name} ({evt.start_time} to {evt.end_time})")
            
            elif choice == "2":
                name = input("Event name: ").strip()
                desc = input("Description: ").strip() or None
                location = input("Location: ").strip() or None
                
                # Simple date/time input
                from datetime import datetime, timedelta
                today = datetime.now()
                start = today.replace(hour=9, minute=0).isoformat()
                end = today.replace(hour=18, minute=0).isoformat()
                
                if name:
                    evt = db.create_event(name, start, end, desc, location)
                    print(f"Created: {evt.name}")
                else:
                    print("Event name is required")
            
            elif choice == "3":
                event_id = input("Event ID: ").strip()
                if event_id.isdigit() and self.system:
                    self.system.set_event(int(event_id))
            
            elif choice == "4":
                break
    
    def run(self):
        """Main CLI loop"""
        # Initialize database with sample data
        db.add_sample_data()
        
        print("\n" + "=" * 50)
        print("Employee Attendance System")
        print("Beta Prototype v1.0")
        print("=" * 50)
        
        try:
            while True:
                self.print_menu()
                choice = input("Select option: ").strip()
                
                if choice == "1":
                    self.start_system("full")
                elif choice == "2":
                    self.start_system("usb")
                elif choice == "3":
                    self.start_system("camera")
                elif choice == "4":
                    self.stop_system()
                elif choice == "5":
                    self.view_stats()
                elif choice == "6":
                    self.view_attendance()
                elif choice == "7":
                    self.simulate_scan()
                elif choice == "8":
                    self.manage_employees()
                elif choice == "9":
                    self.manage_events()
                elif choice == "0":
                    self.stop_system()
                    print("Goodbye!")
                    break
                else:
                    print("Invalid option")
        
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            self.stop_system()


def run_simple_demo():
    """Run a simple demonstration"""
    print("=" * 60)
    print("Attendance System - Simple Demo")
    print("=" * 60)
    
    # Initialize database
    db.add_sample_data()
    
    # Create config (USB only for simple demo)
    config = SystemConfig(
        enable_usb_scanner=True,
        enable_camera_scanner=False,
        enable_proximity_detection=False,
        enable_voice=True
    )
    
    # Create and start system
    system = AttendanceSystem(config)
    
    try:
        with system:
            print("\nSystem running. Simulating scans...")
            print("(In real use, scan badges with USB scanner)")
            print("Press Ctrl+C to stop\n")
            
            # Simulate some scans
            time.sleep(2)
            print("\n--- Simulating scans ---")
            
            test_scans = ['EMP001', 'EMP002', 'EMP999', 'EMP001', 'EMP003']
            for badge in test_scans:
                print(f"\n> Simulating scan: {badge}")
                system.simulate_scan(badge)
                time.sleep(3)
            
            print("\n--- Demo scans complete ---")
            print("Press Ctrl+C to stop system")
            
            # Keep running
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nStopping demo...")
    
    print("\nDemo complete!")
    print("\nFinal Statistics:")
    stats = system.get_stats()
    print(f"  Total scans: {stats['total_scans']}")
    print(f"  Successful check-ins: {stats['successful_checkins']}")
    print(f"  Failed scans: {stats['failed_scans']}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Attendance System')
    parser.add_argument('--demo', action='store_true', help='Run simple demo')
    parser.add_argument('--cli', action='store_true', help='Run interactive CLI')
    parser.add_argument('--init-audio', action='store_true', help='Generate sample audio files')
    
    args = parser.parse_args()
    
    if args.init_audio:
        from voice_feedback import init_sample_audio
        init_sample_audio()
    elif args.demo:
        run_simple_demo()
    else:
        # Default to CLI
        cli = AttendanceSystemCLI()
        cli.run()
