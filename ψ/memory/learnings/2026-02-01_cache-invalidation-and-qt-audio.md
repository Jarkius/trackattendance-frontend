# Cache Guards Need Invalidation Strategies

**Date**: 2026-02-01
**Context**: TrackAttendance Frontend — employee roster loading from Excel to SQLite
**Confidence**: High

## Key Learning

When implementing "load once" guard clauses like `if already_loaded(): return`, always pair them with an invalidation mechanism. In our case, `employees_loaded()` checked if the SQLite employees table had any rows. Once a single employee was imported, it would never reimport — even when the source Excel file gained 9 new employees.

This is a classic cache invalidation problem disguised as a simple optimization. The fix was destructive (delete the database), but the proper solution is change detection: hash the source file on import, store the hash, and compare on startup.

A secondary learning: QMediaPlayer in PyQt6 has a cold-start delay on first playback. Pre-warming the player by loading (but not playing) the first audio file during init eliminates this delay entirely. This is a useful pattern for any Qt app that needs responsive audio feedback.

## The Pattern

```python
# BAD: Guard without invalidation
def load_data(self):
    if self.db.has_data():
        return  # Never reimports!

# GOOD: Guard with change detection
def load_data(self):
    current_hash = hash_file(self.source_path)
    stored_hash = self.db.get_source_hash()
    if stored_hash == current_hash:
        return  # Only skip if source unchanged
    self._reimport(self.source_path)
    self.db.set_source_hash(current_hash)
```

## Why This Matters

In production attendance systems, missing employees means missed scans, which means incorrect attendance records. Silent data staleness is worse than a loud error — at least errors get reported. This pattern applies broadly: any "load once" optimization in data pipelines needs a freshness check.

## Tags

`cache-invalidation`, `sqlite`, `pyqt6`, `audio`, `data-pipeline`, `guard-clause`
