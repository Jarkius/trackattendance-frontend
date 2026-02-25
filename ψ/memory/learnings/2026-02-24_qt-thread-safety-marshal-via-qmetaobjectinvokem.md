---
title: Qt Thread Safety — Marshal via QMetaObject.invokeMethod: When a background threa
tags: [qt, thread-safety, pyqt6, qmediaplayer, camera, plugin-architecture]
created: 2026-02-24
source: rrr: trackattendance-frontend
---

# Qt Thread Safety — Marshal via QMetaObject.invokeMethod: When a background threa

Qt Thread Safety — Marshal via QMetaObject.invokeMethod: When a background thread needs to trigger Qt operations (QMediaPlayer, QPixmap, QWidget), never call Qt directly. Make the target class extend QObject, store data in a plain Python field, then QMetaObject.invokeMethod(self, "slot_name", QueuedConnection) to schedule on main thread. Even read-only Qt access (playbackState()) from background threads is unsafe — replace with time-based flags (plain float timestamps). Pattern applies to any PyQt6 plugin with background processing threads.

---
*Added via Oracle Learn*
