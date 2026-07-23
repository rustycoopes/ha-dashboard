---
name: to-issues
description: Publish an approved WBS slice as a GitHub issue — quizzes on acceptance-criteria completeness first, applies the feature-slug + slice-id + enhancement labels.
disable-model-invocation: true
---

# To Issues

Turn one already-sliced, already-approved WBS file into a GitHub issue ready for `/to-implementation` to pick up cold. Vertical-slicing and granularity decisions are `/to-wbs`'s job — this skill does not re-slice or re-negotiate scope.

## Process

### 1. Gather context

Take a WBS slice file path as input (e.g. `docs/features/<feature-slug>/WBS/slice-2-oauth-connect.md`). If the user instead hands you a whole feature, ask which slice (or run once per slice, in dependency order, so earlier issue numbers exist to reference as blockers).

Read the slice file in full, plus the `PRD.md`/`TDD.md` it links back to for any context you need.

### 2. Quiz the user on readiness

The one thing this skill is responsible for verifying: does this slice have **enough detail for `/to-implementation` to start without asking clarifying questions**? Check specifically for:

- Acceptance criteria that are concrete and verifiable, not vague ("works correctly")
- Success criteria for anything ambiguous in the "What to build" section
- Blockers correctly identified (and, if this isn't the first slice being published, resolved to real issue numbers)

If anything is thin, ask the user for the missing specifics and update the WBS slice file itself (not just the issue body) so the source of truth stays in sync.

### 3. Determine labels

Two separate labels, plus the standard one:

- `<feature-slug>` — the feature this slice belongs to (matches the WBS directory name)
- `<slice-id>` — this slice's identifier (e.g. `slice-2`)
- `enhancement` (existing label)

Create the `<feature-slug>` and `<slice-id>` labels with `gh label create` if they don't already exist in the repo.

### 4. Publish the issue

Publish to the GitHub issue tracker using the template below, applying all three labels and assigning to the **OrganizeMe** project board. If this slice is blocked by another slice already published, reference its real issue number.

<issue-template>
## Parent

Link to `docs/features/<feature-slug>/PRD.md` and the WBS slice file this issue was generated from.

## What to build

Copied/adapted from the WBS slice's "What to build" section — the end-to-end behavior, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Blocked by

- A reference to the blocking issue (if any)

Or "None - can start immediately" if no blockers.

</issue-template>

Do NOT close or modify any parent issue.

### 5. Hand off

Tell the user the issue number and that `/to-implementation` (directly, or via `/next-issue`) is next.
