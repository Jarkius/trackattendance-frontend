# Automated Tests Find Real Bugs That Manual Testing Misses

**Date**: 2026-02-02
**Context**: TrackAttendance frontend #37 validation — auto-focus bug found by UI test
**Confidence**: High

## Key Learning

Writing automated tests for "manual testing checklist" items isn't just about verification — it discovers real bugs that manual testing is unlikely to catch. In this case, a test for "dashboard scroll shouldn't jump to barcode input" revealed that the barcode input retained focus when the dashboard overlay opened, because the HTML `autofocus` attribute gives persistent focus that survives overlay transitions.

The fix was a one-liner (`barcodeInput.blur()` on dashboard open), but the bug would have been hard to notice manually in kiosk production use. Users rarely open the dashboard while actively scanning, so the focus interference would only manifest as subtle scroll jumps.

Two additional patterns emerged: (1) SQLite threading tests must use separate connections per thread, matching the real app's architecture where the sync thread has its own DB connection, and (2) UI tests should call the app's own functions rather than directly manipulating DOM, otherwise you're testing a different code path than production.

## The Pattern

```javascript
// Bug: autofocus persists through overlay transitions
<input id="barcode-input" autofocus>

// showDashboardOverlay() sets dashboardOpen = true
// but the input ALREADY has focus from page load
// returnFocusToInput() guard only prevents RE-focusing

// Fix: actively blur when overlay opens
const showDashboardOverlay = () => {
    dashboardOpen = true;
    if (barcodeInput) barcodeInput.blur();  // Release focus
    // ... rest of overlay logic
};
```

```python
# SQLite threading: separate connections per thread
def sync_worker():
    thread_db = DatabaseManager(db_path)  # Own connection
    scans = thread_db.fetch_pending_scans(limit=10)
    thread_db.mark_scans_as_synced([s.id for s in scans])
    thread_db.close()
```

## Why This Matters

- Automated tests catch interaction bugs that are invisible in normal usage
- The `autofocus` HTML attribute creates persistent focus that must be explicitly cleared
- SQLite's thread safety model requires per-thread connections (which matches real app architecture)
- Testing through app functions vs direct DOM gives different results — always test the real code path

## Tags

`testing`, `autofocus`, `sqlite`, `threading`, `ui-testing`, `pyqt6`, `trackattendance`
