"""
Voice Feedback System for Attendance Tracking
Handles pre-recorded voice messages and text-to-speech fallback
"""

import os
import sys
import pygame
import threading
import queue
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum
import time

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

# Try to import gTTS for text-to-speech (requires internet)
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# Try to import pyttsx3 for offline TTS (Windows SAPI5, macOS NSSpeech)
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Audio files directory
AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'audio')


class VoiceMessage(Enum):
    """Pre-defined voice messages"""
    WELCOME = "welcome"
    SCAN_PROMPT = "scan_prompt"
    BADGE_MATCHED = "badge_matched"
    BADGE_NOT_FOUND = "badge_not_found"
    ALREADY_CHECKED_IN = "already_checked_in"
    CHECK_IN_SUCCESS = "check_in_success"
    CHECK_OUT_SUCCESS = "check_out_success"
    GOODBYE = "goodbye"
    ERROR = "error"
    PROXIMITY_GREETING = "proximity_greeting"


@dataclass
class VoiceConfig:
    """Configuration for voice feedback"""
    use_prerecorded: bool = True
    use_tts_fallback: bool = True
    language: str = 'en'
    volume: float = 0.8
    greeting_cooldown: int = 10  # Seconds between proximity greetings


class VoiceFeedback:
    """
    Voice feedback system with pre-recorded audio and TTS fallback
    
    Features:
    - Pre-recorded voice messages for common scenarios
    - Text-to-speech fallback for dynamic messages
    - Queue-based audio playback (non-blocking)
    - Proximity detection greeting with cooldown
    """
    
    # Default messages for TTS fallback
    DEFAULT_MESSAGES = {
        VoiceMessage.WELCOME: "Welcome to the attendance system.",
        VoiceMessage.SCAN_PROMPT: "Please scan your badge.",
        VoiceMessage.BADGE_MATCHED: "Badge recognized.",
        VoiceMessage.BADGE_NOT_FOUND: "Badge not found. Please contact HR.",
        VoiceMessage.ALREADY_CHECKED_IN: "You are already checked in.",
        VoiceMessage.CHECK_IN_SUCCESS: "Check-in successful. Welcome!",
        VoiceMessage.CHECK_OUT_SUCCESS: "Check-out successful. Goodbye!",
        VoiceMessage.GOODBYE: "Thank you. Have a great day!",
        VoiceMessage.ERROR: "An error occurred. Please try again.",
        VoiceMessage.PROXIMITY_GREETING: "Hello! Please scan your badge to check in.",
    }
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.last_greeting_time = 0
        self._playback_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Ensure audio directory exists
        os.makedirs(AUDIO_DIR, exist_ok=True)
        
        # Initialize pygame mixer
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.audio_available = True
        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")
            self.audio_available = False
        
        # Start playback thread
        self._start_playback_thread()
    
    def _start_playback_thread(self):
        """Start the background audio playback thread"""
        self._running = True
        self._playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._playback_thread.start()
    
    def _playback_worker(self):
        """Background worker for audio playback"""
        while self._running:
            try:
                audio_file, message_type = self.audio_queue.get(timeout=0.5)
                self.is_playing = True
                
                if self.audio_available and os.path.exists(audio_file):
                    try:
                        pygame.mixer.music.load(audio_file)
                        pygame.mixer.music.set_volume(self.config.volume)
                        pygame.mixer.music.play()
                        
                        # Wait for playback to finish
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                    except Exception as e:
                        print(f"Audio playback error: {e}")
                
                self.is_playing = False
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Playback worker error: {e}")
                self.is_playing = False
    
    def _get_audio_file_path(self, message_type: VoiceMessage) -> str:
        """Get path to pre-recorded audio file"""
        return os.path.join(AUDIO_DIR, f"{message_type.value}.mp3")
    
    def _generate_tts_audio(self, text: str, output_file: str) -> bool:
        """Generate TTS audio file. Tries gTTS (online) then pyttsx3 (offline)."""
        # Try gTTS first (better quality, requires internet)
        if GTTS_AVAILABLE:
            try:
                tts = gTTS(text=text, lang=self.config.language, slow=False)
                tts.save(output_file)
                return True
            except Exception as e:
                print(f"gTTS generation error (no internet?): {e}")

        # Fallback to pyttsx3 (offline, works on Windows SAPI5 and macOS NSSpeech)
        if PYTTSX3_AVAILABLE:
            try:
                engine = pyttsx3.init()
                engine.save_to_file(text, output_file)
                engine.runAndWait()
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True
            except Exception as e:
                print(f"pyttsx3 generation error: {e}")

        # Last resort on macOS: use 'say' command
        if IS_MACOS:
            try:
                import subprocess
                subprocess.run(
                    ['say', '-o', output_file, '--data-format=LEF32@22050', text],
                    capture_output=True, timeout=10
                )
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    return True
            except Exception:
                pass

        return False
    
    def speak(self, message_type: VoiceMessage, custom_text: Optional[str] = None,
              priority: bool = False):
        """
        Queue a voice message for playback
        
        Args:
            message_type: Type of pre-defined message
            custom_text: Optional custom text (for TTS)
            priority: If True, insert at front of queue
        """
        audio_file = self._get_audio_file_path(message_type)
        
        # Check if pre-recorded audio exists
        if self.config.use_prerecorded and os.path.exists(audio_file):
            if priority:
                # Create new queue with priority item first
                new_queue = queue.Queue()
                new_queue.put((audio_file, message_type))
                while not self.audio_queue.empty():
                    new_queue.put(self.audio_queue.get())
                self.audio_queue = new_queue
            else:
                self.audio_queue.put((audio_file, message_type))
            return
        
        # Fallback to TTS
        if self.config.use_tts_fallback and GTTS_AVAILABLE:
            text = custom_text or self.DEFAULT_MESSAGES.get(message_type, "")
            if text:
                # Generate TTS audio
                tts_file = os.path.join(AUDIO_DIR, f"tts_{int(time.time())}.mp3")
                if self._generate_tts_audio(text, tts_file):
                    self.audio_queue.put((tts_file, message_type))
    
    def speak_text(self, text: str, priority: bool = False):
        """
        Speak arbitrary text using TTS
        
        Args:
            text: Text to speak
            priority: If True, insert at front of queue
        """
        if not GTTS_AVAILABLE or not self.config.use_tts_fallback:
            print(f"TTS not available. Message: {text}")
            return
        
        tts_file = os.path.join(AUDIO_DIR, f"tts_{int(time.time())}.mp3")
        if self._generate_tts_audio(text, tts_file):
            if priority:
                new_queue = queue.Queue()
                new_queue.put((tts_file, VoiceMessage.WELCOME))
                while not self.audio_queue.empty():
                    new_queue.put(self.audio_queue.get())
                self.audio_queue = new_queue
            else:
                self.audio_queue.put((tts_file, VoiceMessage.WELCOME))
    
    def can_greet(self) -> bool:
        """Check if enough time has passed since last greeting"""
        current_time = time.time()
        if current_time - self.last_greeting_time >= self.config.greeting_cooldown:
            self.last_greeting_time = current_time
            return True
        return False
    
    def proximity_greeting(self):
        """Play proximity greeting if cooldown has passed"""
        if self.can_greet():
            self.speak(VoiceMessage.PROXIMITY_GREETING, priority=True)
    
    def announce_check_in(self, employee_name: str, success: bool = True):
        """Announce check-in result"""
        if success:
            # Play success sound + name
            self.speak(VoiceMessage.CHECK_IN_SUCCESS)
            # Optionally speak name after
            # self.speak_text(f"Welcome, {employee_name}")
        else:
            self.speak(VoiceMessage.BADGE_NOT_FOUND)
    
    def announce_check_out(self, employee_name: str, success: bool = True):
        """Announce check-out result"""
        if success:
            self.speak(VoiceMessage.CHECK_OUT_SUCCESS)
            # self.speak_text(f"Goodbye, {employee_name}")
        else:
            self.speak(VoiceMessage.ERROR)
    
    def create_sample_audio_files(self):
        """Generate sample TTS audio files for all message types"""
        if not GTTS_AVAILABLE:
            print("gTTS not available. Install with: pip install gtts")
            return
        
        print("Generating sample audio files...")
        for msg_type, text in self.DEFAULT_MESSAGES.items():
            audio_file = self._get_audio_file_path(msg_type)
            if not os.path.exists(audio_file):
                if self._generate_tts_audio(text, audio_file):
                    print(f"Created: {audio_file}")
                else:
                    print(f"Failed to create: {audio_file}")
            else:
                print(f"Already exists: {audio_file}")
        print("Sample audio generation complete!")
    
    def stop(self):
        """Stop playback and cleanup"""
        self._running = False
        if self._playback_thread:
            self._playback_thread.join(timeout=1)
        if self.audio_available:
            pygame.mixer.quit()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Global voice feedback instance
_voice_feedback: Optional[VoiceFeedback] = None


def get_voice_feedback(config: Optional[VoiceConfig] = None) -> VoiceFeedback:
    """Get or create global voice feedback instance"""
    global _voice_feedback
    if _voice_feedback is None:
        _voice_feedback = VoiceFeedback(config)
    return _voice_feedback


def init_sample_audio():
    """Initialize sample audio files"""
    vf = VoiceFeedback()
    vf.create_sample_audio_files()
    vf.stop()


if __name__ == '__main__':
    # Generate sample audio files
    init_sample_audio()
    
    # Test voice feedback
    print("Testing voice feedback...")
    vf = VoiceFeedback()
    
    vf.speak(VoiceMessage.WELCOME)
    time.sleep(3)
    
    vf.speak(VoiceMessage.SCAN_PROMPT)
    time.sleep(3)
    
    vf.speak(VoiceMessage.CHECK_IN_SUCCESS)
    time.sleep(3)
    
    vf.stop()
    print("Voice feedback test complete!")
