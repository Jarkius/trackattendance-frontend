# Admin Clear Should Reset ALL State

**Date**: 2026-02-02
**Context**: TrackAttendance frontend admin panel clear feature
**Confidence**: High

## Key Learning

When building a "clear all data" admin function, think beyond just the primary data rows. Consider all related state that should reset: configuration (station names), sequences (autoincrement IDs), caches, and application state. A partial clear leaves stale config that can silently carry over to the next usage context.

In this case, clearing scans without clearing the station name meant the next event would inherit the previous station's identity. And staying in the app after a full wipe left the user in a broken UI state with no way to re-enter the station name without restarting.

The fix was to also clear the `stations` table, reset SQLite's `sqlite_sequence`, and auto-close the app after 3 seconds so the next launch starts completely fresh with a station name prompt.

## The Pattern

```python
# Bad: Partial clear
def clear_all_scans(self):
    self._connection.execute("DELETE FROM scans")

# Good: Complete reset
def clear_all_scans(self):
    self._connection.execute("DELETE FROM scans")
    self._connection.execute("DELETE FROM sqlite_sequence WHERE name='scans'")
    self._connection.execute("DELETE FROM stations")
```

## Why This Matters

- Between events, station names change. Stale config causes confusion.
- Auto-close forces a clean restart, preventing operation on zeroed-out state.
- SQLite doesn't support TRUNCATE — use DELETE + sqlite_sequence clear to reset IDs.
- Always think: "what state exists beyond the primary table?"

## Tags

`sqlite`, `admin`, `reset`, `state-management`, `ux`, `trackattendance`
