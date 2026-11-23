#!/usr/bin/env python3
"""
Tests for transient-vs-rejected error classification, batch bisection and
failed-scan recovery (issue #101).

Run: python tests/test_sync_error_classification.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("CLOUD_API_KEY", "test-api-key-for-testing")
os.environ.setdefault("CLOUD_API_URL", "http://test.example.com")
os.environ["CLOUD_READ_ONLY"] = "False"

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from database import DatabaseManager, ScanRecord
from sync import SyncService


class MockResponse:
    def __init__(self, status_code, json_data=None, text="", json_error=False):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self._json_error = json_error
        self.text = text
        self.encoding = "utf-8"
        self.elapsed = Mock()
        self.elapsed.total_seconds.return_value = 0.01

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._json_data


def _make_scan(scan_id, badge_id=None):
    return ScanRecord(
        id=scan_id, badge_id=badge_id or f"B{scan_id}",
        scanned_at="2026-11-24T10:00:00Z", station_name="TestStation",
        employee_full_name=None, legacy_id=None, sl_l1_desc=None,
        position_desc=None, email=None, scan_source="scanner",
        sync_status="pending", synced_at=None, sync_error=None,
    )


class ExplodingDb:
    """Any attribute access fails: proves the network-only path never touches SQLite."""

    def __getattr__(self, name):
        raise AssertionError(f"network-only path touched db.{name}")


def _service():
    return SyncService(db=ExplodingDb(), api_url="http://test.example.com", api_key="k")


def _server_rejecting(bad_badges):
    """Fake requests.post: 400 if any event's badge is bad, else 200 covering the batch."""
    calls = []

    def post(url, json=None, **kwargs):
        events = json["events"]
        calls.append([e["badge_id"] for e in events])
        if any(e["badge_id"] in bad_badges for e in events):
            return MockResponse(400, text="invalid meta")
        return MockResponse(200, {"saved": len(events), "duplicates": 0})

    return post, calls


@patch("sync.time.sleep")
class TestBisection(unittest.TestCase):
    @patch("sync.requests.post")
    def test_one_bad_event_in_ten_fails_only_that_event(self, mock_post, _sleep):
        post, calls = _server_rejecting({"B4"})
        mock_post.side_effect = post
        scans = [_make_scan(i) for i in range(1, 11)]

        result = _service().sync_scan_batch_network_only(scans, "TestStation")

        self.assertEqual(result["failed_ids"], [4])
        self.assertEqual(sorted(result["synced_ids"]), [1, 2, 3, 5, 6, 7, 8, 9, 10])
        self.assertEqual(result["pending_ids"], [])
        self.assertEqual(result["synced_count"], 9)
        self.assertIsNotNone(result["error"])

    @patch("sync.requests.post")
    def test_every_id_lands_in_exactly_one_bucket(self, mock_post, _sleep):
        post, _ = _server_rejecting({"B2", "B9"})
        mock_post.side_effect = post
        scans = [_make_scan(i) for i in range(1, 13)]

        result = _service().sync_scan_batch_network_only(scans, "TestStation")

        buckets = result["synced_ids"] + result["failed_ids"] + result["pending_ids"]
        self.assertEqual(sorted(buckets), list(range(1, 13)))
        self.assertEqual(sorted(result["failed_ids"]), [2, 9])

    @patch("sync.requests.post")
    def test_422_is_bisected_like_400(self, mock_post, _sleep):
        def post(url, json=None, **kwargs):
            events = json["events"]
            if any(e["badge_id"] == "B1" for e in events):
                return MockResponse(422)
            return MockResponse(200, {"saved": len(events), "duplicates": 0})

        mock_post.side_effect = post
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self.assertEqual(result["failed_ids"], [1])
        self.assertEqual(result["synced_ids"], [2])

    @patch("sync.requests.post")
    def test_single_rejected_event_is_failed(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(400)
        result = _service().sync_scan_batch_network_only([_make_scan(7)], "S")
        self.assertEqual(result["failed_ids"], [7])
        self.assertEqual(mock_post.call_count, 1)

    @patch("sync.requests.post")
    def test_transient_error_mid_bisection_leaves_unresolved_pending(self, mock_post, _sleep):
        # Whole batch -> 400; first half -> 200; second half -> 404 (deploy blip).
        responses = [
            MockResponse(400),
            MockResponse(200, {"saved": 2, "duplicates": 0}),
            MockResponse(404),
        ]
        mock_post.side_effect = responses
        scans = [_make_scan(i) for i in range(1, 5)]

        result = _service().sync_scan_batch_network_only(scans, "S")

        self.assertEqual(sorted(result["synced_ids"]), [1, 2])
        self.assertEqual(sorted(result["pending_ids"]), [3, 4])
        self.assertEqual(result["failed_ids"], [])

    @patch("sync.requests.post")
    def test_bisection_budget_keeps_remainder_pending(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(400)  # everything is rejected
        scans = [_make_scan(i) for i in range(1, 101)]

        with patch("sync._MAX_BISECT_REQUESTS", 5):
            result = _service().sync_scan_batch_network_only(scans, "S")

        self.assertEqual(mock_post.call_count, 6)  # 1 initial + 5 budgeted
        buckets = result["synced_ids"] + result["failed_ids"] + result["pending_ids"]
        self.assertEqual(sorted(buckets), list(range(1, 101)))
        self.assertTrue(result["pending_ids"])


@patch("sync.time.sleep")
class TestPayloadTooLarge(unittest.TestCase):
    @patch("sync.requests.post")
    def test_413_batch_is_split_and_halves_succeed(self, mock_post, _sleep):
        def post(url, json=None, **kwargs):
            events = json["events"]
            if len(events) > 5:
                return MockResponse(413)
            return MockResponse(200, {"saved": len(events), "duplicates": 0})

        mock_post.side_effect = post
        scans = [_make_scan(i) for i in range(1, 11)]

        result = _service().sync_scan_batch_network_only(scans, "S")

        self.assertEqual(sorted(result["synced_ids"]), list(range(1, 11)))
        self.assertEqual(result["failed_ids"], [])
        self.assertEqual(result["pending_ids"], [])
        self.assertEqual(result["synced_count"], 10)
        self.assertEqual(mock_post.call_count, 3)

    @patch("sync.requests.post")
    def test_413_for_single_events_is_pending_never_failed(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(413)
        scans = [_make_scan(i) for i in range(1, 5)]

        result = _service().sync_scan_batch_network_only(scans, "S")

        self.assertEqual(sorted(result["pending_ids"]), [1, 2, 3, 4])
        self.assertEqual(result["failed_ids"], [])
        self.assertEqual(result["synced_ids"], [])
        self.assertIsNotNone(result["error"])

    @patch("sync.requests.post")
    def test_413_splitting_respects_budget(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(413)
        scans = [_make_scan(i) for i in range(1, 101)]

        with patch("sync._MAX_BISECT_REQUESTS", 4):
            result = _service().sync_scan_batch_network_only(scans, "S")

        self.assertEqual(mock_post.call_count, 5)
        self.assertEqual(sorted(result["pending_ids"]), list(range(1, 101)))
        self.assertEqual(result["failed_ids"], [])


@patch("sync.time.sleep")
class TestTransientClassification(unittest.TestCase):
    def _assert_all_pending(self, result, ids):
        self.assertEqual(sorted(result["pending_ids"]), ids)
        self.assertEqual(result["failed_ids"], [])
        self.assertEqual(result["synced_ids"], [])
        self.assertIsNotNone(result["error"])

    @patch("sync.requests.post")
    def test_chunked_encoding_error_is_pending(self, mock_post, _sleep):
        mock_post.side_effect = requests.exceptions.ChunkedEncodingError("cut off")
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self._assert_all_pending(result, [1, 2])

    @patch("sync.requests.post")
    def test_generic_request_exception_is_pending(self, mock_post, _sleep):
        mock_post.side_effect = requests.exceptions.RequestException("boom")
        result = _service().sync_scan_batch_network_only([_make_scan(1)], "S")
        self._assert_all_pending(result, [1])

    @patch("sync.requests.post")
    def test_non_rejection_4xx_statuses_are_pending(self, mock_post, _sleep):
        for status in (403, 404, 408):
            with self.subTest(status=status):
                mock_post.reset_mock()
                mock_post.return_value = MockResponse(status)
                result = _service().sync_scan_batch_network_only(
                    [_make_scan(1), _make_scan(2)], "S"
                )
                self._assert_all_pending(result, [1, 2])
                self.assertEqual(mock_post.call_count, 1)  # no bisection for these

    @patch("sync.requests.post")
    def test_200_with_non_json_body_is_pending(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(200, text="<html>captive portal</html>", json_error=True)
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self._assert_all_pending(result, [1, 2])

    @patch("sync.requests.post")
    def test_200_with_empty_object_body_leaves_everything_pending(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(200, {})
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self._assert_all_pending(result, [1, 2])
        self.assertEqual(result["synced_count"], 0)

    @patch("sync.requests.post")
    def test_200_with_json_that_is_not_an_object_is_pending(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(200, json_data=["nope"])
        result = _service().sync_scan_batch_network_only([_make_scan(1)], "S")
        self._assert_all_pending(result, [1])

    @patch("sync.requests.post")
    def test_200_whose_counts_do_not_cover_batch_is_pending(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(200, {"saved": 1, "duplicates": 0})
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self._assert_all_pending(result, [1, 2])

    @patch("sync.requests.post")
    def test_duplicates_count_toward_coverage(self, mock_post, _sleep):
        mock_post.return_value = MockResponse(200, {"saved": 1, "duplicates": 1})
        result = _service().sync_scan_batch_network_only([_make_scan(1), _make_scan(2)], "S")
        self.assertEqual(sorted(result["synced_ids"]), [1, 2])
        self.assertEqual(result["synced_count"], 2)

    @patch("sync.requests.post")
    def test_other_request_exception_is_not_retried_but_timeout_is(self, mock_post, _sleep):
        mock_post.side_effect = requests.exceptions.ChunkedEncodingError("x")
        _service().sync_scan_batch_network_only([_make_scan(1)], "S")
        self.assertEqual(mock_post.call_count, 1)

        mock_post.reset_mock()
        mock_post.side_effect = requests.exceptions.Timeout("slow")
        result = _service().sync_scan_batch_network_only([_make_scan(1)], "S")
        self.assertGreater(mock_post.call_count, 1)
        self.assertEqual(result["pending_ids"], [1])


class TestRequeueFailedScans(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db = DatabaseManager(Path(self.temp_dir) / "test.db")
        self.db.set_station_name("TestStation")

    def tearDown(self):
        self.db.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_failed_scans_become_pending_and_synced_are_untouched(self):
        conn = self.db._connection
        for i, status in enumerate(["failed", "failed", "synced", "pending"], start=1):
            with conn:
                conn.execute(
                    "INSERT INTO scans (badge_id, scanned_at, station_name, sync_status) "
                    "VALUES (?, ?, ?, ?)",
                    (f"B{i}", "2026-11-24T10:00:00Z", "TestStation", status),
                )

        count = self.db.requeue_failed_scans()

        self.assertEqual(count, 2)
        stats = self.db.get_sync_statistics()
        self.assertEqual((stats["pending"], stats["synced"], stats["failed"]), (3, 1, 0))
        self.assertEqual(self.db.requeue_failed_scans(), 0)


if __name__ == "__main__":
    unittest.main()
