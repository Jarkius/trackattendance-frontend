# Update TypeScript Types Before Runtime Code

**Date**: 2026-03-01
**Context**: trackattendance API — scan_source field addition broke CI
**Confidence**: High

## Key Learning

When adding a new field to a TypeScript API, always update the type/interface definition first, then add the runtime code. The reverse order (code first, types later) reliably leads to CI failures because the type checker runs before runtime, and a missing field in the interface is an instant compile error.

In this session, I added `scan_source` to the INSERT query, the array builder, and the export mapping — but forgot to add it to the `ScanInput` type definition. The CI type check caught it, but the fix required an extra commit-push-deploy cycle (~5 minutes wasted).

The fix is simple: make the interface update the FIRST edit, not the last. Types are documentation — if the type doesn't declare a field, that field doesn't officially exist in the API contract.

## The Pattern

```typescript
// Step 1: FIRST — update the type
type ScanInput = {
  idempotency_key: string;
  badge_id: string;
  station_name: string;
  scanned_at: string;
  meta?: Record<string, any> | null;
  business_unit?: string | null;
  scan_source?: string;           // ADD THIS FIRST
};

// Step 2: THEN — add runtime code
scanSources.push(ev.scan_source ?? "badge");
```

## Why This Matters

TypeScript's value is in catching errors before deployment. But that only works if types are kept in sync with runtime code. Making type updates the first step (not an afterthought) ensures the compiler guides you through all the places the new field needs to be handled, rather than discovering them through CI failures.

## Tags

`typescript`, `types`, `api`, `ci-cd`, `workflow`, `trackattendance`
