"""Run a blocking call off the Qt main thread without losing its synchronous
return-value contract.

Several QWebChannel-exposed slots (Dashboard, Settings, Live Sync's
cross-station duplicate check) call `requests.*()` directly on the Qt main
thread. The caller genuinely needs the result before continuing (e.g. Live
Sync's block-mode duplicate rejection must happen before the scan is
recorded), so this isn't a fire-and-forget job for BackgroundSyncCoordinator
(sync.py) — it needs to behave like a normal function call, just without
freezing the UI while it waits.
"""

from __future__ import annotations

import threading
from typing import Callable, TypeVar

from PyQt6.QtCore import QCoreApplication, QEventLoop, QObject, pyqtSignal

T = TypeVar("T")


class _WorkerDone(QObject):
    finished = pyqtSignal()


def call_without_freezing_ui(fn: Callable[[], T]) -> T:
    """Call fn() on a worker thread and return its result, pumping the Qt
    event loop on the calling thread while waiting so paint/input/other
    QWebChannel events keep processing instead of the whole app freezing.

    Falls back to calling fn() directly when no QApplication/QCoreApplication
    instance exists (e.g. under pytest, which never constructs one) — a
    nested QEventLoop.exec() never returns without one, so this guard keeps
    every test's existing synchronous-call behavior unchanged.

    Any exception raised inside fn() propagates to the caller.
    """
    if QCoreApplication.instance() is None:
        return fn()

    outcome: list = []
    done = _WorkerDone()
    loop = QEventLoop()
    done.finished.connect(loop.quit)

    def _run() -> None:
        try:
            outcome.append((True, fn()))
        except Exception as exc:  # noqa: BLE001 - re-raised on the caller's thread below
            outcome.append((False, exc))
        done.finished.emit()

    threading.Thread(target=_run, daemon=True, name="call-without-freezing-ui").start()
    loop.exec()

    ok, value = outcome[0]
    if not ok:
        raise value
    return value


__all__ = ["call_without_freezing_ui"]
