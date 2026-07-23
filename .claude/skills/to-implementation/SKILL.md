---
name: to-implementation
description: Implement a GitHub issue onto a branch, end to end — build, review, PR, deploy, and record delivery. Ensure there is a loop to confirm implementation. When the user asks to implement an issue or a PRD.
---

Implement the work described by the issue.
When starting the issue, move the status to In Progress.

Locate the relevant WBS slice spec from the issue's labels (each slice file embeds the schema, endpoints, and utilities that slice needs — load only that one, not the whole PRD/TDD, unless a specific question requires it):

- If the issue carries a `<feature-slug>` + `<slice-id>` label pair, read
  `docs/features/<feature-slug>/WBS/slice-<n>-<name>.md` (find the exact filename by slice number if
  the label alone doesn't spell it out).
- If the issue instead carries a legacy `restructure-rN` label (the still-active Platform
  Restructure track), read `docs/features/platform-restructure/WBS/slice-R<N>.md` as before.
- If there's no WBS slice at all (a small, direct-to-issue change per CLAUDE.md's minor-change
  path), work from the issue body alone.

Use /tdd where possible, at pre-agreed seams.

Ensure to ask any questions if there is any lack of clarity in what needs doing.
Interview the user for any open questions and show the plan.

Treat this change as a major feature and follow the steps defined in CLAUDE.md to create a new branch.

Assume multiple agents are running, so use a separate directory/worktree for this work.

Implement this feature as efficiently as possible, use sub-agents where appropriate.

Once the implementation is working, compare the work against the acceptance criteria to ensure all items are accounted for.
Once done, perform a thorough code review of the work — use the code-review-master and code-quality-guardian agents to find improvements.
If changes are recommended, implement them now.
For all other suggested improvements, create a GitHub issue with the status of Intake, carrying the same `<feature-slug>` + `<slice-id>` labels (or `restructure-rN` for the legacy track) as this issue, plus the `modelsuggested` label.

Once the code is ready, record delivery:

1. If a WBS slice file exists for this issue, append a `## Delivered` section to it — issue number,
   branch name, date, and a short account of what actually shipped (including anything that
   diverged from the plan), matching the pattern already used in
   `docs/features/platform-restructure/WBS/slice-R13.md`.
2. Add one line to `docs/changelog.md`'s `[Unreleased]` section: date, issue number, title, and a
   link to the WBS slice's Delivered section (or to the issue/PR if there's no WBS slice).

Commit all outstanding changes to GitHub with a meaningful message. Push the changes to remote. Then raise a PR to merge this all into main. Make sure that the GitHub build completes correctly and any deployment is successful.

Once the build and deployment is successful, mark the issue as done and add the branch name into the comments.
