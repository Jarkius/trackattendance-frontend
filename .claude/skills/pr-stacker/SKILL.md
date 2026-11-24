---
name: pr-stacker
description: Split a large or tightly coupled feature branch into a safe sequence of reviewable stacked pull requests while preserving the final result. Use when a branch has a large mixed diff, multiple independently reviewable layers, or elevated review risk.
---

# PR Stacker

## Mission

Make a large change easier to review and release without changing its intended final result. Prefer the simplest safe split; do not stack PRs solely to meet a line-count threshold.

## 1. Preflight

Inspect:
- Current branch, base branch, and working-tree status.
- Existing commits and merge-base.
- CI and test status.
- Full diff, including untracked files.
- Dependencies between schema, backend, frontend, tests, and docs.

Preserve uncommitted and unrelated work. Do not reset, clean, stash, amend, rebase published history, or delete branches without explicit authorization.

If the branch is not clean, stop branch manipulation and report the issue. Continue read-only analysis where useful.

## 2. Decide whether stacking is useful

Recommend stacking when the change contains independently reviewable layers or a large mixed diff that materially increases review risk.

Do not stack when:
- The changes are tightly coupled and intermediate states cannot remain valid.
- The branch is small and coherent.
- The repository's PR process does not support stacked dependencies.

If no safe split exists, recommend one coherent PR with a clear review plan.

## 3. Plan the stack

Group changes by dependency and deployability, not by file type alone.

A typical sequence:
1. Documentation, contracts, pure helpers, and isolated tests.
2. Backward-compatible schema expansion and compatibility code.
3. Backend and service behavior.
4. UI and integration.
5. Data backfill, consumer switch, and destructive contract cleanup only after compatibility is proven.

Adapt this sequence to the actual architecture. A migration is not automatically late: additive, backward-compatible migrations can be early. Destructive changes belong after consumers have moved and rollback implications are understood.

For each proposed PR, state:
- Purpose and included scope.
- Target branch and parent PR.
- Dependencies.
- CI/test requirements.
- Risk and human review focus.

Present the plan before creating or pushing branches. Local branch preparation is allowed after the user has requested implementation, provided it is non-destructive and the working tree is safe. Pushing, opening PRs, merging, or changing shared branches requires explicit confirmation.

## 4. Materialize safely

Use the repository's established branch and commit conventions. Prefer cherry-pick or carefully staged commits when they preserve intent and make provenance clear.

Do not use broad interactive staging in a way that risks including unrelated user changes. Verify each commit's file list and diff.

Every intermediate PR must be valid against its actual target branch. If a coherent, testable intermediate state is impossible, do not force the split.

## 5. Verify the stack

Run relevant checks for every stack segment:
- Unit and integration tests.
- Typecheck, lint, and build.
- Migration compatibility checks where applicable.
- `git diff --check`.

If the goal is exact final-tree equivalence, compare tree objects:

```bash
git rev-parse original-feature-branch^{tree}
git rev-parse stack-top^{tree}
```

The object IDs should match. Also inspect:

```bash
git diff --stat original-feature-branch stack-top
git diff --exit-code original-feature-branch stack-top
```

Use the actual original feature branch and final stack branch. Do not assume a branch relationship that has not been verified.

If exact equivalence is not the goal, state the intended differences and verify them explicitly.

## 6. Report

Provide the stack order, branch/PR dependencies, verification results, unresolved risks, and reviewer focus. Never claim CI passed unless the checks ran and passed.
