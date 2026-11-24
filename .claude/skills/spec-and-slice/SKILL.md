---
name: spec-and-slice
description: Turn an agreed feature direction into an implementation-ready specification and dependency-aware tickets. Use for substantial features, cross-layer changes, or work that will be delegated across agents or sessions.
---

# Spec and Slice

## Mission

Create the minimum durable specification needed for reliable implementation. Slice by cohesive responsibility and verifiability, not arbitrary line counts.

## 1. Determine whether formal slicing is needed

- Small isolated change: use the issue/request and existing tests; do not create a formal spec.
- Medium feature: create a concise feature spec if requirements span multiple files or layers.
- Large or parallel feature: create a destination spec and dependency-mapped tickets.

Inspect existing docs and follow repository naming conventions before creating files.

## 2. Write the destination specification

Create `docs/specs/<feature-slug>.md` when warranted.

Include:
1. **Problem and goal:** User/business outcome and link to ADR when one exists.
2. **Scope:** In-scope behavior and explicit non-goals.
3. **Domain and contracts:** Entities, ownership, data model, API/request/response contracts, and compatibility requirements.
4. **User behavior:** Stories and testable acceptance criteria, preferably Given/When/Then.
5. **UX contract:** Layout and interaction rules from the selected design, when relevant.
6. **Failure behavior:** Validation, errors, retries, concurrency, permissions, and edge cases relevant to the feature.
7. **Security and operations:** Authorization, auditability, observability, performance, migration, and deployment constraints where relevant.
8. **Verification:** Tests and commands that prove the outcome.

Do not invent exact schemas, APIs, or behavior when evidence is missing. Resolve material gaps through the decision protocol or record a safe assumption.

## 3. Slice by responsibility and dependency

Create tickets under `docs/specs/<feature-slug>/tickets/` only when multiple independently executable work units exist.

A good ticket:
- Has one cohesive responsibility.
- Has a clear outcome and acceptance criteria.
- Can be understood without chat history.
- Names relevant files or boundaries without pretending the implementation is fully known.
- Identifies dependencies and integration points.
- Includes exact verification commands when known.
- Is small enough to implement and review as one unit.

Do not target a fixed number of changed lines. Complexity, coupling, risk, and verification matter more.

## 4. Contract-first parallelism

Before parallel work, agree on shared contracts:
- Domain types and ownership.
- API inputs and outputs.
- Database constraints and migration compatibility.
- Component interfaces and state ownership.
- Error semantics.

Parallelize only independent work. If two tickets edit the same files or depend on unsettled contracts, sequence them or assign a single owner.

Typical sequence:
- Foundations: contracts, additive schema, shared types, fixtures.
- Independent work: backend and frontend against the agreed contract.
- Integration: wiring, persistence, end-to-end tests.
- Release: compatibility checks, data migration, rollout and cleanup.

Adjust the sequence to the actual dependency graph. Do not force a fixed three-wave structure.

## 5. Ticket execution contract

Each ticket should state:
- Objective.
- Dependencies.
- Scope and likely files.
- Acceptance criteria.
- Verification commands.
- Constraints and non-goals.

The implementing agent must inspect existing code, honor the ticket and project conventions, stay within scope, run verification, inspect the diff, and report results. If a real blocker appears, report the evidence and recommend a resolution rather than inventing a contract.

### Required subagent handoff

When assigning a ticket to a subagent or a separate session, send a self-contained execution prompt. Include:
1. The single assigned ticket path.
2. The destination specification path and relevant ADR or decision-register paths.
3. The applicable skill path, such as `.claude/skills/spec-and-slice/SKILL.md`, plus any implementation-specific skill path. Explicitly tell the worker to read the files. Do not rely on parent skill context being inherited.
4. Applicable `CLAUDE.md` and `.claude/rules/` paths. Built-in Explore and Plan agents do not load project instructions in the same way as implementation workers, so provide the required constraints in the task prompt when using them.
5. Locked decisions, assumptions, dependencies, non-goals, and permitted write scope.
6. Exact verification commands and the expected completion report.

The worker must report: objective completed, files changed, tests or checks run with results, deviations from the ticket, unresolved blockers, and integration needs. The parent agent owns integration, combined-diff review, and final verification.

## 6. Handoff

Provide a short handoff summary pointing to the spec and ticket files. Include current status, dependencies, and the next executable ticket.

Do not duplicate the entire spec in the handoff prompt. A fresh agent should be able to work from the repository, destination spec, and assigned ticket.

## 7. Completion

The spec is ready when consequential behavior is explicit, acceptance criteria are testable, dependencies are visible, and no unresolved critical decision blocks implementation. Do not require user approval for routine formatting or ticket organization.
