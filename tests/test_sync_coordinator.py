#!/usr/bin/env python3
"""Tests for BackgroundSyncCoordinator in sync.py.

Covers the bounded FIFO network-only worker: submission order, single-worker
reuse, queue-full rejection, barrier/generation invalidation of stale results,
callback delivery, and deterministic shutdown.

No PyQt6 dependency — this is pure-Python threading/queue logic.

Run: python tests/test_sync_coordinator.py
"""

import os
import sys
import threading
import time
import unittest
from pathlib import Path

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")

sys.path.insert(0, str(Path(__file__).parent.parent))

from sync import BackgroundSyncCoordinator


class TestFifoOrderAndWorkerReuse(unittest.TestCase):
    def setUp(self):
        self.coordinator = BackgroundSyncCoordinator(max_queue_size=32)

    def tearDown(self):
        self.coordinator.shutdown(timeout=5)

    def test_jobs_run_in_submission_order(self):
        order = []
        lock = threading.Lock()
        done = threading.Event()
        count = 10

        def make_job(i):
            def _job():
                with lock:
                    order.append(i)
                return i
            return _job

        def on_result(job_id, result):
            if result == count - 1:
                done.set()

        for i in range(count):
            self.coordinator.submit(make_job(i), on_result=on_result)

        self.assertTrue(done.wait(timeout=5), "jobs did not complete in time")
        self.assertEqual(order, list(range(count)))

    def test_exactly_one_worker_thread_handles_all_jobs(self):
        thread_ids = set()
        lock = threading.Lock()
        done = threading.Event()
        count = 20

        def job():
            with lock:
                thread_ids.add(threading.current_thread().ident)
            return None

        remaining = [count]

        def on_result(job_id, result):
            with lock:
                remaining[0] -= 1
                if remaining[0] == 0:
                    done.set()

        for _ in range(count):
            self.coordinator.submit(job, on_result=on_result)

        self.assertTrue(done.wait(timeout=5), "jobs did not complete in time")
        self.assertEqual(len(thread_ids), 1, "more than one worker thread executed jobs")

    def test_submit_does_not_block_caller(self):
        started = threading.Event()
        release = threading.Event()

        def slow_job():
            started.set()
            release.wait(timeout=5)
            return "done"

        start = time.time()
        job_id = self.coordinator.submit(slow_job)
        elapsed = time.time() - start

        self.assertIsNotNone(job_id)
        self.assertLess(elapsed, 0.5, "submit() should return immediately, not block")
        self.assertTrue(started.wait(timeout=5))
        release.set()


class TestQueueFullRejection(unittest.TestCase):
    def setUp(self):
        self.coordinator = BackgroundSyncCoordinator(max_queue_size=2)

    def tearDown(self):
        self.coordinator.shutdown(timeout=5)

    def test_submit_returns_none_when_queue_full(self):
        block_worker = threading.Event()

        def blocking_job():
            block_worker.wait(timeout=5)
            return None

        # First job is immediately dequeued and occupies the sole worker.
        first_id = self.coordinator.submit(blocking_job)
        self.assertIsNotNone(first_id)

        # Give the worker a moment to actually dequeue the first job so the
        # queue itself is empty and available for the next two submissions.
        time.sleep(0.05)

        second_id = self.coordinator.submit(lambda: None)
        third_id = self.coordinator.submit(lambda: None)
        self.assertIsNotNone(second_id)
        self.assertIsNotNone(third_id)

        # Queue (maxsize=2) is now full with second+third; a fourth must be rejected.
        fourth_id = self.coordinator.submit(lambda: None)
        self.assertIsNone(fourth_id, "submit() must reject when the bounded queue is full")

        block_worker.set()

    def test_rejected_job_leaves_underlying_work_item_untouched(self):
        """A None return means the caller's row/work item was never claimed —
        simulated here by a counter the caller only increments after a
        successful submit()."""
        block_worker = threading.Event()
        claimed = []

        def blocking_job():
            block_worker.wait(timeout=5)

        self.coordinator.submit(blocking_job)
        time.sleep(0.05)
        self.coordinator.submit(lambda: None)
        self.coordinator.submit(lambda: None)

        job_id = self.coordinator.submit(lambda: None)
        if job_id is not None:
            claimed.append(job_id)

        self.assertEqual(claimed, [], "work item must not be marked claimed when rejected")
        block_worker.set()


class TestBarrierInvalidatesStaleResults(unittest.TestCase):
    def setUp(self):
        self.coordinator = BackgroundSyncCoordinator(max_queue_size=32)

    def tearDown(self):
        self.coordinator.shutdown(timeout=5)

    def test_queued_jobs_are_dropped_by_barrier(self):
        ran = []

        def job():
            ran.append(1)

        # Occupy the worker so subsequent submissions stay queued.
        block_worker = threading.Event()
        self.coordinator.submit(lambda: block_worker.wait(timeout=5))
        time.sleep(0.05)

        self.coordinator.submit(job)
        self.coordinator.submit(job)

        self.coordinator.pause_barrier()
        block_worker.set()
        time.sleep(0.2)

        self.assertEqual(ran, [], "jobs queued before the barrier must not run after it")

    def test_in_flight_job_callback_is_skipped_after_barrier(self):
        """A job already dequeued (mid-run) when pause_barrier() fires must not
        have its callback delivered, even though the job function itself
        still executes to completion."""
        job_started = threading.Event()
        release_job = threading.Event()
        callback_fired = threading.Event()

        def in_flight_job():
            job_started.set()
            release_job.wait(timeout=5)
            return "stale-result"

        def on_result(job_id, result):
            callback_fired.set()

        self.coordinator.submit(in_flight_job, on_result=on_result)
        self.assertTrue(job_started.wait(timeout=5), "job did not start")

        self.coordinator.pause_barrier()
        release_job.set()

        # Give the worker time to finish the job and attempt the callback.
        fired = callback_fired.wait(timeout=1)
        self.assertFalse(fired, "stale callback must not fire after the barrier")

    def test_resume_allows_new_submissions(self):
        self.coordinator.pause_barrier()
        self.assertIsNone(self.coordinator.submit(lambda: None))

        self.coordinator.resume()

        done = threading.Event()
        job_id = self.coordinator.submit(lambda: None, on_result=lambda jid, r: done.set())
        self.assertIsNotNone(job_id)
        self.assertTrue(done.wait(timeout=5))

    def test_submit_rejected_while_paused(self):
        self.coordinator.pause_barrier()
        self.assertIsNone(self.coordinator.submit(lambda: None))


class TestCallbackDelivery(unittest.TestCase):
    def setUp(self):
        self.coordinator = BackgroundSyncCoordinator(max_queue_size=32)

    def tearDown(self):
        self.coordinator.shutdown(timeout=5)

    def test_on_result_receives_job_id_and_return_value(self):
        received = {}
        done = threading.Event()

        def on_result(job_id, result):
            received["job_id"] = job_id
            received["result"] = result
            done.set()

        job_id = self.coordinator.submit(lambda: "hello", on_result=on_result)

        self.assertTrue(done.wait(timeout=5))
        self.assertEqual(received["job_id"], job_id)
        self.assertEqual(received["result"], "hello")

    def test_on_error_receives_exception_when_job_raises(self):
        received = {}
        done = threading.Event()

        def failing_job():
            raise ValueError("boom")

        def on_error(job_id, exc):
            received["job_id"] = job_id
            received["exc"] = exc
            done.set()

        job_id = self.coordinator.submit(failing_job, on_error=on_error)

        self.assertTrue(done.wait(timeout=5))
        self.assertEqual(received["job_id"], job_id)
        self.assertIsInstance(received["exc"], ValueError)

    def test_worker_survives_job_exception(self):
        """A raising job must not kill the worker thread — subsequent jobs
        must still run."""
        def failing_job():
            raise RuntimeError("boom")

        self.coordinator.submit(failing_job)

        done = threading.Event()
        self.coordinator.submit(lambda: "ok", on_result=lambda jid, r: done.set())

        self.assertTrue(done.wait(timeout=5), "worker did not process job after a prior exception")

    def test_no_callback_required(self):
        """submit() without on_result/on_error must not raise or hang."""
        job_id = self.coordinator.submit(lambda: None)
        self.assertIsNotNone(job_id)
        time.sleep(0.1)  # let it run; nothing to assert beyond "did not crash"


class TestDeterministicShutdown(unittest.TestCase):
    def test_shutdown_joins_worker_thread(self):
        coordinator = BackgroundSyncCoordinator(max_queue_size=8)
        coordinator.submit(lambda: None)
        time.sleep(0.05)

        coordinator.shutdown(timeout=5)

        self.assertTrue(coordinator.is_shutdown())
        self.assertFalse(coordinator._worker.is_alive(), "worker thread must be joined after shutdown")

    def test_shutdown_rejects_new_submissions(self):
        coordinator = BackgroundSyncCoordinator(max_queue_size=8)
        coordinator.shutdown(timeout=5)

        job_id = coordinator.submit(lambda: None)
        self.assertIsNone(job_id, "submit() must reject work after shutdown")

    def test_double_shutdown_is_safe(self):
        coordinator = BackgroundSyncCoordinator(max_queue_size=8)
        coordinator.shutdown(timeout=5)
        coordinator.shutdown(timeout=5)  # must not raise or hang

    def test_shutdown_bounded_even_with_queued_unrun_job(self):
        """A job still sitting in the queue (never dequeued) when shutdown()
        is called must not prevent shutdown from returning promptly."""
        coordinator = BackgroundSyncCoordinator(max_queue_size=8)
        block_worker = threading.Event()

        coordinator.submit(lambda: block_worker.wait(timeout=5))
        time.sleep(0.05)
        coordinator.submit(lambda: None)  # this one stays queued, never runs

        block_worker.set()  # let the in-flight job finish so shutdown can join
        start = time.time()
        coordinator.shutdown(timeout=5)
        elapsed = time.time() - start

        self.assertLess(elapsed, 5.0)
        self.assertTrue(coordinator.is_shutdown())


def main():
    print("=" * 70)
    print("SYNC COORDINATOR TESTS")
    print("=" * 70)
    print()

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFifoOrderAndWorkerReuse))
    suite.addTests(loader.loadTestsFromTestCase(TestQueueFullRejection))
    suite.addTests(loader.loadTestsFromTestCase(TestBarrierInvalidatesStaleResults))
    suite.addTests(loader.loadTestsFromTestCase(TestCallbackDelivery))
    suite.addTests(loader.loadTestsFromTestCase(TestDeterministicShutdown))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
