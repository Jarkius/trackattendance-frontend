#!/usr/bin/env python3
"""
Performance test for Live Sync (#54) — measures API latency under load.

NOTE: All requests come from a single IP, hitting the 60/min rate limit.
In production, 20 stations have separate IPs (each well under the limit).
Tests account for this by:
  - Pacing requests to stay under rate limit where possible
  - Separating 429 (rate limit) from real errors
  - Using smaller concurrent batches with pauses between tests

Tests:
  1. Single-request latency baseline (10 sequential requests)
  2. Concurrent dup checks (burst of 20, simulates worst-case simultaneous scan)
  3. Concurrent single-scan syncs (burst of 20)
  4. Mixed workload: dup check + sync per station (sequential, paced)

Usage:
  python tests/perf_live_sync.py [--url URL] [--key KEY]
"""

import argparse
import os
import sys
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

import requests


STATIONS = 20
PASS_THRESHOLD_MS = 200   # Per-request latency ceiling (sequential / real per-station)
P95_CONCURRENT_MS = 600   # p95 for concurrent burst from single IP (client-side contention)
                          # In production each station has its own IP, so real p95 ≈ sequential
RATE_LIMIT_PAUSE = 62     # Seconds to wait when we've exhausted the rate limit window


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def _stats(latencies: list[float]) -> dict:
    if not latencies:
        return {"count": 0, "min_ms": 0, "max_ms": 0, "avg_ms": 0,
                "median_ms": 0, "p95_ms": 0, "p99_ms": 0}
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    return {
        "count": n,
        "min_ms": _ms(min(sorted_lat)),
        "max_ms": _ms(max(sorted_lat)),
        "avg_ms": _ms(statistics.mean(sorted_lat)),
        "median_ms": _ms(statistics.median(sorted_lat)),
        "p95_ms": _ms(sorted_lat[int(n * 0.95)] if n >= 20 else max(sorted_lat)),
        "p99_ms": _ms(sorted_lat[int(n * 0.99)] if n >= 100 else max(sorted_lat)),
    }


def check_duplicate(api_url: str, api_key: str, badge_id: str, station: str) -> tuple[float, int, dict]:
    """Single dup check request. Returns (latency_sec, status_code, body)."""
    start = time.perf_counter()
    resp = requests.get(
        f"{api_url}/v1/scans/check-duplicate",
        params={"badge_id": badge_id, "window_minutes": "5", "exclude_station": station},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=5.0,
    )
    elapsed = time.perf_counter() - start
    try:
        body = resp.json()
    except Exception:
        body = {}
    return elapsed, resp.status_code, body


def sync_single(api_url: str, api_key: str, badge_id: str, station: str) -> tuple[float, int]:
    """Single scan sync via batch endpoint. Returns (latency_sec, status_code)."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "events": [{
            "idempotency_key": f"perf-test-{station}-{badge_id}-{int(time.time()*1000)}",
            "badge_id": badge_id,
            "station_name": station,
            "scanned_at": now,
            "business_unit": "PerfTest",
            "scan_source": "perf_test",
        }]
    }
    start = time.perf_counter()
    resp = requests.post(
        f"{api_url}/v1/scans/batch",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=5.0,
    )
    elapsed = time.perf_counter() - start
    return elapsed, resp.status_code


def wait_for_rate_limit_reset():
    """Wait for rate limit window to reset."""
    print(f"\n  ⏳ Waiting {RATE_LIMIT_PAUSE}s for rate limit reset...")
    time.sleep(RATE_LIMIT_PAUSE)


def test_warmup(api_url: str, api_key: str) -> bool:
    """Warm up Cloud Run instance."""
    print("\n🔥 Warming up Cloud Run...")
    for i in range(3):
        try:
            lat, status, _ = check_duplicate(api_url, api_key, "WARMUP", "WarmupStation")
            print(f"  Warmup {i+1}: {_ms(lat)}ms (HTTP {status})")
            if status == 429:
                wait_for_rate_limit_reset()
                continue
            if status != 200:
                print(f"  ⚠️  Non-200 response — check API key / endpoint")
                return False
        except Exception as e:
            print(f"  ❌ Warmup failed: {e}")
            return False
    return True


def test_1_single_latency(api_url: str, api_key: str) -> bool:
    """Test 1: Single request latency baseline (sequential, 10 requests)."""
    print("\n━━━ Test 1: Single Request Latency (10 sequential) ━━━")
    latencies = []
    for i in range(10):
        lat, status, body = check_duplicate(api_url, api_key, f"PERF-SINGLE-{i}", "Station-1")
        if status == 429:
            print(f"  Request {i+1:2d}: RATE LIMITED — skipping")
            continue
        latencies.append(lat)
        dup = body.get("duplicate", "?")
        print(f"  Request {i+1:2d}: {_ms(lat):6.1f}ms  HTTP {status}  dup={dup}")

    if len(latencies) < 5:
        print("  ⚠️  Too many rate limits — cannot measure reliably")
        return False

    s = _stats(latencies)
    print(f"\n  Summary: avg={s['avg_ms']}ms  median={s['median_ms']}ms  max={s['max_ms']}ms")
    ok = s["max_ms"] < PASS_THRESHOLD_MS
    print(f"  {'✅ PASS' if ok else '❌ FAIL'}: max {s['max_ms']}ms {'<' if ok else '>='} {PASS_THRESHOLD_MS}ms threshold")
    return ok


def test_2_concurrent_dup_check(api_url: str, api_key: str) -> bool:
    """Test 2: 20 stations doing concurrent dup checks (single burst).

    This measures the key scenario: all 20 stations happen to scan at the
    exact same moment. In production each station has its own IP so no rate
    limiting applies. Here we fire 20 from one IP — 429s are expected and
    excluded from latency measurement.
    """
    print(f"\n━━━ Test 2: {STATIONS} Concurrent Dup Checks (single burst) ━━━")
    latencies = []
    errors = 0
    rate_limited = 0

    with ThreadPoolExecutor(max_workers=STATIONS) as pool:
        futures = {
            pool.submit(check_duplicate, api_url, api_key, f"PERF-CONC-{i}", f"Station-{i+1}"): i
            for i in range(STATIONS)
        }
        for fut in as_completed(futures):
            station_idx = futures[fut]
            try:
                lat, status, body = fut.result()
                if status == 429:
                    rate_limited += 1
                elif status == 200:
                    latencies.append(lat)
                else:
                    errors += 1
                    print(f"  Station-{station_idx+1}: HTTP {status}")
            except Exception as e:
                errors += 1
                print(f"  Station-{station_idx+1}: ERROR {e}")

    if not latencies:
        print("  ⚠️  All requests rate-limited — cannot measure")
        return False

    s = _stats(latencies)
    print(f"  {len(latencies)} successful / {rate_limited} rate-limited / {errors} errors")
    print(f"  Latency: avg={s['avg_ms']}ms  p95={s['p95_ms']}ms  max={s['max_ms']}ms")
    if rate_limited > 0:
        print(f"  ℹ️  {rate_limited} rate-limited (429) — expected from single IP, won't happen in production")
    ok = s["p95_ms"] < P95_CONCURRENT_MS and errors == 0
    print(f"  {'✅ PASS' if ok else '❌ FAIL'}: p95={s['p95_ms']}ms {'<' if s['p95_ms'] < P95_CONCURRENT_MS else '>='} {P95_CONCURRENT_MS}ms (concurrent/single-IP), real errors={errors}")
    return ok


def test_3_concurrent_sync(api_url: str, api_key: str) -> bool:
    """Test 3: 20 stations syncing a single scan concurrently."""
    print(f"\n━━━ Test 3: {STATIONS} Concurrent Single-Scan Syncs ━━━")
    latencies = []
    errors = 0
    rate_limited = 0

    with ThreadPoolExecutor(max_workers=STATIONS) as pool:
        futures = {
            pool.submit(sync_single, api_url, api_key, f"PERF-SYNC-{i}", f"Station-{i+1}"): i
            for i in range(STATIONS)
        }
        for fut in as_completed(futures):
            station_idx = futures[fut]
            try:
                lat, status = fut.result()
                if status == 429:
                    rate_limited += 1
                elif status == 200:
                    latencies.append(lat)
                else:
                    errors += 1
                    print(f"  Station-{station_idx+1}: HTTP {status}")
            except Exception as e:
                errors += 1
                print(f"  Station-{station_idx+1}: ERROR {e}")

    if not latencies:
        print("  ⚠️  All requests rate-limited — cannot measure")
        return False

    s = _stats(latencies)
    print(f"  {len(latencies)} successful / {rate_limited} rate-limited / {errors} errors")
    print(f"  Latency: avg={s['avg_ms']}ms  p95={s['p95_ms']}ms  max={s['max_ms']}ms")
    if rate_limited > 0:
        print(f"  ℹ️  {rate_limited} rate-limited (429) — expected from single IP")
    ok = s["p95_ms"] < P95_CONCURRENT_MS and errors == 0
    print(f"  {'✅ PASS' if ok else '❌ FAIL'}: p95={s['p95_ms']}ms {'<' if s['p95_ms'] < P95_CONCURRENT_MS else '>='} {P95_CONCURRENT_MS}ms (concurrent/single-IP), real errors={errors}")
    return ok


def test_4_paced_mixed(api_url: str, api_key: str) -> bool:
    """Test 4: Paced mixed workload — dup check + sync, one station at a time.

    Simulates realistic per-station flow (check dup, then sync) at a rate
    that stays within the single-IP rate limit.
    """
    count = min(STATIONS, 10)  # 10 stations × 2 ops = 20 requests, under rate limit
    print(f"\n━━━ Test 4: Paced Mixed Workload ({count} stations, sequential) ━━━")

    # Warm connection after rate-limit pause
    check_duplicate(api_url, api_key, "PERF-MIX-WARM", "Warmup")
    print("  (connection warmed)")
    dup_latencies = []
    sync_latencies = []
    errors = 0

    for i in range(count):
        badge = f"PERF-MIX-{i}"
        station = f"Station-{i+1}"

        lat1, s1, _ = check_duplicate(api_url, api_key, badge, station)
        if s1 == 429:
            print(f"  Station-{i+1}: rate limited on dup check — stopping")
            break
        if s1 == 200:
            dup_latencies.append(lat1)
        else:
            errors += 1

        lat2, s2 = sync_single(api_url, api_key, badge, station)
        if s2 == 429:
            print(f"  Station-{i+1}: rate limited on sync — stopping")
            break
        if s2 == 200:
            sync_latencies.append(lat2)
        else:
            errors += 1

        print(f"  Station-{i+1:2d}: dup={_ms(lat1):5.1f}ms  sync={_ms(lat2):5.1f}ms  "
              f"total={_ms(lat1+lat2):5.1f}ms")

    if not dup_latencies or not sync_latencies:
        print("  ⚠️  Rate limited — cannot measure")
        return False

    ds = _stats(dup_latencies)
    ss = _stats(sync_latencies)
    combined = [d + s for d, s in zip(dup_latencies, sync_latencies)]
    cs = _stats(combined)

    print(f"\n  Dup checks:  avg={ds['avg_ms']}ms  max={ds['max_ms']}ms")
    print(f"  Syncs:       avg={ss['avg_ms']}ms  max={ss['max_ms']}ms")
    print(f"  Combined:    avg={cs['avg_ms']}ms  max={cs['max_ms']}ms (dup+sync per scan)")
    print(f"  Errors: {errors}")

    # Combined dup+sync should be under 400ms (2 × 200ms threshold)
    combined_threshold = PASS_THRESHOLD_MS * 2
    ok = cs["max_ms"] < combined_threshold and errors == 0
    print(f"  {'✅ PASS' if ok else '❌ FAIL'}: combined max {cs['max_ms']}ms {'<' if cs['max_ms'] < combined_threshold else '>='} {combined_threshold}ms")
    return ok


def main():
    parser = argparse.ArgumentParser(description="Live Sync performance test")
    parser.add_argument("--url", default=os.getenv("CLOUD_API_URL", ""), help="API base URL")
    parser.add_argument("--key", default=os.getenv("CLOUD_API_KEY", ""), help="API key")
    args = parser.parse_args()

    if not args.url or not args.key:
        print("❌ Set CLOUD_API_URL and CLOUD_API_KEY in .env or pass --url/--key")
        sys.exit(1)

    print(f"🎯 Live Sync Performance Test (#54)")
    print(f"   API: {args.url}")
    print(f"   Simulated stations: {STATIONS}")
    print(f"   Latency threshold: <{PASS_THRESHOLD_MS}ms sequential, <{P95_CONCURRENT_MS}ms concurrent burst")
    print(f"   ℹ️  Rate limit (60/min) applies to single-IP tests only.")
    print(f"      In production, each station has its own IP.")

    if not test_warmup(args.url, args.key):
        print("\n❌ Warmup failed — cannot proceed")
        sys.exit(1)

    results = {}
    results["1_single_latency"] = test_1_single_latency(args.url, args.key)

    # Pause before concurrent tests to maximize rate budget
    print("\n  ⏳ Brief pause before concurrent tests...")
    time.sleep(3)

    results["2_concurrent_dup"] = test_2_concurrent_dup_check(args.url, args.key)

    # Wait for rate limit reset before next concurrent test
    wait_for_rate_limit_reset()

    results["3_concurrent_sync"] = test_3_concurrent_sync(args.url, args.key)

    # Wait again, then do paced mixed test
    wait_for_rate_limit_reset()

    results["4_paced_mixed"] = test_4_paced_mixed(args.url, args.key)

    print("\n" + "=" * 55)
    print("📊 RESULTS")
    print("=" * 55)
    all_pass = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("✅ ALL TESTS PASSED — API latency is well within bounds for 20 stations.")
        print("   Cloud Run + PostgreSQL handles Live Sync load without slowdown.")
    else:
        print("❌ SOME TESTS FAILED — review latency numbers above.")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
