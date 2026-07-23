---
name: to-prd
description: Turn the current conversation into a PRD and write it to the feature directory — no interview, just synthesis of what you've already discussed.
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a PRD. Do NOT interview the user — just synthesize what you already know. Requirements-gathering is `/grilling`'s job, upstream of this skill; if the conversation doesn't already have enough detail to write a real PRD, say so and suggest a `/grilling` session first rather than interviewing here.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the PRD, and respect any ADRs in the area you're touching (`docs/adr/`).

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

3. Derive a short kebab-case `<feature-slug>` from the feature (e.g. `prompt-versioning`). Confirm it with the user if there's any ambiguity — it's the name every later skill in the chain (`/to-design`, `/to-wbs`, `/to-issues`, `/to-implementation`) will key off.

4. Determine which repo the feature directory belongs in: if the feature is scoped to a single app, it lives in that app's own repo; if it's cross-app/platform-level, it lives in `organize-me`. Create `docs/features/<feature-slug>/` there if it doesn't exist.

5. Write the PRD using the template below to `docs/features/<feature-slug>/PRD.md`. This skill does not touch the issue tracker — no GitHub issue gets created for the feature as a whole; that happens per-slice, later, via `/to-issues`.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

6. Tell the user the PRD is written and that `/to-design` is next.
