# Explicit Schema Over Clever Storage

**Date**: 2026-03-01
**Context**: trackattendance scan_source field — Postgres column vs jsonb meta
**Confidence**: High

## Key Learning

When adding a new field that will be queried, displayed, or exported, prefer a proper database column over nesting it in a jsonb/meta field. The initial instinct to avoid schema migrations by stuffing data into existing jsonb columns creates hidden complexity that compounds over time.

In this case, `scan_source` (badge vs manual_lookup) was initially placed in the `meta` jsonb field to avoid an ALTER TABLE migration. The user correctly pushed back — every query touching scan_source would need `meta->>'scan_source'` instead of a simple column reference, every export would need special extraction logic, and anyone reading the schema wouldn't know the field existed without inspecting jsonb contents.

The proper column approach required one ALTER TABLE statement and a TypeScript type update. The jsonb approach would have required ongoing cognitive overhead in every query, export, and dashboard that touches the field.

## The Pattern

```
# Bad: Hidden in jsonb
SELECT meta->>'scan_source' as scan_source FROM scans

# Good: Proper column
SELECT scan_source FROM scans

# Migration is a one-time cost:
ALTER TABLE scans ADD COLUMN IF NOT EXISTS scan_source TEXT NOT NULL DEFAULT 'badge'
```

## Why This Matters

Schema migrations are a one-time cost. Cognitive overhead of remembering hidden fields is an ongoing cost paid by every developer, every query, and every debugging session. Choose the approach that makes the common case simple, not the one that avoids a single migration.

## Tags

`database`, `schema-design`, `postgres`, `jsonb`, `simplicity`, `trackattendance`
