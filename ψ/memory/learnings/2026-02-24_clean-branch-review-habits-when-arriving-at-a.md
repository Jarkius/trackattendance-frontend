---
title: ## Clean Branch Review Habits
tags: [git, workflow, retrospectives, branch-hygiene]
created: 2026-02-24
source: rrr: trackattendance-frontend
---

# ## Clean Branch Review Habits

## Clean Branch Review Habits

When arriving at a branch mid-stream, always check for the most recent retrospective before responding. This provides context that git log alone cannot — the *why* behind commits, friction encountered, and planned next steps.

Anti-pattern: Tracked files that change on every app run (like log files) create persistent dirty-tree noise in `git status`. Either gitignore them or untrack them early to keep the working tree signal clean.

A "nothing to commit" response should be delivered quickly and clearly — don't over-explain.

---
*Added via Oracle Learn*
