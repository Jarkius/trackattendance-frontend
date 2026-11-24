#!/usr/bin/env python3
"""Voice clip discovery: .mp3 and .wav are both played, other files are ignored."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import audio
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "PyQt6 not installed")
class TestFindVoiceFiles(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_mp3_and_wav_found_other_files_ignored(self):
        for name in ["b.mp3", "a speech.wav", "C.WAV", "D.MP3", "notes.txt", "cover.jpg"]:
            (self.dir / name).write_bytes(b"x")
        (self.dir / "sub.mp3").mkdir()
        found = [p.name for p in audio.find_voice_files(self.dir)]
        self.assertEqual(sorted(found), sorted(["b.mp3", "a speech.wav", "C.WAV", "D.MP3"]))

    def test_missing_dir_returns_empty(self):
        self.assertEqual(audio.find_voice_files(self.dir / "nope"), [])


if __name__ == "__main__":
    unittest.main()
