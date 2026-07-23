# No QA Cloud Run environment for ha-dashboard, mitigated with a CI-level pipeline smoke test

**Status:** Proposed
**Date:** 2026-07-23
**Feature:** [`ha-dashboard`](../features/ha-dashboard/TDD.md)

## Context

The PRD decided ha-dashboard skips the platform's standard QA+prod Cloud Run pair, since there is
exactly one real Home Assistant instance to validate against and a QA deployment would just be
redundant traffic against that same instance. This is a deliberate deviation from every other
hosted app on the platform (`event-creator`, `doc-library`), both of which proved their deploy
pipeline and Alembic migration history against QA before prod ever saw either.

The gap that decision leaves open isn't the HA integration itself (a second environment wouldn't
give it anything a mocked WS-server unit-test suite doesn't already cover) — it's that ha-dashboard
would otherwise be the **first hosted app whose CI/CD pipeline, Dockerfile, and first-ever
`alembic upgrade head`** are exercised for the first time directly against prod, with no
non-production tier to catch a broken migration, a bad container, or a deploy-config mistake first.

## Decision

Stay prod-only for the live HA-integration surface (no `ha-dashboard-qa` Cloud Run service, no
`encryption-key-qa` secret grant, no QA entry in the Load Balancer/registry). Add a CI job, ahead
of the prod deploy step, that:

1. Builds the production Docker image.
2. Runs it against a throwaway Postgres (local to the CI job, not Supabase QA/prod).
3. Runs `alembic upgrade head` against that throwaway database and asserts it succeeds.
4. Hits the container's own health check.

This validates the deploy pipeline mechanics (Dockerfile correctness, migration history integrity,
container boot) without needing a second live Cloud Run service, a second Supabase branch, or any
LB/registry wiring — none of which the actual risk (a bad migration or broken container) requires
to catch.

## Alternatives considered

- **Full QA+prod pair, matching every other hosted app.** Rejected as the PRD's baseline decision:
  for an app whose only external dependency is one specific home HA instance, a QA deployment adds
  real ongoing cost (a second Cloud Run service, a second Postgres/Alembic target, LB path rules,
  CI complexity) with no corresponding second thing to validate against — QA and prod would be
  testing the identical HA connection.
- **Prod-only with no mitigation at all.** Rejected — this leaves the deploy pipeline itself
  (independent of the HA integration) with no pre-production validation, which is a real
  regression from platform norm, not a scoped, justified exception like the HA-instance reasoning
  above.
- **`gcloud run deploy` with `--no-traffic` / canary revision on the prod service itself**, instead
  of a CI-local Docker Compose-style check. Considered as a complementary future hardening step
  (Cloud Run's revision model supports it for free) but not required to close this gap — the
  CI-level migration/boot check catches the failure modes that matter (broken migration, broken
  image) earlier and cheaper, before any GCP resource is touched at all.

## Consequences

- The deploy pipeline gets real pre-prod validation without provisioning a second environment,
  closing the gap the PRD's "prod only" decision would otherwise leave open.
- ha-dashboard's CI shape now differs from `event-creator`/`doc-library`'s (which validate against
  a real QA Cloud Run service) — worth a one-line note in whatever CI-setup documentation
  `/new-hosted-app` scaffolds, so this isn't mistaken for an oversight when the repo is stood up.
- If ha-dashboard ever grows a second real consumer of its HA connection (unlikely given the PRD's
  explicit single-instance scope), this decision should be revisited — the CI-level check doesn't
  substitute for a real QA environment if there's ever a second live thing to validate against.
