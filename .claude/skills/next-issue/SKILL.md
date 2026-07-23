---
name: next-issue
description: >-
  Choose the single highest-priority issue to work on next from the OrganizeMe GitHub project
  board, explain the choice, and kick off implementation. Use this whenever the user asks what to
  work on next, which issue to pick up, to "grab/start the next issue", "what's next", or to triage
  the Todo column — even if they don't name an issue number. The point is deliberate selection
  (earlier slices before later ones, then bugs before enhancements before future-enhancements, and
  judgment within a tier), NOT just taking the lowest issue number.
---

# Pick and start the next issue

This project tracks work as GitHub issues on the **OrganizeMe** project board (project #2, owner
`rustycoopes`). The job of this skill is to look at what's ready to work on, make a *considered*
choice about what delivers the most value next, get the user's OK, and hand off to the
`/to-implementation` skill to actually build it.

The reason selection is a deliberate step (rather than "take the next open issue") is that a good
build order gives the project a solid base: finish earlier slices before later ones, fix what's
broken before adding new things, land foundational pieces before the work that depends on them, and
don't sink effort into low-priority polish while higher-value work sits waiting.

**Scope: any active feature track, plus the legacy restructure track.** A "track" is either the
legacy Platform Restructure track (`framework-refactor` + `restructure-rN` labels) or a new-style
feature track (`docs/features/<feature-slug>/` — issues carrying a `<feature-slug>` label +
`slice-N` label). Within a track, the slice is read from its slice label; always strongly prefer
the lowest-numbered slice in a track that still has ready work — an earlier slice is the foundation
later ones build on, so it gets drained before the next one starts.

**Ignore `In Progress` issues completely.** An `In Progress` issue is already claimed — assume
another worker (or a concurrent loop session) owns it. Never pick, resume, or hand off to an
`In Progress` issue, even if it would otherwise be the highest-priority next thing to do. Select
only from work that has **not been started** (`Todo`). If the item you'd expect to pick next is
`In Progress`, skip it and take the next-best not-started `Todo` item instead. The gathering helper
in Step 1 already filters to `Todo`, so `In Progress` issues won't appear in the candidate list —
do not go around that filter to look them up.

## Step 1 — Gather what's ready

Run the bundled helper to get every `Todo` issue across all tracks, grouped by track, then slice
number, then priority tier:

```bash
python .claude/skills/next-issue/scripts/todo_issues.py
```

It reads the project board via `gh`, keeps only items whose Status is `Todo` that belong to a
recognized track (legacy `restructure-rN`, or a `<feature-slug>` + `slice-N` pair), and returns a
`tracks` array (each with a `slices` array ordered by slice number ascending; within each slice,
issues are bucketed into `bug` → `enhancement` → `future-enhancement` → `other`). It deliberately
does **not** pick for you. Pass `--feature <feature-slug-or-restructure>` to restrict to one track,
and `--slice <n>` to further restrict to one slice within it, if the user asks for one specifically.

If the helper returns zero issues across all tracks, there's nothing to start: tell the user there's
no `Todo` work ready and stop.

## Step 2 — Narrow to a track, then a slice, then the top tier

**If only one track has ready `Todo` work, use it.** If more than one track has ready work (e.g.
the legacy restructure track and a new feature are both mid-flight), do not silently pick between
them — this is a strategic call, not a mechanical one. Summarize what's ready in each track and ask
the user which to prioritize, unless they already named a feature/issue when invoking this skill.

Within the chosen track, pick the **slice**: take the lowest-numbered slice that has any `Todo`
work. Everything in higher-numbered slices of that track is out of contention for this run.

Then, within that slice, priority is strict across tiers, highest first:

1. **`bug`** — a broken thing undermines the base everything else builds on, so bugs come first.
2. **`enhancement`** — the planned work for that slice.
3. **`future-enhancement`** — deferred improvements/decisions; worth doing but lowest priority.
4. **`other`** — untiered issues (in practice, most restructure-track issues land here, since they
   typically carry only `framework-refactor` + `restructure-rN` with no bug/enhancement label).

Take the highest non-empty tier. Everything below it is out of contention — you only choose *within*
the top occupied tier of the earliest occupied slice. In the common case where a slice's only
candidate(s) are untiered, `other` is that top tier — treat it like any other tier for Step 3.

## Step 3 — Choose within the tier (this is the real work)

Do **not** default to the lowest issue number. Read the candidate issues in the top tier
(`gh issue view <n>`) and weigh them:

- **What unblocks the most?** An issue that other Todo issues depend on should go first. Issue
  bodies often say this outright (e.g. "Blocked by #17", "before #16/#17"). Prefer the *unblocker*
  over the *blocked*. (Example: sidebar shell #17 is a dependency of the E2E-tests issue #23, so
  #17 goes first even though both are enhancements.)
- **What's foundational?** Shared plumbing, scaffolding, or interfaces that later work reuses beat
  leaf features.
- **Is it actually ready?** If a candidate is blocked by something still open, or (common for
  `future-enhancement`) is really a "decide whether to…" item needing a product decision rather
  than code, it's not a clean start. Note that.

Pick exactly one. If it's a genuinely close call, say so and name your runner-up.

## Step 4 — Present the choice and confirm

Before starting any implementation, tell the user:

- **The pick:** issue number + title.
- **Why:** which track/slice and tier it's in, what it beat, and the deciding factor (earliest slice
  with work / unblocks X / foundational / only bug open, etc.).
- **Any caveat:** if the pick is a "decide whether…" `future-enhancement`, flag that it likely
  needs a quick decision from them first, and recommend settling that before building.



## Step 5 — Hand off to implementation

Start the selected issue with the `/to-implementation` skill, passing it the
chosen issue. From there, `to-implementation` owns the branch/worktree, build loop, review, PR, and
marking the issue done — this skill's job is finished once the right issue is handed over.

IF there are open questions which the user does not respond to within 60 seconds, please choose your recommendation and document the decision in docs/model-report/model-decisions.md


## Notes

- **Only one issue.** Even if several are ready, hand off exactly one; the user can re-run this
  skill for the next.
- **Never resume `In Progress` work.** Treat any `In Progress` issue as owned by another worker and
  skip it — do not offer to finish it, do not hand off to it. Always pick the next not-started
  (`Todo`) item instead (see the "Ignore `In Progress` issues completely" rule above). This avoids
  two sessions colliding on the same branch/PR.
- **Ties within a tier** are where your judgment earns its keep; make the reasoning visible so the
  user can override it if they know something you don't.
