---
name: ux-bakeoff
description: Compare materially different interactive UI approaches when workflow, layout, or interaction uncertainty cannot be resolved efficiently through codebase inspection and discussion. Use before committing to a consequential or unfamiliar user experience.
---

# UX Bake-Off

## Mission

Use prototypes to resolve real UX uncertainty. Optimize for decision quality and speed, not prototype count.

## 1. Decide whether a bake-off is warranted

Inspect the existing application shell, design system, relevant screens, components, and user workflow.

- **Low uncertainty:** Build one recommended prototype or implement the established pattern directly.
- **Medium uncertainty:** Build two distinct alternatives.
- **High uncertainty:** Build up to three alternatives when each tests a meaningful interaction model.

Do not create multiple options that differ only in color, spacing, or decoration. Do not prototype when an existing pattern clearly solves the problem.

## 2. Define the experiment

Before building, write a short statement of:
- User task being optimized.
- Main UX uncertainty.
- Evaluation criteria.
- Constraints from the existing application.

Use criteria relevant to the task, such as task completion time, discoverability, error prevention, context switching, accessibility, and consistency.

## 3. Build prototypes efficiently

Prefer mounting prototypes in the real application shell or a dedicated development route. Use local mock state where backend behavior is not needed.

Keep prototypes isolated and disposable:
- Do not introduce production schema or API changes for a throwaway prototype.
- Do not silently promote mock behavior into production.
- Keep keyboard and pointer interactions credible when they are central to the experience.
- Document any shortcuts that affect evaluation.

Provide one clear route or switch to compare the alternatives.

## 4. Collect focused feedback

Ask users to perform representative tasks, not to give vague opinions.

Ask only questions that distinguish the alternatives or reveal a defect. Examples:
- Which approach makes the primary action easiest to find?
- Where did you hesitate or make an error?
- Which interaction behaved differently from your expectation?

Consolidate feedback into one refinement pass. Ask at most 2 related questions per round and avoid repeated preference polling.

If feedback is sufficient, lock the decision. A further pass is justified only when testing exposes a material usability, accessibility, or functional defect.

## 5. Reproduce visual and interaction defects

When a defect is reported:
1. Reproduce it in the same route and viewport.
2. Inspect DOM, computed styles, browser console, and network behavior as relevant.
3. Use screenshots or automated browser tests when available.
4. Distinguish rendering artifacts from data, layout, or export defects.
5. Fix the cause or document a verified limitation.

Do not claim pixel-level verification without inspecting rendered output.

## 6. Record the UX decision

Produce a concise UX Decision Note containing:
- Selected approach and why.
- Primary workflow and interaction rules.
- Important states: loading, empty, error, success, disabled, and responsive behavior where relevant.
- Keyboard and accessibility expectations.
- Deferred details and known limitations.

Clean up throwaway routes and prototype code unless the user explicitly wants to retain them. Proceed to specification or implementation without asking for a generic approval when the user has already selected the direction.
