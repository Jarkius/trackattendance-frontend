---
name: system-review
description: Review a substantive code diff for correctness, security, maintainability, architectural consistency, and recurring agent-generated anti-patterns. Use during PR review or before merging high-impact changes.
---

# System Review

## Mission

Find material defects in the current change and identify systemic improvements only when evidence supports them. Keep review focused on the diff and its consequences.

## 1. Establish review scope

Inspect the base/head diff, changed files, surrounding implementation, relevant tests, project rules, and applicable ADRs. Understand the intended behavior before judging the implementation.

Separate:
- New defects introduced by the change.
- Existing defects exposed by the change.
- Pre-existing technical debt.
- Optional improvements unrelated to the requested change.

Do not expand a focused review into a general rewrite.

## 2. Review by risk

Prioritize:

1. **Correctness and data integrity:** incorrect state transitions, race conditions, transaction boundaries, duplicate handling, migrations, retries, and data loss.
2. **Security and privacy:** authorization gaps, injection, secret exposure, unsafe deserialization, trust-boundary validation, and sensitive logging.
3. **Contracts and compatibility:** API/schema changes, type mismatches, nullability, error semantics, and backward compatibility.
4. **Reliability and performance:** failure handling, resource leaks, unbounded work, N+1 queries, caching, and observability.
5. **Maintainability:** unnecessary coupling, duplicated logic, unclear ownership, and abstractions that increase complexity.
6. **Tests and documentation:** missing meaningful coverage, misleading examples, stale docs, and comments that contradict behavior.

## 3. Contextual anti-pattern radar

Investigate rather than automatically reject:
- `any`, type assertions, non-null assertions, and unsafe casts.
- Raw strings for routes, events, query parameters, and API contracts.
- Untyped network boundaries.
- Duplicated low-level helpers.
- Redundant, stale, or misleading comments.
- Comments that preserve constraints better enforced by types or tests.
- Patterns copied from outdated documentation.

A construct is a finding only when it creates a concrete risk, violates an established project rule, or makes the code materially harder to maintain. TypeScript intersections and assertions are not inherently defects; assess their use and boundary validation.

## 4. Classify findings

Use:
- **Critical:** exploitable security issue, data corruption/loss, or severe production failure.
- **High:** functional defect, authorization failure, broken contract, or serious reliability issue.
- **Medium:** meaningful maintainability, performance, or test gap.
- **Low:** minor clarity or consistency improvement.

Each finding must include:
- Severity.
- File and line reference.
- Concrete failure scenario.
- Why it matters.
- Recommended fix.

Do not report speculative issues as confirmed defects. State uncertainty and the evidence needed.

## 5. Separate patch from systemic improvement

For each issue, decide:
- **Immediate patch:** fix the current defect.
- **Systemic improvement:** add a helper, type, test, lint rule, documentation correction, or incremental ratchet.

Recommend a permanent guardrail only when recurrence, broad impact, or high risk justifies its maintenance cost. One isolated mistake usually warrants a focused fix, not a new abstraction or lint rule.

Prefer incremental ratchets that prevent new violations without requiring a full legacy cleanup.

## 6. Comment audit

Review comments added or materially changed in the diff. Recommend:
- `DELETE`: redundant or misleading.
- `REFACTOR`: improve names or structure instead.
- `TEST`: encode behavior as an executable test.
- `ADR`: move durable architectural rationale to an ADR.
- `KEEP`: preserve necessary context that cannot be expressed clearly elsewhere.

Do not demand removal of useful comments.

## 7. Review output

Start with the overall result:
- Findings count by severity.
- Whether the change is safe to merge based on inspected evidence.
- Checks run and checks not run.

Then list findings from highest to lowest severity. If no material findings exist, say so and note verification gaps. Keep optional improvements separate from merge blockers.
