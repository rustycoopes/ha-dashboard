---
name: to-wbs
description: Break a feature's PRD + TDD into vertical-slice WBS files under docs/features/<feature-slug>/WBS/, quizzing on granularity and dependencies. Feeds /to-issues.
disable-model-invocation: true
---

# To WBS

Break a feature's technical design into a work-breakdown structure of independently-deployable vertical slices, stored as files. This is the planning step — `/to-issues` handles turning an approved slice into a GitHub issue later.

## Process

### 1. Gather context

Read `docs/features/<feature-slug>/PRD.md` and `docs/features/<feature-slug>/TDD.md`. If either is missing, stop and tell the user which of `/to-prd` or `/to-design` to run first.

### 2. Explore the codebase (optional)

If you have not already explored the codebase for this feature, do so to understand the current state of the code. Slice titles and descriptions should use the project's domain glossary vocabulary, and respect any ADRs the TDD links to.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the TDD into **tracer bullet** slices. Each slice is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

<vertical-slice-rules>

- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Any prefactoring should be done first

</vertical-slice-rules>

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Blocked by**: which other slices (if any) must complete first
- **User stories / design sections covered**: which parts of the PRD/TDD this addresses

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?

Iterate until the user approves the breakdown.

### 5. Write the WBS files

For each approved slice, write `docs/features/<feature-slug>/WBS/slice-<n>-<short-name>.md` using the template below. Number slices in dependency order.

<slice-template>

# Slice <n> — <Title>

> Part of the `<feature-slug>` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** One-sentence statement of the end-user- or integrator-visible outcome.

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation. Avoid specific file paths or code snippets — they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it here and note briefly that it came from a prototype.

## Design notes

Anything from the TDD specifically relevant to implementing this slice — link back to the TDD section or ADR rather than repeating it at length.

## Blocked by

- A reference to the blocking slice (if any)

Or "None - can start immediately" if no blockers.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Testing

Seams to test at, prior art in the codebase for this style of test.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->

</slice-template>

### 6. Hand off

Tell the user the slice files are written and that `/to-issues` is next — pass it each slice file (or run it once per slice) to publish the GitHub issues in dependency order.
