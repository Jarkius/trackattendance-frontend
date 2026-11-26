"""Which video / image the full-screen display (idle screensaver, hold screen) shows.

Like voices/: a media/ folder next to the .exe (next to main.py in dev) holds the event's
own files and is changed per event without a rebuild. Video and image are chosen
independently, each falling back to the neutral defaults bundled in assets/media.

Candidates are returned in order (event file first, built-in second) rather than one
answer, because only trying a file tells whether it really plays. Videos are tried in
order with Qt's own player (native_video.VideoProbe), images by the page, and each falls
back to the next, so an unplayable event file never means a black screen.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

VIDEO_EXTENSIONS = (".webm", ".mp4")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

EVENT_SOURCE = "media folder"
BUILTIN_SOURCE = "built-in"


def _added_or_changed(path: Path) -> float:
    """When the file arrived here or last changed, whichever is later.

    Explorer keeps a file's original modified date when copying, so a video exported
    last week but copied in just now has an old st_mtime; its creation time on this
    disk (st_birthtime, or st_ctime on Windows before Python 3.12) is the copy time.
    """
    st = path.stat()
    return max(st.st_mtime, getattr(st, "st_birthtime", st.st_ctime))


def _media_files(directory: Path, extensions) -> List[Path]:
    """Matching files directly in directory (any case), newest first (name breaks ties).

    Newest first because operators replace content by dropping a new file in: the file
    they just added must win over an older one, whatever the names.
    """
    if not directory.is_dir():
        return []
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in extensions]
    return sorted(files, key=lambda p: (-_added_or_changed(p), p.name.lower()))


def resolve_screensaver_media(event_dir: Path, builtin_dir: Path) -> Dict[str, list]:
    """Return {"video": [...], "image": [...]}, each a list of candidates to try in order.

    A candidate is {"url", "name", "source"}. Every matching file in event_dir comes
    first, newest first, so an unplayable newest file falls back to the next one; then
    the built-in default. Empty list = nothing to show.
    """
    result: Dict[str, list] = {}
    for kind, extensions in (("video", VIDEO_EXTENSIONS), ("image", IMAGE_EXTENSIONS)):
        candidates = [
            {"url": p.resolve().as_uri(), "name": p.name, "source": EVENT_SOURCE}
            for p in _media_files(event_dir, extensions)
        ]
        builtin = _media_files(builtin_dir, extensions)
        if builtin:
            candidates.append({"url": builtin[0].resolve().as_uri(), "name": builtin[0].name,
                               "source": BUILTIN_SOURCE})
        result[kind] = candidates
    return result


def describe(media: Dict[str, list]) -> str:
    """One log line: what each kind will try, in order."""
    def fmt(cands):
        return " -> ".join(f"{c['name']} ({c['source']})" for c in cands) or "none"
    return f"video: {fmt(media.get('video', []))} | image: {fmt(media.get('image', []))}"
