#!/usr/bin/env python3
"""
Attendance System Launcher
Simple entry point to run different modes
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='Employee Attendance System - Beta Prototype',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python launcher.py --demo          Run demonstration
  python launcher.py --cli           Interactive CLI mode
  python launcher.py --web           Start web dashboard
  python launcher.py --test          Run tests
  python launcher.py --init-audio    Generate audio files
        '''
    )
    
    parser.add_argument('--demo', action='store_true',
                       help='Run demonstration mode')
    parser.add_argument('--cli', action='store_true',
                       help='Interactive CLI mode')
    parser.add_argument('--web', action='store_true',
                       help='Start web dashboard')
    parser.add_argument('--web-host', default='0.0.0.0',
                       help='Web dashboard host (default: 0.0.0.0)')
    parser.add_argument('--web-port', type=int, default=5000,
                       help='Web dashboard port (default: 5000)')
    parser.add_argument('--test', action='store_true',
                       help='Run system tests')
    parser.add_argument('--init-audio', action='store_true',
                       help='Generate sample audio files')
    parser.add_argument('--camera-only', action='store_true',
                       help='Use camera only (no USB scanner)')
    parser.add_argument('--usb-only', action='store_true',
                       help='Use USB scanner only (no camera)')
    
    args = parser.parse_args()
    
    # If no arguments, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    if args.test:
        print("Running system tests...")
        import test_system
        return
    
    if args.init_audio:
        print("Generating sample audio files...")
        try:
            from voice_feedback import init_sample_audio
            init_sample_audio()
        except ImportError as e:
            print(f"Error: {e}")
            print("Install dependencies: pip install gTTS pygame")
        return
    
    if args.web:
        print("Starting web dashboard...")
        from web_dashboard import run_web_dashboard
        run_web_dashboard(host=args.web_host, port=args.web_port)
        return
    
    if args.demo:
        print("Running demonstration...")
        from main_system import run_simple_demo
        run_simple_demo()
        return
    
    if args.cli:
        print("Starting interactive CLI...")
        from main_system import AttendanceSystemCLI
        cli = AttendanceSystemCLI()
        cli.run()
        return
    
    # Default: run based on flags
    if args.camera_only or args.usb_only:
        from main_system import AttendanceSystem, SystemConfig
        
        config = SystemConfig(
            enable_usb_scanner=not args.camera_only,
            enable_camera_scanner=not args.usb_only,
            enable_proximity_detection=not args.usb_only,
            enable_voice=True
        )
        
        system = AttendanceSystem(config)
        try:
            with system:
                print("\nSystem running. Press Ctrl+C to stop.\n")
                import time
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")

if __name__ == '__main__':
    main()
