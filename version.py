"""Single source of truth for the app version.

Kept dependency-free (no Qt, no config) so TrackAttendance.spec and release
scripts can import it. Bump this together with the CHANGELOG/README entry.
"""

__version__ = "2.1.11"
