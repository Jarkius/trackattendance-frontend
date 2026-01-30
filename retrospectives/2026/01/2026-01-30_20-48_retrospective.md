# Session Retrospective

**Session Date**: 2026-01-30
**Start Time**: ~20:00 GMT+7 (~13:00 UTC)
**End Time**: 20:48 GMT+7 (13:48 UTC)
**Duration**: ~48 minutes
**Primary Focus**: API sync connection issue diagnosis and .env key alignment
**Session Type**: Bug Fix / Investigation
**Current Issue**: N/A (ad-hoc troubleshooting)
**Last Commit**: ed05489

## Session Summary

Investigated API connection failure when clicking the sync button. Traced the issue to an API key mismatch between the Python client `.env` (hex key) and the Cloud Run deployed service (service account email). Aligned all `.env` files across three locations and rebuilt the `.exe`. Confirmed the external `dist\.env` takes priority over bundled `.env` as designed.

## Timeline

- 20:00 - User reported sync button connection issues, API root returning OK
- 20:05 - Explored sync.py, config.py, .env, and Node.js server code in parallel
- 20:10 - Identified API key mismatch: client had hex key, Cloud Run had service account email
- 20:15 - User confirmed they had updated .env, re-read both .env files
- 20:20 - Verified Cloud Run env vars via gcloud CLI - confirmed service account email as API_KEY
- 20:25 - Updated Python client .env to service account email
- 20:28 - Updated local Node.js server .env to match
- 20:30 - Rebuilt .exe with pyinstaller using spec file
- 20:35 - Tested API auth via Python requests - HTTP 200 confirmed
- 20:38 - User confirmed dist\.env already had correct key and .exe was working
- 20:40 - Discussed root cause: running `python main.py` used project root .env with wrong key
- 20:42 - User verified external .env override by toggling DEBUG flag
- 20:45 - Committed and pushed settings/build changes
- 20:48 - Created retrospective

## Technical Details

### Files Modified
```
.claude/settings.local.json
Build.txt
```

### Configuration Changes (not committed - .env files are gitignored)
- `C:\Workspace\Dev\Python\QR\.env` - Changed CLOUD_API_KEY from hex to service account email
- `C:\Workspace\Dev\NodeJS\trackattendance-api\.env` - Changed API_KEY from hex to service account email

### Key Code Paths Investigated
- `sync.py:96-132` - Authentication test sends `Bearer {api_key}` to `/v1/scans/batch`
- `config.py:20-33` - .env loading priority: exe directory first, then script directory
- `server.ts:52-63` - Auth middleware: simple string comparison of Bearer token vs API_KEY
- `TrackAttendance.spec:13` - `.env` bundled into exe via `datas=[('.env', '.')]`

### Architecture Decisions
- Confirmed external `.env` next to `.exe` takes priority over bundled `.env` - good for deployment flexibility
- No code changes needed - the issue was purely configuration (key mismatch)

## AI Diary (REQUIRED - DO NOT SKIP)

This session was an interesting debugging exercise. When the user reported sync failing with the API root returning OK, the immediate suspicion was authentication - since the root health check bypasses auth but `/v1/scans/batch` requires it.

I explored both the Python client and Node.js server code in parallel, which quickly revealed the key mismatch. The Python `.env` had a service account email while the local server `.env` had a hex key. My initial analysis concluded the service account email was wrong (since it looks like a GCP identity, not an API key). But the user clarified this was a deliberate security enhancement.

The key insight came from running `gcloud run services describe` - the Cloud Run deployment used the service account email, not the hex key. The local server `.env` was simply out of date.

What surprised me was when the user pointed out that `dist\.env` already had the correct key. This meant the `.exe` should have been working fine all along when run from `dist\`. The actual failure was from running `python main.py` which reads the project root `.env`. I had been chasing a more complex explanation when the answer was simpler.

The user's test of toggling DEBUG in `dist\.env` to verify the external override was a smart validation step - confirming the config loading priority works as designed without needing to trace code.

## What Went Well

- Parallel exploration of client and server code quickly identified the key mismatch
- Using `gcloud run services describe` definitively showed the deployed API_KEY value
- Python `requests` test confirmed auth worked with the correct key
- User's systematic approach (testing from dist\.env, toggling DEBUG) validated the fix

## What Could Improve

- Should have checked Cloud Run env vars earlier instead of assuming the local server `.env` was the source of truth
- Over-complicated the root cause analysis - the simple explanation (wrong .env being read) was correct
- Could have asked earlier whether user was running `python main.py` or the `.exe`

## Blockers & Resolutions

- **Blocker**: curl failed from dev environment (exit code 35 - SSL issue)
  **Resolution**: Used Python `requests` library instead to test API auth

- **Blocker**: Couldn't determine which .env was being used at runtime
  **Resolution**: User toggled DEBUG flag in dist\.env to confirm external override

## Honest Feedback (REQUIRED - DO NOT SKIP)

This session was efficient for investigation but I initially overcomplicated the root cause. I built a narrative about "stale .exe builds" when the real issue was simply running `python main.py` with the wrong project root `.env`. The user's practical testing approach (checking dist\.env, toggling DEBUG) was more effective than my theoretical analysis.

The `gcloud` CLI command was the turning point - it eliminated ambiguity about what Cloud Run was actually using. I should default to checking deployed state first rather than comparing local files.

One frustration: curl not working from this environment meant I couldn't directly test the API. The Python fallback worked but added an extra step.

The session was productive overall - all .env files are now aligned, the .exe is rebuilt, and we confirmed the config loading priority works correctly.

## Lessons Learned

- **Pattern**: Always check deployed env vars (`gcloud run services describe`) when debugging API auth - local `.env` files may be stale
- **Pattern**: Ask "where are you running from?" early when debugging config issues - `python main.py` vs `.exe` read different `.env` files
- **Anti-Pattern**: Don't assume the most complex explanation is correct - the simplest one (wrong .env) was right
- **Discovery**: External `.env` next to `.exe` reliably overrides bundled `.env` - confirmed by user's DEBUG toggle test

## Next Steps

- [ ] Consider adding startup log line showing which `.env` file was loaded and the API key prefix (first 4 chars) for easier debugging
- [ ] Plan BU total employee count feature for dashboard (user's next request)
- [ ] Evaluate stronger API key security (random 256-bit key or GCP IAM auth)

## Related Resources

- Commit: ed05489
- Cloud Run service: trackattendance-api (asia-southeast1)

## Retrospective Validation Checklist

- [x] AI Diary section has detailed narrative (not placeholder)
- [x] Honest Feedback section has frank assessment (not placeholder)
- [x] Session Summary is clear and concise
- [x] Timeline includes actual times and events
- [x] Technical Details are accurate
- [x] Lessons Learned has actionable insights
- [x] Next Steps are specific and achievable
