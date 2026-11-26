#!/usr/bin/env python3
"""Tests for screensaver_media: event media/ folder first, built-in defaults second.

Run: python tests/test_screensaver_media.py
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from screensaver_media import BUILTIN_SOURCE, EVENT_SOURCE, describe, resolve_screensaver_media  # noqa: E402


def touch(directory: Path, *names):
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"x")


class TestResolveScreensaverMedia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.event = base / "media"
        self.builtin = base / "assets" / "media"

    def tearDown(self):
        self._tmp.cleanup()

    def names(self, cands):
        return [(c["name"], c["source"]) for c in cands]

    def test_event_file_comes_before_builtin(self):
        touch(self.event, "party.webm", "kv.jpg")
        touch(self.builtin, "default-loop.webm", "default-key-visual.png")
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(self.names(m["video"]),
                         [("party.webm", EVENT_SOURCE), ("default-loop.webm", BUILTIN_SOURCE)])
        self.assertEqual(self.names(m["image"]),
                         [("kv.jpg", EVENT_SOURCE), ("default-key-visual.png", BUILTIN_SOURCE)])

    def test_video_and_image_fall_back_independently(self):
        touch(self.event, "party.webm")                      # event brings only a video
        touch(self.builtin, "default-loop.webm", "default-key-visual.png")
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(m["video"][0]["source"], EVENT_SOURCE)
        self.assertEqual(self.names(m["image"]), [("default-key-visual.png", BUILTIN_SOURCE)])

    def test_missing_event_folder_uses_builtin(self):
        touch(self.builtin, "default-loop.webm")
        m = resolve_screensaver_media(self.event, self.builtin)  # self.event never created
        self.assertEqual(self.names(m["video"]), [("default-loop.webm", BUILTIN_SOURCE)])
        self.assertEqual(m["image"], [])

    def test_nothing_anywhere_gives_empty_lists(self):
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(m, {"video": [], "image": []})
        self.assertEqual(describe(m), "video: none | image: none")

    def test_mp4_is_a_candidate_and_extensions_are_case_insensitive(self):
        touch(self.event, "Event.MP4", "Poster.PNG", "notes.txt", "song.mp3")
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(self.names(m["video"]), [("Event.MP4", EVENT_SOURCE)])
        self.assertEqual(self.names(m["image"]), [("Poster.PNG", EVENT_SOURCE)])

    def test_newest_file_first_then_older_ones_as_fallback(self):
        # Operator adds "checkin-guide_v07.mp4" next to an older "checkin-guide.webm":
        # the new one must be tried first even though it sorts later by name.
        touch(self.event, "checkin-guide.webm")
        time.sleep(0.05)
        touch(self.event, "checkin-guide_v07.mp4")
        touch(self.builtin, "default-loop.webm")
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(self.names(m["video"]), [
            ("checkin-guide_v07.mp4", EVENT_SOURCE),
            ("checkin-guide.webm", EVENT_SOURCE),
            ("default-loop.webm", BUILTIN_SOURCE),
        ])

    @unittest.skipUnless(sys.platform == "win32", "creation time = copy time only on Windows")
    def test_just_copied_file_wins_even_with_an_old_modified_date(self):
        # Explorer keeps the modified date of a copied file: a video exported last week
        # and copied in now must still count as the newest.
        touch(self.event, "current.webm")
        time.sleep(0.05)
        touch(self.event, "exported-last-week.webm")
        week_ago = time.time() - 7 * 24 * 3600
        os.utime(self.event / "exported-last-week.webm", (week_ago, week_ago))
        m = resolve_screensaver_media(self.event, self.builtin)
        self.assertEqual(m["video"][0]["name"], "exported-last-week.webm")

    def test_urls_are_file_uris_the_page_can_load(self):
        touch(self.event, "party loop.webm")                 # space in name
        url = resolve_screensaver_media(self.event, self.builtin)["video"][0]["url"]
        self.assertTrue(url.startswith("file:///"))
        self.assertIn("party%20loop.webm", url)

    def test_shipped_defaults_exist(self):
        m = resolve_screensaver_media(self.event, ROOT / "assets" / "media")
        self.assertEqual(self.names(m["video"]), [("default-loop.webm", BUILTIN_SOURCE)])
        self.assertEqual(self.names(m["image"]), [("default-key-visual.png", BUILTIN_SOURCE)])


if __name__ == "__main__":
    unittest.main()
