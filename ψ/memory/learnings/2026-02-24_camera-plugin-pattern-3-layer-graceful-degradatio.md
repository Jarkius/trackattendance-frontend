---
title: Camera Plugin Pattern: 3-layer graceful degradation for optional hardware featur
tags: [plugin-architecture, graceful-degradation, pyqt6, camera, optional-dependency, trackattendance]
created: 2026-02-24
source: rrr: trackattendance-frontend
---

# Camera Plugin Pattern: 3-layer graceful degradation for optional hardware featur

Camera Plugin Pattern: 3-layer graceful degradation for optional hardware features in PyQt6 kiosk apps. Layer 1: config toggle (default OFF). Layer 2: folder existence + late import inside start() (never at module level). Layer 3: runtime hardware check. Key insight: camera is a helper, not a blocker — route camera scans through the same Api.submit_scan() path as USB badges for free UI feedback. Follow AutoSyncManager pattern: create after view → inject into Api → start on loadFinished → stop in finally.

---
*Added via Oracle Learn*
