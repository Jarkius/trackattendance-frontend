# Performance Testing Against Rate-Limited APIs

**Date**: 2026-03-13
**Context**: TrackAttendance Live Sync perf test — 20 stations simulated from single IP against 60/min rate limit
**Confidence**: High

## Key Learning

When performance-testing a distributed system from a single machine, the test infrastructure itself introduces constraints that don't exist in production. The TrackAttendance API has a 60/min rate limit per IP. In production, 20 stations each have their own IP (effectively 60/min × 20 = 1200/min total capacity). But from a single test machine, all 200 requests in a burst test hit the same rate limit bucket.

The first test version treated all non-200 responses as failures, causing every test beyond the first to fail. The fix was threefold: (1) separate HTTP 429 (rate limit) from real errors — they have completely different implications; (2) add rate-limit-aware pauses between test phases; (3) set different latency thresholds for concurrent-from-single-IP (connection contention) vs sequential (realistic per-station).

A related discovery: after a 60+ second pause for rate limit reset, the first request takes 3-4x longer than steady-state due to TCP connection re-establishment. Adding a warmup request before measurement eliminates this artifact.

## The Pattern

```python
# BAD: treats rate limiting as failure
if status != 200:
    errors += 1

# GOOD: separates rate limiting from real errors
if status == 429:
    rate_limited += 1  # expected from single-IP test
elif status == 200:
    latencies.append(lat)
else:
    errors += 1  # real error

# Report both clearly
print(f"{len(latencies)} successful / {rate_limited} rate-limited / {errors} errors")
if rate_limited > 0:
    print("Rate-limited requests expected from single IP, won't happen in production")
```

## Why This Matters

Performance tests that conflate infrastructure limitations with system performance give false negatives, leading teams to either (a) waste time optimizing things that aren't problems, or (b) lose trust in the test suite and skip perf testing entirely. Honest measurement requires understanding what you're actually testing.

Also applies to: connection pool exhaustion from single client, DNS caching differences, TLS handshake overhead in burst tests, etc.

## Tags

`performance-testing`, `rate-limiting`, `distributed-systems`, `test-design`, `cloud-run`, `single-ip-testing`
