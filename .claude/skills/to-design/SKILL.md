---
name: to-design
description: Turn a feature's PRD into a technical design (TDD.md) using parallel design sub-agents, and write an ADR for every decision with real trade-offs.
disable-model-invocation: true
---

This skill takes `docs/features/<feature-slug>/PRD.md` and produces the technical design that resolves the engineering decisions the PRD deliberately left open — into a concrete architecture, ready for `/to-wbs` to break into slices.

## Process

1. Read `docs/features/<feature-slug>/PRD.md`. If it doesn't exist, stop and tell the user to run `/to-prd` first.

2. Explore the codebase for the existing patterns, seams, and conventions in the area this feature touches — prefer reusing what's there over introducing something new. Check `docs/adr/` for prior decisions that constrain this design.

3. Spawn three design sub-agents **in parallel** (single message, multiple `Agent` tool calls), each reviewing the PRD from its own lens:
   - `fastapi-expert` — stack-specific implementation concerns: endpoints, schemas, migrations, background work, testing seams, given this is a Python 3.12 + FastAPI codebase.
   - `clean-architecture-expert` — layering and boundaries: where this feature's logic should live relative to existing modules, what stays decoupled from what.
   - `microservices-architect` — service/deployment topology: does this stay within one app, does it cross the Host/hosted-app boundary, any infra implications.

   Give each agent the full PRD plus the codebase context from step 2, and ask each to flag the real trade-offs it sees, not just describe an approach.

4. Synthesize the three agents' input plus your own judgment into `docs/features/<feature-slug>/TDD.md` using the template below. Where they disagree, make the call yourself and say why in the doc.

5. For every decision in the doc that has a genuine trade-off (not a forced/only-option choice), write `docs/adr/<feature-slug>-<decision-slug>.md` and link it from the relevant section of `TDD.md`. Use this ADR shape:

<adr-template>

# <Decision title>

**Status:** Proposed
**Date:** <today's date>
**Feature:** [`<feature-slug>`](features/<feature-slug>/TDD.md)

## Context
What forced this decision — the constraint, requirement, or problem.

## Decision
What was chosen.

## Alternatives considered
Other options and why they were rejected.

## Consequences
What this makes easier, harder, or forecloses later.

</adr-template>

<tdd-template>

# <Feature name> — Technical Design

**Feature:** [`PRD.md`](PRD.md)
**Date:** <today's date>
**Status:** Draft

## Architecture at a Glance

The 3-6 bullet summary of the shape of the solution — same altitude as an executive summary of the design.

## Design Decisions

One subsection per resolved decision (schema, API contracts, module boundaries, external integrations, background processing, etc.). For each: what was decided, why, and a link to `docs/adr/<feature-slug>-<decision-slug>.md` if it has a dedicated ADR.

## Component/Data Flow

A diagram (mermaid is fine) or prose walkthrough of how a request/event moves through the new pieces.

## Testing Approach

Seams to test at, prior art in the codebase for this style of test, what's out of scope for automated coverage.

## Open Questions

Anything left unresolved that `/to-wbs` or `/to-implementation` will need to settle.

</tdd-template>

6. Tell the user `TDD.md` (and any ADRs) are written, flag any Open Questions that need their input before slicing, and that `/to-wbs` is next.
