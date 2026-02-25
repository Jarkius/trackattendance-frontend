---
title: When a table already stores key-value pairs, expose generic get_meta(key)/set_me
tags: [database, caching, DRY, meta-accessors, startup-optimization]
created: 2026-02-25
source: rrr: trackattendance-frontend
---

# When a table already stores key-value pairs, expose generic get_meta(key)/set_me

When a table already stores key-value pairs, expose generic get_meta(key)/set_meta(key, value) accessors rather than adding one-off methods per key. Existing specific methods become thin wrappers. Also: when adding a cache layer (e.g. mtime-before-hash), always verify both the read AND write paths are covered — a cache that's checked but never populated is a silent bug.

---
*Added via Oracle Learn*
