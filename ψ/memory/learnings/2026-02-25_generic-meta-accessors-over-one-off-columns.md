# Generic Meta Accessors Over One-Off Columns

**Date**: 2026-02-25
**Project**: trackattendance-frontend
**Context**: Adding mtime caching to roster import optimization

## Pattern

When a table already stores key-value pairs (like `roster_meta` with `key`/`value` columns), expose generic `get_meta(key)` / `set_meta(key, value)` accessors rather than adding new one-off methods for each key. Existing specific methods (`get_roster_hash`) become thin wrappers.

## Why

- Avoids method proliferation as new metadata keys are added
- The SQL is identical regardless of key — parameterized queries handle it
- Keeps the database layer DRY while preserving type-specific convenience methods

## Also Learned

When adding a cache layer (like mtime-before-hash), verify both the read path AND the write path. The original change checked mtime on read but forgot to save it after a successful import, meaning the cache would never populate.
