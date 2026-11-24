---
name: grill-with-docs
description: Resolve material product, domain, lifecycle, and architecture uncertainty by inspecting existing project evidence and conducting a bounded discovery interview. Use before planning high-impact, ambiguous, or cross-cutting features.
---

# Grill With Docs

## Mission

Establish enough shared understanding to implement safely. Do not turn discovery into an endless interview. The agent owns investigation and technical recommendations; the user owns business intent and consequential decisions.

## 1. Choose the right depth

- Fast Track tasks do not need formal grilling.
- Standard tasks need focused discovery only when a material decision is unresolved.
- Full Engineering tasks use the bounded workflow below.

## 2. Reconnaissance before questions

Inspect only the relevant sources:
1. `CLAUDE.md`, README, project glossary, relevant docs, and ADRs.
2. Existing schemas, types, APIs, database models, and tests.
3. Relevant application workflows and neighboring features.
4. Git history for the abstractions or behavior being changed when historical intent matters.

Check the working tree. Preserve unrelated user changes.

Summarize established facts and identify actual gaps. Do not ask for facts already available in the repository.

## 3. Classify uncertainty

- **P0:** Critical safety, security, data-integrity, legal/compliance, or irreversible business decision. Must resolve before the affected action.
- **P1:** Material product, domain, architecture, or UX choice. Recommend an option and ask only if human judgment is needed.
- **P2:** Reversible engineering choice. Follow project conventions.
- **P3:** Minor detail. Decide autonomously.

## 4. Conduct bounded discovery

Ask no more than 2 related questions in one round and normally no more than 3 rounds total. Treat these as ceilings, not targets. A task can require zero questions.

Every question must include:
- The decision being made.
- Why it matters.
- The recommended option and rationale.
- Meaningful alternatives only.

Prefer specific questions, for example:

"Recommendation: preserve the source record and create a derived record with provenance. This avoids accidental mutation of upstream data. Should the derived record remain independently editable?"

Do not ask broad questions such as "How should we design this?"

Prioritize only dimensions relevant to the feature:
- User workflow and desired outcome.
- Domain terms and entity boundaries.
- Ownership, lifecycle, duplication, undo, archive, and deletion.
- Data source, provenance, synchronization, and conflict behavior.
- Reuse versus isolation.
- Compatibility, security, performance, and operational constraints.

Do not force all dimensions into every interview.

## 5. Decision closure

For complex work, maintain a concise decision register in the feature notes or destination spec. Do not create a separate register for small work.

Use:
- `LOCKED`: user-approved or established by authoritative project evidence.
- `ASSUMED`: safe, reversible default selected by the agent.
- `DEFERRED`: explicitly outside the current scope.
- `OPEN`: unresolved and blocks safe progress.

Do not reopen locked decisions without new material evidence.

If the question ceiling is reached:
1. Resolve P2/P3 choices using project conventions.
2. Record safe assumptions.
3. Identify any remaining P0/P1 blocker.
4. Produce a discovery summary.
5. Continue unless a critical blocker prevents safe work.

The user can end discovery at any time. On request, summarize the current state rather than continuing to interview.

## 6. Decision handoff

When later implementation will run in another session or subagent, persist the decisions needed to execute safely in the destination spec, decision register, or ADR. Include the decision status (`LOCKED`, `ASSUMED`, `DEFERRED`, or `OPEN`), rationale where material, and any constraints or consequences.

Do not rely on chat history as the only record of a decision. Keep the artifact concise and link it from the destination spec or ticket.

## 7. Produce only useful artifacts

When discovery is complete:
- Update the glossary only when a domain term is new or materially clarified.
- Create an ADR only when a consequential architectural decision needs a durable rationale.
- Do not create an ADR for routine implementation choices.
- Capture unresolved non-blocking items as assumptions or non-goals.

An ADR should state context, decision, alternatives, consequences, and status. Follow the repository's ADR numbering and format.

## 8. Exit criteria

Discovery is complete when:
- The problem and desired outcome are clear.
- Critical decisions are resolved.
- Material assumptions and non-goals are recorded.
- Testable acceptance criteria can be written.
- No unresolved high-risk blocker remains.

Proceed to design or specification without requesting a generic "end grilling" confirmation.
