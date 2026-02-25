# Lesson: Clean Branch Review Habits

**Date**: 2026-02-24
**Source**: rrr session on Jarkius/check-camera-poc
**Concepts**: git, workflow, retrospectives

## Pattern

When arriving at a branch mid-stream, always check for the most recent retrospective before responding. This provides context that git log alone cannot — the *why* behind commits, friction encountered, and planned next steps.

## Anti-pattern

Tracked files that change on every app run (like `logs/trackattendance.log`) create persistent dirty-tree noise in `git status`. Either gitignore them or untrack them early to keep the working tree signal clean.

## Takeaway

A "nothing to commit" response should be delivered quickly and clearly. Don't over-explain — the user just needs confirmation that the branch is clean and synced.
