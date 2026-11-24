---
name: engineering-orchestrator
description: Route engineering requests to a proportional workflow and coordinate the discovery, UX, specification, review, delivery, and retrospective skills. Use when a task is broad, spans multiple engineering stages, or the right workflow is unclear.
---

# Engineering Orchestrator

## Mission

Choose the smallest workflow that can deliver the requested outcome safely. This skill is a router, not a mandatory ceremony and not a replacement for engineering judgment.

## 1. Classify the task

Choose one mode:

### Fast Track
Use for isolated bug fixes, small refactors, configuration changes, documentation edits, and straightforward UI changes.

Workflow: inspect → implement → verify → report.

Do not create an ADR, formal spec, ticket set, UX bake-off, or retrospective unless evidence warrants one.

### Standard
Use for medium features, API changes, component work, and refactors with several affected areas.

Workflow: inspect → resolve material decisions → lightweight plan/spec → implement → verify → review.

Use only the skills that solve a real need.

### Full Engineering
Use for high-impact features, domain/data-model changes, cross-system changes, multi-agent work, risky migrations, or substantial architectural redesign.

Workflow: bounded discovery → design if needed → destination spec and slices → implementation → review → delivery planning → retrospective when useful.

## 2. Inspect before routing

Read the relevant `CLAUDE.md`, project rules, repository structure, target code, tests, schemas, and existing ADRs. Inspect Git status before editing. Do not repeat questions already answered by repository evidence.

Before introducing or changing workflow infrastructure, audit the existing setup: `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, `.claude/skills/`, `.claude/agents/`, hooks, settings, and any installed framework conventions (for example BMAD or other orchestration systems). Reuse existing mechanisms where they already solve the problem. Do not add duplicate task routers, write guards, hooks, or ticket systems without a demonstrated gap.

## 3. Select skills conditionally

- `grill-with-docs`: use when product, domain, lifecycle, or architecture ambiguity materially affects implementation.
- `ux-bakeoff`: use when meaningful interaction alternatives need hands-on comparison.
- `spec-and-slice`: use when the feature needs a durable specification, multiple tickets, or parallel implementation.
- `system-review`: use for substantive PR/diff review or recurring systemic quality problems.
- `pr-stacker`: use when a large branch needs decomposition into reviewable PRs.
- `session-retro`: use after a meaningful merge or milestone when evidence can improve the engineering system.

Do not invoke every skill by default. Do not delegate work solely to appear agentic.

## 4. Execute autonomously

After routing, continue with the selected workflow. Do not stop to ask the user to approve routine stage transitions, file edits, test runs, or implementation details.

Ask only for P0 blockers or P1 decisions requiring human judgment, following `.claude/rules/engineering-decision-protocol.md`.

If the user says "use defaults", resolve non-critical choices autonomously. If the user says "ask me first", request approval for material decisions, but still handle routine implementation details. If the user says "stop and summarize", stop the current workflow and provide the current state, decisions, assumptions, and next action.

## 5. Handoff discipline

When moving between skills or delegating to a subagent, pass a self-contained handoff. A subagent starts with its own context and must not be expected to know the parent conversation or which skills the parent invoked.

For each delegated task, provide:
- Objective and acceptance criteria.
- Assigned ticket and destination-spec paths, when they exist.
- The relevant `.claude/skills/<skill-name>/SKILL.md` path and an explicit instruction to read it. If using a custom subagent, preload the skill through its `skills` frontmatter when appropriate.
- Applicable project rule and `CLAUDE.md` paths. Do not assume built-in Explore or Plan agents load project instructions.
- Locked decisions, assumptions, constraints, dependencies, and exact write scope.
- Verification commands and required report format.

Require the worker to report its objective, files changed, tests and results, deviations, blockers, and integration needs. Review the worker's report and combined diff before declaring completion.

Do not copy the entire conversation or duplicate the full spec in handoff prompts. Point to durable repository artifacts. Avoid delegation for small or tightly coupled tasks where coordination costs exceed the benefit.

## 6. Completion

A task is complete when the requested outcome is implemented or the requested artifact is produced, relevant verification has run, and remaining limitations are reported. Do not create follow-up work merely to make the workflow look complete.
