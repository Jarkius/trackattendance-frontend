# Parallel Agents for Code Hardening at Scale

**Date**: 2026-02-02
**Context**: TrackAttendance Frontend — 60-issue code assessment and 14-fix implementation
**Confidence**: High

## Key Learning

When applying many independent fixes to a codebase, splitting them into phases by priority and running each phase as a separate parallel agent eliminates merge conflicts and maximizes throughput. In this session, 3 agents applied 14 fixes across 9 files simultaneously with zero conflicts — because each phase touched different concerns (security vs bugs vs cleanup).

The assessment-to-fix pipeline that worked: (1) Launch explore agents to find issues, (2) Categorize by severity into phases, (3) Ensure each phase touches mostly different files, (4) Launch one agent per phase with detailed instructions, (5) Commit everything together.

A critical insight: 401 Unauthorized should always be a permanent error in sync services. Retrying bad credentials with exponential backoff wastes 35 seconds and confuses users. The correct behavior is fail fast, report clearly, let the user fix the API key.

For cache invalidation on local files (like Excel roster imports), SHA256 hashing is the simplest correct solution. Store the hash in DB on import, compare on startup. No file watchers, no polling, no timestamp checks (which break on copy/move). If hash matches, skip. If not, clear and reimport.

## The Pattern

```
# Assessment pipeline
1. Explore agents (2 parallel) → find issues
2. Categorize: Critical > High > Moderate
3. Plan agents → design fixes per phase
4. Implementation agents (3 parallel) → apply fixes
5. Single commit with phase breakdown

# Cache invalidation
stored_hash = db.get_file_hash()
current_hash = sha256(file)
if stored_hash == current_hash:
    skip_reimport()
else:
    clear_old_data()
    reimport()
    db.set_file_hash(current_hash)
```

## Why This Matters

Code assessments often find dozens of issues but implementation stalls because fixes are applied sequentially. Parallel agents turn a multi-hour fix session into a 15-minute batch operation. The key constraint is ensuring each agent's file set doesn't overlap — which naturally happens when fixes are categorized by concern (security, correctness, cleanup).

## Tags

`parallel-agents`, `code-assessment`, `security-hardening`, `cache-invalidation`, `sync-patterns`, `error-handling`
