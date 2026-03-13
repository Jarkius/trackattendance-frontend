# load_dotenv Leaks .env Values Into Test Environment

**Date**: 2026-03-13
**Context**: TrackAttendance — 23 sync tests failing because CLOUD_READ_ONLY=true from .env leaked into tests
**Confidence**: High

## Key Learning

When a Python project uses `python-dotenv` with `load_dotenv()` in a config module that runs at import time, the `.env` file's values are loaded into `os.environ` before test setup code runs. This means `os.environ.setdefault(key, value)` in test files will NOT override values that `.env` has already set, because the key already exists in the environment.

The fix is to use `os.environ[key] = value` (force-set) instead of `setdefault` in test setup sections that run before config import. This ensures the test value wins regardless of what `.env` contains.

In our case, `.env` had `CLOUD_READ_ONLY=true` (set during a monitoring-mode event session). The config module's `load_dotenv()` loaded this into `os.environ` at import time, and all sync operations (`sync_pending_scans`, `send_heartbeat`) checked this flag and bailed out silently — causing 23 test failures across 4 test files.

## The Pattern

```python
# BAD — setdefault won't override values loaded by load_dotenv()
os.environ.setdefault("CLOUD_READ_ONLY", "False")  # No-op if .env already set it

# GOOD — force-set always wins
os.environ["CLOUD_READ_ONLY"] = "False"  # Overrides .env value

# Also needed in patch.dict when config is reloaded mid-test
with patch.dict('os.environ', {
    'CLOUD_READ_ONLY': 'False',  # Must include here too
    'OTHER_CONFIG': 'value',
}):
    importlib.reload(config)  # Picks up patched values
```

## Why This Matters

- Production `.env` files commonly have flags like read-only mode, monitoring mode, or debug settings that differ from test expectations
- `setdefault` is the "safe" choice for setting defaults but fails silently when `load_dotenv()` has pre-populated the key
- Tests that pass in CI (no `.env` file) but fail locally (`.env` present) are a common symptom of this issue
- The failure is silent — sync operations return early with no error, tests just get wrong results

## Tags

`testing`, `python`, `dotenv`, `environment`, `debugging`, `silent-failure`
