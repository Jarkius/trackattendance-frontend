---
name: session-retro
description: Run an evidence-based retrospective after a meaningful merge, release, or multi-ticket milestone to identify recurring friction and make targeted improvements to engineering standards, tools, documentation, or skills.
---

# Session Retro

## Mission

Turn meaningful engineering evidence into targeted system improvements. A retrospective is optional for small or routine tasks. Do not create process artifacts merely to prove a retrospective occurred.

## 1. Gather relevant evidence

Use available sources:
- PR review comments and requested revisions.
- CI failures, escaped defects, and follow-up issues.
- Relevant agent session notes or logs when available and authorized.
- Repeated clarification loops, wasted tool calls, context loss, and misunderstood requirements.
- Current `CLAUDE.md`, rules, ADRs, and skill instructions.

Do not claim access to session logs or external systems unless they are available.

## 2. Identify patterns

Classify observations:
- **Documentation:** stale, contradictory, or missing guidance.
- **Abstraction or guardrail:** missing type, helper, validation, test, or lint protection.
- **Workflow or skill:** unclear ownership, missing step, excessive questions, or weak handoff.
- **Tooling or environment:** unreliable scripts, slow tests, missing commands, or integration friction.
- **One-off incident:** isolated mistake with no evidence of a recurring systemic cause.

Look for root causes rather than attributing failures to model behavior alone.

## 3. Apply an evidence threshold

- One low-impact incident: record the observation or fix the immediate issue.
- Repeated friction: propose a targeted change.
- One high-impact failure or clear systemic weakness: propose a guardrail immediately.
- Verified recurring pattern: implement and test a durable improvement.

Do not ignore a clear high-risk defect merely because it occurred once.

## 4. Choose the smallest effective improvement

Possible actions:
- Correct one misleading example or rule.
- Add a focused test or fixture.
- Add a typed helper or validation at a real boundary.
- Add an incremental lint/CI ratchet.
- Clarify one skill's trigger, stop condition, or handoff.
- Create a scoped follow-up issue.

Do not modify multiple skills unless the evidence shows a shared cause. Avoid adding checklists, registers, or abstractions that do not prevent a demonstrated failure.

## 5. Implement and verify

When the user has requested a retrospective and the improvement is local, low-risk, and clearly supported by evidence, implement the targeted change autonomously.

For changes with broad policy impact, security implications, or significant maintenance cost, present the recommendation before applying it.

Run the relevant tests, lint, or validation for tooling changes. Inspect the diff and ensure the improvement does not contradict existing rules.

## 6. Report

Provide a concise report:
- What happened.
- Evidence and root cause.
- Immediate fix, if any.
- System improvement made or proposed.
- Verification.
- Follow-up owner/action only when needed.

A valid retrospective can conclude that no systemic change is justified.
